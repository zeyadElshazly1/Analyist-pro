"""
Seasonality detection via autocorrelation at the expected seasonal lag.
"""
from __future__ import annotations

import pandas as pd

from .constants import FREQ_TO_LAG


def detect_seasonality(values: pd.Series, frequency: str) -> dict:
    lag = FREQ_TO_LAG.get(frequency, 7)
    if len(values) < lag * 2:
        return {"detected": False, "lag": lag, "autocorr": None}
    try:
        autocorr = float(values.autocorr(lag=lag))
        detected = abs(autocorr) > 0.3
        return {
            "detected":  detected,
            "lag":       lag,
            "autocorr":  round(autocorr, 4),
            "strength": (
                "strong"   if abs(autocorr) > 0.6
                else "moderate" if abs(autocorr) > 0.3
                else "weak"
            ),
            "note": (
                f"{'Strong' if abs(autocorr) > 0.6 else 'Moderate'} {frequency} seasonality detected "
                f"(autocorr at lag={lag}: {autocorr:.2f})"
                if detected
                else f"No significant {frequency} seasonality detected"
            ),
        }
    except Exception:
        return {"detected": False, "lag": lag, "autocorr": None}
