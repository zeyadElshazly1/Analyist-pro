import pandas as pd
import numpy as np
from scipy import stats


def _bh_correct(p_values: list) -> list:
    """Benjamini-Hochberg FDR correction."""
    n = len(p_values)
    if n == 0:
        return []
    indexed = sorted(enumerate(p_values), key=lambda x: x[1])
    adjusted = [0.0] * n
    prev = 1.0
    for rank, (orig_idx, p) in enumerate(reversed(indexed), 1):
        adj = min(prev, p * n / (n - rank + 1))
        adjusted[orig_idx] = adj
        prev = adj
    return adjusted


def _strength_label(r: float) -> str:
    a = abs(r)
    if a < 0.1:
        return "Negligible"
    if a < 0.3:
        return "Weak"
    if a < 0.5:
        return "Moderate"
    if a < 0.7:
        return "Strong"
    return "Very strong"


def build_correlation_matrix(df: pd.DataFrame) -> dict:
    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    if len(numeric_cols) < 2:
        raise ValueError("Need at least 2 numeric columns for correlation analysis")

    # Limit to 20 columns for performance
    cols = numeric_cols[:20]
    sub = df[cols].dropna()

    if len(sub) < 5:
        raise ValueError("Not enough complete rows for correlation analysis")

    pearson_matrix: dict[str, dict] = {}
    spearman_matrix: dict[str, dict] = {}
    pairs = []

    for col in cols:
        pearson_matrix[col] = {}
        spearman_matrix[col] = {}

    for i, c1 in enumerate(cols):
        for j, c2 in enumerate(cols):
            pair_data = df[[c1, c2]].dropna()
            if len(pair_data) < 5:
                pearson_matrix[c1][c2] = None
                spearman_matrix[c1][c2] = None
                continue
            p_r, p_p = stats.pearsonr(pair_data[c1], pair_data[c2])
            s_r, s_p = stats.spearmanr(pair_data[c1], pair_data[c2])
            pearson_matrix[c1][c2] = round(float(p_r), 4)
            spearman_matrix[c1][c2] = round(float(s_r), 4)
            if i < j:
                pairs.append({
                    "col_a": c1,
                    "col_b": c2,
                    "pearson_r": round(float(p_r), 4),
                    "pearson_p": round(float(p_p), 6),
                    "spearman_r": round(float(s_r), 4),
                    "spearman_p": round(float(s_p), 6),
                    "n": len(pair_data),
                })

    # BH correction on Pearson p-values
    if pairs:
        pvals = [pair["pearson_p"] for pair in pairs]
        adj_pvals = _bh_correct(pvals)
        for pair, adj_p in zip(pairs, adj_pvals):
            pair["adj_p"] = round(adj_p, 6)
            # Require BOTH minimum effect size |r| > 0.3 AND statistical significance
            has_effect = abs(pair["pearson_r"]) > 0.3
            pair["is_significant"] = bool(adj_p < 0.05 and has_effect)
            pair["strength"] = _strength_label(pair["pearson_r"])
            pair["direction"] = "positive" if pair["pearson_r"] > 0 else "negative"

            # Which correlation method is more appropriate?
            # If Pearson and Spearman differ substantially, flag as non-linear
            r_diff = abs(pair["pearson_r"] - pair["spearman_r"])
            if r_diff > 0.15 and abs(pair["spearman_r"]) > abs(pair["pearson_r"]):
                pair["method_note"] = "Spearman stronger — possible monotonic non-linear relationship"
                pair["recommended_method"] = "spearman"
            else:
                pair["method_note"] = "Pearson and Spearman agree — linear relationship likely"
                pair["recommended_method"] = "pearson"

    # Sort pairs by abs Pearson r descending
    pairs.sort(key=lambda x: abs(x["pearson_r"]), reverse=True)

    # Top pairs: significant AND |r| > 0.3
    top_pairs = [p for p in pairs if p.get("is_significant", False)][:10]

    return {
        "columns": cols,
        "pearson_matrix": pearson_matrix,
        "spearman_matrix": spearman_matrix,
        "pairs": pairs,
        "top_pairs": top_pairs,
        "n_significant": len(top_pairs),
        "minimum_effect_threshold": 0.3,
        "fdr_alpha": 0.05,
    }
