import hashlib
import logging
import os
import tempfile

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.config import ALLOWED_EXTENSIONS, MAX_UPLOAD_BYTES, UPLOAD_DIR
from app.db import get_db
from app.middleware.auth import get_current_user
from app.middleware.plans import plan_max_file_bytes
from app.models import Project, ProjectFile, User
from app.services.audit import log_event
from app.services.cache import invalidate_project_cache
from app.services.storage import get_local_path, save_file
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
    request: Request = None,  # type: ignore[assignment]
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
    plan_limit = plan_max_file_bytes(current_user)
    effective_limit = min(MAX_UPLOAD_BYTES, plan_limit)
    if size_bytes > effective_limit:
        mb = size_bytes / (1024 * 1024)
        max_mb = effective_limit / (1024 * 1024)
        detail: dict | str
        if size_bytes > plan_limit:
            detail = {
                "message": (
                    f"File too large for your {current_user.plan or 'free'} plan "
                    f"({mb:.1f} MB). Upgrade for larger file support."
                ),
                "feature": "file_size",
                "current_plan": current_user.plan or "free",
            }
            raise HTTPException(status_code=402, detail=detail)
        raise HTTPException(
            status_code=413,
            detail=f"File too large: {mb:.1f} MB. Maximum allowed: {max_mb:.0f} MB.",
        )

    # ── Compute hash for cache invalidation ───────────────────────────────────
    file_hash = hashlib.sha256(content).hexdigest()

    # ── Write to temp file, then hand off to storage backend ─────────────────
    # storage.save_file() performs an atomic local rename *or* an S3 upload,
    # returning the stored_path that goes into the database.
    safe_filename = f"project_{project_id}_{filename}"
    fd, tmp_path = tempfile.mkstemp(dir=UPLOAD_DIR, suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(content)
        stored_path = save_file(project_id, safe_filename, tmp_path)
    except Exception as e:
        # Clean up the temp file on any failure before storage.save_file()
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        logger.error(f"File save failed for project {project_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=503,
            detail="Could not save the uploaded file. Please try again.",
        )

    # ── Persist to database (with rollback on failure) ───────────────────────
    try:
        project_file = ProjectFile(
            project_id=project_id,
            filename=filename,
            stored_path=stored_path,
            size_bytes=size_bytes,
            file_hash=file_hash,
        )
        db.add(project_file)
        project.status = "ready"
        db.commit()
        db.refresh(project_file)
    except SQLAlchemyError as e:
        db.rollback()
        # Best-effort cleanup of the stored file
        from app.services.storage import delete_file
        try:
            delete_file(stored_path)
        except Exception:
            pass
        logger.error(f"DB write failed for project {project_id} upload: {e}", exc_info=True)
        raise HTTPException(
            status_code=503,
            detail="Could not save file metadata to the database. Please try again.",
        )

    # ── Update in-memory cache only after successful DB commit ────────────────
    # Capture previous hash BEFORE overwriting the cache entry so cache
    # invalidation can compare old vs new hashes correctly.
    prev_info = PROJECT_FILES.get(project_id)
    prev_hash = prev_info.get("file_hash") if prev_info else None

    local = get_local_path(stored_path)
    PROJECT_FILES[project_id] = {
        "filename": filename,
        "path": local or stored_path,
        "stored_path": stored_path,
        "file_hash": file_hash,
        "size_bytes": size_bytes,
    }

    # Invalidate any cached analysis when the file content changes
    if prev_hash and prev_hash != file_hash:
        invalidate_project_cache(project_id, prev_hash)

    logger.info(
        f"Upload: project={project_id} user={current_user.id[:8]}… "
        f"file='{filename}' size={size_bytes} hash={file_hash[:8]}…"
    )

    log_event(
        db,
        action="upload",
        user_id=current_user.id,
        resource_type="project",
        resource_id=str(project_id),
        detail={"filename": filename, "size_bytes": size_bytes, "file_hash": file_hash[:8]},
        ip_address=request.client.host if request and request.client else None,
    )

    return {
        "project_id": project_id,
        "filename": filename,
        "stored_path": stored_path,
        "size_bytes": size_bytes,
        "file_hash": file_hash,
    }
