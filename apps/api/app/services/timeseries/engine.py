"""
Time-series analysis orchestrator.

run_timeseries(df, date_col, value_col, aggregation) → dict
detect_date_columns(df) → list[str]

Pipeline:
  1. aggregate     — group duplicate dates (the param was accepted but ignored before)
  2. infer_frequency — pd.infer_freq() + total_seconds() fallback (fixes sub-day)
  3. rolling stats + linear trend
  4. stl_decompose — trend / seasonal / residual components
  5. detect_anomalies — MAD-based robust z-score on STL residuals
  6. detect_gaps   — total_seconds() so hourly gaps are detected
  7. detect_seasonality, detect_changepoints
  8. stationarity test (ADF or variance fallback)
  9. forecast_values
 10. build data_points — vectorized zip (replaces iterrows)
"""
from __future__ import annotations

import pandas as pd
import numpy as np
from scipy import stats

from .anomalies import detect_anomalies
from .changepoints import detect_changepoints
from .constants import FREQ_TO_PERIOD, VALID_AGGREGATIONS
from .decomposition import stl_decompose
from .forecaster import forecast_values
from .frequency import infer_frequency, median_diff_seconds
from .gaps import detect_gaps
from .seasonality import detect_seasonality


def detect_date_columns(df: pd.DataFrame) -> list[str]:
    return df.select_dtypes(include=["datetime64"]).columns.tolist()


def run_timeseries(
    df: pd.DataFrame,
    date_col: str,
    value_col: str,
    aggregation: str = "mean",
) -> dict:
    """
    Full time-series analysis.

    aggregation: one of 'mean', 'sum', 'count', 'min', 'max', 'median'
    """
    if aggregation not in VALID_AGGREGATIONS:
        aggregation = "mean"

    # ── 1. Aggregate duplicate dates ─────────────────────────────────────────
    ts = df[[date_col, value_col]].dropna().copy()
    ts = (
        ts.groupby(date_col, as_index=False)[value_col]
        .agg(aggregation)
    )
    ts = ts.sort_values(date_col).reset_index(drop=True)

    if len(ts) < 4:
        raise ValueError(
            f"Not enough data points for time series analysis (need ≥4, got {len(ts)})"
        )

    dates  = ts[date_col]
    values = ts[value_col].astype(float)

    # ── 2. Frequency & gaps ──────────────────────────────────────────────────
    frequency      = infer_frequency(dates)
    med_diff_s     = median_diff_seconds(dates)
    gaps           = detect_gaps(dates, med_diff_s)

    # ── 3. Rolling statistics ────────────────────────────────────────────────
    w_short    = min(7,  max(3, len(values) // 5))
    w_long     = min(14, max(5, len(values) // 3))
    roll_short = values.rolling(w_short, min_periods=1).mean()
    roll_long  = values.rolling(w_long,  min_periods=1).mean()

    # ── 4. Linear trend ──────────────────────────────────────────────────────
    x = np.arange(len(values))
    slope, intercept, r_value, p_value, _ = stats.linregress(x, values)
    trend_line = slope * x + intercept
    trend      = "up" if slope > 0 else "down"

    # ── 5. STL decomposition ─────────────────────────────────────────────────
    period = FREQ_TO_PERIOD.get(frequency, 7)
    period = min(period, len(values) // 2)
    trend_comp, seasonal_comp, residual_comp = stl_decompose(values, period)

    # ── 6. Anomaly detection (MAD on STL residuals) ──────────────────────────
    is_anomaly = detect_anomalies(residual_comp)

    # ── 7. Seasonality & changepoints ────────────────────────────────────────
    seasonality  = detect_seasonality(values, frequency)
    changepoints = detect_changepoints(values, dates, window=max(3, len(values) // 15))

    # ── 8. Stationarity test ─────────────────────────────────────────────────
    try:
        from statsmodels.tsa.stattools import adfuller  # noqa: PLC0415
        adf_result   = adfuller(values, autolag="AIC")
        is_stationary = bool(adf_result[1] < 0.05)
        adf_p         = round(float(adf_result[1]), 4)
        adf_stat      = round(float(adf_result[0]), 4)
    except Exception:
        half          = len(values) // 2
        var1          = float(values.iloc[:half].var())
        var2          = float(values.iloc[half:].var())
        is_stationary = abs(var1 - var2) / max(var1 + var2, 1e-9) < 0.5
        adf_p         = None
        adf_stat      = None

    # ── 9. Forecast ──────────────────────────────────────────────────────────
    n_forecast = min(30, max(7, len(values) // 4))
    forecast   = forecast_values(values, n_periods=n_forecast)

    # ── 10. Build data_points (vectorized) ───────────────────────────────────
    data_points = [
        {
            "date":               str(d)[:10],
            "value":              round(float(v),  4),
            "rolling_short":      round(float(rs), 4),
            "rolling_long":       round(float(rl), 4),
            "trend_line":         round(float(tl), 4),
            "is_anomaly":         bool(ia),
            "trend_component":    round(float(tc), 4),
            "seasonal_component": round(float(sc), 4),
            "residual_component": round(float(rc), 4),
        }
        for d, v, rs, rl, tl, ia, tc, sc, rc in zip(
            dates,
            values.to_numpy(),
            roll_short.to_numpy(),
            roll_long.to_numpy(),
            trend_line,
            is_anomaly,
            trend_comp.to_numpy(),
            seasonal_comp.to_numpy(),
            residual_comp.to_numpy(),
        )
    ]

    # ── Summary ──────────────────────────────────────────────────────────────
    first_val     = float(values.iloc[0])
    last_val      = float(values.iloc[-1])
    change_pct    = round((last_val - first_val) / first_val * 100, 2) if first_val != 0 else None
    anomaly_count = sum(1 for pt in data_points if pt["is_anomaly"])
    mean_val      = float(values.mean())
    std_val       = float(values.std())
    volatility    = round(std_val / mean_val, 4) if mean_val != 0 else None

    return {
        "date_col":    date_col,
        "value_col":   value_col,
        "aggregation": aggregation,
        "frequency":   frequency,
        "n_points":    len(data_points),
        "data_points": data_points,
        "forecast":    forecast,
        "changepoints": changepoints,
        "seasonality": seasonality,
        "gaps": {
            "count":                len(gaps),
            "periods":              gaps[:5],
            "median_interval_days": round(med_diff_s / 86400, 1),
        },
        "decomposition": {
            "period": period,
            "method": "STL" if period >= 2 else "none",
        },
        "summary": {
            "first_value":    round(first_val, 4),
            "last_value":     round(last_val,  4),
            "change_pct":     change_pct,
            "trend":          trend,
            "trend_r2":       round(float(r_value ** 2), 4),
            "trend_p":        round(float(p_value), 4),
            "trend_strength": round(float(abs(r_value)), 4),
            "is_stationary":  is_stationary,
            "adf_stat":       adf_stat,
            "adf_p":          adf_p,
            "volatility":     volatility,
            "anomaly_count":  anomaly_count,
            "mean":           round(mean_val, 4),
            "std":            round(std_val,  4),
            "min":            round(float(values.min()), 4),
            "max":            round(float(values.max()), 4),
        },
    }
