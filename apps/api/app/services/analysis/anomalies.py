"""
Anomaly detectors.

Multivariate: Isolation Forest across all numeric columns (requires sklearn).
Univariate: adaptive IQR (skewed) or Z-score (symmetric) per column.
Both are capped at MAX_UNIVARIATE_COLS to bound runtime.
"""
import numpy as np
import pandas as pd
from scipy import stats

from .budget import MAX_UNIVARIATE_COLS


def _isolation_forest_anomalies(df: pd.DataFrame, numeric_cols: list[str]) -> set:
    """Return row-index set of multivariate outliers via Isolation Forest."""
    if len(numeric_cols) < 2:
        return set()
    try:
        from sklearn.ensemble import IsolationForest
    except ImportError:
        return set()
    sub = df[numeric_cols].dropna()
    if len(sub) < 20:
        return set()
    contamination = min(0.1, max(0.01, 10 / len(sub)))
    clf = IsolationForest(contamination=contamination, random_state=42, n_estimators=100)
    preds = clf.fit_predict(sub)
    return set(sub.index[preds == -1].tolist())


def detect_multivariate_anomalies(df: pd.DataFrame, numeric_cols: list[str]) -> list[dict]:
    """Isolation Forest over numeric_cols (capped at MAX_UNIVARIATE_COLS)."""
    cols = numeric_cols[:MAX_UNIVARIATE_COLS]
    if len(cols) < 2:
        return []
    anomaly_indices = _isolation_forest_anomalies(df, cols)
    anomaly_count = len(anomaly_indices)
    if anomaly_count == 0:
        return []
    anomaly_pct = round(anomaly_count / len(df) * 100, 1)
    return [{
        "type": "anomaly",
        "severity": "high" if anomaly_pct > 5 else "medium",
        "confidence": round(min(95, 70 + anomaly_pct * 2), 1),
        "title": f"Multivariate anomalies detected ({anomaly_count} rows)",
        "finding": (
            f"{anomaly_count} records ({anomaly_pct}% of data) show unusual combinations "
            f"of values across {len(cols)} numeric columns — flagged by Isolation Forest."
        ),
        "evidence": f"Isolation Forest, {len(cols)} features, {anomaly_count} anomalous rows",
        "action": (
            f"Inspect the {anomaly_count} flagged rows — they may represent data entry errors, "
            f"fraud signals, or genuinely extreme cases worth investigating."
        ),
    }]


def detect_univariate_anomalies(df: pd.DataFrame, numeric_cols: list[str]) -> list[dict]:
    """Adaptive IQR / Z-score univariate outlier detection (capped at MAX_UNIVARIATE_COLS)."""
    insights: list[dict] = []
    for col in numeric_cols[:MAX_UNIVARIATE_COLS]:
        col_data = df[col].dropna()
        if len(col_data) < 10:
            continue
        skew = abs(float(col_data.skew()))
        if skew > 1.5:
            q1, q3 = float(col_data.quantile(0.25)), float(col_data.quantile(0.75))
            iqr = q3 - q1
            if iqr <= 0:
                continue
            lower, upper = q1 - 3.0 * iqr, q3 + 3.0 * iqr
            outlier_mask = (col_data < lower) | (col_data > upper)
            outlier_count = int(outlier_mask.sum())
            method_label = "IQR (3× fence)"
            evidence_detail = f"IQR fence [{lower:.3g}, {upper:.3g}], skew={skew:.2f}"
        else:
            if col_data.std() < 1e-10:
                continue
            z_scores = np.abs(stats.zscore(col_data))
            outlier_count = int((z_scores > 3).sum())
            worst_z = round(float(z_scores.max()), 1)
            method_label = "Z-score (±3σ)"
            evidence_detail = (
                f"Max Z-score: {worst_z}. Mean: {col_data.mean():.2f}, Std: {col_data.std():.2f}"
            )

        if outlier_count > 0:
            outlier_pct = round(outlier_count / len(col_data) * 100, 1)
            insights.append({
                "type": "anomaly",
                "severity": "high" if outlier_pct > 5 else "medium",
                "confidence": round(min(97, 75 + outlier_pct * 2), 1),
                "title": f"Anomalies in {col}",
                "finding": (
                    f"{outlier_count} records ({outlier_pct}% of data) in '{col}' are statistical "
                    f"outliers using {method_label}."
                ),
                "evidence": evidence_detail,
                "action": (
                    f"Review the {outlier_count} extreme values in '{col}'. "
                    f"They could represent data entry errors, fraud, or your most extreme cases."
                ),
            })
    return insights
