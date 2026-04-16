"""
STL decomposition with moving-average fallback.

stl_decompose(values, period) → (trend, seasonal, residual)
"""
from __future__ import annotations

import pandas as pd


def stl_decompose(
    values: pd.Series,
    period: int,
) -> tuple[pd.Series, pd.Series, pd.Series]:
    if period < 2 or len(values) < period * 2:
        return (
            values.copy(),
            pd.Series(0.0, index=values.index),
            pd.Series(0.0, index=values.index),
        )

    try:
        from statsmodels.tsa.seasonal import STL  # noqa: PLC0415
        stl    = STL(values, period=period, robust=True)
        result = stl.fit()
        return (
            pd.Series(result.trend,    index=values.index),
            pd.Series(result.seasonal, index=values.index),
            pd.Series(result.resid,    index=values.index),
        )
    except Exception:
        pass

    # MA fallback
    trend     = values.rolling(period, center=True, min_periods=1).mean()
    detrended = values - trend
    seasonal  = pd.Series(0.0, index=values.index)
    for offset in range(period):
        indices = list(range(offset, len(values), period))
        vals_at_offset = detrended.iloc[indices].dropna()
        season_val = float(vals_at_offset.mean()) if len(vals_at_offset) > 0 else 0.0
        for idx in indices:
            if idx < len(values):
                seasonal.iloc[idx] = season_val
    residual = values - trend - seasonal
    return trend, seasonal, residual
