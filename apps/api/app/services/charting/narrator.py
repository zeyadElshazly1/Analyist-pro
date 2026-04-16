"""
Template-based narration helpers.

Each function returns a 2–3 sentence plain-English description of the insight
shown by a chart.  The narration is attached as the ``insight`` key in every
chart payload so the frontend can display it without calling an LLM.
"""
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
    pct_change = float((values.iloc[-1] - values.iloc[0]) / (abs(values.iloc[0]) + 1e-10) * 100)
    direction  = "increased" if pct_change > 0 else "decreased"
    volatility = round(float(values.std() / (abs(values.mean()) + 1e-10) * 100), 1)
    return (
        f"'{col}' has {direction} by {abs(pct_change):.1f}% over the observed period. "
        f"Volatility is {volatility:.1f}% (coefficient of variation). "
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
