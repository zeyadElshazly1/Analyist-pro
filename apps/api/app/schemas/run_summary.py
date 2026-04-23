"""
DTOs for analysis run visibility.

RunSummary  — used by GET /analysis/runs/{project_id} (list, no blobs)
RunDetail   — used by GET /analysis/run/{run_id}      (single run, adds has_* payload flags)
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class RunSummary(BaseModel):
    model_config = {"from_attributes": True}

    run_id: int
    project_id: int
    status: str
    trigger_source: Optional[str]
    started_at: Optional[datetime]
    finished_at: Optional[datetime]      # AnalysisResult.created_at = completion stamp
    error_summary: Optional[str]
    file_id: Optional[int]
    file_hash: Optional[str]
    filename: Optional[str]              # joined from ProjectFile (None if file deleted)
    has_result: bool                     # True when result_json is populated
    duration_seconds: Optional[float]   # None if started_at or finished_at missing


class RunDetail(RunSummary):
    """
    Extends RunSummary with per-block payload presence flags.

    Callers can use these to decide which report sections are available
    without ever receiving the full result_json blob.
    """
    has_cleaning_result: bool    # cleaning_result block present in result_json
    has_health_result: bool      # health_result block present
    has_insight_results: bool    # insight_results list is non-empty
    has_executive_panel: bool    # executive_panel block present
    has_report_result: bool      # AI story (story_result_json) generated
