"""Numeric vs categorical column comparison."""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

from .stats import _cohens_d, _effect_label, _bh_correction


def compare_num_cat(
    df: pd.DataFrame, num_col: str, cat_col: str, flipped: bool = False
) -> dict:
    n_total = len(df[[num_col, cat_col]])
    clean = df[[num_col, cat_col]].dropna()
    n_used_pre = len(clean)

    top_cats = clean[cat_col].value_counts().head(10).index.tolist()
    clean = clean[clean[cat_col].isin(top_cats)]
    n_used = len(clean)

    if n_used < 5:
        raise ValueError("Not enough values for comparison")

    sample_loss = {
        "n_total": n_total,
        "n_used": n_used,
        "n_dropped": n_total - n_used,
        "pct_dropped": round((n_total - n_used) / max(n_total, 1) * 100, 1),
    }

    group_stats = []
    box_data = []
    arrays: dict[str, np.ndarray] = {}

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
        arrays[str(cat)] = grp.to_numpy(dtype=float)

    array_list = list(arrays.values())

    test_used = "none"
    test_p = None
    effect_size = None
    effect_label_str = None
    pairwise: list[dict] = []

    if len(array_list) == 2:
        a, b = array_list[0], array_list[1]
        _, welch_p = stats.ttest_ind(a, b, equal_var=False)
        test_p = round(float(welch_p), 6)
        test_used = "Welch's t-test"
        d = _cohens_d(a, b)
        effect_size = round(abs(d), 4)
        effect_label_str = _effect_label(d)
        try:
            _, mw_p = stats.mannwhitneyu(a, b, alternative="two-sided")
            pairwise.append({"test": "Mann-Whitney U", "p": round(float(mw_p), 6)})
        except Exception:
            pass

    elif len(array_list) >= 3:
        _, anova_p = stats.f_oneway(*array_list)
        test_p = round(float(anova_p), 6)
        test_used = "one-way ANOVA"
        grand_mean = np.concatenate(array_list).mean()
        ss_between = sum(len(g) * (g.mean() - grand_mean) ** 2 for g in array_list)
        ss_total = sum(((v - grand_mean) ** 2) for g in array_list for v in g)
        eta2 = ss_between / ss_total if ss_total > 0 else 0.0
        effect_size = round(float(eta2), 4)
        effect_label_str = "large" if eta2 > 0.14 else "medium" if eta2 > 0.06 else "small"

        cats = list(arrays.keys())
        raw_pairwise: list[dict] = []
        for i in range(len(cats)):
            for j in range(i + 1, len(cats)):
                try:
                    _, pw_p = stats.ttest_ind(arrays[cats[i]], arrays[cats[j]], equal_var=False)
                    d = _cohens_d(arrays[cats[i]], arrays[cats[j]])
                    raw_pairwise.append({
                        "group_a": cats[i],
                        "group_b": cats[j],
                        "p": round(float(pw_p), 4),
                        "cohens_d": round(abs(d), 4),
                        "significant": bool(pw_p < 0.05),
                    })
                except Exception:
                    pass

        # BH FDR correction on all pairwise p-values
        if raw_pairwise:
            raw_ps = [pw["p"] for pw in raw_pairwise]
            adj_ps = _bh_correction(raw_ps)
            for pw, adj_p in zip(raw_pairwise, adj_ps):
                pw["adjusted_p"] = adj_p
                pw["significant_adjusted"] = bool(adj_p < 0.05)

        pairwise = raw_pairwise

    is_significant = bool(test_p < 0.05) if test_p is not None else None
    p_text = f"p={test_p:.4f}" if test_p is not None else "p=N/A"

    interpretation = (
        f"{test_used} {p_text} — "
        f"{'statistically significant' if is_significant else 'no significant'} difference across {cat_col} groups. "
        + (
            f"Effect size: η²={effect_size:.2f} ({effect_label_str})."
            if effect_size is not None and test_used != "Welch's t-test"
            else ""
        )
        + (
            f"Cohen's d={effect_size:.2f} ({effect_label_str}) — the practical difference is {effect_label_str}."
            if test_used == "Welch's t-test" and effect_size is not None
            else ""
        )
    )

    return {
        "type": "num_cat",
        "col_a": num_col if not flipped else cat_col,
        "col_b": cat_col if not flipped else num_col,
        "num_col": num_col,
        "cat_col": cat_col,
        "n": n_used,
        "test_used": test_used,
        "test_p": test_p,
        "is_significant": is_significant,
        "effect_size": effect_size,
        "effect_label": effect_label_str,
        "group_stats": group_stats,
        "box_data": box_data,
        "pairwise_tests": pairwise[:15],
        "interpretation": interpretation,
        "sample_loss": sample_loss,
    }
