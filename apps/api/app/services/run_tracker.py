"""
Shared run-lifecycle helpers for analysis routes.

Used by both /analysis/run (sync) and /analysis/stream (async SSE) so
run model behaviour stays identical across both paths.

Public API
----------
resolve_file_id(db, project_id, file_hash) -> int | None
set_run_status(db, run, status)            -> None   (best-effort commit)
fail_run(db, run, summary)                 -> None   (best-effort commit)
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models import AnalysisResult, ProjectFile

logger = logging.getLogger(__name__)


def resolve_file_id(db: Session, project_id: int, file_hash: str | None) -> int | None:
    """Return the ProjectFile.id matching (project_id, file_hash), or None."""
    if not file_hash:
        return None
    pf = (
        db.query(ProjectFile)
        .filter(ProjectFile.project_id == project_id, ProjectFile.file_hash == file_hash)
        .order_by(ProjectFile.uploaded_at.desc())
        .first()
    )
    return pf.id if pf else None


def set_run_status(db: Session, run: AnalysisResult | None, status: str) -> None:
    """Commit a status transition. Best-effort — never raises."""
    if run is None:
        return
    try:
        run.status = status
        db.commit()
    except Exception:
        db.rollback()
        logger.warning("Failed to commit run status=%s for run id=%s", status, run.id)


def fail_run(db: Session, run: AnalysisResult | None, summary: str) -> None:
    """Mark a run as failed and commit. Best-effort — never raises."""
    if run is None:
        return
    try:
        run.status = "failed"
        run.error_summary = summary[:500]
        db.commit()
    except Exception:
        db.rollback()
        logger.warning("Failed to commit run failure for run id=%s", run.id)


def create_run_stub(
    db: Session,
    project_id: int,
    file_hash: str | None,
    user_id: str | None,
    trigger_source: str = "user",
) -> AnalysisResult | None:
    """
    Create and commit an AnalysisResult stub at the start of a pipeline run.

    Returns the persisted run record, or None if the DB write fails.
    Caller should continue without run tracking if None is returned.
    """
    from sqlalchemy.exc import SQLAlchemyError

    try:
        file_id = resolve_file_id(db, project_id, file_hash)
        run = AnalysisResult(
            project_id=project_id,
            status="created",
            started_at=datetime.now(timezone.utc),
            trigger_source=trigger_source,
            file_hash=file_hash,
            file_id=file_id,
            user_id=user_id,
            result_json="{}",  # placeholder until pipeline completes
        )
        db.add(run)
        db.commit()
        db.refresh(run)
        logger.info("Run %s created for project %s", run.id, project_id)
        return run
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(
            "Failed to create run stub for project %s: %s", project_id, e, exc_info=True
        )
        return None


def finalise_run(
    db: Session,
    run: AnalysisResult | None,
    result_json_str: str,
) -> None:
    """
    Write the completed result_json, set status='report_ready', and stamp
    created_at as the completion time. Best-effort — never raises.
    """
    if run is None:
        return
    from sqlalchemy.exc import SQLAlchemyError

    try:
        run.result_json = result_json_str
        run.status = "report_ready"
        run.created_at = datetime.now(timezone.utc)
        db.commit()
    except SQLAlchemyError as e:
        db.rollback()
        logger.error("Failed to finalise run %s: %s", run.id, e, exc_info=True)
