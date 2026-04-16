"""
Advanced insight detectors.

All six detectors apply budget caps (MAX_ADV_NUMERIC / MAX_ADV_CATEGORICAL /
MAX_LEADING_PAIRS) to prevent O(n²) or O(n³) runtime on wide datasets.

Detectors:
  detect_concentration_risk   — Pareto / category dominance
  detect_interaction_effects  — correlation r varies by subgroup
  detect_simpsons_paradox     — sign of correlation flips in subgroups
  detect_missing_patterns     — structural MAR/MNAR via point-biserial r
  detect_leading_indicators   — lag cross-correlation (datetime required)
  detect_multicollinearity    — VIF > 5 / 10
"""
from itertools import combinations

import numpy as np
import pandas as pd
from scipy import stats

from .budget import MAX_ADV_NUMERIC, MAX_ADV_CATEGORICAL, MAX_LEADING_PAIRS, MAX_LAG_DEPTH


# ── Concentration risk ────────────────────────────────────────────────────────

def detect_concentration_risk(
    df: pd.DataFrame,
    numeric_cols: list[str],
    categorical_cols: list[str],
) -> list[dict]:
    """Pareto (numeric) and category dominance (categorical) concentration."""
    insights: list[dict] = []

    for num_col in numeric_cols[:MAX_ADV_NUMERIC]:
        col = df[num_col].dropna()
        if len(col) < 20 or col.min() < 0:
            continue
        total = float(col.sum())
        if total <= 0:
            continue
        sorted_col = col.sort_values(ascending=False)
        top10_n = max(1, int(len(col) * 0.1))
        top20_n = max(1, int(len(col) * 0.2))
        top10_share = float(sorted_col.iloc[:top10_n].sum() / total * 100)
        top20_share = float(sorted_col.iloc[:top20_n].sum() / total * 100)
        if top10_share <= 50:
            continue
        insights.append({
            "type": "concentration",
            "severity": "high" if top10_share > 70 else "medium",
            "confidence": round(min(95, 60 + top10_share * 0.4), 1),
            "title": f"Concentration risk in {num_col}",
            "finding": (
                f"Top 10% of records account for {top10_share:.1f}% of total {num_col}. "
                f"Top 20% account for {top20_share:.1f}%. Strong Pareto concentration detected."
            ),
            "evidence": (
                f"Top 10%: {top10_share:.1f}%, Top 20%: {top20_share:.1f}% of total {num_col}"
            ),
            "action": (
                f"Segment analysis around the top {top10_n} records in {num_col}. "
                f"Consider whether this concentration represents risk or opportunity."
            ),
        })

    for cat_col in categorical_cols[:MAX_ADV_CATEGORICAL]:
        counts = df[cat_col].value_counts()
        if len(counts) < 2:
            continue
        top_share = float(counts.iloc[0] / len(df) * 100)
        if top_share <= 70:
            continue
        insights.append({
            "type": "concentration",
            "severity": "medium",
            "confidence": 90.0,
            "title": f"Category dominance: {cat_col}",
            "finding": (
                f"'{counts.index[0]}' accounts for {top_share:.1f}% of all records in '{cat_col}'. "
                f"This heavy imbalance can bias models and aggregations."
            ),
            "evidence": (
                f"{counts.index[0]}: {int(counts.iloc[0])} of {len(df)} rows ({top_share:.1f}%)"
            ),
            "action": (
                f"Check whether '{counts.index[0]}' over-representation is a data collection artifact. "
                f"Consider stratified analysis for the minority categories."
            ),
        })

    return insights


# ── Interaction effects ───────────────────────────────────────────────────────

def detect_interaction_effects(
    df: pd.DataFrame,
    numeric_cols: list[str],
    categorical_cols: list[str],
) -> list[dict]:
    """
    Find pairs where the correlation between two numerics differs substantially
    across levels of a categorical moderator (r range > 0.3).
    """
    insights: list[dict] = []
    if len(numeric_cols) < 2 or not categorical_cols:
        return []

    # Use top 3 numeric pairs by |r|, bounded by budget
    pair_corrs: list[tuple] = []
    for c1, c2 in combinations(numeric_cols[:MAX_ADV_NUMERIC], 2):
        clean = df[[c1, c2]].dropna()
        if len(clean) < 20:
            continue
        try:
            r, _ = stats.pearsonr(clean[c1], clean[c2])
            if abs(r) > 0.25:
                pair_corrs.append((c1, c2, float(r)))
        except Exception:
            pass
    pair_corrs.sort(key=lambda x: abs(x[2]), reverse=True)

    for c1, c2, overall_r in pair_corrs[:3]:
        for mod_col in categorical_cols[:MAX_ADV_CATEGORICAL]:
            group_corrs: dict[str, float] = {}
            for cat_val, group in df.groupby(mod_col):
                sub = group[[c1, c2]].dropna()
                if len(sub) < 15:
                    continue
                try:
                    r, _ = stats.pearsonr(sub[c1], sub[c2])
                    group_corrs[str(cat_val)] = float(r)
                except Exception:
                    pass
            if len(group_corrs) < 2:
                continue
            r_vals = list(group_corrs.values())
            r_range = max(r_vals) - min(r_vals)
            if r_range <= 0.3:
                continue
            max_group = max(group_corrs, key=group_corrs.get)
            min_group = min(group_corrs, key=group_corrs.get)
            insights.append({
                "type": "interaction",
                "severity": "high" if r_range > 0.5 else "medium",
                "confidence": round(min(90, 60 + r_range * 60), 1),
                "title": f"Interaction effect: {c1} × {c2} moderated by {mod_col}",
                "finding": (
                    f"The relationship between '{c1}' and '{c2}' (overall r={overall_r:.2f}) "
                    f"varies substantially by '{mod_col}': "
                    f"r={group_corrs[max_group]:.2f} for '{max_group}' "
                    f"vs r={group_corrs[min_group]:.2f} for '{min_group}'."
                ),
                "evidence": (
                    f"Correlation range across {mod_col} groups: {r_range:.2f}. "
                    f"Groups: {', '.join(f'{k}={v:.2f}' for k, v in group_corrs.items())}"
                ),
                "action": (
                    f"Analyze '{c1}' vs '{c2}' separately for each '{mod_col}' group. "
                    f"A model built on the overall correlation may be misleading."
                ),
            })

    return insights[:3]


# ── Simpson's paradox ─────────────────────────────────────────────────────────

def detect_simpsons_paradox(
    df: pd.DataFrame,
    numeric_cols: list[str],
    categorical_cols: list[str],
) -> list[dict]:
    """Report pairs where the overall r sign flips in ≥ 2 subgroups."""
    insights: list[dict] = []
    if len(numeric_cols) < 2 or not categorical_cols:
        return []

    for c1, c2 in combinations(numeric_cols[:MAX_ADV_NUMERIC], 2):
        clean = df[[c1, c2]].dropna()
        if len(clean) < 20:
            continue
        try:
            overall_r, _ = stats.pearsonr(clean[c1], clean[c2])
        except Exception:
            continue
        if abs(overall_r) < 0.15:
            continue

        for cat_col in categorical_cols[:MAX_ADV_CATEGORICAL]:
            flip_count = 0
            for _, group in df.groupby(cat_col):
                sub = group[[c1, c2]].dropna()
                if len(sub) < 10:
                    continue
                try:
                    r, _ = stats.pearsonr(sub[c1], sub[c2])
                    if (r > 0 and overall_r < 0) or (r < 0 and overall_r > 0):
                        flip_count += 1
                except Exception:
                    pass
            if flip_count >= 2:
                insights.append({
                    "type": "simpsons_paradox",
                    "severity": "high",
                    "confidence": 80.0,
                    "title": f"Possible Simpson's Paradox: {c1} vs {c2} by {cat_col}",
                    "finding": (
                        f"Overall, '{c1}' and '{c2}' have r={overall_r:.2f}, but within "
                        f"{flip_count} subgroups of '{cat_col}' the relationship reverses direction. "
                        f"This is a warning sign of Simpson's Paradox."
                    ),
                    "evidence": (
                        f"Overall r={overall_r:.2f}, {flip_count} subgroups show opposite sign"
                    ),
                    "action": (
                        f"Always segment by '{cat_col}' when analyzing '{c1}' vs '{c2}'. "
                        f"The overall correlation is misleading — it is driven by group composition, "
                        f"not the true relationship."
                    ),
                })

    return insights[:2]


# ── Missing data patterns ─────────────────────────────────────────────────────

def detect_missing_patterns(
    df: pd.DataFrame,
    numeric_cols: list[str],
) -> list[dict]:
    """Detect structural missingness via point-biserial r (MAR/MNAR signal)."""
    insights: list[dict] = []
    missing_cols = [col for col in df.columns if df[col].isnull().any()]
    if not missing_cols:
        return []

    from scipy.stats import pointbiserialr

    for miss_col in missing_cols[:MAX_ADV_NUMERIC]:
        miss_indicator = df[miss_col].isnull().astype(int)
        for num_col in numeric_cols[:MAX_ADV_NUMERIC]:
            if num_col == miss_col:
                continue
            other = df[num_col].fillna(df[num_col].median())
            try:
                r, p = pointbiserialr(miss_indicator, other)
                if abs(r) > 0.35 and p < 0.05:
                    insights.append({
                        "type": "missing_pattern",
                        "severity": "medium",
                        "confidence": round(abs(r) * 100, 1),
                        "title": f"Structural missing data: {miss_col} linked to {num_col}",
                        "finding": (
                            f"'{miss_col}' is {'more' if r > 0 else 'less'} likely to be missing "
                            f"when '{num_col}' is {'high' if r > 0 else 'low'} (r={r:.2f}). "
                            f"This is a MAR or MNAR pattern, not random missingness."
                        ),
                        "evidence": (
                            f"Point-biserial r={r:.3f}, p={p:.4f} between missingness "
                            f"indicator and {num_col}"
                        ),
                        "action": (
                            f"Do not use simple mean/median imputation for '{miss_col}'. "
                            f"Use model-based imputation (KNN or MICE) conditioned on '{num_col}'."
                        ),
                    })
                    break  # one finding per missing column
            except Exception:
                pass

    return insights[:3]


# ── Leading indicators ────────────────────────────────────────────────────────

def detect_leading_indicators(
    df: pd.DataFrame,
    numeric_cols: list[str],
) -> list[dict]:
    """
    Detect X→Y lag correlations.  Requires a datetime column — without one,
    row order is arbitrary and lag analysis would be meaningless.
    """
    if len(numeric_cols) < 2 or len(df) < 20:
        return []

    datetime_cols = df.select_dtypes(include=["datetime64"]).columns.tolist()
    if not datetime_cols:
        return []

    time_col = datetime_cols[0]
    df_sorted = df.sort_values(time_col).reset_index(drop=True)
    max_lag = min(MAX_LAG_DEPTH, len(df_sorted) // 4)

    insights: list[dict] = []
    cols = numeric_cols[:MAX_LEADING_PAIRS]

    for c1, c2 in combinations(cols, 2):
        clean = df_sorted[[c1, c2]].dropna().reset_index(drop=True)
        if len(clean) < 20:
            continue
        try:
            base_r, _ = stats.pearsonr(clean[c1], clean[c2])
        except Exception:
            continue

        best_lag, best_r = 0, 0.0
        for lag in range(1, max_lag + 1):
            a = clean[c1].iloc[:-lag].values
            b = clean[c2].iloc[lag:].values
            if len(a) < 10:
                continue
            try:
                r, _ = stats.pearsonr(a, b)
                if abs(r) > abs(best_r) and abs(r) > abs(base_r) + 0.1:
                    best_r = r
                    best_lag = lag
            except Exception:
                pass

        if best_lag > 0 and abs(best_r) > 0.4:
            insights.append({
                "type": "leading_indicator",
                "severity": "medium",
                "confidence": round(abs(best_r) * 100, 1),
                "title": f"Leading indicator: {c1} → {c2} (lag {best_lag})",
                "finding": (
                    f"'{c1}' at time T correlates with '{c2}' at time T+{best_lag} "
                    f"(r={best_r:.2f} at lag {best_lag}, vs r={base_r:.2f} at lag 0). "
                    f"'{c1}' may be a leading indicator of '{c2}'."
                ),
                "evidence": (
                    f"Cross-correlation at lag={best_lag}: r={best_r:.3f} "
                    f"(baseline: r={base_r:.3f}). Data sorted by '{time_col}'."
                ),
                "action": (
                    f"Monitor '{c1}' as an early warning signal for '{c2}'. "
                    f"Changes in '{c1}' may precede changes in '{c2}' by {best_lag} periods."
                ),
                "note": f"Rows sorted by '{time_col}' for this analysis.",
            })

    return insights[:2]


# ── Multicollinearity ─────────────────────────────────────────────────────────

def detect_multicollinearity(
    df: pd.DataFrame,
    numeric_cols: list[str],
) -> list[dict]:
    """VIF-based multicollinearity detection (requires statsmodels)."""
    if len(numeric_cols) < 3:
        return []

    usable = [c for c in numeric_cols if df[c].isnull().mean() < 0.3]
    if len(usable) < 3:
        return []

    sub = df[usable].dropna()
    if len(sub) < max(20, len(usable) * 2):
        return []

    usable = [c for c in usable if sub[c].std() > 1e-10]
    if len(usable) < 3:
        return []

    sub = sub[usable]
    try:
        from statsmodels.stats.outliers_influence import variance_inflation_factor
        X = sub.values
        vif_scores = {
            usable[i]: float(variance_inflation_factor(X, i))
            for i in range(len(usable))
        }
    except Exception:
        return []

    high_vif = {col: v for col, v in vif_scores.items() if v > 5}
    if not high_vif:
        return []

    severe = {col: v for col, v in high_vif.items() if v > 10}
    moderate = {col: v for col, v in high_vif.items() if 5 < v <= 10}
    severity = "high" if severe else "medium"
    affected = sorted(high_vif.items(), key=lambda x: x[1], reverse=True)
    top_cols = ", ".join(f"{c} (VIF={v:.1f})" for c, v in affected[:4])

    parts: list[str] = []
    if severe:
        s_cols = ", ".join(f"'{c}'" for c in severe)
        parts.append(
            f"{len(severe)} column(s) have severe multicollinearity (VIF > 10): {s_cols}."
        )
    if moderate:
        m_cols = ", ".join(f"'{c}'" for c in moderate)
        parts.append(
            f"{len(moderate)} column(s) have moderate multicollinearity (VIF 5–10): {m_cols}."
        )

    return [{
        "type": "multicollinearity",
        "severity": severity,
        "confidence": round(min(95, 70 + len(high_vif) * 5), 1),
        "title": f"Multicollinearity detected ({len(high_vif)} columns)",
        "finding": " ".join(parts) + (
            " Including all of these as features in a model will produce unstable, "
            "hard-to-interpret coefficients."
        ),
        "evidence": f"VIF scores: {top_cols}",
        "action": (
            "Remove or combine redundant columns before modeling. "
            "Consider PCA to reduce correlated features into orthogonal components, "
            "or drop the column with the highest VIF and re-check."
        ),
    }]
