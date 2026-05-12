"""
Analysis pipeline orchestrator.

Wires together all detector sub-modules and applies runtime budget caps so no
detector sees more columns than its budget constant allows.

Public API (backward-compatible with app.services.analyzer):
    analyze_dataset(df)             -> tuple[list[dict], str]
    generate_executive_panel(insights) -> dict
    get_dataset_summary(df)         -> dict
"""
import logging

import numpy as np
import pandas as pd

from app.services.dataset_context import (
    CONFIDENCE_THRESHOLD,
    FINANCIAL_MARKETS_SNAPSHOT,
    FINANCIAL_MARKETS_TIMESERIES,
    detect_dataset_context,
)

from .domain.registry import run_domain_pack
from .insight_suppression import suppress_for_dataset_context

from .budget import (
    MAX_CORR_COLS,
    MAX_SEG_CATS,
    MAX_SEG_NUMS,
    MAX_UNIVARIATE_COLS,
    MAX_ADV_NUMERIC,
    MAX_ADV_CATEGORICAL,
    MAX_TREND_COLS,
    MAX_LEADING_PAIRS,
)
from .correlation import detect_correlations
from .anomalies import detect_multivariate_anomalies, detect_univariate_anomalies
from .distributions import detect_skewness
from .segments import detect_segment_gaps, detect_binary_rates
from .data_quality import detect_high_cardinality, detect_missing_columns, detect_constant_columns
from .advanced import (
    detect_concentration_risk,
    detect_interaction_effects,
    detect_simpsons_paradox,
    detect_missing_patterns,
    detect_leading_indicators,
    detect_multicollinearity,
)
from .trends import detect_trends
from .narrative import _detect_domain, _enrich_insight, generate_narrative
from .ranking import rank_insights
from app.config import MAX_INSIGHTS

# How many ranked candidates to pass back to the route so that plan hygiene
# can recover clean insights that would otherwise have been discarded by the
# pre-hygiene cap.  The route applies the final MAX_INSIGHTS cap after hygiene.
POST_HYGIENE_CANDIDATE_MULTIPLIER = 3


logger = logging.getLogger(__name__)


def analyze_dataset(df: pd.DataFrame) -> tuple[list[dict], str]:
    """
    Run the full insight detection pipeline and return (insights, narrative).

    Columns recognised as high-cardinality ID columns (> 95% unique, name
    contains 'id') are excluded from analysis.
    """
    # Drop pure-ID columns up front — name contains "id" AND > 95% unique values
    id_cols = [
        col for col in df.columns
        if "id" in col.lower() and df[col].nunique() / max(len(df), 1) > 0.95
    ]
    df = df.drop(columns=id_cols, errors="ignore")

    ctx = detect_dataset_context(df)

    # ── Column lists ──────────────────────────────────────────────────────────
    all_numeric = df.select_dtypes(include=[np.number]).columns.tolist()
    categorical_cols = [
        col for col in df.select_dtypes(include=["object", "category"]).columns
        if df[col].nunique() < 50
    ]

    # Binary integer columns (0/1 flags like SeniorCitizen) behave as categorical
    # for rate/segment analysis but are typed as numeric after cleaning.  Include
    # them in categorical_cols so detect_binary_rates and detect_segment_gaps can
    # produce meaningful segment insights (e.g. SeniorCitizen churn rate).
    binary_int_cols = [
        col for col in df.select_dtypes(include=[np.number]).columns
        if df[col].nunique() == 2
    ]
    # Deduplicate preserving order.  Binary int cols are placed BEFORE string
    # categoricals so they fall within the MAX_SEG_CATS budget slice and are
    # actually visited by detect_binary_rates / detect_segment_gaps.
    categorical_cols = list(dict.fromkeys(binary_int_cols + categorical_cols))

    # Budget-capped column slices
    numeric_cols   = all_numeric[:MAX_UNIVARIATE_COLS]
    corr_cols      = all_numeric[:MAX_CORR_COLS]
    seg_cats       = categorical_cols[:MAX_SEG_CATS]
    seg_nums       = all_numeric[:MAX_SEG_NUMS]
    adv_numeric    = all_numeric[:MAX_ADV_NUMERIC]
    adv_cats       = categorical_cols[:MAX_ADV_CATEGORICAL]
    trend_cols     = all_numeric[:MAX_TREND_COLS]
    leading_cols   = all_numeric[:MAX_LEADING_PAIRS]

    # ── Run detectors ─────────────────────────────────────────────────────────
    insights: list[dict] = []

    # 1. Correlations
    insights += detect_correlations(df, corr_cols)

    # 2. Multivariate anomalies
    insights += detect_multivariate_anomalies(df, numeric_cols)

    # 3. Univariate anomalies
    insights += detect_univariate_anomalies(df, numeric_cols)

    # 4. Distribution skewness
    insights += detect_skewness(df, numeric_cols)

    # 5. Segment gaps
    insights += detect_segment_gaps(df, seg_cats, seg_nums)

    # 6. Binary rate analysis
    insights += detect_binary_rates(df, categorical_cols)

    # 7. Data quality
    insights += detect_high_cardinality(df)
    insights += detect_missing_columns(df)
    insights += detect_constant_columns(df, numeric_cols)

    # 8. Advanced detectors
    insights += detect_concentration_risk(df, adv_numeric, adv_cats)
    insights += detect_interaction_effects(df, adv_numeric, adv_cats)
    insights += detect_simpsons_paradox(df, adv_numeric, adv_cats)
    insights += detect_missing_patterns(df, adv_numeric)
    insights += detect_leading_indicators(df, leading_cols)
    insights += detect_multicollinearity(df, adv_numeric)

    # 9. Trends (datetime only — no row-order fallback)
    insights += detect_trends(df, trend_cols)

    # 10. Domain-specific insights (financial snapshot, when confidently detected)
    try:
        if ctx.dataset_type == FINANCIAL_MARKETS_TIMESERIES:
            insights.extend(run_domain_pack(df, ctx))
        elif (
            ctx.dataset_type == FINANCIAL_MARKETS_SNAPSHOT
            and ctx.confidence >= CONFIDENCE_THRESHOLD
        ):
            insights.extend(run_domain_pack(df, ctx))
    except Exception:
        logger.exception("Domain pack wiring failed; continuing without domain insights")

    insights = suppress_for_dataset_context(insights, ctx)

    # ── Rank, deduplicate — wider candidate pool for post-hygiene recovery ────
    candidate_limit = MAX_INSIGHTS * POST_HYGIENE_CANDIDATE_MULTIPLIER
    top_insights, total_found = rank_insights(insights, ctx, limit=candidate_limit)

    # ── Enrich + narrative ────────────────────────────────────────────────────
    top_insights = [_enrich_insight(ins) for ins in top_insights]
    narrative = generate_narrative(top_insights, df, total_found=total_found)

    return top_insights, narrative


def _raw_confidence(ins: dict) -> float:
    try:
        value = float(ins.get("confidence", 50.0))
    except (TypeError, ValueError):
        return 50.0
    if value < 0:
        return 0.0
    if value > 100:
        return 100.0
    return value


def _is_executive_panel_eligible(ins: dict) -> bool:
    """Whether an insight may appear in opportunities, risks, or action_plan.

    Plan-suppressed and low-confidence findings remain in the main insight list
    but are omitted from the executive summary (88C).
    """
    if ins.get("suppressed_by_plan") is True:
        return False
    if _raw_confidence(ins) < 50.0:
        return False
    return True


def generate_executive_panel(insights: list[dict]) -> dict:
    """
    Derive Opportunities, Risks, and an Action Plan from the top insights.

    Findings suppressed by analysis_plan_hygiene (``suppressed_by_plan``) or with
    raw confidence below 50 (0–100 scale) are excluded from all three sections;
    they remain available in the main insight list (88C).

    Returns a dict with three lists suitable for rendering on the frontend.
    """
    OPPORTUNITY_TYPES = {
        "correlation", "segment", "leading_indicator", "concentration", "trend", "interaction"
    }
    RISK_TYPES = {
        "anomaly", "data_quality", "multicollinearity", "simpsons_paradox", "missing_pattern"
    }

    opportunities: list[dict] = []
    risks: list[dict] = []
    action_plan: list[dict] = []

    for ins in insights:
        if not _is_executive_panel_eligible(ins):
            continue

        itype = ins.get("type", "")
        sev = ins.get("severity", "low")
        title = ins.get("title", "")
        action = ins.get("action", "")
        finding = ins.get("finding", "")

        if itype in OPPORTUNITY_TYPES and sev in ("high", "medium") and len(opportunities) < 4:
            opportunities.append({
                "title": title,
                "summary": finding[:140] + ("…" if len(finding) > 140 else ""),
                "severity": sev,
            })
        elif itype in RISK_TYPES and sev in ("high", "medium") and len(risks) < 4:
            risks.append({
                "title": title,
                "summary": finding[:140] + ("…" if len(finding) > 140 else ""),
                "severity": sev,
            })

        if action and len(action_plan) < 5:
            action_plan.append({
                "action": action[:180] + ("…" if len(action) > 180 else ""),
                "type": itype,
                "severity": sev,
            })

    return {
        "opportunities": opportunities,
        "risks": risks,
        "action_plan": action_plan,
    }


_LARGE_DATASET_THRESHOLD = 100_000
_LARGE_DATASET_INFERENCE_SAMPLE = 10_000


def get_dataset_summary(df: pd.DataFrame) -> dict:
    """Return a lightweight summary dict describing the dataset's shape."""
    n_rows = len(df)
    ctx = detect_dataset_context(df)
    large = n_rows > _LARGE_DATASET_THRESHOLD
    return {
        "rows": n_rows,
        "columns": len(df.columns),
        "numeric_cols": len(df.select_dtypes(include=[np.number]).columns),
        "categorical_cols": len(df.select_dtypes(include=["object"]).columns),
        "datetime_cols": len(df.select_dtypes(include=["datetime64"]).columns),
        "missing_pct": round(
            df.isnull().sum().sum() / max(n_rows * len(df.columns), 1) * 100, 1
        ),
        "domain": _detect_domain(df.columns.tolist()),
        "large_dataset_mode": large,
        "analyzed_rows": n_rows,
        "sample_strategy": (
            f"Statistical inference uses a representative {_LARGE_DATASET_INFERENCE_SAMPLE:,}-row sample "
            f"for performance. All findings and cleaning cover the full {n_rows:,}-row dataset."
            if large else None
        ),
        "dataset_context": {
            "dataset_type":    ctx.dataset_type,
            "confidence":      ctx.confidence,
            "matched_signals": list(ctx.matched_signals),
            "semantic_roles":  dict(ctx.semantic_roles),
            "warnings":        list(ctx.warnings),
        },
    }
