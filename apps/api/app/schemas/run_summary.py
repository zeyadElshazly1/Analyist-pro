"""
DTOs for analysis run visibility and result retrieval.

RunSummary  — list endpoint, no blobs
RunDetail   — single-run metadata + has_* flags, no blobs
RunResults  — canonical result blocks for reopening a completed run
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

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


class RunResults(BaseModel):
    """
    Canonical result blocks for a completed run — the "open prior work" payload.

    All block fields are None when the run did not reach report_ready status.
    Legacy fields (health_score, profile, insights, cleaning_report) are
    intentionally excluded; consumers should use the canonical V1 blocks.
    """
    run_id: int
    project_id: int
    status: str
    error_summary: Optional[str]

    # ── Canonical V1 result blocks ────────────────────────────────────────────
    cleaning_result: Optional[dict[str, Any]]   # CleaningResult model dump
    health_result: Optional[dict[str, Any]]     # HealthResult model dump
    insight_results: Optional[list[Any]]        # list of InsightResult model dumps
    executive_panel: Optional[dict[str, Any]]   # high-level summary panel
    narrative: Optional[str]                    # plain-text narrative
    report_result: Optional[dict[str, Any]]     # AI data story (story_result_json)
