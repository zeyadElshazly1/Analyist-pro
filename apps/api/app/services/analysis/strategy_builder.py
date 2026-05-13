"""
90F — Analysis strategy builder, risk detector, and hypothesis planner.

Turns a DatasetFingerprint + ColumnSemanticRole list + grain_label into:
  - AnalysisStrategy  (what to run / avoid, which columns and chart families)
  - list[AnalysisRisk] (named data-quality and structural warnings)
  - HypothesisPlan    (generic questions to investigate)

Pure functions, no I/O, no side effects, no domain packs.
"""
from __future__ import annotations

from app.schemas.pre_analysis import (
    AnalysisRisk,
    AnalysisStrategy,
    ColumnSemanticRole,
    DatasetFingerprint,
    HypothesisPlan,
)

# ── Role-category helpers ─────────────────────────────────────────────────────

_METRIC_ROLES  = frozenset({"metric", "currency_amount", "rate_percentage", "target"})
_DIM_ROLES     = frozenset({"dimension", "geographic", "boolean_flag"})
_CHART_METRIC_ROLES = frozenset({"metric", "currency_amount", "rate_percentage"})


def _cols_with_role(roles: list[ColumnSemanticRole], *primary_roles: str) -> list[str]:
    role_set = frozenset(primary_roles)
    return [r.column_name for r in roles if r.primary_role in role_set]


def _has_role(roles: list[ColumnSemanticRole], *primary_roles: str) -> bool:
    role_set = frozenset(primary_roles)
    return any(r.primary_role in role_set for r in roles)


# ── 1. build_analysis_strategy ───────────────────────────────────────────────

def build_analysis_strategy(
    fingerprint: DatasetFingerprint,
    column_roles: list[ColumnSemanticRole],
    grain_label: str,
) -> AnalysisStrategy:
    """Return an :class:`AnalysisStrategy` for the dataset."""
    rows = fingerprint.row_count
    miss_rate = fingerprint.overall_missing_rate

    has_time    = _has_role(column_roles, "time")
    has_metric  = _has_role(column_roles, *_METRIC_ROLES)
    has_chart_metric = _has_role(column_roles, *_CHART_METRIC_ROLES)
    has_dim     = _has_role(column_roles, *_DIM_ROLES)
    has_target  = _has_role(column_roles, "target")
    has_text    = _has_role(column_roles, "free_text")
    has_leakage = _has_role(column_roles, "leakage_candidate")

    metric_cols = _cols_with_role(column_roles, *_METRIC_ROLES)
    pure_metric_or_rate = _cols_with_role(
        column_roles, "metric", "currency_amount", "rate_percentage"
    )
    two_metrics = len(pure_metric_or_rate) >= 2

    # ── Recommended analysis types (priority order) ──────────────────────────
    recommended: list[str] = []

    if has_target:
        recommended.append("target_analysis")
    if has_time and has_metric:
        recommended.append("trend_analysis")
    if has_dim and has_metric:
        recommended.append("segment_comparison")
    if two_metrics:
        recommended.append("correlation_analysis")
    if has_metric and rows >= 20:
        recommended.append("anomaly_detection")
    if has_metric:
        recommended.append("distribution_analysis")
    if miss_rate > 0:
        recommended.append("missingness_analysis")
    if has_text:
        recommended.append("text_review")

    # ── Deprioritised analysis types ─────────────────────────────────────────
    deprioritised: list[str] = []

    if not has_time:
        deprioritised.append("trend_analysis")
    if not has_dim:
        deprioritised.append("segment_comparison")
    if not two_metrics:
        deprioritised.append("correlation_analysis")
    if rows < 20:
        deprioritised.append("anomaly_detection")
    if not has_target:
        deprioritised.append("target_analysis")
    if not has_text:
        deprioritised.append("text_review")

    # ── Recommended columns (preserve original column order) ─────────────────
    rec_metrics = _cols_with_role(column_roles, *_METRIC_ROLES)[:8]
    rec_dims    = _cols_with_role(column_roles, *_DIM_ROLES)[:8]
    rec_time    = _cols_with_role(column_roles, "time")[:3]

    # ── Recommended chart families ────────────────────────────────────────────
    charts: list[str] = []
    if "trend_analysis"      in recommended:
        charts.append("line")
    if "segment_comparison"  in recommended:
        charts.append("bar")
    if "correlation_analysis" in recommended:
        charts.append("scatter")
    if "distribution_analysis" in recommended:
        charts.append("histogram")
    if "text_review" in recommended or has_leakage:
        charts.append("table")

    return AnalysisStrategy(
        recommended_analysis_types=recommended,
        deprioritised_analysis_types=deprioritised,
        recommended_metric_columns=rec_metrics,
        recommended_dimension_columns=rec_dims,
        recommended_time_columns=rec_time,
        recommended_chart_families=charts,
    )


# ── 2. detect_analysis_risks ─────────────────────────────────────────────────

def detect_analysis_risks(
    fingerprint: DatasetFingerprint,
    column_roles: list[ColumnSemanticRole],
) -> list[AnalysisRisk]:
    """Return a list of :class:`AnalysisRisk` objects for the dataset."""
    risks: list[AnalysisRisk] = []
    rows = fingerprint.row_count
    total_cols = fingerprint.column_count

    # Gather role groupings once
    id_cols = _cols_with_role(column_roles, "entity_id", "transaction_id")
    leakage_cols  = _cols_with_role(column_roles, "leakage_candidate")
    target_cols   = _cols_with_role(column_roles, "target")
    helper_cols   = [
        r for r in column_roles
        if r.primary_role == "helper_artifact"
        and r.notes and "date-part" in r.notes.lower()
    ]

    # ── too_many_id_columns ──────────────────────────────────────────────────
    if total_cols > 0 and len(id_cols) / total_cols > 0.20:
        risks.append(AnalysisRisk(
            risk_name="too_many_id_columns",
            severity="medium",
            affected_columns=id_cols,
            description=(
                f"{len(id_cols)} of {total_cols} columns are ID-like "
                f"({len(id_cols)/total_cols:.0%}). High-cardinality IDs can "
                "dominate findings and inflate uniqueness metrics."
            ),
        ))

    # ── sparse_columns ───────────────────────────────────────────────────────
    sparse = [r.column_name for r in column_roles if r.missing_rate > 0.60]
    if sparse:
        risks.append(AnalysisRisk(
            risk_name="sparse_columns",
            severity="medium",
            affected_columns=sparse,
            description=(
                f"{len(sparse)} column(s) exceed 60% missing rate. "
                "Findings on these columns may be unreliable."
            ),
        ))

    # ── date_part_artifacts ──────────────────────────────────────────────────
    if helper_cols:
        risks.append(AnalysisRisk(
            risk_name="date_part_artifacts",
            severity="low",
            affected_columns=[r.column_name for r in helper_cols],
            description=(
                "One or more columns appear to be date-part extractions "
                "(e.g. _month, _year). These should be excluded from "
                "analysis or used only for time aggregation."
            ),
        ))

    # ── possible_leakage ─────────────────────────────────────────────────────
    if leakage_cols and target_cols:
        risks.append(AnalysisRisk(
            risk_name="possible_leakage",
            severity="high",
            affected_columns=leakage_cols + target_cols,
            description=(
                "Potential target leakage detected: leakage-candidate columns "
                "exist alongside a target column. Findings may overstate "
                "predictive signal."
            ),
        ))

    # ── target_leakage_risk ──────────────────────────────────────────────────
    high_conf_leakage = [
        r.column_name for r in column_roles
        if r.primary_role == "leakage_candidate" and r.role_confidence > 0.7
    ]
    if high_conf_leakage:
        risks.append(AnalysisRisk(
            risk_name="target_leakage_risk",
            severity="high",
            affected_columns=high_conf_leakage,
            description=(
                "One or more leakage-candidate columns have high confidence "
                "scores. These columns may encode post-outcome information "
                "and should be excluded before modelling."
            ),
        ))

    # ── very_small_sample / small_sample ─────────────────────────────────────
    if rows < 30:
        risks.append(AnalysisRisk(
            risk_name="very_small_sample",
            severity="high",
            affected_columns=[],
            description=(
                f"Dataset has only {rows} rows. Statistical findings are "
                "likely unreliable at this sample size."
            ),
        ))
    elif rows < 100:
        risks.append(AnalysisRisk(
            risk_name="small_sample",
            severity="medium",
            affected_columns=[],
            description=(
                f"Dataset has {rows} rows. Some statistical findings may "
                "lack sufficient power; interpret with caution."
            ),
        ))

    # ── high_cardinality_dimensions ──────────────────────────────────────────
    threshold = max(50, rows * 0.5)
    high_card_dims = [
        r.column_name for r in column_roles
        if r.primary_role in {"dimension", "geographic"}
        and r.cardinality > threshold
    ]
    if high_card_dims:
        risks.append(AnalysisRisk(
            risk_name="high_cardinality_dimensions",
            severity="medium",
            affected_columns=high_card_dims,
            description=(
                f"{len(high_card_dims)} dimension/geographic column(s) have "
                "cardinality above the threshold for reliable segment "
                "comparison. Consider grouping or excluding them."
            ),
        ))

    # ── constant_columns ─────────────────────────────────────────────────────
    constant = [
        r.column_name for r in column_roles
        if r.cardinality <= 1 and rows > 0
    ]
    if constant:
        risks.append(AnalysisRisk(
            risk_name="constant_columns",
            severity="low",
            affected_columns=constant,
            description=(
                f"{len(constant)} column(s) have only one unique value and "
                "carry no analytical signal. Consider removing them."
            ),
        ))

    # ── mixed_grain ───────────────────────────────────────────────────────────
    has_tx_id  = _has_role(column_roles, "transaction_id")
    has_ent_id = _has_role(column_roles, "entity_id")
    if has_tx_id and has_ent_id and fingerprint.dataset_shape == "snapshot":
        risks.append(AnalysisRisk(
            risk_name="mixed_grain",
            severity="medium",
            affected_columns=_cols_with_role(
                column_roles, "transaction_id", "entity_id"
            ),
            description=(
                "Both transaction-ID and entity-ID columns are present in a "
                "snapshot-shaped table. The dataset may mix multiple grain "
                "levels, which can cause double-counting or misleading "
                "segment aggregations."
            ),
        ))

    return risks


# ── 3. build_hypothesis_plan ─────────────────────────────────────────────────

def build_hypothesis_plan(
    fingerprint: DatasetFingerprint,
    column_roles: list[ColumnSemanticRole],
    grain_label: str,
) -> HypothesisPlan:
    """Return a :class:`HypothesisPlan` with deterministic generic hypotheses."""
    rows = fingerprint.row_count
    miss_rate = fingerprint.overall_missing_rate

    has_metric  = _has_role(column_roles, *_METRIC_ROLES)
    has_dim     = _has_role(column_roles, *_DIM_ROLES)
    has_time    = _has_role(column_roles, "time")
    has_target  = _has_role(column_roles, "target")
    has_text    = _has_role(column_roles, "free_text")
    has_id_risk = _has_role(column_roles, "entity_id", "transaction_id", "helper_artifact")
    pure_metric_count = len(_cols_with_role(
        column_roles, "metric", "currency_amount", "rate_percentage"
    ))

    hypotheses: list[str] = []

    if has_metric and has_dim:
        hypotheses.append(
            "Check whether key metrics vary meaningfully across important dimensions."
        )

    if has_metric and has_time:
        hypotheses.append(
            "Check whether key metrics trend over the detected time column."
        )

    if miss_rate > 0:
        hypotheses.append(
            "Check whether missingness is concentrated in specific columns."
        )

    if has_id_risk:
        hypotheses.append(
            "Check whether high-cardinality ID or helper columns are "
            "incorrectly driving findings."
        )

    if pure_metric_count >= 2:
        hypotheses.append(
            "Check whether metric pairs show strong correlation or anti-correlation."
        )

    if rows >= 20 and has_metric:
        hypotheses.append(
            "Check whether anomalous rows deviate from the main distribution."
        )

    if has_target:
        hypotheses.append(
            "Check whether the target variable is balanced and which fields "
            "are associated with it."
        )

    if has_text:
        hypotheses.append(
            "Review free-text columns for recurring themes or data quality issues."
        )

    # Always add fallback
    hypotheses.append(
        "Review basic distributions and data quality before drawing conclusions."
    )

    return HypothesisPlan(hypotheses=hypotheses[:8])
