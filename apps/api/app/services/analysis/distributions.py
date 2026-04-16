"""
Distribution skewness detector.

Reports columns with |skewness| > 1.5 as needing log-transformation.
Capped at MAX_UNIVARIATE_COLS.
"""
import pandas as pd

from .budget import MAX_UNIVARIATE_COLS


def detect_skewness(df: pd.DataFrame, numeric_cols: list[str]) -> list[dict]:
    """Return skewness insights for heavily skewed numeric columns."""
    insights: list[dict] = []
    for col in numeric_cols[:MAX_UNIVARIATE_COLS]:
        col_data = df[col].dropna()
        if len(col_data) < 20:
            continue
        skew = float(col_data.skew())
        if abs(skew) <= 1.5:
            continue
        direction = "right (positive)" if skew > 0 else "left (negative)"
        insights.append({
            "type": "distribution",
            "severity": "medium",
            "confidence": round(min(95, 60 + abs(skew) * 8), 1),
            "title": f"Skewed distribution: {col}",
            "finding": (
                f"'{col}' is heavily skewed {direction} (skewness={skew:.2f}). "
                f"Most values cluster at the {'low' if skew > 0 else 'high'} end."
            ),
            "evidence": (
                f"Skewness={skew:.3f}, Mean={col_data.mean():.2f}, Median={col_data.median():.2f}"
            ),
            "action": (
                f"Consider log-transforming '{col}' before modeling. "
                f"Gap between mean ({col_data.mean():.2f}) and median ({col_data.median():.2f}) "
                f"confirms skew."
            ),
        })
    return insights
