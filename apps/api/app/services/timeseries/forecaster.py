"""
Time-series forecasting.

forecast_values(values, n_periods) → list[dict]

Tries Holt-Winters (damped) via statsmodels; falls back to last-value + drift.
Each output dict includes model_used so the frontend can indicate quality.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

_Z_80 = 1.28


def forecast_values(values: pd.Series, n_periods: int = 30) -> list[dict]:
    try:
        from statsmodels.tsa.holtwinters import ExponentialSmoothing  # noqa: PLC0415
        model  = ExponentialSmoothing(values, trend="add", damped_trend=True)
        fit    = model.fit(optimized=True)
        fc     = fit.forecast(n_periods)
        resid_std = float(fit.resid.std())
        return [
            {
                "step":       i + 1,
                "forecast":   round(float(f), 4),
                "lower_80":   round(float(f) - _Z_80 * resid_std * np.sqrt(i + 1), 4),
                "upper_80":   round(float(f) + _Z_80 * resid_std * np.sqrt(i + 1), 4),
                "model_used": "HoltWinters",
            }
            for i, f in enumerate(fc)
        ]
    except Exception:
        pass

    # Drift fallback
    if len(values) < 2:
        return []
    last  = float(values.iloc[-1])
    slope = float(values.iloc[-1] - values.iloc[-2])
    std   = float(values.std())
    return [
        {
            "step":       i + 1,
            "forecast":   round(last + slope * (i + 1), 4),
            "lower_80":   round(last + slope * (i + 1) - _Z_80 * std, 4),
            "upper_80":   round(last + slope * (i + 1) + _Z_80 * std, 4),
            "model_used": "drift",
        }
        for i in range(n_periods)
    ]
