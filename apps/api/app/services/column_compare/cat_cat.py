"""Categorical vs categorical column comparison."""
from __future__ import annotations

import pandas as pd
from scipy import stats

from .stats import _cramers_v, _cramers_label


def _group_rare(series: pd.Series, top_n: int) -> pd.Series:
    top = series.value_counts().head(top_n).index
    return series.where(series.isin(top), other="(Other)")


def compare_cat_cat(df: pd.DataFrame, col_a: str, col_b: str) -> dict:
    n_total = len(df[[col_a, col_b]])
    clean = df[[col_a, col_b]].dropna()
    n_used = len(clean)

    if n_used < 5:
        raise ValueError("Not enough values for comparison")

    sample_loss = {
        "n_total": n_total,
        "n_used": n_used,
        "n_dropped": n_total - n_used,
        "pct_dropped": round((n_total - n_used) / max(n_total, 1) * 100, 1),
    }

    col_a_grouped = _group_rare(clean[col_a], 8)
    col_b_grouped = _group_rare(clean[col_b], 8)
    crosstab = pd.crosstab(col_a_grouped, col_b_grouped)

    chi2_p = None
    cramers = 0.0
    if crosstab.shape[0] >= 2 and crosstab.shape[1] >= 2:
        try:
            _, chi2_p, _, _ = stats.chi2_contingency(crosstab)
            chi2_p = round(float(chi2_p), 6)
            cramers = _cramers_v(crosstab)
        except Exception:
            pass

    cramers_label = _cramers_label(cramers)
    is_significant = bool(chi2_p < 0.05) if chi2_p is not None else None

    heatmap = []
    row_totals = crosstab.sum(axis=1)
    for row_label in crosstab.index:
        for col_label in crosstab.columns:
            count = int(crosstab.loc[row_label, col_label])
            row_total = int(row_totals[row_label])
            heatmap.append({
                "row": str(row_label),
                "col": str(col_label),
                "value": count,
                "row_pct": round(count / max(row_total, 1) * 100, 1),
            })

    interpretation = (
        (
            f"Chi-square p={chi2_p:.4f} — {'significant' if is_significant else 'no significant'} association between {col_a} and {col_b}. "
            f"Cramér's V={cramers:.2f} ({cramers_label} association) — "
            f"{'the two categories are meaningfully related' if cramers > 0.3 else 'the association is weak and may not be actionable'}."
        )
        if chi2_p is not None
        else f"Crosstab of {col_a} vs {col_b}"
    )

    return {
        "type": "cat_cat",
        "col_a": col_a,
        "col_b": col_b,
        "n": n_used,
        "chi2_p": chi2_p,
        "cramers_v": round(cramers, 4),
        "cramers_label": cramers_label,
        "is_significant": is_significant,
        "row_labels": [str(x) for x in crosstab.index.tolist()],
        "col_labels": [str(x) for x in crosstab.columns.tolist()],
        "heatmap": heatmap,
        "interpretation": interpretation,
        "sample_loss": sample_loss,
    }
