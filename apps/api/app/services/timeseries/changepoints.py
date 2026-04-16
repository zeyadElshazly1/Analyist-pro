"""
CUSUM-based changepoint detection.

Flags points where the rolling mean shifts by more than 1.5σ.
Deduplicates within the window keeping the most extreme shift.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def detect_changepoints(
    values: pd.Series,
    dates: pd.Series,
    window: int = 5,
) -> list[dict]:
    if len(values) < window * 3:
        return []
    roll_mean = values.rolling(window=window, center=True, min_periods=2).mean()
    overall_std = float(values.std())
    if overall_std < 1e-10:
        return []

    changepoints: list[dict] = []
    for i in range(window, len(values) - window):
        before = float(roll_mean.iloc[i - 1]) if not np.isnan(roll_mean.iloc[i - 1]) else float(values.iloc[i - 1])
        after  = float(roll_mean.iloc[i])     if not np.isnan(roll_mean.iloc[i])     else float(values.iloc[i])
        shift  = abs(after - before)
        if shift > 1.5 * overall_std:
            direction = "up" if after > before else "down"
            changepoints.append({
                "date":             str(dates.iloc[i])[:10],
                "index":            i,
                "direction":        direction,
                "magnitude":        round(shift, 4),
                "magnitude_sigma":  round(shift / overall_std, 2),
                "note": (
                    f"Trend shifted {direction} by {shift:.3g} "
                    f"({shift / overall_std:.1f}σ) around this date"
                ),
            })

    # Deduplicate: keep only the most extreme changepoint in each window
    if len(changepoints) > 1:
        filtered = [changepoints[0]]
        for cp in changepoints[1:]:
            if cp["index"] - filtered[-1]["index"] >= window:
                filtered.append(cp)
            elif cp["magnitude"] > filtered[-1]["magnitude"]:
                filtered[-1] = cp
        changepoints = filtered

    return changepoints[:5]
