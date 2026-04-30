"""
Segment gap detectors.

detect_segment_gaps: Welch's t-test + Cohen's d to find numeric gaps between
    categorical groups. Capped at MAX_SEG_CATS × MAX_SEG_NUMS pairs.

detect_binary_rates: Chi-square rate analysis for binary categorical targets.
    BUG FIX: positive class is the least-frequent value (stable across runs),
    not vals[0] (non-deterministic .unique() ordering).
"""
import re as _re

import numpy as np
import pandas as pd
from scipy import stats

from .stats_helpers import _cohens_d
from .budget import MAX_SEG_CATS, MAX_SEG_NUMS, MAX_BINARY_RATE_CATS


# Keywords whose presence in a column name (as a full token) signals that it is
# a business-outcome / classification target.  Rate-gap insights linking a
# predictor to such a column receive the target-driver priority boost in the
# ranker; insights linking to other binary columns (e.g. gender, partner) do not.
_OUTCOME_KEYWORDS: frozenset[str] = frozenset({
    "churn", "fraud", "default", "conversion", "convert", "click",
    "purchase", "buy", "leave", "exit", "cancel", "resign", "subscribe",
    "attrition", "retention", "outcome", "target", "response", "label",
    "churned", "converted", "defaulted", "lapsed",
})


def _is_outcome_col(col_name: str) -> bool:
    """True when a column name looks like a business-outcome / classification target.

    Uses token-based matching (splits on underscores / spaces) so that
    'churn' matches 'churn' and 'customer_churn' but NOT 'church'.
    """
    tokens = set(_re.split(r"[_\s]+", col_name.lower()))
    return bool(tokens & _OUTCOME_KEYWORDS)


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

    Scoring uses absolute rate difference (ARD) as the primary signal:
    - Severity: "high"   if ARD ≥ 25 pp  OR  rate ratio ≥ 5×
                "medium" otherwise
    - Confidence: weighted blend of ARD, ratio, and per-group support.
    - Threshold: keep when ARD ≥ 10 pp  OR  ratio > 1.5 (whichever fires first).
      Using ARD as primary guard means a 45% vs 15% gap (30 pp, ratio 3×) is
      always surfaced even when the ratio alone would be borderline.

    All rate-gap insights carry ``is_target_driver=True`` so the ranking layer
    can apply a priority boost relative to non-targeted pattern detectors.
    """
    binary_cols = [col for col in categorical_cols if df[col].nunique() == 2]
    insights: list[dict] = []

    for target_col in binary_cols:
        vals = df[target_col].dropna().unique()
        if len(vals) != 2:
            continue

        # BUG FIX: use least-frequent value as positive class for determinism
        pos_class = df[target_col].value_counts().index[-1]

        # For recognised business-outcome targets (churn, fraud, conversion, etc.)
        # we use the wider budget so that all potential predictors (e.g. Contract,
        # PaymentMethod) are discovered even in wide datasets.
        # For non-outcome binary columns (gender, partner, etc.) we keep the
        # narrower MAX_SEG_CATS budget to avoid flooding the top-N ranked list
        # with demographic cross-correlations that are rarely actionable.
        col_budget = MAX_BINARY_RATE_CATS if _is_outcome_col(target_col) else MAX_SEG_CATS
        for cat_col in categorical_cols[:col_budget]:
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
            abs_rate_diff = float(rates[max_group] - rates[min_group])

            # Primary filter: absolute rate difference must be meaningful
            # (≥ 10 percentage-points) OR the ratio must be large.
            # This replaces the old "if min == 0: skip" guard that was
            # discarding genuine 50%-vs-0% findings.
            min_rate = float(rates[min_group])
            # Safe ratio — cap at 99 to avoid infinity, handle zero-min groups
            ratio = min(float(rates[max_group]) / max(min_rate, 0.01), 99.0)

            if abs_rate_diff < 0.10 and ratio <= 1.5:
                continue

            # Severity: driven by absolute gap (directly interpretable) rather
            # than relative ratio, which amplifies small-base noise.
            severity = "high" if abs_rate_diff >= 0.25 or ratio >= 5 else "medium"

            # Confidence: rewards large absolute gaps, sizable ratios, and
            # well-populated groups (support saturation at n=200 per group).
            min_group_support = int(group_sizes[group_sizes >= 20].min())
            support_factor = min(1.0, min_group_support / 200)
            confidence = round(
                min(95, 45 + abs_rate_diff * 160 + min(ratio, 10) * 2 + support_factor * 8),
                1,
            )

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
                "severity": severity,
                "confidence": confidence,
                "title": f"Rate gap: {cat_col} → {target_col}",
                "finding": (
                    f"'{max_group}' has {abs_rate_diff:.1%} higher '{pos_class}' rate "
                    f"than '{min_group}' "
                    f"({rates[max_group]:.1%} vs {rates[min_group]:.1%}, "
                    f"{ratio:.1f}× lift)."
                ),
                "evidence": (
                    f"Absolute rate gap={abs_rate_diff:.1%}, ratio={ratio:.2f}× "
                    f"across {len(rates)} segments "
                    f"(min 20 rows per group{evidence_p})"
                ),
                "action": (
                    f"'{max_group}' in '{cat_col}' shows a {abs_rate_diff:.1%} higher "
                    f"'{pos_class}' rate than '{min_group}' — "
                    f"consider treating '{cat_col}' as a priority lever for '{target_col}'."
                ),
                # True only when target_col is a recognised business-outcome column
                # (churn, fraud, conversion, etc.).  Arbitrary binary columns like
                # gender or partner are NOT flagged as targets so they don't crowd
                # out genuine churn/fraud drivers in the top-N ranked insights.
                "is_target_driver": _is_outcome_col(target_col),
            })
    return insights
