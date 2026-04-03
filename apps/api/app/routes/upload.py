import hashlib
import os

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.config import ALLOWED_EXTENSIONS, MAX_UPLOAD_BYTES, UPLOAD_DIR
from app.db import get_db
from app.models import Project, ProjectFile
from app.state import PROJECT_FILES

router = APIRouter(prefix="/upload", tags=["upload"])

os.makedirs(UPLOAD_DIR, exist_ok=True)


@router.post("")
async def upload_file(
    project_id: int = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    # ── Validate project exists ───────────────────────────────────────────────
    project = db.query(Project).filter(Project.id == project_id).first()
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

    # ── Save file to disk ─────────────────────────────────────────────────────
    safe_filename = f"project_{project_id}_{filename}"
    path = os.path.join(UPLOAD_DIR, safe_filename)
    with open(path, "wb") as f:
        f.write(content)

    # ── Persist to database ───────────────────────────────────────────────────
    project_file = ProjectFile(
        project_id=project_id,
        filename=filename,
        stored_path=path,
        size_bytes=size_bytes,
        file_hash=file_hash,
    )
    db.add(project_file)

    # Update project status
    project.status = "ready"
    db.commit()
    db.refresh(project_file)

    # ── Update in-memory cache (backward compat with existing services) ───────
    PROJECT_FILES[project_id] = {
        "filename": filename,
        "path": path,
        "file_hash": file_hash,
        "size_bytes": size_bytes,
    }

    return {
        "project_id": project_id,
        "filename": filename,
        "path": path,
        "size_bytes": size_bytes,
        "file_hash": file_hash,
    }
