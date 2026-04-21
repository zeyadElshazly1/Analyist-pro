"""
Canonical CompareResult schema — V1.

Represents one file-to-file comparison: structural changes, volume shifts,
metric movements, health changes, and a consultant-ready summary draft.
The goal is to answer "what changed and should the client care?" — not to
dump every statistical diff into a raw table.

Consumers:
  - Compare step UI (schema diff, metric delta cards, caution flag banner)
  - "What changed?" summary for the report builder
  - Run model (CompareResult stored in result_json for paired runs)

Main producer:
  - services/multifile_compare.py → compare_files(path_a, path_b)

See ADAPTER_NOTES at the bottom for the field-by-field mapping.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

# ── Sub-types ─────────────────────────────────────────────────────────────────

ChangeDirection = Literal["improved", "declined", "unchanged"]

MetricChangeFlag = Literal[
    "significant",   # |mean_delta_pct| > 20 %
    "notable",       # |mean_delta_pct| 5–20 %
    "stable",        # |mean_delta_pct| < 5 %
    "no_data",       # column missing in one or both files
]

CautionKind = Literal[
    "columns_removed",          # columns in A are absent from B
    "columns_added",            # new columns appear in B
    "large_volume_drop",        # row count fell > 20 %
    "large_volume_spike",       # row count rose > 50 %
    "significant_metric_shift", # a shared numeric column moved > 20 %
    "health_declined",          # overall health score dropped > 5 pts
    "high_row_overlap",         # > 90 % of rows are identical (may not be a true new period)
    "low_row_overlap",          # < 10 % overlap — files may be unrelated datasets
]

WarningSeverity = Literal["high", "medium", "low"]


# ── Sub-models ────────────────────────────────────────────────────────────────

class FileRef(BaseModel):
    """Identity and scale of one file in the comparison."""
    file_name: str   = Field(description="Original filename or display label.")
    project_id: int | None = Field(
        default=None,
        description="ProjectFile.project_id — None if the file was passed by path only.",
    )
    row_count: int    = Field(ge=0)
    column_count: int = Field(ge=0)


class SchemaChanges(BaseModel):
    """Column-level structural diff between the two files."""
    added_columns: list[str] = Field(
        default_factory=list,
        description="Columns present in file_b but absent from file_a.",
    )
    removed_columns: list[str] = Field(
        default_factory=list,
        description="Columns present in file_a but absent from file_b.",
    )
    shared_columns: list[str] = Field(
        default_factory=list,
        description="Columns present in both files.",
    )

    @property
    def has_schema_drift(self) -> bool:
        return bool(self.added_columns or self.removed_columns)


class RowVolumeChange(BaseModel):
    """Row count comparison and hash-based row overlap estimate."""
    count_a: int = Field(ge=0, description="Row count in file_a after cleaning.")
    count_b: int = Field(ge=0, description="Row count in file_b after cleaning.")
    diff: int    = Field(description="count_b − count_a (negative = fewer rows).")
    diff_pct: float | None = Field(
        default=None,
        description="(count_b − count_a) / count_a × 100. None if count_a is 0.",
    )
    overlap_count: int = Field(
        ge=0,
        description="Number of rows that appear in both files (hash-based estimate).",
    )
    overlap_pct_of_a: float | None = Field(
        default=None,
        description="overlap_count / count_a × 100. None if count_a is 0.",
    )


class MetricDelta(BaseModel):
    """Numeric metric comparison for one shared column."""
    column: str
    mean_a: float | None  = None
    mean_b: float | None  = None
    mean_delta_pct: float | None = Field(
        default=None,
        description="(mean_b − mean_a) / |mean_a| × 100. None if mean_a is 0 or missing.",
    )
    median_a: float | None = None
    median_b: float | None = None
    std_a: float | None    = None
    std_b: float | None    = None
    change_flag: MetricChangeFlag = Field(
        description=(
            "'significant' → |mean_delta_pct| > 20 %. "
            "'notable' → 5–20 %. "
            "'stable' → < 5 %. "
            "'no_data' → column not numeric in one or both files."
        ),
    )


class HealthChange(BaseModel):
    """Health score comparison between the two files."""
    score_a: float = Field(ge=0.0, le=100.0)
    score_b: float = Field(ge=0.0, le=100.0)
    grade_a: str   = Field(description="Letter grade A–F for file_a.")
    grade_b: str   = Field(description="Letter grade A–F for file_b.")
    delta: float   = Field(
        description="score_b − score_a. Positive = B is healthier than A.",
    )
    direction: ChangeDirection


class CautionFlag(BaseModel):
    """
    One thing the consultant should review before sharing with a client.

    Caution flags are not errors — they are signals that something changed
    materially and warrants a sentence of explanation in the report.
    """
    kind: CautionKind
    severity: WarningSeverity
    column: str | None = Field(
        default=None,
        description="Relevant column name when the flag is column-specific.",
    )
    message: str = Field(
        description="Human-readable explanation suitable for a review banner or report note.",
    )


# ── Canonical schema ──────────────────────────────────────────────────────────

class CompareResult(BaseModel):
    """
    V1 compare result — consultant-facing output for one file-to-file comparison.

    Designed to answer "what changed and does the client need to know?" rather
    than to reproduce every statistical diff. Caution flags surface the most
    important changes; summary_draft turns findings into reportable text.
    """

    # ── Identity ──────────────────────────────────────────────────────────────
    compare_id: str = Field(
        description=(
            "Deterministic identifier for this comparison pair. "
            "Format: '{project_id_a}:{project_id_b}' or a short hash. "
            "Stable so the UI can cache and reference the result."
        ),
    )

    # ── Files compared ────────────────────────────────────────────────────────
    file_a: FileRef = Field(description="Reference file (earlier period or baseline).")
    file_b: FileRef = Field(description="Comparison file (later period or variant).")

    # ── Structural diff ───────────────────────────────────────────────────────
    schema_changes: SchemaChanges

    # ── Volume ────────────────────────────────────────────────────────────────
    row_volume_changes: RowVolumeChange

    # ── Numeric metric movements ──────────────────────────────────────────────
    metric_deltas: list[MetricDelta] = Field(
        default_factory=list,
        description=(
            "Per-column metric comparison for shared numeric columns. "
            "Capped at 15 columns (same budget as the current service)."
        ),
    )

    # ── Health comparison ─────────────────────────────────────────────────────
    health_changes: HealthChange

    # ── Report-ready text ─────────────────────────────────────────────────────
    summary_draft: str = Field(
        description=(
            "Auto-generated 2–4 sentence summary of the most important changes. "
            "Intended as a starting point for the report builder — the consultant "
            "can edit it before including it in a client deliverable."
        ),
    )

    # ── Review flags ──────────────────────────────────────────────────────────
    caution_flags: list[CautionFlag] = Field(
        default_factory=list,
        description=(
            "Signals that something changed materially and needs a review sentence "
            "before client delivery. Ordered by severity descending."
        ),
    )


# ── Adapter notes ─────────────────────────────────────────────────────────────
#
# CURRENT PRODUCER
#   services/multifile_compare.py  compare_files(path_a, path_b, label_a, label_b) → dict
#
# CLEAN MAPPINGS — direct or rename-only:
#
#   schema_changes.added_columns   ← result["schema"]["only_b"]
#   schema_changes.removed_columns ← result["schema"]["only_a"]
#   schema_changes.shared_columns  ← result["schema"]["shared"]
#
#   row_volume_changes.count_a     ← result["rows"]["a"]
#   row_volume_changes.count_b     ← result["rows"]["b"]
#   row_volume_changes.diff        ← result["rows"]["diff"]
#   row_volume_changes.overlap_count     ← result["row_overlap"]["count"]
#   row_volume_changes.overlap_pct_of_a  ← result["row_overlap"]["pct_of_a"]
#
#   health_changes.score_a   ← result["health_scores"]["a"]["total"]
#   health_changes.score_b   ← result["health_scores"]["b"]["total"]
#   health_changes.grade_a   ← result["health_scores"]["a"]["grade"]
#   health_changes.grade_b   ← result["health_scores"]["b"]["grade"]
#
#   metric_deltas (partial):
#     column, mean_a, mean_b, mean_delta_pct, median_a, median_b, std_a, std_b
#     all map from result["stats_comparison"] list items
#
# FIELDS NEEDING ADAPTERS — data partially exists but needs logic:
#
#   compare_id:
#     Not generated. Adapter: f"{project_id_a}:{project_id_b}" or
#     hashlib.md5(f"{path_a}|{path_b}".encode()).hexdigest()[:10]
#
#   file_a / file_b (FileRef):
#     label_a/label_b → file_name (rename).
#     row_count and column_count are in result["rows"]["a"] and result["columns"]["a"].
#     project_id is NOT in the compare_files() output — must be passed in from the
#     route (payload.project_id_a / payload.project_id_b).
#
#   row_volume_changes.diff_pct:
#     Not in output. Adapter: (count_b - count_a) / count_a * 100
#     (guard against count_a == 0 → None).
#
#   metric_deltas.change_flag:
#     Not in output. Adapter: classify mean_delta_pct:
#       abs(pct) > 20 → "significant"
#       abs(pct) 5–20 → "notable"
#       abs(pct) < 5  → "stable"
#       pct is None   → "no_data"
#
#   health_changes.delta:
#     Not in output. Adapter: score_b - score_a.
#
#   health_changes.direction:
#     Not in output. Adapter:
#       delta > 2  → "improved"
#       delta < -2 → "declined"
#       else       → "unchanged"
#     (±2 pt tolerance avoids flagging noise as meaningful direction changes)
#
# FIELDS MISSING ENTIRELY — not produced at all, need new logic:
#
#   summary_draft:
#     Not generated by compare_files(). Adapter (template-based):
#     Build from the 3–4 most important findings:
#       - row volume change (if > 5%)
#       - removed / added columns (if any)
#       - largest significant metric delta
#       - health direction
#     Example: "{file_b.file_name} has {diff:+,} rows ({diff_pct:+.1f}%) vs
#     {file_a.file_name}. [N] columns were added/removed. Average {col} shifted
#     by {pct:.0f}%. Overall data quality {direction} from grade {grade_a} to
#     {grade_b}."
#
#   caution_flags:
#     Not generated. Adapter — emit a flag when:
#       removed_columns is non-empty              → "columns_removed", high
#       added_columns is non-empty                → "columns_added", low
#       diff_pct < -20                            → "large_volume_drop", high
#       diff_pct > 50                             → "large_volume_spike", medium
#       any MetricDelta.change_flag == "significant" → "significant_metric_shift", medium (per column)
#       health_changes.delta < -5                 → "health_declined", high
#       overlap_pct_of_a > 90                     → "high_row_overlap", medium
#       overlap_pct_of_a < 10 (and overlap not None) → "low_row_overlap", medium
