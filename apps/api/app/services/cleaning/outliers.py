"""
Outlier detection and treatment engine.

Supports multiple strategies: winsorize, cap, flag_only, preserve, isolate.
Auto-selects strategy based on column semantics to protect valuable extremes.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .constants import _PRESERVE_OUTLIER_RE
from .semantic import PROTECTED_TYPES

OutlierStrategy = str  # "winsorize" | "cap" | "flag_only" | "preserve" | "isolate"


def _detect_outlier_bounds(series: pd.Series) -> tuple[float, float, str]:
    """Compute (lower, upper, method_desc) using IQR for skewed data, ±4σ for normal."""
    skew = abs(float(series.skew()))
    if skew > 1.0:
        q1, q3 = float(series.quantile(0.25)), float(series.quantile(0.75))
        iqr = q3 - q1
        lower = q1 - 3.0 * iqr
        upper = q3 + 3.0 * iqr
        method_desc = "3×IQR fence (skewed distribution)"
    else:
        mean, std = float(series.mean()), float(series.std())
        lower = mean - 4 * std
        upper = mean + 4 * std
        method_desc = "±4σ clip (normal distribution)"
    return lower, upper, method_desc


def choose_outlier_strategy(col: str, semantic_type: str | None) -> OutlierStrategy:
    """Determine the best outlier strategy given column name and semantic type.

    Rules (priority order):
    1. Protected semantic types (id/phone/postal/sku/account_number) → "preserve"
    2. Revenue semantic type OR name matches financial pattern → "preserve"
    3. Default → "winsorize" (current behavior)
    """
    if semantic_type in PROTECTED_TYPES:
        return "preserve"
    if semantic_type == "revenue":
        return "preserve"
    if _PRESERVE_OUTLIER_RE.search(col):
        return "preserve"
    return "winsorize"


def _handle_outliers(
    series: pd.Series,
    strategy: OutlierStrategy = "winsorize",
) -> tuple[pd.Series, int, str]:
    """Apply chosen outlier strategy to a numeric series.

    Returns (result_series, n_affected, description).

    Strategies:
    - "winsorize" / "cap": clip values to [lower, upper] bounds
    - "flag_only":         return series unchanged, report count
    - "preserve":          return series unchanged, n_affected = 0 (skip)
    - "isolate":           replace outliers with NaN (does not impute)
    """
    col_data = series.dropna()
    if len(col_data) < 20:
        return series, 0, ""

    lower, upper, method_desc = _detect_outlier_bounds(col_data)
    outside = int(((col_data < lower) | (col_data > upper)).sum())

    if outside == 0 or strategy == "preserve":
        return series, 0, ""

    if strategy in ("winsorize", "cap"):
        result = series.clip(lower=lower, upper=upper)
        desc = f"Clipped {outside} extreme values using {method_desc} [{lower:.4g}, {upper:.4g}]"
        return result, outside, desc

    if strategy == "flag_only":
        desc = f"Flagged {outside} extreme values using {method_desc} [{lower:.4g}, {upper:.4g}] (no clip)"
        return series, outside, desc

    if strategy == "isolate":
        result = series.where((series >= lower) | series.isnull() | (series <= upper), other=np.nan)
        desc = f"Isolated {outside} extreme values to NaN using {method_desc} [{lower:.4g}, {upper:.4g}]"
        return result, outside, desc

    return series, 0, ""


def _flag_suspicious_zeros(
    df: pd.DataFrame,
    threshold: float = 0.10,
) -> list[dict]:
    """
    Flag numeric columns where a suspiciously high fraction of non-missing values
    are exactly zero — which often signals that 0 was used to encode missingness
    rather than a true measurement.

    No mutation — only returns a list of warning dicts.
    threshold: minimum zero-fraction to trigger a warning (default 10%).
    """
    warnings: list[dict] = []
    for col in df.select_dtypes(include=[np.number]).columns:
        non_null = df[col].dropna()
        if len(non_null) < 20:
            continue
        zero_count = int((non_null == 0).sum())
        zero_pct = zero_count / len(non_null)
        if zero_pct < threshold:
            continue
        col_range = float(non_null.max() - non_null.min())
        if col_range == 0:
            continue  # constant column — zeros expected
        if non_null.nunique() <= 2:
            continue  # binary column — zeros are legitimate
        warnings.append({
            "column": col,
            "zero_count": zero_count,
            "zero_pct": round(zero_pct * 100, 1),
            "message": (
                f"'{col}' has {zero_count} exact zeros ({zero_pct * 100:.1f}% of non-null values). "
                f"Zeros may encode missing data rather than a true measurement. "
                f"Verify with the data source before modeling."
            ),
        })
    return warnings
