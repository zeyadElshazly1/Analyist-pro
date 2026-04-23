"""
DTO for a single analysis run summary — lightweight, no result blobs.

Used by GET /analysis/runs/{project_id} to expose run history for:
  - reopening/resuming prior work
  - debugging failures
  - comparing executions
  - eventual run-history UI
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, computed_field


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
    duration_seconds: Optional[float]    # None if started_at or finished_at missing
