"""Numeric × numeric correlation computation."""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

from .stats import _bh_correct, _significance_stars, _strength_label


def _pearson_pvalue(r: float, n: int) -> float:
    """Analytical p-value for a Pearson r, avoiding a full stats.pearsonr() call."""
    if n <= 2:
        return 1.0
    if abs(r) >= 1.0 - 1e-10:
        return 0.0
    t = r * np.sqrt((n - 2) / max(1.0 - r ** 2, 1e-10))
    return float(2 * stats.t.sf(abs(t), df=n - 2))


def compute_num_num_pairs(
    df: pd.DataFrame, num_cols: list[str]
) -> tuple[dict, dict, list[dict]]:
    """
    Returns (pearson_matrix, spearman_matrix, pairs).

    Uses pandas.DataFrame.corr() for vectorized r-values and computes p-values
    analytically. Primary method is auto-selected per pair (Pearson / Spearman /
    Kendall) based on sample size and skewness.
    """
    # Vectorized r-value matrices — pandas handles pairwise dropna internally
    pearson_df = df[num_cols].corr(method="pearson")
    spearman_df = df[num_cols].corr(method="spearman")

    # Pairwise complete-case counts via matrix multiply (no per-pair slice needed)
    notna_mat = df[num_cols].notna().to_numpy(dtype=float)
    pairwise_n_mat = (notna_mat.T @ notna_mat).astype(int)
    col_index = {col: i for i, col in enumerate(num_cols)}

    # Pre-compute per-column skewness once
    skew_cache: dict[str, float] = {
        col: abs(float(stats.skew(df[col].dropna()))) for col in num_cols
    }

    pearson_matrix: dict[str, dict] = {c: {} for c in num_cols}
    spearman_matrix: dict[str, dict] = {c: {} for c in num_cols}
    pairs: list[dict] = []

    for i, c1 in enumerate(num_cols):
        for j, c2 in enumerate(num_cols):
            if c1 == c2:
                pearson_matrix[c1][c2] = 1.0
                spearman_matrix[c1][c2] = 1.0
                continue

            p_r = float(pearson_df.loc[c1, c2])
            s_r = float(spearman_df.loc[c1, c2])
            n = int(pairwise_n_mat[col_index[c1], col_index[c2]])

            if np.isnan(p_r) or n < 5:
                pearson_matrix[c1][c2] = None
                spearman_matrix[c1][c2] = None
                continue

            pearson_matrix[c1][c2] = round(p_r, 4)
            spearman_matrix[c1][c2] = round(s_r, 4) if not np.isnan(s_r) else None

            if i >= j:
                continue

            # Per-pair data slice — needed for skewness check and Kendall
            pair_data = df[[c1, c2]].dropna()
            n_used = len(pair_data)
            n_total = len(df[[c1, c2]])

            p_p = _pearson_pvalue(p_r, n_used)
            s_p = _pearson_pvalue(s_r, n_used)  # approximation for Spearman

            # Robust method selection
            is_skewed = skew_cache[c1] > 1.0 or skew_cache[c2] > 1.0
            is_small_n = n_used < 30

            if is_small_n:
                kendall_tau, kendall_p = stats.kendalltau(
                    pair_data[c1].values, pair_data[c2].values
                )
                primary_r = round(float(kendall_tau), 4)
                primary_p = round(float(kendall_p), 6)
                recommended_method = "kendall"
                method_note = f"Kendall τ used — small sample (n={n_used})"
            elif is_skewed:
                primary_r = round(s_r, 4)
                primary_p = round(s_p, 6)
                recommended_method = "spearman"
                method_note = "Spearman used — skewed distribution detected"
            else:
                primary_r = round(p_r, 4)
                primary_p = round(p_p, 6)
                recommended_method = "pearson"
                method_note = "Pearson used — symmetric distributions"

            pairs.append({
                "col_a": c1,
                "col_b": c2,
                "type": "num_num",
                "pearson_r": round(p_r, 4),
                "pearson_p": round(p_p, 6),
                "spearman_r": round(s_r, 4) if not np.isnan(s_r) else None,
                "spearman_p": round(s_p, 6),
                "primary_r": primary_r,
                "primary_p": primary_p,
                "recommended_method": recommended_method,
                "method_note": method_note,
                "is_skewed": is_skewed,
                "is_small_n": is_small_n,
                "n": n_used,
                "rows_used": n_used,
                "rows_dropped": n_total - n_used,
                "coverage_pct": round(n_used / max(n_total, 1) * 100, 1),
            })

    # BH correction on primary p-values
    if pairs:
        adj_pvals = _bh_correct([p["primary_p"] for p in pairs])
        for pair, adj_p in zip(pairs, adj_pvals):
            has_effect = abs(pair["primary_r"]) > 0.3
            pair["adj_p"] = round(adj_p, 6)
            pair["is_significant"] = bool(adj_p < 0.05 and has_effect)
            pair["strength"] = _strength_label(pair["primary_r"])
            pair["direction"] = "positive" if pair["primary_r"] > 0 else "negative"
            pair["significance_stars"] = _significance_stars(adj_p)

    return pearson_matrix, spearman_matrix, pairs
