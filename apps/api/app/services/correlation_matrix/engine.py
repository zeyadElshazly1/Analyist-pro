"""Main correlation matrix engine."""
from __future__ import annotations

import numpy as np
import pandas as pd

from .candidates import _rank_categorical_candidates, _rank_numeric_candidates
from .cat_cat import compute_cat_cat_pairs
from .mixed import compute_mixed_pairs
from .num_num import compute_num_num_pairs
from .stats import _partial_correlation


def build_correlation_matrix(df: pd.DataFrame) -> dict:
    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    categorical_cols = [
        col
        for col in df.select_dtypes(include=["object", "category"]).columns
        if 2 <= df[col].nunique() <= 30
    ]

    if len(numeric_cols) < 2 and len(categorical_cols) < 2:
        raise ValueError(
            "Need at least 2 numeric or categorical columns for correlation analysis"
        )

    # Rank candidates by signal quality instead of taking first N
    num_cols = _rank_numeric_candidates(df, numeric_cols, max_n=20)
    cat_cols = _rank_categorical_candidates(df, categorical_cols, max_n=10)

    # Guard: need at least 5 complete rows for numeric analysis
    if len(num_cols) >= 2:
        sub = df[num_cols].dropna()
        if len(sub) < 5:
            raise ValueError(
                "Not enough complete rows for numeric correlation analysis"
            )

    # Numeric × Numeric
    if len(num_cols) >= 2:
        pearson_matrix, spearman_matrix, num_pairs = compute_num_num_pairs(df, num_cols)
    else:
        pearson_matrix = spearman_matrix = {}
        num_pairs = []

    # Partial correlations for top significant numeric triplets
    partial_corrs: list[dict] = []
    top_sig = [p for p in num_pairs if p.get("is_significant")][:5]
    for pair in top_sig:
        c1, c2 = pair["col_a"], pair["col_b"]
        for control in num_cols:
            if control in (c1, c2):
                continue
            pc = _partial_correlation(df, c1, c2, control)
            if pc is not None:
                attenuation = abs(pair["pearson_r"]) - abs(pc)
                if abs(attenuation) > 0.1:
                    partial_corrs.append({
                        "col_a": c1,
                        "col_b": c2,
                        "control": control,
                        "partial_r": pc,
                        "full_r": pair["pearson_r"],
                        "attenuation": round(attenuation, 4),
                        "note": (
                            f"r({c1},{c2}) drops from {pair['pearson_r']:.2f} to {pc:.2f} "
                            f"when controlling for {control} "
                            f"— {control} may partially explain the relationship"
                        ),
                    })
                break  # one confound per pair

    # Categorical × Categorical
    cat_pairs = compute_cat_cat_pairs(df, cat_cols) if len(cat_cols) >= 2 else []

    # Binary × Numeric
    binary_cols = [col for col in categorical_cols if df[col].nunique() == 2]
    mixed_pairs = compute_mixed_pairs(df, binary_cols, num_cols)

    # Sort by effect size descending
    num_pairs.sort(key=lambda x: abs(x.get("primary_r", 0)), reverse=True)
    cat_pairs.sort(key=lambda x: abs(x.get("cramers_v", 0)), reverse=True)
    mixed_pairs.sort(key=lambda x: abs(x.get("point_biserial_r", 0)), reverse=True)

    top_pairs = [p for p in num_pairs if p.get("is_significant")][:10]
    top_cat_pairs = [p for p in cat_pairs if p.get("is_significant")][:5]
    top_mixed_pairs = [p for p in mixed_pairs if p.get("is_significant")][:5]

    return {
        "columns": num_cols,
        "categorical_columns": cat_cols,
        "pearson_matrix": pearson_matrix,
        "spearman_matrix": spearman_matrix,
        "pairs": num_pairs,
        "categorical_pairs": cat_pairs,
        "mixed_pairs": mixed_pairs,
        "partial_correlations": partial_corrs,
        "top_pairs": top_pairs,
        "top_categorical_pairs": top_cat_pairs,
        "top_mixed_pairs": top_mixed_pairs,
        "n_significant": len(top_pairs),
        "minimum_effect_threshold": 0.3,
        "fdr_alpha": 0.05,
    }
