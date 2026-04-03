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

# Legacy list kept for any code that still reads it directly (will be phased out)
PROJECTS: list = []


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
    if cached and cached.get("path") and Path(cached["path"]).exists():
        return cached

    # 2. Database lookup
    try:
        from app.db import SessionLocal
        from app.models import ProjectFile
        db = SessionLocal()
        try:
            pf = (
                db.query(ProjectFile)
                .filter(ProjectFile.project_id == project_id)
                .order_by(ProjectFile.uploaded_at.desc())
                .first()
            )
            if pf and Path(pf.stored_path).exists():
                info = {
                    "filename": pf.filename,
                    "path": pf.stored_path,
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
    api_root = Path(__file__).resolve().parents[1]
    uploads_dir = api_root / "uploads"
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
