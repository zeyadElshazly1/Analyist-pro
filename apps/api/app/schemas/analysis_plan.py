"""
Schema for the AnalysisPlan produced by the Dataset Intelligence Layer.

The plan is built once per file (after intake, before cleaning) and consumed
by downstream steps to make context-aware decisions about column handling,
finding ranking, chart selection, and report framing.
"""
from __future__ import annotations

from pydantic import BaseModel, field_validator


class ChartHint(BaseModel):
    chart_type: str          # "scatter" | "bar" | "line" | "histogram" | "heatmap"
    x_column: str
    y_column: str | None = None
    rationale: str
    priority: int            # 1 = highest


class AnalysisPlan(BaseModel):
    dataset_kind: str        # "sales"|"finance"|"hr"|"insurance"|"marketing"|"operations"|"research"|"generic"
    confidence: float        # 0.0–1.0; below 0.6 downstream falls back to generic
    business_context: str
    primary_entity: str | None = None
    target_metrics: list[str] = []
    important_dimensions: list[str] = []
    time_columns: list[str] = []
    columns_to_ignore: list[str] = []
    recommended_charts: list[ChartHint] = []
    insight_priorities: list[str] = []
    analysis_warnings: list[str] = []
    report_template_hint: str = "generic"  # "executive_summary"|"detailed_audit"|"trend_report"|"generic"

    @field_validator("confidence")
    @classmethod
    def clamp_confidence(cls, v: float) -> float:
        return max(0.0, min(1.0, v))
