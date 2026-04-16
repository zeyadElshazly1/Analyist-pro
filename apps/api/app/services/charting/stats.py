"""
Statistical helpers for chart generation.

_pearson         — Pearson r + p-value
_spearman        — Spearman rho + p-value
_normality_badge — Shapiro-Wilk / D'Agostino badge for histogram significance
"""
import pandas as pd
from scipy import stats as scipy_stats


def _pearson(a: pd.Series, b: pd.Series) -> tuple[float, float]:
    """Return (r, p_value) for Pearson correlation. Raises on degenerate input."""
    r, p = scipy_stats.pearsonr(a, b)
    return float(r), float(p)


def _spearman(a: pd.Series, b: pd.Series) -> tuple[float, float]:
    """Return (rho, p_value) for Spearman rank correlation."""
    rho, p = scipy_stats.spearmanr(a, b)
    return float(rho), float(p)


def _normality_badge(clean: pd.Series) -> tuple[str | None, float | None]:
    """
    Test whether a numeric series departs from normality.

    Uses Shapiro-Wilk for n ≤ 5 000 and D'Agostino-Pearson for larger samples.
    Returns (badge, p_value) where badge is 'normal' | 'non-normal' | None.
    None is returned when there are fewer than 8 observations.
    """
    if len(clean) < 8:
        return None, None
    try:
        sample = clean.sample(min(len(clean), 2000), random_state=42)
        if len(sample) <= 5000:
            _, p = scipy_stats.shapiro(sample)
        else:
            _, p = scipy_stats.normaltest(sample)
        badge = "non-normal" if p < 0.05 else "normal"
        return badge, float(p)
    except Exception:
        return None, None
