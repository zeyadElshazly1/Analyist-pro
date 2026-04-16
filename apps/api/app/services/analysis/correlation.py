"""
Correlation detector.

Computes pairwise Pearson or Spearman correlations between numeric columns,
applies Benjamini-Hochberg FDR correction, and returns insight dicts for
pairs that survive both the |r| > 0.3 and adjusted-p < 0.05 thresholds.
"""
from itertools import combinations

import pandas as pd
from scipy import stats

from .stats_helpers import _bh_correct, _normality_test
from .budget import MAX_CORR_COLS


def detect_correlations(df: pd.DataFrame, numeric_cols: list[str]) -> list[dict]:
    """
    Return correlation insights for numeric column pairs.

    Columns are capped at MAX_CORR_COLS before any pairwise work so the
    O(n²) combination count stays bounded on wide datasets.
    """
    cols = numeric_cols[:MAX_CORR_COLS]
    if len(cols) < 2:
        return []

    raw: list[tuple] = []
    for col1, col2 in combinations(cols, 2):
        clean = df[[col1, col2]].dropna()
        if len(clean) < 10:
            continue
        is_normal = _normality_test(clean[col1]) and _normality_test(clean[col2])
        if is_normal:
            corr, pvalue = stats.pearsonr(clean[col1], clean[col2])
            method = "Pearson"
        else:
            corr, pvalue = stats.spearmanr(clean[col1], clean[col2])
            method = "Spearman"
        if abs(corr) > 0.3:
            raw.append((col1, col2, float(corr), float(pvalue), method, len(clean)))

    if not raw:
        return []

    adj_pvals = _bh_correct([x[3] for x in raw])
    insights: list[dict] = []
    for (col1, col2, corr, _, method, n), adj_p in zip(raw, adj_pvals):
        if abs(corr) <= 0.3 or adj_p >= 0.05:
            continue
        direction = "positively" if corr > 0 else "negatively"
        strength = (
            "very strongly" if abs(corr) > 0.9
            else "strongly" if abs(corr) > 0.7
            else "moderately" if abs(corr) > 0.5
            else "weakly"
        )
        severity = "high" if abs(corr) > 0.7 else "medium"
        insights.append({
            "type": "correlation",
            "severity": severity,
            "confidence": round(abs(corr) * 100, 1),
            "col_a": col1,
            "col_b": col2,
            "title": f"Relationship detected: {col1} & {col2}",
            "finding": (
                f"{col1} and {col2} are {strength} {direction} correlated "
                f"(r={corr:.2f}, {method}). When {col1} increases, {col2} tends to "
                f"{'increase' if corr > 0 else 'decrease'}."
            ),
            "evidence": f"{method} r={corr:.3f}, adjusted p={adj_p:.4f}, n={n}",
            "action": (
                f"Investigate whether {col1} drives {col2}. Consider multicollinearity "
                f"if both are used as model features."
            ),
        })

    return insights
