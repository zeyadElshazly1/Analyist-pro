"""
Analysis pipeline orchestrator.

Wires together all detector sub-modules and applies runtime budget caps so no
detector sees more columns than its budget constant allows.

Public API (backward-compatible with app.services.analyzer):
    analyze_dataset(df)             -> tuple[list[dict], str]
    generate_executive_panel(insights) -> dict
    get_dataset_summary(df)         -> dict
"""
import numpy as np
import pandas as pd

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


def analyze_dataset(df: pd.DataFrame) -> tuple[list[dict], str]:
    """
    Run the full insight detection pipeline and return (insights, narrative).

    Columns recognised as high-cardinality ID columns (> 95% unique, name
    contains 'id') are excluded from analysis.
    """
    # Drop pure-ID columns up front
    id_cols = [
        col for col in df.columns
        if "id" in col.lower() and df[col].nunique() / max(len(df), 1) > 0.95
    ]
    df = df.drop(columns=id_cols, errors="ignore")

    # ── Column lists ──────────────────────────────────────────────────────────
    all_numeric = df.select_dtypes(include=[np.number]).columns.tolist()
    categorical_cols = [
        col for col in df.select_dtypes(include=["object", "category"]).columns
        if df[col].nunique() < 50
    ]

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

    # ── Rank, deduplicate, cap ────────────────────────────────────────────────
    top_insights, total_found = rank_insights(insights)

    # ── Enrich + narrative ────────────────────────────────────────────────────
    top_insights = [_enrich_insight(ins) for ins in top_insights]
    narrative = generate_narrative(top_insights, df, total_found=total_found)

    return top_insights, narrative


def generate_executive_panel(insights: list[dict]) -> dict:
    """
    Derive Opportunities, Risks, and an Action Plan from the top insights.
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


def get_dataset_summary(df: pd.DataFrame) -> dict:
    """Return a lightweight summary dict describing the dataset's shape."""
    return {
        "rows": len(df),
        "columns": len(df.columns),
        "numeric_cols": len(df.select_dtypes(include=[np.number]).columns),
        "categorical_cols": len(df.select_dtypes(include=["object"]).columns),
        "datetime_cols": len(df.select_dtypes(include=["datetime64"]).columns),
        "missing_pct": round(
            df.isnull().sum().sum() / max(len(df) * len(df.columns), 1) * 100, 1
        ),
        "domain": _detect_domain(df.columns.tolist()),
    }
