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

    skewness = float(col_data.skew())
    is_skewed = abs(skewness) > 1.0

    # ── Method 1: Z-score ────────────────────────────────────────────────────
    z_scores = stats.zscore(col_data)
    # Adaptive threshold: relax to ±3.5σ for heavily skewed data to reduce false positives
    z_threshold = 3.5 if is_skewed else 3.0
    z_outlier_mask = np.abs(z_scores) > z_threshold

    # ── Method 2: IQR ────────────────────────────────────────────────────────
    q1, q3 = float(col_data.quantile(0.25)), float(col_data.quantile(0.75))
    iqr = q3 - q1
    # Adaptive multiplier: use 3.0 for skewed data (more tolerant), 1.5 for normal
    iqr_multiplier = 3.0 if is_skewed else 1.5
    iqr_lower = q1 - iqr_multiplier * iqr
    iqr_upper = q3 + iqr_multiplier * iqr
    iqr_outlier_mask = (col_data < iqr_lower) | (col_data > iqr_upper)

    # ── Method 3: Isolation Forest (multivariate context) ────────────────────
    iso_outlier_mask = pd.Series(False, index=col_data.index)
    iso_scores = pd.Series(np.nan, index=col_data.index)
    iso_available = False

    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    if len(numeric_cols) >= 2 and len(col_data) >= 20:
        try:
            from sklearn.ensemble import IsolationForest
            sub = df[numeric_cols].loc[col_data.index].fillna(df[numeric_cols].median())
            contamination = min(0.1, max(0.01, 1 / len(sub) * 10))
            clf = IsolationForest(contamination=contamination, random_state=42, n_estimators=100)
            preds = clf.fit_predict(sub)
            scores_raw = clf.score_samples(sub)
            iso_outlier_mask = pd.Series(preds == -1, index=col_data.index)
            # Normalize scores to [0,1] — lower = more anomalous
            iso_scores = pd.Series(
                (scores_raw - scores_raw.min()) / (scores_raw.max() - scores_raw.min() + 1e-10),
                index=col_data.index,
            )
            iso_available = True
        except Exception:
            pass

    # ── Combined: flagged by at least one method ──────────────────────────────
    combined_mask = z_outlier_mask | iqr_outlier_mask.values
    if iso_available:
        combined_mask = combined_mask | iso_outlier_mask.values

    # ── Build histogram with outlier flagging ────────────────────────────────
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

    # ── Build outlier rows ────────────────────────────────────────────────────
    outlier_indices = col_data.index[combined_mask].tolist()
    mean_val = float(col_data.mean())

    outlier_rows = []
    for idx in outlier_indices:
        val = float(col_data.loc[idx])
        z = float(z_scores[col_data.index.get_loc(idx)])
        pct_dev = round((val - mean_val) / mean_val * 100, 1) if mean_val != 0 else None
        row_dict = {
            "index": int(idx),
            "value": round(val, 4),
            "z_score": round(z, 3),
            "iqr_flag": bool(iqr_outlier_mask.loc[idx]),
            "zscore_flag": bool(abs(z) > z_threshold),
            "iso_flag": bool(iso_outlier_mask.loc[idx]) if iso_available else None,
            "iso_score": round(float(iso_scores.loc[idx]), 4) if iso_available and not np.isnan(iso_scores.loc[idx]) else None,
            "pct_deviation": pct_dev,
        }
        try:
            other = df.loc[idx].drop(column).to_dict()
            row_dict["context"] = {k: v for k, v in list(other.items())[:4]}
        except Exception:
            pass
        outlier_rows.append(row_dict)

    # Sort by abs z_score descending
    outlier_rows.sort(key=lambda r: abs(r["z_score"]), reverse=True)

    methods: dict = {
        "zscore": {
            "count": int(z_outlier_mask.sum()),
            "threshold": f"±{z_threshold}σ",
            "pct": round(float(z_outlier_mask.sum()) / len(col_data) * 100, 2),
            "adaptive": is_skewed,
        },
        "iqr": {
            "count": int(iqr_outlier_mask.sum()),
            "multiplier": iqr_multiplier,
            "lower_fence": round(iqr_lower, 4),
            "upper_fence": round(iqr_upper, 4),
            "pct": round(float(iqr_outlier_mask.sum()) / len(col_data) * 100, 2),
            "adaptive": is_skewed,
        },
        "combined": {
            "count": int(combined_mask.sum()),
            "pct": round(float(combined_mask.sum()) / len(col_data) * 100, 2),
        },
    }

    if iso_available:
        methods["isolation_forest"] = {
            "count": int(iso_outlier_mask.sum()),
            "pct": round(float(iso_outlier_mask.sum()) / len(col_data) * 100, 2),
            "features_used": len(numeric_cols),
            "description": "Multivariate anomaly detection across all numeric columns",
        }

    return {
        "column": column,
        "total_rows": len(col_data),
        "skewness": round(skewness, 3),
        "adaptive_thresholds": is_skewed,
        "methods": methods,
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
