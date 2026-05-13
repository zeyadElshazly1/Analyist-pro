"""
Schema for the Pre-Analysis Intelligence Layer V2.

Produced by the pre-analysis pipeline before any detector runs.
Consumed by cleaning, ranking, chart generation, narrative, executive
panel, report builder, and saved-run persistence.

This module is schema-only — no pipeline wiring lives here.
"""
from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

# ── Allowed value sets ────────────────────────────────────────────────────────

_DATASET_SHAPES = frozenset({
    "transactional",
    "snapshot",
    "time_series",
    "event_log",
    "survey",
    "entity_table",
    "panel_data",
    "unknown",
})

_PRIMARY_ROLES = frozenset({
    "metric",
    "dimension",
    "time",
    "entity_id",
    "transaction_id",
    "target",
    "leakage_candidate",
    "helper_artifact",
    "free_text",
    "geographic",
    "currency_amount",
    "rate_percentage",
    "boolean_flag",
    "unknown",
})

_SEVERITIES = frozenset({"low", "medium", "high"})

_GRAIN_LABELS = frozenset({
    "customer",
    "order",
    "policy",
    "transaction",
    "event",
    "product",
    "employee",
    "time_period",
    "session",
    "survey_response",
    "unknown",
})


# ── Models ────────────────────────────────────────────────────────────────────

class DatasetFingerprint(BaseModel):
    row_count: int
    column_count: int
    numeric_column_count: int = 0
    categorical_column_count: int = 0
    datetime_column_count: int = 0
    boolean_column_count: int = 0
    free_text_column_count: int = 0
    overall_missing_rate: float = 0.0
    duplicate_row_count: int = 0
    overall_data_density: float = 1.0
    dataset_shape: str = "unknown"

    @field_validator("row_count", "column_count")
    @classmethod
    def non_negative_main(cls, v: int) -> int:
        if v < 0:
            raise ValueError("must be >= 0")
        return v

    @field_validator(
        "numeric_column_count",
        "categorical_column_count",
        "datetime_column_count",
        "boolean_column_count",
        "free_text_column_count",
        "duplicate_row_count",
    )
    @classmethod
    def non_negative_counts(cls, v: int) -> int:
        if v < 0:
            raise ValueError("must be >= 0")
        return v

    @field_validator("overall_missing_rate", "overall_data_density")
    @classmethod
    def clamp_rate(cls, v: float) -> float:
        return max(0.0, min(1.0, v))

    @field_validator("dataset_shape")
    @classmethod
    def validate_dataset_shape(cls, v: str) -> str:
        if v not in _DATASET_SHAPES:
            raise ValueError(
                f"dataset_shape {v!r} is not valid; "
                f"allowed: {sorted(_DATASET_SHAPES)}"
            )
        return v


class ColumnSemanticRole(BaseModel):
    column_name: str
    primary_role: str
    secondary_roles: list[str] = Field(default_factory=list)
    role_confidence: float = 0.0
    cardinality: int = 0
    missing_rate: float = 0.0
    notes: str | None = None

    @field_validator("column_name")
    @classmethod
    def column_name_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("column_name cannot be empty")
        return v

    @field_validator("primary_role")
    @classmethod
    def validate_primary_role(cls, v: str) -> str:
        if v not in _PRIMARY_ROLES:
            raise ValueError(
                f"primary_role {v!r} is not valid; "
                f"allowed: {sorted(_PRIMARY_ROLES)}"
            )
        return v

    @field_validator("role_confidence", "missing_rate")
    @classmethod
    def clamp_rate(cls, v: float) -> float:
        return max(0.0, min(1.0, v))

    @field_validator("cardinality")
    @classmethod
    def non_negative_cardinality(cls, v: int) -> int:
        if v < 0:
            raise ValueError("cardinality must be >= 0")
        return v


class AnalysisStrategy(BaseModel):
    recommended_analysis_types: list[str] = Field(default_factory=list)
    deprioritised_analysis_types: list[str] = Field(default_factory=list)
    recommended_metric_columns: list[str] = Field(default_factory=list)
    recommended_dimension_columns: list[str] = Field(default_factory=list)
    recommended_time_columns: list[str] = Field(default_factory=list)
    recommended_chart_families: list[str] = Field(default_factory=list)


class AnalysisRisk(BaseModel):
    risk_name: str
    severity: str
    affected_columns: list[str] = Field(default_factory=list)
    description: str

    @field_validator("risk_name")
    @classmethod
    def risk_name_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("risk_name cannot be empty")
        return v

    @field_validator("description")
    @classmethod
    def description_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("description cannot be empty")
        return v

    @field_validator("severity")
    @classmethod
    def validate_severity(cls, v: str) -> str:
        if v not in _SEVERITIES:
            raise ValueError(
                f"severity {v!r} is not valid; allowed: {sorted(_SEVERITIES)}"
            )
        return v


class HypothesisPlan(BaseModel):
    hypotheses: list[str] = Field(default_factory=list)

    @field_validator("hypotheses")
    @classmethod
    def strip_empty_hypotheses(cls, v: list[str]) -> list[str]:
        return [h for h in v if h.strip()]


class PreAnalysisProfile(BaseModel):
    fingerprint: DatasetFingerprint
    column_roles: list[ColumnSemanticRole] = Field(default_factory=list)
    grain_label: str = "unknown"
    grain_confidence: float = 0.0
    strategy: AnalysisStrategy = Field(default_factory=AnalysisStrategy)
    risks: list[AnalysisRisk] = Field(default_factory=list)
    hypothesis_plan: HypothesisPlan = Field(default_factory=HypothesisPlan)
    generated_at: str
    planner_version: str = "v2.0-deterministic"

    @field_validator("grain_label")
    @classmethod
    def validate_grain_label(cls, v: str) -> str:
        if v not in _GRAIN_LABELS:
            raise ValueError(
                f"grain_label {v!r} is not valid; "
                f"allowed: {sorted(_GRAIN_LABELS)}"
            )
        return v

    @field_validator("grain_confidence")
    @classmethod
    def clamp_grain_confidence(cls, v: float) -> float:
        return max(0.0, min(1.0, v))

    @field_validator("generated_at")
    @classmethod
    def generated_at_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("generated_at cannot be empty")
        return v

    @field_validator("planner_version")
    @classmethod
    def planner_version_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("planner_version cannot be empty")
        return v
