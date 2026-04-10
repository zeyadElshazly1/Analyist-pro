"""
Project file state management.

In-memory dict acts as a fast cache; the database (ProjectFile table) is the
source of truth. On cache miss, we query the DB; if DB is also missing we fall
back to scanning the uploads directory (backward-compat with files uploaded
before DB persistence was added).
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Fast in-memory cache: { project_id: { filename, path, file_hash, ... } }
PROJECT_FILES: dict[int, dict[str, Any]] = {}


def get_project_file_info(project_id: int) -> dict[str, Any] | None:
    """
    Return file info for a project.
    Resolution order:
      1. In-memory cache (fastest)
      2. Database (survives restarts)
      3. Disk scan of uploads/ (backward compat)
    """
    # 1. In-memory cache hit
    cached = PROJECT_FILES.get(project_id)
    if cached and cached.get("path"):
        if Path(cached["path"]).exists():
            return cached
        # Cached path is gone (e.g. S3 temp file deleted or local file removed).
        # Try to re-materialise from stored_path before falling back to DB.
        stored = cached.get("stored_path")
        if stored:
            from app.services.storage import get_local_path
            fresh = get_local_path(stored)
            if fresh:
                cached["path"] = fresh
                return cached

    # 2. Database lookup
    try:
        from app.db import SessionLocal
        from app.models import ProjectFile
        from app.services.storage import get_local_path
        db = SessionLocal()
        try:
            pf = (
                db.query(ProjectFile)
                .filter(ProjectFile.project_id == project_id)
                .order_by(ProjectFile.uploaded_at.desc())
                .first()
            )
            if pf:
                local_path = get_local_path(pf.stored_path)
                if local_path:
                    info = {
                        "filename": pf.filename,
                        "path": local_path,
                        "stored_path": pf.stored_path,
                        "file_hash": pf.file_hash,
                        "size_bytes": pf.size_bytes,
                    }
                    PROJECT_FILES[project_id] = info
                    logger.debug(f"Restored project {project_id} file info from DB")
                    return info
        finally:
            db.close()
    except Exception as e:
        logger.warning(f"DB lookup for project {project_id} failed: {e}")

    # 3. Disk scan fallback (backward compat with pre-DB uploads)
    from app.config import UPLOAD_DIR
    uploads_dir = Path(UPLOAD_DIR)
    if not uploads_dir.exists():
        return None

    matches = sorted(
        uploads_dir.glob(f"project_{project_id}_*"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if not matches:
        return None

    chosen = matches[0]
    prefix = f"project_{project_id}_"
    original_name = chosen.name[len(prefix):] if chosen.name.startswith(prefix) else chosen.name
    info = {"filename": original_name, "path": str(chosen), "file_hash": None}
    PROJECT_FILES[project_id] = info
    logger.info(f"Restored project {project_id} file info from disk scan (legacy)")
    return info
