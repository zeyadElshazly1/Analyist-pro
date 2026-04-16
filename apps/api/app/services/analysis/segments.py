"""
Segment gap detectors.

detect_segment_gaps: Welch's t-test + Cohen's d to find numeric gaps between
    categorical groups. Capped at MAX_SEG_CATS × MAX_SEG_NUMS pairs.

detect_binary_rates: Chi-square rate analysis for binary categorical targets.
    BUG FIX: positive class is the least-frequent value (stable across runs),
    not vals[0] (non-deterministic .unique() ordering).
"""
import numpy as np
import pandas as pd
from scipy import stats

from .stats_helpers import _cohens_d
from .budget import MAX_SEG_CATS, MAX_SEG_NUMS


def detect_segment_gaps(
    df: pd.DataFrame,
    categorical_cols: list[str],
    numeric_cols: list[str],
) -> list[dict]:
    """
    For each (cat_col, num_col) pair, check whether groups differ significantly.
    Only pairs where at least two groups each have ≥ 30 rows are tested.
    """
    insights: list[dict] = []
    for cat_col in categorical_cols[:MAX_SEG_CATS]:
        for num_col in numeric_cols[:MAX_SEG_NUMS]:
            group_data = {
                name: grp.dropna().values
                for name, grp in df.groupby(cat_col)[num_col]
            }
            valid_groups = {k: v for k, v in group_data.items() if len(v) >= 30}
            if len(valid_groups) < 2:
                continue
            group_means = {k: np.mean(v) for k, v in valid_groups.items()}
            max_group = max(group_means, key=group_means.get)
            min_group = min(group_means, key=group_means.get)
            if group_means[min_group] == 0:
                continue
            ratio = group_means[max_group] / group_means[min_group]
            if ratio <= 1.5:
                continue
            _, welch_p = stats.ttest_ind(
                valid_groups[max_group], valid_groups[min_group], equal_var=False
            )
            if welch_p >= 0.05:
                continue
            d = _cohens_d(valid_groups[max_group], valid_groups[min_group])
            effect_label = "large" if abs(d) >= 0.8 else "medium" if abs(d) >= 0.5 else "small"
            severity = "high" if ratio > 3 and abs(d) >= 0.5 else "medium"
            insights.append({
                "type": "segment",
                "severity": severity,
                "confidence": round(min(95, 55 + ratio * 4), 1),
                "title": f"Segment gap: {cat_col} → {num_col}",
                "finding": (
                    f"'{max_group}' has {ratio:.1f}x higher average {num_col} than '{min_group}' "
                    f"({group_means[max_group]:.2f} vs {group_means[min_group]:.2f})."
                ),
                "evidence": (
                    f"Welch's t-test p={welch_p:.4f}, Cohen's d={d:.2f} ({effect_label} effect), "
                    f"ratio={ratio:.2f}x, groups n={len(valid_groups[max_group])}/{len(valid_groups[min_group])}"
                ),
                "action": (
                    f"Prioritize or investigate '{max_group}' in '{cat_col}' — "
                    f"it significantly outperforms '{min_group}' on {num_col} "
                    f"with a {effect_label} effect size."
                ),
            })
    return insights


def detect_binary_rates(
    df: pd.DataFrame,
    categorical_cols: list[str],
) -> list[dict]:
    """
    For binary categorical targets, compare positive-class rates across
    grouping columns using chi-square test.

    Positive class = least-frequent value (stable, deterministic).
    """
    binary_cols = [col for col in categorical_cols if df[col].nunique() == 2]
    insights: list[dict] = []

    for target_col in binary_cols:
        vals = df[target_col].dropna().unique()
        if len(vals) != 2:
            continue

        # BUG FIX: use least-frequent value as positive class for determinism
        pos_class = df[target_col].value_counts().index[-1]

        for cat_col in categorical_cols[:MAX_SEG_CATS]:
            if cat_col == target_col or df[cat_col].nunique() < 2:
                continue
            group_sizes = df.groupby(cat_col)[target_col].count()
            large_groups = group_sizes[group_sizes >= 20].index
            rates = (
                df[df[cat_col].isin(large_groups)]
                .groupby(cat_col)[target_col]
                .apply(lambda x: (x == pos_class).mean())
                .dropna()
            )
            if len(rates) < 2:
                continue
            max_group, min_group = rates.idxmax(), rates.idxmin()
            if rates[min_group] == 0:
                continue
            ratio = rates[max_group] / rates[min_group]
            if ratio <= 1.8:
                continue

            evidence_p = ""
            try:
                from scipy.stats import chi2_contingency
                ct = pd.crosstab(
                    df.loc[df[cat_col].isin(large_groups), cat_col],
                    df.loc[df[cat_col].isin(large_groups), target_col],
                )
                chi2_val, chi2_p, _, _ = chi2_contingency(ct)
                evidence_p = f", χ²={chi2_val:.2f}, p={chi2_p:.4f}"
            except Exception:
                pass

            insights.append({
                "type": "segment",
                "severity": "high" if ratio > 4 else "medium",
                "confidence": round(min(95, 55 + ratio * 5), 1),
                "title": f"Rate gap: {cat_col} → {target_col}",
                "finding": (
                    f"'{max_group}' has {ratio:.1f}x higher '{pos_class}' rate than '{min_group}' "
                    f"({rates[max_group]:.1%} vs {rates[min_group]:.1%})."
                ),
                "evidence": (
                    f"Rate ratio={ratio:.2f}x across {len(rates)} segments "
                    f"(min 20 rows per group{evidence_p})"
                ),
                "action": (
                    f"'{max_group}' in '{cat_col}' shows dramatically different "
                    f"'{target_col}' behavior — consider targeting it separately."
                ),
            })
    return insights
