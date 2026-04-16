"""Categorical × categorical correlation computation (Cramér's V)."""
from __future__ import annotations

import pandas as pd

from .stats import _cramers_v, _significance_stars, _strength_label


def compute_cat_cat_pairs(df: pd.DataFrame, cat_cols: list[str]) -> list[dict]:
    pairs: list[dict] = []
    for i, c1 in enumerate(cat_cols):
        for j, c2 in enumerate(cat_cols):
            if i >= j:
                continue
            n_total = len(df[[c1, c2]])
            pair_data = df[[c1, c2]].dropna()
            n_used = len(pair_data)
            if n_used < 10:
                continue
            v, p = _cramers_v(pair_data[c1], pair_data[c2])
            pairs.append({
                "col_a": c1,
                "col_b": c2,
                "type": "cat_cat",
                "cramers_v": v,
                "cramers_p": p,
                "n": n_used,
                "is_significant": bool(p < 0.05 and v > 0.1),
                "strength": _strength_label(v),
                "significance_stars": _significance_stars(p),
                "rows_used": n_used,
                "rows_dropped": n_total - n_used,
                "coverage_pct": round(n_used / max(n_total, 1) * 100, 1),
            })
    return pairs
