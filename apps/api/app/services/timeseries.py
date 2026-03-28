import pandas as pd
import numpy as np
from scipy import stats


def detect_date_columns(df: pd.DataFrame) -> list[str]:
    """Return list of datetime column names."""
    return df.select_dtypes(include=["datetime64"]).columns.tolist()


def _auto_frequency(series: pd.Series) -> str:
    """Guess frequency label from a sorted datetime series."""
    if len(series) < 2:
        return "unknown"
    diffs = series.sort_values().diff().dropna()
    median_diff = diffs.median()
    days = median_diff.days
    if days <= 1:
        return "daily"
    if days <= 8:
        return "weekly"
    if days <= 32:
        return "monthly"
    if days <= 95:
        return "quarterly"
    return "yearly"


def run_timeseries(df: pd.DataFrame, date_col: str, value_col: str) -> dict:
    """Full time series analysis for a date column + value column pair."""
    ts = df[[date_col, value_col]].dropna().copy()
    ts = ts.sort_values(date_col).reset_index(drop=True)

    if len(ts) < 4:
        raise ValueError(f"Not enough data points for time series analysis (need ≥4, got {len(ts)})")

    dates = ts[date_col]
    values = ts[value_col].astype(float)
    frequency = _auto_frequency(dates)

    # Rolling statistics (7-point and 14-point window)
    w7 = min(7, max(3, len(values) // 5))
    w14 = min(14, max(5, len(values) // 3))
    roll7 = values.rolling(w7, min_periods=1).mean()
    roll14 = values.rolling(w14, min_periods=1).mean()

    # Linear trend
    x = np.arange(len(values))
    slope, intercept, r_value, p_value, _ = stats.linregress(x, values)
    trend = "up" if slope > 0 else "down"
    trend_strength = abs(r_value)

    # Residuals for anomaly detection
    trend_line = slope * x + intercept
    residuals = values - trend_line
    residual_std = residuals.std()
    is_anomaly = (np.abs(residuals) > 2 * residual_std).tolist() if residual_std > 0 else [False] * len(values)

    # ADF-style stationarity via variance check (statsmodels is optional)
    try:
        from statsmodels.tsa.stattools import adfuller
        adf_result = adfuller(values, autolag="AIC")
        is_stationary = bool(adf_result[1] < 0.05)
        adf_p = round(float(adf_result[1]), 4)
        adf_stat = round(float(adf_result[0]), 4)
    except Exception:
        # Fallback: compare first-half vs second-half variance
        half = len(values) // 2
        var1 = float(values.iloc[:half].var())
        var2 = float(values.iloc[half:].var())
        is_stationary = abs(var1 - var2) / max(var1 + var2, 1e-9) < 0.5
        adf_p = None
        adf_stat = None

    # Volatility (coefficient of variation)
    mean_val = float(values.mean())
    std_val = float(values.std())
    volatility = round(std_val / mean_val, 4) if mean_val != 0 else None

    # STL-style decomposition (simple moving average approach)
    period = {"daily": 7, "weekly": 4, "monthly": 12, "quarterly": 4, "yearly": 1}.get(frequency, 7)
    period = min(period, len(values) // 2)
    if period >= 2:
        trend_component = values.rolling(period, center=True, min_periods=1).mean()
        seasonal_component = values - trend_component
        residual_component = values - trend_component - seasonal_component.rolling(period, center=True, min_periods=1).mean()
    else:
        trend_component = values
        seasonal_component = pd.Series([0.0] * len(values))
        residual_component = values - trend_component

    # Build data_points
    data_points = []
    for i, (_, row) in enumerate(ts.iterrows()):
        data_points.append({
            "date": str(row[date_col])[:10],
            "value": round(float(row[value_col]), 4),
            "rolling_short": round(float(roll7.iloc[i]), 4),
            "rolling_long": round(float(roll14.iloc[i]), 4),
            "trend_line": round(float(trend_line[i]), 4),
            "is_anomaly": bool(is_anomaly[i]),
            "trend_component": round(float(trend_component.iloc[i]), 4),
            "seasonal_component": round(float(seasonal_component.iloc[i]), 4),
            "residual_component": round(float(residual_component.iloc[i]), 4),
        })

    first_val = float(values.iloc[0])
    last_val = float(values.iloc[-1])
    change_pct = round((last_val - first_val) / first_val * 100, 2) if first_val != 0 else None
    anomaly_count = sum(1 for pt in data_points if pt["is_anomaly"])

    return {
        "date_col": date_col,
        "value_col": value_col,
        "frequency": frequency,
        "n_points": len(data_points),
        "data_points": data_points,
        "summary": {
            "first_value": round(first_val, 4),
            "last_value": round(last_val, 4),
            "change_pct": change_pct,
            "trend": trend,
            "trend_r2": round(float(r_value ** 2), 4),
            "trend_p": round(float(p_value), 4),
            "trend_strength": round(trend_strength, 4),
            "is_stationary": is_stationary,
            "adf_stat": adf_stat,
            "adf_p": adf_p,
            "volatility": volatility,
            "anomaly_count": anomaly_count,
            "mean": round(mean_val, 4),
            "std": round(std_val, 4),
            "min": round(float(values.min()), 4),
            "max": round(float(values.max()), 4),
        },
    }
