"""
Canonical CleaningResult schema — V1.

Represents the full output of one cleaning pipeline run: what was changed,
what was flagged, and a summary of confidence in the resulting dataset.

Consumers:
  - Cleaning review UI (applied / flagged / unchanged sections)
  - Trust display in the Insights step
  - Run model (CleaningResult stored in result_json alongside other step outputs)

Actual production is in services/cleaning/pipeline.py -> clean_dataset().
See ADAPTER_NOTES at the bottom of this module for the field-by-field mapping.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

# ── Sub-types ─────────────────────────────────────────────────────────────────

CleaningMode = Literal["aggressive", "safe"]

MissingnessMechanism = Literal["MCAR", "MAR", "MNAR", "unknown"]

ImputationStrategy = Literal[
    "dropped",          # column removed (>60% missing)
    "mean",
    "median",
    "mode",
    "knn",
    "mice",
    "flag_and_fill",    # MNAR: binary flag column created + fill
    "safe_suggestion",  # safe mode — no mutation applied
]

OutcomeKind = Literal[
    "renamed",          # column name normalised
    "dropped",          # column or row removed
    "type_converted",   # dtype changed
    "imputed",          # missing values filled
    "outlier_clipped",  # values winsorised / capped
    "outlier_flagged",  # warning only — no mutation
    "boolean_unified",  # yes/YES/y/1 → canonical form
    "whitespace_stripped",
    "casing_normalised",
    "date_features_added",
    "suspicious_flagged",
]


# ── Sub-models ────────────────────────────────────────────────────────────────

class ColumnRename(BaseModel):
    """A single column whose name was normalised during cleaning."""
    original: str = Field(description="Name in the raw file.")
    cleaned: str  = Field(description="Name after lowercase + underscore normalisation.")


class TypeFix(BaseModel):
    """A dtype conversion applied to one column."""
    column: str
    to_dtype: str = Field(
        description=(
            "Target type label: 'numeric', 'datetime', 'boolean', "
            "'currency', 'percentage'."
        )
    )
    n_values_converted: int = Field(
        ge=0,
        description="Number of non-null values successfully converted.",
    )


class MissingnessNote(BaseModel):
    """Missing-value handling for one column."""
    column: str
    missing_count: int   = Field(ge=0)
    missing_pct: float   = Field(ge=0.0, le=100.0)
    mechanism: MissingnessMechanism = Field(
        description=(
            "Detected missingness mechanism: "
            "MCAR (random), MAR (related to other cols), "
            "MNAR (value-dependent), or 'unknown'."
        )
    )
    strategy_applied: ImputationStrategy


class DuplicateNote(BaseModel):
    """Aggregated duplicate-row and duplicate-column findings."""
    duplicate_rows_found: int    = Field(ge=0)
    duplicate_rows_removed: int  = Field(ge=0)
    duplicate_columns: list[str] = Field(
        default_factory=list,
        description="Column names removed because their values were identical to a preceding column.",
    )


class SuspiciousColumn(BaseModel):
    """A column flagged for review — no mutation was applied."""
    column: str
    issue_type: str = Field(
        description=(
            "Short machine label, e.g. 'suspicious_zeros', "
            "'outliers_preserved', 'high_missing'."
        )
    )
    detail: str = Field(description="Human-readable explanation for the review UI.")


class CleaningSummary(BaseModel):
    """Top-level metrics from one cleaning run."""
    original_rows: int
    original_cols: int
    final_rows: int
    final_cols: int
    rows_removed: int   = Field(ge=0)
    cols_removed: int   = Field(ge=0)
    steps_applied: int  = Field(ge=0, description="Total cleaning steps that ran.")
    confidence_score: float = Field(
        ge=0.0, le=100.0,
        description="0–100 composite score for the cleaned dataset.",
    )
    confidence_grade: str = Field(
        description="Letter grade derived from confidence_score (A–F).",
    )
    time_saved_estimate: str = Field(
        description="Human-readable estimate, e.g. '~12 minutes'.",
    )
    mode: CleaningMode


# ── Canonical schema ──────────────────────────────────────────────────────────

class CleaningResult(BaseModel):
    """
    V1 cleaning result — the full structured output of one pipeline run.

    All list fields are empty (not None) when nothing of that kind occurred,
    so callers can iterate without null checks.
    """

    # ── Output reference ──────────────────────────────────────────────────────
    cleaned_dataset_ref: str | None = Field(
        default=None,
        description=(
            "Stored path or PreparedDataset ID of the cleaned Parquet artifact. "
            "None until the persistence layer (PreparedDataset) is wired up."
        ),
    )

    # ── What was changed ──────────────────────────────────────────────────────
    renamed_columns: list[ColumnRename] = Field(
        default_factory=list,
        description="Columns whose names were normalised (original → cleaned).",
    )
    dropped_columns: list[str] = Field(
        default_factory=list,
        description=(
            "Column names removed for any reason: all-null, duplicate content, "
            "or >60% missing values."
        ),
    )
    type_fixes: list[TypeFix] = Field(
        default_factory=list,
        description="dtype conversions applied (currency, %, numeric, datetime, boolean).",
    )

    # ── What was flagged ──────────────────────────────────────────────────────
    missingness_notes: list[MissingnessNote] = Field(
        default_factory=list,
        description="Per-column missing-value handling records.",
    )
    duplicate_notes: DuplicateNote = Field(
        default_factory=lambda: DuplicateNote(
            duplicate_rows_found=0,
            duplicate_rows_removed=0,
            duplicate_columns=[],
        ),
        description="Aggregated row + column duplicate findings.",
    )
    suspicious_columns: list[SuspiciousColumn] = Field(
        default_factory=list,
        description=(
            "Columns that need human review — no mutation applied. "
            "Includes suspicious zeros, preserved outliers, high-missing warnings."
        ),
    )

    # ── Inferences made ───────────────────────────────────────────────────────
    assumptions_made: list[str] = Field(
        default_factory=list,
        description=(
            "Human-readable list of inferences the pipeline made autonomously: "
            "missingness mechanism classification, semantic column detection, "
            "outlier strategy selection, date format inference."
        ),
    )

    # ── Summary ───────────────────────────────────────────────────────────────
    cleaning_summary: CleaningSummary


# ── Adapter notes ─────────────────────────────────────────────────────────────
#
# CURRENT PRODUCER
#   services/cleaning/pipeline.py  clean_dataset(df, mode)
#   returns: (df_clean, report: list[dict], summary: dict)
#   The report list has items: {"step": str, "detail": str, "impact": str}
#
# CLEAN MAPPINGS — direct field assignments, no transformation needed:
#   summary["confidence_score"]           → cleaning_summary.confidence_score
#   summary["confidence_grade"]           → cleaning_summary.confidence_grade
#   summary["original_rows/cols"]         → cleaning_summary.original_*
#   summary["final_rows/cols"]            → cleaning_summary.final_*
#   summary["rows_removed/cols_removed"]  → cleaning_summary.*
#   summary["steps"]                      → cleaning_summary.steps_applied  (rename)
#   summary["time_saved_estimate"]        → cleaning_summary.time_saved_estimate
#   summary["mode"]                       → cleaning_summary.mode
#   summary["duplicate_col_names"]        → duplicate_notes.duplicate_columns
#   summary["suspicious_issues_remaining"] → suspicious_columns
#       (rename: item["type"] → issue_type)
#
# FIELDS NEEDING ADAPTERS — data exists but needs extraction or restructuring:
#
#   renamed_columns:
#     The pipeline tracks `renamed = count` (line 199) and `original_cols` list,
#     but does NOT emit per-column pairs. Adapter: zip(original_cols, df_clean.columns)
#     after step 3 and emit ColumnRename for each pair where a != b.
#
#   dropped_columns:
#     Scattered across three steps: empty cols (step 1), duplicate cols (step 2b,
#     already in summary["duplicate_col_names"]), and high-missing cols (step 6
#     per-column drop). Adapter: collect col name at each drop site and union.
#
#   type_fixes:
#     Encoded as free-text in the `report` list steps ("Parse currency: col",
#     "Convert to numeric: col", "Harmonize date formats: col", etc.).
#     Adapter: filter report for steps matching type-conversion keywords,
#     parse column name from step string, map to TypeFix with n_values_converted
#     extracted from the `detail` string.
#
#   missingness_notes:
#     Each imputation is a report entry. `mechanism` and `strategy_applied` are
#     embedded in the `step` string ("Impute missing (MNAR): col"). Adapter: filter
#     report for imputation steps; parse mechanism from step label; parse
#     missing_count/pct from detail string.
#
#   duplicate_notes.duplicate_rows_found:
#     `dupes` variable (line 159) is not forwarded to summary. Adapter: add
#     "duplicate_rows_found" to the summary dict in clean_dataset().
#
#   assumptions_made:
#     Not currently tracked as a list. Adapter: emit one entry per:
#       • semantic column detected (e.g. "Detected 'email_address' as ID column — skipped type conversion")
#       • missingness mechanism classified (e.g. "MAR detected in 'revenue' — used KNN imputation")
#       • outlier strategy chosen (e.g. "Preserved outliers in 'price' — semantic type is revenue")
#
#   cleaned_dataset_ref:
#     NOT produced yet — PreparedDataset persistence is not wired to the
#     cleaning pipeline. Will be populated once Wave 1 of PERSISTENCE_FIX_ORDER.md
#     is implemented (dataset_loader.py adapter).
