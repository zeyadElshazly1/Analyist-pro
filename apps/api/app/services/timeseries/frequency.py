"""
Frequency inference for time series.

infer_frequency(date_series) → str

Tries pd.infer_freq() first (exact), then falls back to median
total_seconds() which works for any granularity including sub-day.
The old .days approach returned 0 for hourly/minutely timedeltas.
"""
from __future__ import annotations

import pandas as pd

# Maps pandas freq alias prefixes → human labels (longest prefix first)
_PANDAS_FREQ_TO_LABEL: list[tuple[str, str]] = [
    ("min", "minutely"), ("T",  "minutely"),
    ("h",   "hourly"),   ("H",  "hourly"),
    ("B",   "daily"),    ("D",  "daily"),
    ("W",   "weekly"),
    ("ME",  "monthly"),  ("MS", "monthly"), ("M", "monthly"),
    ("QE",  "quarterly"),("QS", "quarterly"),("Q", "quarterly"),
    ("YE",  "yearly"),   ("YS", "yearly"),  ("Y", "yearly"), ("A", "yearly"),
]


def infer_frequency(date_series: pd.Series) -> str:
    """Return the most likely frequency label for a datetime series."""
    # 1. Try pd.infer_freq on a deduplicated sorted index (needs ≥3 points)
    try:
        sorted_u = date_series.sort_values().drop_duplicates()
        if len(sorted_u) >= 3:
            freq = pd.infer_freq(sorted_u)
            if freq:
                freq_upper = freq.upper()
                for prefix, label in _PANDAS_FREQ_TO_LABEL:
                    if freq_upper.startswith(prefix.upper()):
                        return label
    except Exception:
        pass

    # 2. Fallback: median total_seconds (handles all granularities)
    if len(date_series) < 2:
        return "unknown"
    diffs = date_series.sort_values().diff().dropna()
    median_seconds = diffs.median().total_seconds()

    if median_seconds <=      120:  return "minutely"
    if median_seconds <=     7200:  return "hourly"
    if median_seconds <=   129600:  return "daily"      # ≤ 1.5 days
    if median_seconds <=   691200:  return "weekly"     # ≤ 8 days
    if median_seconds <=  2764800:  return "monthly"    # ≤ 32 days
    if median_seconds <=  8208000:  return "quarterly"  # ≤ 95 days
    return "yearly"


def median_diff_seconds(date_series: pd.Series) -> float:
    """Return the median gap between consecutive dates in seconds."""
    if len(date_series) < 2:
        return 86400.0
    diffs = date_series.sort_values().diff().dropna()
    return float(diffs.median().total_seconds())
