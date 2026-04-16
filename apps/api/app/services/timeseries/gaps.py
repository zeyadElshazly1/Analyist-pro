"""
Gap detection for time series.

detect_gaps(date_series, median_diff_seconds) → list[dict]

Uses total_seconds() so hourly and minutely gaps are correctly detected
(the old implementation used .days which was always 0 for sub-day data).
"""
from __future__ import annotations

import pandas as pd


def detect_gaps(date_series: pd.Series, median_diff_seconds: float) -> list[dict]:
    """Find periods where data is missing based on expected cadence."""
    sorted_dates = date_series.sort_values().reset_index(drop=True)
    threshold_seconds = median_diff_seconds * 2.5
    gaps: list[dict] = []
    for i in range(1, len(sorted_dates)):
        diff_s = (sorted_dates.iloc[i] - sorted_dates.iloc[i - 1]).total_seconds()
        if diff_s > threshold_seconds:
            gaps.append({
                "from":     str(sorted_dates.iloc[i - 1])[:19],
                "to":       str(sorted_dates.iloc[i])[:19],
                "gap_days": round(diff_s / 86400, 2),
            })
    return gaps
