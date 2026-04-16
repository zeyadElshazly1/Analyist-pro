"""
Trend detector.

BUG FIX: The original analyzer.py fell back to row-index as the time axis when
no datetime column was present.  Row order is arbitrary (reshuffling the data
produces different "trends"), so this produced meaningless findings.

This module requires a datetime column.  If none exists, detect_trends returns
[] immediately — no row-order fallback.
"""
import numpy as np
import pandas as pd
from scipy import stats

from .budget import MAX_TREND_COLS


def detect_trends(df: pd.DataFrame, numeric_cols: list[str]) -> list[dict]:
    """
    Return trend insights for numeric columns that show a statistically
    significant monotonic trend over time.

    Only runs when a datetime column is present in df.
    Threshold: p < 0.05 AND R² > 0.15 to filter noise.
    Returns at most 3 insights (highest R² first).
    """
    if not numeric_cols or len(df) < 10:
        return []

    datetime_cols = df.select_dtypes(include=["datetime64"]).columns.tolist()
    if not datetime_cols:
        return []  # no row-order fallback — see module docstring

    time_col = datetime_cols[0]
    x = (df[time_col] - df[time_col].min()).dt.days.values.astype(float)
    time_label = f"over time (by '{time_col}')"
    unit_label = "per day"

    insights: list[dict] = []
    for col in numeric_cols[:MAX_TREND_COLS]:
        col_data = df[col]
        valid = col_data.notna()
        y = col_data[valid].values.astype(float)
        x_clean = x[valid.values] if len(x) == len(df) else x[:len(y)]
        if len(y) < 10:
            continue
        try:
            slope, _, r, p, _ = stats.linregress(x_clean, y)
        except Exception:
            continue
        r2 = r ** 2
        if p >= 0.05 or r2 < 0.15:
            continue

        direction = "upward" if slope > 0 else "downward"
        mean_y = float(np.mean(y))
        pct_change = (
            abs(slope) * (x_clean[-1] - x_clean[0]) / max(abs(mean_y), 1e-10) * 100
        )
        insights.append({
            "type": "trend",
            "severity": "high" if r2 > 0.5 else "medium",
            "confidence": round(min(97, r2 * 100), 1),
            "title": f"Trend detected: {col} ({direction})",
            "finding": (
                f"'{col}' shows a significant {direction} trend {time_label} "
                f"(slope={slope:+.4g} {unit_label}, R²={r2:.2f}). "
                f"Total change across the dataset: ~{pct_change:.1f}%."
            ),
            "evidence": (
                f"OLS slope={slope:+.4g} {unit_label}, R²={r2:.3f}, p={p:.4f}, n={len(y)}"
            ),
            "action": (
                f"Investigate the driver of the {direction} trend in '{col}'. "
                + (
                    "Consider detrending before correlation analysis to avoid spurious relationships."
                    if r2 > 0.3
                    else "Monitor whether this trend continues."
                )
            ),
        })

    insights.sort(key=lambda x: x["confidence"], reverse=True)
    return insights[:3]
