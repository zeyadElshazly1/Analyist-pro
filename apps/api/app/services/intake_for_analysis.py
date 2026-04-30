"""
Helper: build the canonical IntakeResult for a project at analysis time.

This is the bridge between the upload route (which already has the live
ParseReport in hand) and the analysis route (which loads the file again
later, sometimes after server restart).  It recomputes the IntakeResult
from disk and the ProjectFile row so the sync and streaming analysis
pipelines can persist ``intake_result`` in their stored ``result_json``
without changing the existing pipeline shape.

The helper is intentionally non-fatal: any failure returns ``None`` so the
analysis pipeline never crashes if the file is missing, the parser hits a
new edge case, or anything else goes sideways.  Persistence-on-best-effort
is the right trade-off here — the rest of the analysis is still valid even
if intake metadata can't be regenerated.
"""
from __future__ import annotations

import logging
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.models import ProjectFile

logger = logging.getLogger(__name__)


def build_intake_for_project(
    db: Session,
    project_id: int,
    *,
    file_path: Optional[str] = None,
    file_hash: Optional[str] = None,
) -> Optional[dict[str, Any]]:
    """Return a serialised IntakeResult dict for the project's latest file.

    Args:
        db:         SQLAlchemy session.
        project_id: Owning project.
        file_path:  Optional already-resolved local path; falls back to
                    looking up the latest file in PROJECT_FILES / DB.
        file_hash:  When provided, prefer the ProjectFile row matching this
                    hash so the intake snapshot is tied to the exact file
                    version the analysis ran against.

    Returns:
        ``IntakeResult.model_dump()``-shaped dict on success, or ``None``
        if any step fails (no file, parse error, etc.).
    """
    try:
        pf = _resolve_project_file(db, project_id, file_hash)
        if pf is None:
            return None

        path = file_path or _resolve_local_path(pf)
        if not path:
            return None

        from app.services.file_loader import load_dataset_with_report
        from app.services.intake_adapter import build_intake_result

        df, report = load_dataset_with_report(path)
        return build_intake_result(pf, df, report).model_dump()
    except Exception as exc:  # pragma: no cover - defence-in-depth
        logger.debug(
            f"Intake snapshot generation failed for project {project_id}: {exc}"
        )
        return None


# ── Internals ────────────────────────────────────────────────────────────────

def _resolve_project_file(
    db: Session,
    project_id: int,
    file_hash: Optional[str],
) -> Optional[ProjectFile]:
    """Return the ProjectFile row to base intake_result on.

    Prefers an exact ``file_hash`` match (so the intake snapshot tracks the
    exact file version that was analysed).  Falls back to the most-recent
    upload for the project.
    """
    q = db.query(ProjectFile).filter(ProjectFile.project_id == project_id)
    if file_hash:
        match = q.filter(ProjectFile.file_hash == file_hash).order_by(
            ProjectFile.uploaded_at.desc()
        ).first()
        if match is not None:
            return match
    return q.order_by(ProjectFile.uploaded_at.desc()).first()


def _resolve_local_path(pf: ProjectFile) -> Optional[str]:
    """Resolve the on-disk path for a ProjectFile, honouring the storage backend."""
    try:
        from app.services.storage import get_local_path
        local = get_local_path(pf.stored_path)
        return local or pf.stored_path
    except Exception:
        return pf.stored_path
