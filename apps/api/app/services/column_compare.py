import pandas as pd
import numpy as np
from scipy import stats


def get_columns(df: pd.DataFrame) -> list[str]:
    return df.columns.tolist()


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

    r, p = stats.pearsonr(clean[col_a], clean[col_b])
    sr, sp = stats.spearmanr(clean[col_a], clean[col_b])

    sample = clean.sample(min(len(clean), 400), random_state=42)
    scatter = [{"x": round(float(row[col_a]), 4), "y": round(float(row[col_b]), 4)} for _, row in sample.iterrows()]

    coeffs = np.polyfit(clean[col_a], clean[col_b], 1)
    x_range = np.linspace(float(clean[col_a].min()), float(clean[col_a].max()), 50)
    regression = [{"x": round(float(x), 4), "y_hat": round(float(np.polyval(coeffs, x)), 4)} for x in x_range]

    return {
        "type": "num_num",
        "col_a": col_a,
        "col_b": col_b,
        "n": len(clean),
        "pearson_r": round(float(r), 4),
        "pearson_p": round(float(p), 6),
        "spearman_r": round(float(sr), 4),
        "spearman_p": round(float(sp), 6),
        "interpretation": (
            f"{'Strong' if abs(r) > 0.7 else 'Moderate' if abs(r) > 0.4 else 'Weak'} "
            f"{'positive' if r > 0 else 'negative'} correlation (r={r:.2f}, p={p:.4f})"
        ),
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
    arrays = []
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
        arrays.append(grp.values)

    # ANOVA
    anova_p = None
    if len(arrays) >= 2:
        _, anova_p = stats.f_oneway(*arrays)
        anova_p = round(float(anova_p), 6)

    return {
        "type": "num_cat",
        "col_a": num_col if not flipped else cat_col,
        "col_b": cat_col if not flipped else num_col,
        "num_col": num_col,
        "cat_col": cat_col,
        "n": len(clean),
        "anova_p": anova_p,
        "is_significant": bool(anova_p < 0.05) if anova_p is not None else None,
        "group_stats": group_stats,
        "box_data": box_data,
        "interpretation": (
            f"ANOVA p={anova_p:.4f} — {'significant' if anova_p < 0.05 else 'not significant'} difference across {cat_col} groups"
            if anova_p is not None else "Compare distributions across categories"
        ),
    }


def _cat_cat(df: pd.DataFrame, col_a: str, col_b: str) -> dict:
    clean = df[[col_a, col_b]].dropna()
    if len(clean) < 5:
        raise ValueError("Not enough values for comparison")

    top_a = clean[col_a].value_counts().head(8).index.tolist()
    top_b = clean[col_b].value_counts().head(8).index.tolist()
    filtered = clean[clean[col_a].isin(top_a) & clean[col_b].isin(top_b)]

    crosstab = pd.crosstab(filtered[col_a], filtered[col_b])

    # Chi-square test
    chi2_p = None
    if crosstab.shape[0] >= 2 and crosstab.shape[1] >= 2:
        try:
            _, chi2_p, _, _ = stats.chi2_contingency(crosstab)
            chi2_p = round(float(chi2_p), 6)
        except Exception:
            pass

    # Serialize crosstab
    heatmap = []
    for row_label in crosstab.index:
        for col_label in crosstab.columns:
            heatmap.append({
                "row": str(row_label),
                "col": str(col_label),
                "value": int(crosstab.loc[row_label, col_label]),
            })

    return {
        "type": "cat_cat",
        "col_a": col_a,
        "col_b": col_b,
        "n": len(filtered),
        "chi2_p": chi2_p,
        "is_significant": bool(chi2_p < 0.05) if chi2_p is not None else None,
        "row_labels": [str(x) for x in crosstab.index.tolist()],
        "col_labels": [str(x) for x in crosstab.columns.tolist()],
        "heatmap": heatmap,
        "interpretation": (
            f"Chi-square p={chi2_p:.4f} — {'significant' if chi2_p < 0.05 else 'no significant'} association between {col_a} and {col_b}"
            if chi2_p is not None else f"Crosstab of {col_a} vs {col_b}"
        ),
    }
