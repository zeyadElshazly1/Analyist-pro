"""
Canonical HealthResult schema — V1.

Represents data-quality diagnostics for one dataset after ingestion and
(optionally) cleaning. This is a trust signal, not an analytics output —
it answers "how reliable is this data?" not "what patterns does it show?".

Consumers:
  - Health step UI (trust indicators, per-column quality bar)
  - Cleaning review (to show what remains after cleaning)
  - Report data-quality notes section
  - Run model (HealthResult stored in result_json alongside IntakeResult)

Main producers:
  - services/profiling/health_scorer.py  → calculate_health_score(df)
  - services/profiling/orchestrator.py   → profile_dataset(df)
  - services/cleaning/semantic.py        → detect_semantic_columns(df)

See ADAPTER_NOTES at the bottom of this module for the field-by-field mapping.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

# ── Sub-types ─────────────────────────────────────────────────────────────────

HealthGrade = Literal["A", "B", "C", "D", "F"]

HealthDimension = Literal[
    "completeness",
    "uniqueness",
    "consistency",
    "validity",
    "structure",
]

WarningSeverity = Literal["high", "medium", "low"]

DatasetType = Literal["timeseries", "transactional", "survey", "general"]


# ── Sub-models ────────────────────────────────────────────────────────────────

class HealthScore(BaseModel):
    """Composite quality score and dimension breakdown."""
    total_score: float = Field(
        ge=0.0, le=100.0,
        description="Overall 0–100 quality score (sum of dimension scores).",
    )
    grade: HealthGrade
    label: str = Field(
        description="Human label: 'Excellent', 'Good', 'Fair', 'Poor', 'Critical'.",
    )
    breakdown: dict[str, float] = Field(
        description=(
            "Per-dimension scores keyed by HealthDimension: "
            "completeness, uniqueness, consistency, validity, structure."
        ),
    )
    dataset_type: DatasetType = Field(
        description="Detected dataset category — drives dimension weighting.",
    )
    dataset_type_confidence: float = Field(
        ge=0.0, le=1.0,
        description="Confidence in the dataset_type classification.",
    )


class ColumnMissingness(BaseModel):
    """Missing-value counts for one column."""
    column: str
    missing_count: int  = Field(ge=0)
    missing_pct: float  = Field(ge=0.0, le=100.0)


class MissingnessStats(BaseModel):
    """Dataset-level missing-value summary."""
    total_missing_cells: int   = Field(ge=0)
    missing_cell_pct: float    = Field(ge=0.0, le=100.0)
    rows_with_any_missing: int = Field(ge=0)
    rows_with_any_missing_pct: float = Field(ge=0.0, le=100.0)
    columns_with_missing: list[ColumnMissingness] = Field(
        default_factory=list,
        description="Only columns that have at least one missing value.",
    )


class DuplicateStats(BaseModel):
    """Duplicate-row counts at the dataset level."""
    duplicate_row_count: int = Field(ge=0)
    duplicate_row_pct: float = Field(
        ge=0.0, le=100.0,
        description="Percentage of rows that are exact duplicates.",
    )


class SemanticColumnType(BaseModel):
    """Semantic classification for one column (detected, not user-assigned)."""
    column: str
    semantic_type: str = Field(
        description=(
            "Detected type label, e.g. 'email', 'phone', 'id', "
            "'revenue', 'date', 'postal_code', 'boolean_flag'."
        ),
    )


class ColumnHealthEntry(BaseModel):
    """Per-column quality score with a list of issues found."""
    column: str
    score: float = Field(
        ge=0.0, le=100.0,
        description="0–100 quality score for this column.",
    )
    issues: list[str] = Field(
        default_factory=list,
        description=(
            "Short issue descriptions, e.g. '12.4% missing (-18)', "
            "'severe skew (-5)', 'constant value (-20)'."
        ),
    )


class HealthWarning(BaseModel):
    """One actionable quality warning for display and report inclusion."""
    dimension: str = Field(
        description="Which health dimension this warning belongs to.",
    )
    message: str = Field(
        description="Human-readable deduction string from the health scorer.",
    )
    severity: WarningSeverity


# ── Canonical schema ──────────────────────────────────────────────────────────

class HealthResult(BaseModel):
    """
    V1 health result — dataset trust signals for one analysis run.

    This schema is distinct from CleaningResult:
      - CleaningResult  → what was *done* to the data (mutations applied)
      - HealthResult    → what the data *is* (diagnostics, remaining issues)

    All list fields default to empty so callers can iterate without null checks.
    """

    # ── Scale ─────────────────────────────────────────────────────────────────
    row_count: int    = Field(ge=0)
    column_count: int = Field(ge=0)

    # ── Quality signals ───────────────────────────────────────────────────────
    missingness_stats: MissingnessStats
    duplicate_stats: DuplicateStats

    # ── Semantic understanding ────────────────────────────────────────────────
    semantic_column_types: list[SemanticColumnType] = Field(
        default_factory=list,
        description="All columns for which a semantic type was detected.",
    )
    key_columns: list[str] = Field(
        default_factory=list,
        description=(
            "Column names identified as identifiers or primary keys "
            "(semantic types: 'id', 'uuid', 'sku', 'order_id', etc.). "
            "These are excluded from statistical analysis by the cleaning pipeline."
        ),
    )

    # ── Composite score ───────────────────────────────────────────────────────
    health_score: HealthScore

    # ── Warnings ─────────────────────────────────────────────────────────────
    health_warnings: list[HealthWarning] = Field(
        default_factory=list,
        description=(
            "Actionable deduction strings from the health scorer, "
            "annotated with dimension and severity."
        ),
    )

    # ── Per-column breakdown ──────────────────────────────────────────────────
    column_health: list[ColumnHealthEntry] = Field(
        default_factory=list,
        description="Per-column quality scores and issue lists for the health screen.",
    )


# ── Adapter notes ─────────────────────────────────────────────────────────────
#
# CURRENT PRODUCERS
#   services/profiling/health_scorer.py  calculate_health_score(df) → dict
#   services/profiling/orchestrator.py   profile_dataset(df) → list[dict]
#   services/cleaning/semantic.py        detect_semantic_columns(df) → dict[str,str]
#
# CLEAN MAPPINGS — direct assignments with renames:
#
#   health_score.total_score         ← health["total"]         (RENAME: "total" → "total_score")
#   health_score.grade               ← health["grade"]
#   health_score.label               ← health["label"]
#   health_score.breakdown           ← health["breakdown"]
#   health_score.dataset_type        ← health["dataset_type"]
#   health_score.dataset_type_confidence ← health["dataset_type_confidence"]
#
#   duplicate_stats.duplicate_row_count  ← computed: df.duplicated().sum()
#   duplicate_stats.duplicate_row_pct    ← health["breakdown"] deductions mention dupe_pct
#                                           (also available: health["business_impact"]["duplicate_rows"])
#
#   column_health                    ← health["column_health"] — dict keyed by col name,
#                                     convert to list[ColumnHealthEntry]
#
#   semantic_column_types            ← detect_semantic_columns(df) → dict[col, type]
#                                     convert to list[SemanticColumnType]
#
# FIELDS NEEDING ADAPTERS:
#
#   health_score.total_score:
#     The scorer uses key "total" — a rename-only adapter is needed everywhere
#     that consumes the dict. The schema uses "total_score" as the canonical name
#     per RESULT_SCHEMA_IMPLEMENTATION_SPEC.md.
#
#   row_count / column_count:
#     Not in the health dict — derive from df.shape after running the scorer.
#
#   missingness_stats:
#     The health dict has business_impact["unreliable_rows"] (rows with any missing)
#     and missing_pct is computable from df. But ColumnMissingness list must be
#     built from df.isnull().sum() — not stored in the health dict directly.
#     Adapter: iterate df.isnull().sum().items(), filter count > 0.
#
#   health_warnings:
#     health["deductions"] is a list of plain strings. Each needs a dimension and
#     severity. Adapter: parse the string prefix (e.g. "Missing data:", "Duplicate
#     rows:", "IQR outliers:", "Mixed types:") → dimension + severity mapping.
#     A simple keyword→(dimension, severity) lookup table covers all current cases.
#
#   key_columns:
#     Filter semantic_map for types in the "identifier" family:
#     {"id", "uuid", "sku", "order_id", "user_id", "account_id"} — any type
#     in PROTECTED_TYPES from cleaning/semantic.py qualifies.
#     Adapter: {col for col, t in semantic_map.items() if t in PROTECTED_TYPES}
#
#   duplicate_stats.duplicate_row_pct:
#     business_impact["duplicate_rows"] gives the count; need to divide by row_count.
#     Or recompute: df.duplicated().sum() / len(df) * 100.
