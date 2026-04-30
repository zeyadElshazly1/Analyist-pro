"""
Template-based narration helpers.

Each function returns a 2–3 sentence plain-English description of the insight
shown by a chart.  The narration is attached as the ``insight`` key in every
chart payload so the frontend can display it without calling an LLM.
"""
import numpy as np
import pandas as pd


def _narrate_distribution(col: str, clean: pd.Series, skew: float) -> str:
    """Template-based 2–3 sentence narration for distribution (histogram) charts."""
    mean   = float(clean.mean())
    median = float(clean.median())
    std    = float(clean.std())
    n      = len(clean)

    if abs(skew) > 1.5:
        direction = "right" if skew > 0 else "left"
        tail_note = "high outliers pull the mean up" if skew > 0 else "low outliers pull the mean down"
        return (
            f"'{col}' is {direction}-skewed (skew={skew:.2f}), meaning {tail_note}. "
            f"The median ({median:.3g}) is a more reliable central estimate than the mean ({mean:.3g}). "
            f"Consider a log transform before using this column in linear models."
        )
    elif abs(mean - median) / (std + 1e-10) < 0.1:
        return (
            f"'{col}' follows an approximately normal distribution (n={n:,}). "
            f"Values are centered around {mean:.3g} with a spread of ±{std:.3g}. "
            f"Standard parametric tests are safe to use on this column."
        )
    else:
        return (
            f"'{col}' has mean={mean:.3g} and median={median:.3g} with std={std:.3g} (n={n:,}). "
            f"The slight difference between mean and median suggests mild asymmetry. "
            f"Review outlier values before applying statistical tests."
        )


def _narrate_timeseries(col: str, values: pd.Series, date_col: str) -> str:
    """Template-based narration for time series charts."""
    arr = pd.to_numeric(values, errors="coerce").dropna().to_numpy(dtype=float)
    if arr.size < 2:
        return (
            f"Trend of '{col}' over '{date_col}' does not have enough valid points for an automatic summary."
        )

    first_v = float(arr[0])
    last_v = float(arr[-1])
    med_abs = float(np.median(np.abs(arr[np.isfinite(arr)])))
    if med_abs <= 0 or not np.isfinite(med_abs):
        med_abs = 1e-9

    # Avoid absurd % change when the first point is zero or tiny vs typical magnitude.
    baseline = abs(first_v)
    tiny_vs_typical = baseline < 0.02 * med_abs
    if baseline <= 1e-12 or tiny_vs_typical:
        trend_note = (
            "Change over the period is easier to read from the chart than from a single headline number — "
            "percentage change from the first point is not meaningful from a near-zero baseline."
        )
    else:
        pct_change = (last_v - first_v) / baseline * 100
        if (
            not np.isfinite(pct_change)
            or abs(pct_change) > 1_000_000
            # Endpoint % change explodes for volatile series or arbitrary row order.
            or abs(pct_change) > 500
        ):
            trend_note = (
                "Relative change from the first observation is extreme or numerically unstable — "
                "use the chart levels rather than a headline percentage."
            )
        else:
            direction = "increased" if pct_change > 0 else "decreased"
            trend_note = (
                f"'{col}' has {direction} by {abs(pct_change):.1f}% between the first and last plotted points. "
            )

    # Volatility vs median magnitude (stable when the mean is near zero).
    vol_pct = round(float(np.std(arr) / med_abs * 100), 1)
    return (
        f"{trend_note}"
        f"Scale of variation is about {vol_pct:.1f}% relative to the series' median absolute level. "
        f"Examine the trend line for structural breaks or seasonality."
    )


def _narrate_scatter(
    col1: str,
    col2: str,
    pearson_r: float,
    pearson_p: float,
    spearman_rho: float | None = None,
) -> str:
    """
    Template-based narration for scatter / correlation charts.

    When spearman_rho is provided the narration uses whichever metric is
    stronger and names it explicitly so users understand the relationship type.
    """
    # Pick the stronger correlation for the narrative
    if spearman_rho is not None and abs(spearman_rho) > abs(pearson_r):
        corr   = spearman_rho
        metric = "ρ"   # Spearman
        pval   = pearson_p  # use Pearson p for significance note (conservative)
    else:
        corr   = pearson_r
        metric = "r"   # Pearson
        pval   = pearson_p

    strength = (
        "very strong" if abs(corr) > 0.9
        else "strong" if abs(corr) > 0.7
        else "moderate" if abs(corr) > 0.5
        else "weak"
    )
    direction = "positive" if corr > 0 else "negative"
    sig_note  = (
        f"statistically significant (p={pval:.4f})"
        if pval < 0.05
        else f"not statistically significant (p={pval:.4f})"
    )
    return (
        f"'{col1}' and '{col2}' show a {strength} {direction} relationship ({metric}={corr:.2f}). "
        f"This correlation is {sig_note}. "
        f"{'Consider whether this is a causal relationship or driven by a confounding variable.' if abs(corr) > 0.5 else 'The relationship is too weak to be actionable on its own.'}"
    )


def _narrate_binary(col: str, n_zero: int, n_one: int, total: int) -> str:
    """Narration for binary flag columns (0/1 encoded booleans like SeniorCitizen).

    Deliberately avoids normality, skewness, or distribution-fit language —
    none of those concepts are meaningful for a two-value flag column.
    """
    pct_one  = round(n_one  / max(total, 1) * 100, 1)
    pct_zero = round(n_zero / max(total, 1) * 100, 1)
    minority_pct = min(pct_one, pct_zero)
    balance_note = (
        "There is significant class imbalance — "
        "consider oversampling the minority class before training predictive models."
        if minority_pct < 20
        else (
            "Mild class imbalance exists; check whether it affects downstream model performance."
            if minority_pct < 35
            else "The two classes are reasonably balanced, which is favourable for analysis."
        )
    )
    return (
        f"'{col}' is a binary flag: {n_one:,} rows ({pct_one}%) have value 1 "
        f"and {n_zero:,} rows ({pct_zero}%) have value 0. "
        f"This column encodes a yes/no or true/false condition — "
        f"normality tests and continuous-distribution statistics do not apply. "
        f"{balance_note}"
    )


def _narrate_categorical(col: str, top_cat: str, top_pct: float, n_unique: int) -> str:
    """Template-based narration for categorical bar charts."""
    if top_pct > 50:
        return (
            f"'{top_cat}' dominates '{col}' with {top_pct:.1f}% of records. "
            f"This heavy concentration may introduce class imbalance in models. "
            f"Consider whether the minority categories carry meaningful signal."
        )
    else:
        return (
            f"'{col}' has {n_unique} categories; '{top_cat}' is the most frequent at {top_pct:.1f}%. "
            f"The distribution appears relatively balanced, which is favorable for analysis. "
            f"Review low-frequency categories for potential grouping or removal."
        )
