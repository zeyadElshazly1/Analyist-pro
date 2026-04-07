import hashlib
import logging
import os
import tempfile

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.config import ALLOWED_EXTENSIONS, MAX_UPLOAD_BYTES, UPLOAD_DIR
from app.db import get_db
from app.middleware.auth import get_current_user
from app.models import Project, ProjectFile, User
from app.state import PROJECT_FILES

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/upload", tags=["upload"])

os.makedirs(UPLOAD_DIR, exist_ok=True)


@router.post("")
async def upload_file(
    project_id: int = Form(...),
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # ── Validate project exists and belongs to user ───────────────────────────
    project = db.query(Project).filter(
        Project.id == project_id, Project.user_id == current_user.id
    ).first()
    if not project:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found.")

    # ── Validate file extension ───────────────────────────────────────────────
    filename = file.filename or "upload"
    ext = os.path.splitext(filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported file type '{ext}'. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
        )

    # ── Read content + validate size ──────────────────────────────────────────
    content = await file.read()
    size_bytes = len(content)
    if size_bytes == 0:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")
    if size_bytes > MAX_UPLOAD_BYTES:
        mb = size_bytes / (1024 * 1024)
        max_mb = MAX_UPLOAD_BYTES / (1024 * 1024)
        raise HTTPException(
            status_code=413,
            detail=f"File too large: {mb:.1f} MB. Maximum allowed: {max_mb:.0f} MB.",
        )

    # ── Compute hash for cache invalidation ───────────────────────────────────
    file_hash = hashlib.sha256(content).hexdigest()

    # ── Atomic file write: write to temp file, then rename ───────────────────
    # This prevents partial files being seen by readers if the write is interrupted.
    safe_filename = f"project_{project_id}_{filename}"
    final_path = os.path.join(UPLOAD_DIR, safe_filename)

    try:
        fd, tmp_path = tempfile.mkstemp(dir=UPLOAD_DIR, suffix=".tmp")
        try:
            with os.fdopen(fd, "wb") as f:
                f.write(content)
            os.replace(tmp_path, final_path)  # atomic on POSIX
        except Exception:
            # Clean up the temp file if rename failed
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise
    except OSError as e:
        logger.error(f"File write failed for project {project_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=503,
            detail="Could not save the uploaded file. Please try again.",
        )

    # ── Persist to database (with rollback on failure) ───────────────────────
    try:
        project_file = ProjectFile(
            project_id=project_id,
            filename=filename,
            stored_path=final_path,
            size_bytes=size_bytes,
            file_hash=file_hash,
        )
        db.add(project_file)
        project.status = "ready"
        db.commit()
        db.refresh(project_file)
    except SQLAlchemyError as e:
        db.rollback()
        # Remove the file we just wrote — DB record doesn't exist
        try:
            os.unlink(final_path)
        except OSError:
            pass
        logger.error(f"DB write failed for project {project_id} upload: {e}", exc_info=True)
        raise HTTPException(
            status_code=503,
            detail="Could not save file metadata to the database. Please try again.",
        )

    # ── Update in-memory cache only after successful DB commit ────────────────
    PROJECT_FILES[project_id] = {
        "filename": filename,
        "path": final_path,
        "file_hash": file_hash,
        "size_bytes": size_bytes,
    }

    logger.info(
        f"Upload: project={project_id} user={current_user.id[:8]}… "
        f"file='{filename}' size={size_bytes} hash={file_hash[:8]}…"
    )

    return {
        "project_id": project_id,
        "filename": filename,
        "path": final_path,
        "size_bytes": size_bytes,
        "file_hash": file_hash,
    }
