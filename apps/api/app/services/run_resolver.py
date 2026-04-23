"""
Shared run-selection and DTO-building utilities.

Used by:
  - GET /analysis/run/{run_id}
  - GET /analysis/runs/{project_id}/latest
  - GET /projects/{project_id}          ← project detail injects latest_run

Public API
----------
resolve_latest_run(db, project_id) -> AnalysisResult | None
build_run_detail(r)                -> RunDetail
"""
from __future__ import annotations

import json
from typing import Optional

from sqlalchemy.orm import Session

from app.models import AnalysisResult
from app.schemas.run_summary import RunDetail


def resolve_latest_run(db: Session, project_id: int) -> AnalysisResult | None:
    """
    Return the most relevant AnalysisResult for a project using priority ordering:
      0 — report_ready   (completed successfully)
      1 — any non-failed (in-progress or incomplete)
      2 — failed         (last resort — still inspectable)

    Includes source_file via joinedload so build_run_detail() never triggers
    an extra query.  Returns None when the project has no runs.
    """
    from sqlalchemy import case
    from sqlalchemy.orm import joinedload

    priority = case(
        (AnalysisResult.status == "report_ready", 0),
        (AnalysisResult.status != "failed", 1),
        else_=2,
    )
    return (
        db.query(AnalysisResult)
        .options(joinedload(AnalysisResult.source_file))
        .filter(AnalysisResult.project_id == project_id)
        .order_by(priority, AnalysisResult.id.desc())
        .first()
    )


def build_run_detail(r: AnalysisResult) -> RunDetail:
    """
    Convert a fetched AnalysisResult (source_file pre-loaded) to a RunDetail DTO.

    Peeks at result_json keys to populate has_* flags without including the blob.
    """
    started = r.started_at
    finished = r.created_at  # created_at = completion stamp set by finalise_run
    duration: Optional[float] = None
    if started and finished and finished > started:
        duration = (finished - started).total_seconds()

    result_keys: set[str] = set()
    if r.status == "report_ready" and r.result_json and r.result_json != "{}":
        try:
            result_keys = set(json.loads(r.result_json).keys())
        except (json.JSONDecodeError, AttributeError):
            pass

    return RunDetail(
        run_id=r.id,
        project_id=r.project_id,
        status=r.status,
        trigger_source=r.trigger_source,
        started_at=started,
        finished_at=finished if r.status == "report_ready" else None,
        error_summary=r.error_summary,
        file_id=r.file_id,
        file_hash=r.file_hash,
        filename=r.source_file.filename if r.source_file else None,
        has_result=r.status == "report_ready",
        duration_seconds=duration,
        has_cleaning_result="cleaning_result" in result_keys,
        has_health_result="health_result" in result_keys,
        has_insight_results="insight_results" in result_keys,
        has_executive_panel="executive_panel" in result_keys,
        has_report_result=bool(r.story_result_json),
    )
