"""Binary × numeric correlation computation (point-biserial)."""
from __future__ import annotations

import pandas as pd

from .stats import _point_biserial, _significance_stars, _strength_label


def compute_mixed_pairs(
    df: pd.DataFrame, binary_cols: list[str], num_cols: list[str]
) -> list[dict]:
    pairs: list[dict] = []
    for bin_col in binary_cols[:5]:
        for num_col in num_cols[:10]:
            n_total = len(df[[bin_col, num_col]])
            pair_data = df[[bin_col, num_col]].dropna()
            n_used = len(pair_data)
            if n_used < 10:
                continue
            r, p = _point_biserial(pair_data[bin_col], pair_data[num_col])
            pairs.append({
                "col_a": bin_col,
                "col_b": num_col,
                "type": "binary_num",
                "point_biserial_r": r,
                "p": p,
                "n": n_used,
                "is_significant": bool(p < 0.05 and abs(r) > 0.1),
                "strength": _strength_label(r),
                "significance_stars": _significance_stars(p),
                "rows_used": n_used,
                "rows_dropped": n_total - n_used,
                "coverage_pct": round(n_used / max(n_total, 1) * 100, 1),
            })
    return pairs
