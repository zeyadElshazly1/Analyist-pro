import pandas as pd
import numpy as np
from scipy import stats


def explore_outliers(df: pd.DataFrame, column: str) -> dict:
    if column not in df.columns:
        raise ValueError(f"Column '{column}' not found")

    series = df[column].dropna()

    if not pd.api.types.is_numeric_dtype(series):
        raise ValueError(f"Column '{column}' is not numeric")
    if len(series) < 3:
        raise ValueError("Not enough data points")

    z_scores = stats.zscore(series)
    outlier_mask = np.abs(z_scores) > 3

    outlier_rows = [
        {"index": int(idx), "value": round(float(val), 4), "z_score": round(float(z), 4)}
        for idx, val, z in zip(
            series.index[outlier_mask],
            series[outlier_mask],
            z_scores[outlier_mask],
        )
    ]

    hist, bin_edges = np.histogram(series, bins=20)
    outlier_values = series[outlier_mask].tolist()

    histogram = [
        {
            "label": f"{bin_edges[i]:.2f}–{bin_edges[i + 1]:.2f}",
            "count": int(hist[i]),
            "is_outlier_bin": any(
                bin_edges[i] <= v <= bin_edges[i + 1] for v in outlier_values
            ),
        }
        for i in range(len(hist))
    ]

    mean = float(series.mean())
    std = float(series.std())

    return {
        "column": column,
        "total_rows": len(series),
        "outlier_count": int(outlier_mask.sum()),
        "outlier_pct": round(float(outlier_mask.mean()) * 100, 2),
        "stats": {
            "mean": round(mean, 4),
            "std": round(std, 4),
            "min": round(float(series.min()), 4),
            "max": round(float(series.max()), 4),
            "lower_bound": round(mean - 3 * std, 4),
            "upper_bound": round(mean + 3 * std, 4),
        },
        "histogram": histogram,
        "outlier_rows": outlier_rows[:50],
    }
