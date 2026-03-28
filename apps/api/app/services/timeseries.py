import pandas as pd
import numpy as np
from scipy import stats


def detect_date_columns(df: pd.DataFrame) -> list[str]:
    return df.select_dtypes(include=["datetime64"]).columns.tolist()


def _auto_frequency(series: pd.Series) -> str:
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


def _detect_gaps(date_series: pd.Series, median_diff_days: float) -> list[dict]:
    """Find periods where data is missing based on expected cadence."""
    sorted_dates = date_series.sort_values().reset_index(drop=True)
    gaps = []
    threshold_days = median_diff_days * 2.5
    for i in range(1, len(sorted_dates)):
        diff_days = (sorted_dates.iloc[i] - sorted_dates.iloc[i - 1]).days
        if diff_days > threshold_days:
            gaps.append({
                "from": str(sorted_dates.iloc[i - 1])[:10],
                "to": str(sorted_dates.iloc[i])[:10],
                "gap_days": int(diff_days),
            })
    return gaps


def _detect_seasonality(values: pd.Series, frequency: str) -> dict:
    """Detect seasonality strength using autocorrelation at the expected seasonal lag."""
    _freq_to_lag = {"daily": 7, "weekly": 4, "monthly": 12, "quarterly": 4, "yearly": 1}
    lag = _freq_to_lag.get(frequency, 7)
    if len(values) < lag * 2:
        return {"detected": False, "lag": lag, "autocorr": None}
    try:
        autocorr = float(values.autocorr(lag=lag))
        detected = abs(autocorr) > 0.3
        return {
            "detected": detected,
            "lag": lag,
            "autocorr": round(autocorr, 4),
            "strength": (
                "strong" if abs(autocorr) > 0.6
                else "moderate" if abs(autocorr) > 0.3
                else "weak"
            ),
            "note": (
                f"{'Strong' if abs(autocorr) > 0.6 else 'Moderate'} {frequency} seasonality detected "
                f"(autocorr at lag={lag}: {autocorr:.2f})"
                if detected else f"No significant {frequency} seasonality detected"
            ),
        }
    except Exception:
        return {"detected": False, "lag": lag, "autocorr": None}


def _detect_changepoints(values: pd.Series, dates: pd.Series, window: int = 5) -> list[dict]:
    """
    Simple CUSUM-based change point detection.
    Flags points where the rolling mean shifts significantly.
    """
    if len(values) < window * 3:
        return []
    roll_mean = values.rolling(window=window, center=True, min_periods=2).mean()
    roll_std = values.rolling(window=window, center=True, min_periods=2).std()
    overall_std = float(values.std())
    if overall_std < 1e-10:
        return []

    changepoints = []
    for i in range(window, len(values) - window):
        before = float(roll_mean.iloc[i - 1]) if not np.isnan(roll_mean.iloc[i - 1]) else float(values.iloc[i - 1])
        after = float(roll_mean.iloc[i]) if not np.isnan(roll_mean.iloc[i]) else float(values.iloc[i])
        shift = abs(after - before)
        if shift > 1.5 * overall_std:
            direction = "up" if after > before else "down"
            changepoints.append({
                "date": str(dates.iloc[i])[:10],
                "index": i,
                "direction": direction,
                "magnitude": round(shift, 4),
                "magnitude_sigma": round(shift / overall_std, 2),
                "note": f"Trend shifted {direction} by {shift:.3g} ({shift / overall_std:.1f}σ) around this date",
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


def _stl_decompose(values: pd.Series, period: int) -> tuple[pd.Series, pd.Series, pd.Series]:
    """
    STL decomposition using statsmodels if available, otherwise simple MA fallback.
    Returns (trend, seasonal, residual).
    """
    if period < 2 or len(values) < period * 2:
        return values.copy(), pd.Series(0.0, index=values.index), pd.Series(0.0, index=values.index)

    try:
        from statsmodels.tsa.seasonal import STL
        stl = STL(values, period=period, robust=True)
        result = stl.fit()
        return (
            pd.Series(result.trend, index=values.index),
            pd.Series(result.seasonal, index=values.index),
            pd.Series(result.resid, index=values.index),
        )
    except Exception:
        pass

    # MA fallback
    trend = values.rolling(period, center=True, min_periods=1).mean()
    detrended = values - trend
    seasonal = pd.Series(0.0, index=values.index)
    if period > 1:
        for offset in range(period):
            indices = range(offset, len(values), period)
            mask = pd.Series(False, index=range(len(values)))
            for idx in indices:
                if idx < len(values):
                    mask.iloc[idx] = True
            season_vals = detrended.iloc[mask.values].mean() if mask.sum() > 0 else 0.0
            for idx in indices:
                if idx < len(values):
                    seasonal.iloc[idx] = season_vals
    residual = values - trend - seasonal
    return trend, seasonal, residual


def _exponential_smoothing_forecast(values: pd.Series, n_periods: int = 30) -> list[dict]:
    """
    Simple Holt-Winters exponential smoothing forecast.
    Returns forecast + 80% confidence intervals.
    """
    try:
        from statsmodels.tsa.holtwinters import ExponentialSmoothing
        model = ExponentialSmoothing(values, trend="add", damped_trend=True)
        fit = model.fit(optimized=True)
        forecast = fit.forecast(n_periods)
        # Confidence interval via residual std
        residuals = fit.resid
        resid_std = float(residuals.std())
        z_80 = 1.28
        return [
            {
                "step": i + 1,
                "forecast": round(float(f), 4),
                "lower_80": round(float(f) - z_80 * resid_std * np.sqrt(i + 1), 4),
                "upper_80": round(float(f) + z_80 * resid_std * np.sqrt(i + 1), 4),
            }
            for i, f in enumerate(forecast)
        ]
    except Exception:
        # Fallback: simple last-value + drift
        if len(values) < 2:
            return []
        last = float(values.iloc[-1])
        slope = float(values.iloc[-1] - values.iloc[-2])
        std = float(values.std())
        return [
            {
                "step": i + 1,
                "forecast": round(last + slope * (i + 1), 4),
                "lower_80": round(last + slope * (i + 1) - 1.28 * std, 4),
                "upper_80": round(last + slope * (i + 1) + 1.28 * std, 4),
            }
            for i in range(n_periods)
        ]


def run_timeseries(
    df: pd.DataFrame,
    date_col: str,
    value_col: str,
    aggregation: str = "mean",
) -> dict:
    """
    Full time series analysis.
    aggregation: one of 'mean', 'sum', 'count', 'min', 'max', 'median'
    """
    valid_aggs = {"mean", "sum", "count", "min", "max", "median"}
    if aggregation not in valid_aggs:
        aggregation = "mean"

    ts = df[[date_col, value_col]].dropna().copy()
    ts = ts.sort_values(date_col).reset_index(drop=True)

    if len(ts) < 4:
        raise ValueError(f"Not enough data points for time series analysis (need ≥4, got {len(ts)})")

    dates = ts[date_col]
    values = ts[value_col].astype(float)
    frequency = _auto_frequency(dates)

    # Rolling statistics
    w_short = min(7, max(3, len(values) // 5))
    w_long = min(14, max(5, len(values) // 3))
    roll_short = values.rolling(w_short, min_periods=1).mean()
    roll_long = values.rolling(w_long, min_periods=1).mean()

    # Linear trend
    x = np.arange(len(values))
    slope, intercept, r_value, p_value, _ = stats.linregress(x, values)
    trend_line = slope * x + intercept
    trend = "up" if slope > 0 else "down"

    # Residuals for anomaly detection
    residuals = values - trend_line
    residual_std = float(residuals.std())
    is_anomaly = (
        (np.abs(residuals) > 2 * residual_std).tolist()
        if residual_std > 0 else [False] * len(values)
    )

    # Gap detection
    diffs_days = dates.sort_values().diff().dropna().dt.days
    median_diff_days = float(diffs_days.median()) if len(diffs_days) > 0 else 1.0
    gaps = _detect_gaps(dates, median_diff_days)

    # Seasonality detection
    seasonality = _detect_seasonality(values, frequency)

    # STL decomposition
    _freq_to_period = {"daily": 7, "weekly": 4, "monthly": 12, "quarterly": 4, "yearly": 1}
    period = _freq_to_period.get(frequency, 7)
    period = min(period, len(values) // 2)
    trend_comp, seasonal_comp, residual_comp = _stl_decompose(values, period)

    # Change point detection
    changepoints = _detect_changepoints(values, dates, window=max(3, len(values) // 15))

    # Stationarity test
    try:
        from statsmodels.tsa.stattools import adfuller
        adf_result = adfuller(values, autolag="AIC")
        is_stationary = bool(adf_result[1] < 0.05)
        adf_p = round(float(adf_result[1]), 4)
        adf_stat = round(float(adf_result[0]), 4)
    except Exception:
        half = len(values) // 2
        var1 = float(values.iloc[:half].var())
        var2 = float(values.iloc[half:].var())
        is_stationary = abs(var1 - var2) / max(var1 + var2, 1e-9) < 0.5
        adf_p = None
        adf_stat = None

    # Volatility
    mean_val = float(values.mean())
    std_val = float(values.std())
    volatility = round(std_val / mean_val, 4) if mean_val != 0 else None

    # Forecast
    forecast = _exponential_smoothing_forecast(values, n_periods=min(30, max(7, len(values) // 4)))

    # Build data points
    data_points = []
    for i, (_, row) in enumerate(ts.iterrows()):
        data_points.append({
            "date": str(row[date_col])[:10],
            "value": round(float(row[value_col]), 4),
            "rolling_short": round(float(roll_short.iloc[i]), 4),
            "rolling_long": round(float(roll_long.iloc[i]), 4),
            "trend_line": round(float(trend_line[i]), 4),
            "is_anomaly": bool(is_anomaly[i]),
            "trend_component": round(float(trend_comp.iloc[i]), 4),
            "seasonal_component": round(float(seasonal_comp.iloc[i]), 4),
            "residual_component": round(float(residual_comp.iloc[i]), 4),
        })

    first_val = float(values.iloc[0])
    last_val = float(values.iloc[-1])
    change_pct = round((last_val - first_val) / first_val * 100, 2) if first_val != 0 else None
    anomaly_count = sum(1 for pt in data_points if pt["is_anomaly"])

    return {
        "date_col": date_col,
        "value_col": value_col,
        "aggregation": aggregation,
        "frequency": frequency,
        "n_points": len(data_points),
        "data_points": data_points,
        "forecast": forecast,
        "changepoints": changepoints,
        "seasonality": seasonality,
        "gaps": {
            "count": len(gaps),
            "periods": gaps[:5],
            "median_interval_days": round(median_diff_days, 1),
        },
        "decomposition": {
            "period": period,
            "method": "STL" if period >= 2 else "none",
        },
        "summary": {
            "first_value": round(first_val, 4),
            "last_value": round(last_val, 4),
            "change_pct": change_pct,
            "trend": trend,
            "trend_r2": round(float(r_value ** 2), 4),
            "trend_p": round(float(p_value), 4),
            "trend_strength": round(float(abs(r_value)), 4),
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
