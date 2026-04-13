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


def _significance_stars(p: float) -> str:
    if p < 0.001:
        return "***"
    if p < 0.01:
        return "**"
    if p < 0.05:
        return "*"
    return "ns"


def _cramers_v(series_a: pd.Series, series_b: pd.Series) -> tuple[float, float]:
    """Cramér's V and chi-square p-value for two categorical columns."""
    try:
        ct = pd.crosstab(series_a, series_b)
        if ct.shape[0] < 2 or ct.shape[1] < 2:
            return 0.0, 1.0
        chi2, p, _, _ = stats.chi2_contingency(ct)
        n = ct.values.sum()
        k = min(ct.shape) - 1
        v = float(np.sqrt(chi2 / (n * k))) if n > 0 and k > 0 else 0.0
        return round(v, 4), round(float(p), 6)
    except Exception:
        return 0.0, 1.0


def _point_biserial(binary_series: pd.Series, numeric_series: pd.Series) -> tuple[float, float]:
    """Point-biserial correlation between a binary and a continuous column."""
    try:
        combined = pd.DataFrame({"b": binary_series, "n": numeric_series}).dropna()
        binary_encoded = pd.factorize(combined["b"])[0].astype(float)
        r, p = stats.pointbiserialr(binary_encoded, combined["n"].values)
        return round(float(r), 4), round(float(p), 6)
    except Exception:
        return 0.0, 1.0


def _partial_correlation(df: pd.DataFrame, col_a: str, col_b: str, control_col: str) -> float | None:
    """Pearson partial correlation of col_a and col_b controlling for control_col."""
    try:
        sub = df[[col_a, col_b, control_col]].dropna()
        if len(sub) < 10:
            return None
        # Residualize both columns on the control
        def _residualize(y: np.ndarray, x: np.ndarray) -> np.ndarray:
            if np.std(x) < 1e-10:
                return y  # can't residualize on a constant
            coeffs = np.polyfit(x, y, 1)
            return y - np.polyval(coeffs, x)

        res_a = _residualize(sub[col_a].values, sub[control_col].values)
        res_b = _residualize(sub[col_b].values, sub[control_col].values)
        r, _ = stats.pearsonr(res_a, res_b)
        return round(float(r), 4)
    except Exception:
        return None


def build_correlation_matrix(df: pd.DataFrame) -> dict:
    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    categorical_cols = [
        col for col in df.select_dtypes(include=["object", "category"]).columns
        if 2 <= df[col].nunique() <= 30
    ]

    if len(numeric_cols) < 2 and len(categorical_cols) < 2:
        raise ValueError("Need at least 2 numeric or categorical columns for correlation analysis")

    # Limit columns for performance
    num_cols = numeric_cols[:20]
    cat_cols = categorical_cols[:10]

    # ── Numeric × Numeric: Pearson + Spearman ────────────────────────────────
    sub = df[num_cols].dropna()
    if len(sub) < 5 and len(num_cols) >= 2:
        raise ValueError("Not enough complete rows for numeric correlation analysis")

    pearson_matrix: dict[str, dict] = {c: {} for c in num_cols}
    spearman_matrix: dict[str, dict] = {c: {} for c in num_cols}
    num_pairs = []

    for i, c1 in enumerate(num_cols):
        for j, c2 in enumerate(num_cols):
            if c1 == c2:
                pearson_matrix[c1][c2] = 1.0
                spearman_matrix[c1][c2] = 1.0
                continue
            pair_data = df[[c1, c2]].dropna()
            if len(pair_data) < 5:
                pearson_matrix[c1][c2] = None
                spearman_matrix[c1][c2] = None
                continue
            # Skip constant columns — correlations are undefined
            if pair_data[c1].std() < 1e-10 or pair_data[c2].std() < 1e-10:
                pearson_matrix[c1][c2] = None
                spearman_matrix[c1][c2] = None
                continue
            try:
                p_r, p_p = stats.pearsonr(pair_data[c1].values, pair_data[c2].values)
                p_r, p_p = float(np.asarray(p_r).flat[0]), float(np.asarray(p_p).flat[0])
            except Exception:
                pearson_matrix[c1][c2] = None
                spearman_matrix[c1][c2] = None
                continue
            try:
                spear = stats.spearmanr(pair_data[c1].values, pair_data[c2].values)
                # scipy >= 1.9 returns SpearmanrResult; older returns (r, p) tuple
                s_r = float(np.asarray(getattr(spear, "statistic", spear[0])).flat[0])
                s_p = float(np.asarray(getattr(spear, "pvalue", spear[1])).flat[0])
            except Exception:
                s_r, s_p = p_r, p_p  # fall back to Pearson values
            pearson_matrix[c1][c2] = round(p_r, 4)
            spearman_matrix[c1][c2] = round(s_r, 4)
            if i < j:
                num_pairs.append({
                    "col_a": c1,
                    "col_b": c2,
                    "type": "num_num",
                    "pearson_r": round(p_r, 4),
                    "pearson_p": round(p_p, 6),
                    "spearman_r": round(s_r, 4),
                    "spearman_p": round(s_p, 6),
                    "n": len(pair_data),
                })

    # BH correction on Pearson p-values
    if num_pairs:
        pvals = [pair["pearson_p"] for pair in num_pairs]
        adj_pvals = _bh_correct(pvals)
        for pair, adj_p in zip(num_pairs, adj_pvals):
            pair["adj_p"] = round(adj_p, 6)
            # Require minimum effect size |r| > 0.3 AND BH-corrected significance
            has_effect = abs(pair["pearson_r"]) > 0.3
            pair["is_significant"] = bool(adj_p < 0.05 and has_effect)
            pair["strength"] = _strength_label(pair["pearson_r"])
            pair["direction"] = "positive" if pair["pearson_r"] > 0 else "negative"
            pair["significance_stars"] = _significance_stars(adj_p)

            # Recommend Pearson vs Spearman
            r_diff = abs(pair["pearson_r"] - pair["spearman_r"])
            if r_diff > 0.15 and abs(pair["spearman_r"]) > abs(pair["pearson_r"]):
                pair["method_note"] = "Spearman stronger — possible non-linear monotonic relationship"
                pair["recommended_method"] = "spearman"
            else:
                pair["method_note"] = "Pearson and Spearman agree — linear relationship likely"
                pair["recommended_method"] = "pearson"

    # ── Partial correlations for top numeric triplets ─────────────────────────
    partial_corrs = []
    top_num = [p for p in num_pairs if p.get("is_significant")][:5]
    for pair in top_num:
        c1, c2 = pair["col_a"], pair["col_b"]
        # Find strongest confound
        for control in num_cols:
            if control == c1 or control == c2:
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
                            f"r({c1},{c2}) drops from {pair['pearson_r']:.2f} to {pc:.2f} when controlling for {control} "
                            f"— {control} may partially explain the relationship"
                        ),
                    })
                break  # one confound per pair for conciseness

    # ── Categorical × Categorical: Cramér's V ────────────────────────────────
    cat_pairs = []
    for i, c1 in enumerate(cat_cols):
        for j, c2 in enumerate(cat_cols):
            if i >= j:
                continue
            pair_data = df[[c1, c2]].dropna()
            if len(pair_data) < 10:
                continue
            v, p = _cramers_v(pair_data[c1], pair_data[c2])
            cat_pairs.append({
                "col_a": c1,
                "col_b": c2,
                "type": "cat_cat",
                "cramers_v": v,
                "cramers_p": p,
                "n": len(pair_data),
                "is_significant": bool(p < 0.05 and v > 0.1),
                "strength": _strength_label(v),
                "significance_stars": _significance_stars(p),
            })

    # ── Binary (2-value) × Numeric: Point-biserial ───────────────────────────
    binary_cols = [col for col in categorical_cols if df[col].nunique() == 2]
    mixed_pairs = []
    for bin_col in binary_cols[:5]:
        for num_col in num_cols[:10]:
            pair_data = df[[bin_col, num_col]].dropna()
            if len(pair_data) < 10:
                continue
            r, p = _point_biserial(pair_data[bin_col], pair_data[num_col])
            mixed_pairs.append({
                "col_a": bin_col,
                "col_b": num_col,
                "type": "binary_num",
                "point_biserial_r": r,
                "p": p,
                "n": len(pair_data),
                "is_significant": bool(p < 0.05 and abs(r) > 0.1),
                "strength": _strength_label(r),
                "significance_stars": _significance_stars(p),
            })

    # Sort by effect size descending
    num_pairs.sort(key=lambda x: abs(x.get("pearson_r", 0)), reverse=True)
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
