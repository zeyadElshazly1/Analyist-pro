"""Shared statistical helpers for the correlation_matrix package."""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats


def _bh_correct(p_values: list[float]) -> list[float]:
    """Benjamini-Hochberg FDR correction. Returns adjusted p-values in input order."""
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


def _point_biserial(
    binary_series: pd.Series, numeric_series: pd.Series
) -> tuple[float, float]:
    """Point-biserial correlation between a binary and a continuous column."""
    try:
        combined = pd.DataFrame({"b": binary_series, "n": numeric_series}).dropna()
        binary_encoded = pd.factorize(combined["b"])[0].astype(float)
        r, p = stats.pointbiserialr(binary_encoded, combined["n"].values)
        return round(float(r), 4), round(float(p), 6)
    except Exception:
        return 0.0, 1.0


def _partial_correlation(
    df: pd.DataFrame, col_a: str, col_b: str, control_col: str
) -> float | None:
    """Pearson partial correlation of col_a and col_b controlling for control_col."""
    try:
        sub = df[[col_a, col_b, control_col]].dropna()
        if len(sub) < 10:
            return None

        def _residualize(y: np.ndarray, x: np.ndarray) -> np.ndarray:
            if np.std(x) < 1e-10:
                return y
            coeffs = np.polyfit(x, y, 1)
            return y - np.polyval(coeffs, x)

        res_a = _residualize(sub[col_a].values, sub[control_col].values)
        res_b = _residualize(sub[col_b].values, sub[control_col].values)
        r, _ = stats.pearsonr(res_a, res_b)
        return round(float(r), 4)
    except Exception:
        return None
