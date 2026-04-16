"""
Statistical helper functions shared across detectors.

Benjamini-Hochberg correction, normality testing, and Cohen's d.
"""
import numpy as np
import pandas as pd
from scipy import stats


def _bh_correct(p_values: list[float]) -> list[float]:
    """Benjamini-Hochberg FDR correction for multiple comparisons."""
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


def _normality_test(series: pd.Series) -> bool:
    """Return True if series appears normally distributed (Shapiro-Wilk or Jarque-Bera)."""
    clean = series.dropna()
    if len(clean) < 8:
        return True
    try:
        if len(clean) <= 5000:
            _, p = stats.shapiro(clean.sample(min(len(clean), 2000), random_state=42))
        else:
            _, p = stats.normaltest(clean)
        return bool(p > 0.05)
    except Exception:
        return True


def _cohens_d(group_a: np.ndarray, group_b: np.ndarray) -> float:
    """Pooled Cohen's d effect size between two groups."""
    na, nb = len(group_a), len(group_b)
    if na < 2 or nb < 2:
        return 0.0
    pooled_std = np.sqrt(
        ((na - 1) * group_a.std() ** 2 + (nb - 1) * group_b.std() ** 2) / (na + nb - 2)
    )
    return float((group_a.mean() - group_b.mean()) / pooled_std) if pooled_std > 1e-10 else 0.0
