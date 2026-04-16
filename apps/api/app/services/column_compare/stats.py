"""Shared statistical helpers for column_compare sub-modules."""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats


def _cohens_d(a: np.ndarray, b: np.ndarray) -> float:
    na, nb = len(a), len(b)
    if na < 2 or nb < 2:
        return 0.0
    pooled_std = np.sqrt(
        ((na - 1) * a.std() ** 2 + (nb - 1) * b.std() ** 2) / (na + nb - 2)
    )
    return float((a.mean() - b.mean()) / pooled_std) if pooled_std > 1e-10 else 0.0


def _cramers_v(contingency: pd.DataFrame) -> float:
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
    combined_min = min(a.min(), b.min())
    combined_max = max(a.max(), b.max())
    if combined_max == combined_min:
        return 1.0
    bins = np.linspace(combined_min, combined_max, n_bins + 1)
    hist_a, _ = np.histogram(a, bins=bins, density=True)
    hist_b, _ = np.histogram(b, bins=bins, density=True)
    sum_a = hist_a.sum()
    sum_b = hist_b.sum()
    if sum_a == 0 or sum_b == 0:
        return 0.0
    hist_a = hist_a / sum_a
    hist_b = hist_b / sum_b
    return round(float(np.minimum(hist_a, hist_b).sum()), 4)


def _effect_label(d: float) -> str:
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


def _bh_correction(p_values: list[float]) -> list[float]:
    """Benjamini-Hochberg FDR correction. Returns adjusted p-values in input order."""
    n = len(p_values)
    if n == 0:
        return []
    order = sorted(range(n), key=lambda i: p_values[i])
    adjusted = [0.0] * n
    running_min = 1.0
    for rev_rank, orig_i in enumerate(reversed(order)):
        rank = n - rev_rank
        adj = p_values[orig_i] * n / rank
        running_min = min(running_min, adj)
        adjusted[orig_i] = min(running_min, 1.0)
    return [round(v, 6) for v in adjusted]
