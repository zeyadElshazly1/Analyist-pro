import pandas as pd
import numpy as np
from scipy import stats


def get_numeric_columns(df: pd.DataFrame) -> list[str]:
    return df.select_dtypes(include=[np.number]).columns.tolist()


def explore_outliers(df: pd.DataFrame, column: str) -> dict:
    if column not in df.columns:
        raise ValueError(f"Column '{column}' not found in dataset")
    if not pd.api.types.is_numeric_dtype(df[column]):
        raise ValueError(f"Column '{column}' is not numeric")

    col_data = df[column].dropna()
    if len(col_data) < 5:
        raise ValueError(f"Column '{column}' has too few values for outlier analysis")

    # Z-score method
    z_scores = stats.zscore(col_data)
    z_outlier_mask = np.abs(z_scores) > 3

    # IQR method
    q1, q3 = float(col_data.quantile(0.25)), float(col_data.quantile(0.75))
    iqr = q3 - q1
    iqr_lower = q1 - 1.5 * iqr
    iqr_upper = q3 + 1.5 * iqr
    iqr_outlier_mask = (col_data < iqr_lower) | (col_data > iqr_upper)

    # Combined: flagged by at least one method
    combined_mask = z_outlier_mask | iqr_outlier_mask.values

    # Build histogram with outlier flagging
    n_bins = min(20, max(8, len(col_data) // 20))
    counts, edges = np.histogram(col_data, bins=n_bins)
    total = len(col_data)
    cumulative = 0
    histogram = []
    for i, count in enumerate(counts):
        cumulative += count
        bin_center = (edges[i] + edges[i + 1]) / 2
        is_outlier_bin = float(bin_center) < iqr_lower or float(bin_center) > iqr_upper
        histogram.append({
            "label": f"{edges[i]:.3g}–{edges[i+1]:.3g}",
            "value": int(count),
            "density": round(float(count) / total, 4),
            "cumulative_pct": round(cumulative / total * 100, 1),
            "is_outlier_bin": bool(is_outlier_bin),
        })

    # Build outlier rows (show the most extreme first)
    outlier_indices = col_data.index[combined_mask].tolist()
    mean_val = float(col_data.mean())

    outlier_rows = []
    for idx in outlier_indices:
        val = float(col_data.loc[idx])
        z = float(z_scores[col_data.index.get_loc(idx)])
        pct_dev = round((val - mean_val) / mean_val * 100, 1) if mean_val != 0 else None
        row_dict = {"index": int(idx), "value": round(val, 4), "z_score": round(z, 3)}
        # Try to include other columns for context
        try:
            other = df.loc[idx].drop(column).to_dict()
            row_dict["context"] = {k: v for k, v in list(other.items())[:4]}
        except Exception:
            pass
        row_dict["iqr_flag"] = bool(iqr_outlier_mask.loc[idx])
        row_dict["zscore_flag"] = bool(abs(z) > 3)
        row_dict["pct_deviation"] = pct_dev
        outlier_rows.append(row_dict)

    # Sort by abs z_score descending
    outlier_rows.sort(key=lambda r: abs(r["z_score"]), reverse=True)

    return {
        "column": column,
        "total_rows": len(col_data),
        "methods": {
            "zscore": {
                "count": int(z_outlier_mask.sum()),
                "threshold": "±3σ",
                "pct": round(float(z_outlier_mask.sum()) / len(col_data) * 100, 2),
            },
            "iqr": {
                "count": int(iqr_outlier_mask.sum()),
                "lower_fence": round(iqr_lower, 4),
                "upper_fence": round(iqr_upper, 4),
                "pct": round(float(iqr_outlier_mask.sum()) / len(col_data) * 100, 2),
            },
            "combined": {
                "count": int(combined_mask.sum()),
                "pct": round(float(combined_mask.sum()) / len(col_data) * 100, 2),
            },
        },
        "stats": {
            "mean": round(float(col_data.mean()), 4),
            "median": round(float(col_data.median()), 4),
            "std": round(float(col_data.std()), 4),
            "q1": round(q1, 4),
            "q3": round(q3, 4),
            "iqr": round(iqr, 4),
            "min": round(float(col_data.min()), 4),
            "max": round(float(col_data.max()), 4),
        },
        "histogram": histogram,
        "outlier_rows": outlier_rows[:100],
    }
