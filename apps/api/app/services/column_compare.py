import pandas as pd
import numpy as np
from scipy import stats


def get_columns(df: pd.DataFrame) -> list[str]:
    return df.columns.tolist()


def _cohens_d(a: np.ndarray, b: np.ndarray) -> float:
    """Cohen's d effect size between two groups."""
    na, nb = len(a), len(b)
    if na < 2 or nb < 2:
        return 0.0
    pooled_std = np.sqrt(((na - 1) * a.std() ** 2 + (nb - 1) * b.std() ** 2) / (na + nb - 2))
    return float((a.mean() - b.mean()) / pooled_std) if pooled_std > 1e-10 else 0.0


def _cramers_v(contingency: pd.DataFrame) -> float:
    """Cramér's V effect size for a contingency table."""
    try:
        chi2, _, _, _ = stats.chi2_contingency(contingency)
        n = contingency.values.sum()
        k = min(contingency.shape) - 1
        if n == 0 or k == 0:
            return 0.0
        return float(np.sqrt(chi2 / (n * k)))
    except Exception:
        return 0.0


def _distribution_overlap(a: np.ndarray, b: np.ndarray, n_bins: int = 50) -> float:
    """
    Overlap coefficient between two distributions (0 = no overlap, 1 = identical).
    Uses histogram intersection.
    """
    combined_min = min(a.min(), b.min())
    combined_max = max(a.max(), b.max())
    if combined_max == combined_min:
        return 1.0
    bins = np.linspace(combined_min, combined_max, n_bins + 1)
    hist_a, _ = np.histogram(a, bins=bins, density=True)
    hist_b, _ = np.histogram(b, bins=bins, density=True)
    # Normalize to sum to 1
    sum_a = hist_a.sum()
    sum_b = hist_b.sum()
    if sum_a == 0 or sum_b == 0:
        return 0.0
    hist_a = hist_a / sum_a
    hist_b = hist_b / sum_b
    return round(float(np.minimum(hist_a, hist_b).sum()), 4)


def _effect_label(d: float) -> str:
    """Cohen's d interpretation."""
    a = abs(d)
    if a < 0.2:
        return "negligible"
    if a < 0.5:
        return "small"
    if a < 0.8:
        return "medium"
    return "large"


def _cramers_label(v: float) -> str:
    if v < 0.1:
        return "negligible"
    if v < 0.3:
        return "weak"
    if v < 0.5:
        return "moderate"
    return "strong"


def compare_columns(df: pd.DataFrame, col_a: str, col_b: str) -> dict:
    if col_a not in df.columns:
        raise ValueError(f"Column '{col_a}' not found")
    if col_b not in df.columns:
        raise ValueError(f"Column '{col_b}' not found")
    if col_a == col_b:
        raise ValueError("Please select two different columns")

    a_is_numeric = pd.api.types.is_numeric_dtype(df[col_a])
    b_is_numeric = pd.api.types.is_numeric_dtype(df[col_b])

    if a_is_numeric and b_is_numeric:
        return _num_num(df, col_a, col_b)
    elif a_is_numeric and not b_is_numeric:
        return _num_cat(df, col_a, col_b)
    elif not a_is_numeric and b_is_numeric:
        return _num_cat(df, col_b, col_a, flipped=True)
    else:
        return _cat_cat(df, col_a, col_b)


def _num_num(df: pd.DataFrame, col_a: str, col_b: str) -> dict:
    clean = df[[col_a, col_b]].dropna()
    if len(clean) < 5:
        raise ValueError("Not enough paired values for comparison")

    a = clean[col_a].values
    b = clean[col_b].values

    # Pearson + Spearman
    pearson_r, pearson_p = stats.pearsonr(a, b)
    spearman_r, spearman_p = stats.spearmanr(a, b)

    # Effect size: Cohen's d (treats them as two samples)
    d = _cohens_d(a, b)
    effect = _effect_label(d)

    # Distribution overlap
    overlap = _distribution_overlap(a, b)

    # Regression line
    coeffs = np.polyfit(a, b, 1)
    x_range = np.linspace(float(clean[col_a].min()), float(clean[col_a].max()), 50)
    regression = [{"x": round(float(x), 4), "y_hat": round(float(np.polyval(coeffs, x)), 4)} for x in x_range]

    # Scatter sample (flag anomalies beyond 2σ residual)
    sample = clean.sample(min(len(clean), 400), random_state=42)
    predicted = np.polyval(coeffs, sample[col_a].values)
    residuals = sample[col_b].values - predicted
    resid_std = float(np.std(residuals))
    scatter = [
        {
            "x": round(float(row[col_a]), 4),
            "y": round(float(row[col_b]), 4),
            "is_anomaly": bool(abs(residuals[i]) > 2 * resid_std),
        }
        for i, (_, row) in enumerate(sample.iterrows())
    ]

    strength = "strong" if abs(pearson_r) > 0.7 else "moderate" if abs(pearson_r) > 0.4 else "weak"
    direction = "positive" if pearson_r > 0 else "negative"
    sig_text = "statistically significant" if pearson_p < 0.05 else "not statistically significant"

    interpretation = (
        f"Pearson r={pearson_r:.2f} ({strength} {direction} correlation, {sig_text}, p={pearson_p:.4f}). "
        f"Effect size: Cohen's d={d:.2f} ({effect}). "
        f"Distribution overlap: {overlap * 100:.0f}% — "
        f"{'the two columns have very similar distributions' if overlap > 0.7 else 'the distributions diverge substantially' if overlap < 0.3 else 'moderate overlap between distributions'}."
    )

    return {
        "type": "num_num",
        "col_a": col_a,
        "col_b": col_b,
        "n": len(clean),
        "pearson_r": round(float(pearson_r), 4),
        "pearson_p": round(float(pearson_p), 6),
        "spearman_r": round(float(spearman_r), 4),
        "spearman_p": round(float(spearman_p), 6),
        "cohens_d": round(d, 4),
        "effect_size": effect,
        "distribution_overlap": overlap,
        "interpretation": interpretation,
        "scatter": scatter,
        "regression_line": regression,
        "slope": round(float(coeffs[0]), 4),
        "intercept": round(float(coeffs[1]), 4),
    }


def _num_cat(df: pd.DataFrame, num_col: str, cat_col: str, flipped: bool = False) -> dict:
    clean = df[[num_col, cat_col]].dropna()
    if len(clean) < 5:
        raise ValueError("Not enough values for comparison")

    top_cats = clean[cat_col].value_counts().head(10).index.tolist()
    clean = clean[clean[cat_col].isin(top_cats)]

    group_stats = []
    box_data = []
    arrays = {}
    for cat in top_cats:
        grp = clean[clean[cat_col] == cat][num_col].dropna()
        if len(grp) < 2:
            continue
        q1, q3 = float(grp.quantile(0.25)), float(grp.quantile(0.75))
        group_stats.append({
            "category": str(cat),
            "count": len(grp),
            "mean": round(float(grp.mean()), 4),
            "median": round(float(grp.median()), 4),
            "std": round(float(grp.std()), 4),
            "min": round(float(grp.min()), 4),
            "max": round(float(grp.max()), 4),
            "q1": round(q1, 4),
            "q3": round(q3, 4),
        })
        box_data.append({
            "category": str(cat),
            "q1": round(q1, 4),
            "median": round(float(grp.median()), 4),
            "q3": round(q3, 4),
            "min": round(float(grp.min()), 4),
            "max": round(float(grp.max()), 4),
        })
        arrays[str(cat)] = grp.values

    array_list = list(arrays.values())

    # Choose test based on number of groups and normality
    test_used = "none"
    test_p = None
    effect_size = None
    effect_label_str = None
    pairwise = []

    if len(array_list) == 2:
        a, b = array_list[0], array_list[1]
        # Welch's t-test (no equal-variance assumption)
        _, welch_p = stats.ttest_ind(a, b, equal_var=False)
        test_p = round(float(welch_p), 6)
        test_used = "Welch's t-test"
        d = _cohens_d(a, b)
        effect_size = round(abs(d), 4)
        effect_label_str = _effect_label(d)
        # Mann-Whitney U as non-parametric alternative
        try:
            _, mw_p = stats.mannwhitneyu(a, b, alternative="two-sided")
            pairwise.append({"test": "Mann-Whitney U", "p": round(float(mw_p), 6)})
        except Exception:
            pass

    elif len(array_list) >= 3:
        _, anova_p = stats.f_oneway(*array_list)
        test_p = round(float(anova_p), 6)
        test_used = "one-way ANOVA"
        # Eta squared as effect size
        grand_mean = np.concatenate(array_list).mean()
        ss_between = sum(len(g) * (g.mean() - grand_mean) ** 2 for g in array_list)
        ss_total = sum(((v - grand_mean) ** 2) for g in array_list for v in g)
        eta2 = ss_between / ss_total if ss_total > 0 else 0.0
        effect_size = round(float(eta2), 4)
        effect_label_str = "large" if eta2 > 0.14 else "medium" if eta2 > 0.06 else "small"

        # Pairwise Welch t-tests
        cats = list(arrays.keys())
        for i in range(len(cats)):
            for j in range(i + 1, len(cats)):
                try:
                    _, pw_p = stats.ttest_ind(arrays[cats[i]], arrays[cats[j]], equal_var=False)
                    d = _cohens_d(arrays[cats[i]], arrays[cats[j]])
                    pairwise.append({
                        "group_a": cats[i],
                        "group_b": cats[j],
                        "p": round(float(pw_p), 4),
                        "cohens_d": round(abs(d), 4),
                        "significant": bool(pw_p < 0.05),
                    })
                except Exception:
                    pass

    is_significant = bool(test_p < 0.05) if test_p is not None else None
    p_text = f"p={test_p:.4f}" if test_p is not None else "p=N/A"

    interpretation = (
        f"{test_used} {p_text} — "
        f"{'statistically significant' if is_significant else 'no significant'} difference across {cat_col} groups. "
        + (f"Effect size: η²={effect_size:.2f} ({effect_label_str})." if effect_size is not None and test_used != "Welch's t-test" else "")
        + (f"Cohen's d={effect_size:.2f} ({effect_label_str}) — the practical difference is {effect_label_str}." if test_used == "Welch's t-test" and effect_size is not None else "")
    )

    return {
        "type": "num_cat",
        "col_a": num_col if not flipped else cat_col,
        "col_b": cat_col if not flipped else num_col,
        "num_col": num_col,
        "cat_col": cat_col,
        "n": len(clean),
        "test_used": test_used,
        "test_p": test_p,
        "is_significant": is_significant,
        "effect_size": effect_size,
        "effect_label": effect_label_str,
        "group_stats": group_stats,
        "box_data": box_data,
        "pairwise_tests": pairwise[:15],
        "interpretation": interpretation,
    }


def _cat_cat(df: pd.DataFrame, col_a: str, col_b: str) -> dict:
    clean = df[[col_a, col_b]].dropna()
    if len(clean) < 5:
        raise ValueError("Not enough values for comparison")

    top_a = clean[col_a].value_counts().head(8).index.tolist()
    top_b = clean[col_b].value_counts().head(8).index.tolist()
    filtered = clean[clean[col_a].isin(top_a) & clean[col_b].isin(top_b)]

    crosstab = pd.crosstab(filtered[col_a], filtered[col_b])

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

    # Row percentages for the heatmap
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
        f"Chi-square p={chi2_p:.4f} — {'significant' if is_significant else 'no significant'} association between {col_a} and {col_b}. "
        f"Cramér's V={cramers:.2f} ({cramers_label} association) — "
        f"{'the two categories are meaningfully related' if cramers > 0.3 else 'the association is weak and may not be actionable'}."
        if chi2_p is not None else f"Crosstab of {col_a} vs {col_b}"
    )

    return {
        "type": "cat_cat",
        "col_a": col_a,
        "col_b": col_b,
        "n": len(filtered),
        "chi2_p": chi2_p,
        "cramers_v": round(cramers, 4),
        "cramers_label": cramers_label,
        "is_significant": is_significant,
        "row_labels": [str(x) for x in crosstab.index.tolist()],
        "col_labels": [str(x) for x in crosstab.columns.tolist()],
        "heatmap": heatmap,
        "interpretation": interpretation,
    }
