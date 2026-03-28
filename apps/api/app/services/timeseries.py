import pandas as pd
import numpy as np

DATE_HINTS = ["date", "time", "year", "month", "day", "week", "timestamp", "period"]


def detect_date_columns(df: pd.DataFrame) -> list:
    date_cols = []
    for col in df.columns:
        if df[col].dtype == "datetime64[ns]":
            date_cols.append(col)
        elif any(hint in col.lower() for hint in DATE_HINTS):
            date_cols.append(col)
    return date_cols


def run_timeseries(df: pd.DataFrame, date_col: str, value_col: str) -> dict:
    if date_col not in df.columns:
        raise ValueError(f"Column '{date_col}' not found")
    if value_col not in df.columns:
        raise ValueError(f"Column '{value_col}' not found")

    ts = df[[date_col, value_col]].copy()

    if ts[date_col].dtype != "datetime64[ns]":
        ts[date_col] = pd.to_datetime(ts[date_col], errors="coerce")

    ts = ts.dropna(subset=[date_col, value_col]).sort_values(date_col)

    if len(ts) < 2:
        raise ValueError("Not enough data points for time series analysis")

    date_range = (ts[date_col].max() - ts[date_col].min()).days
    if date_range <= 30:
        freq, freq_label = "D", "daily"
    elif date_range <= 365:
        freq, freq_label = "W", "weekly"
    else:
        freq, freq_label = "ME", "monthly"

    ts_indexed = ts.set_index(date_col)[value_col]
    resampled = ts_indexed.resample(freq).mean().dropna()

    if len(resampled) < 2:
        resampled = ts_indexed

    data_points = [
        {"date": str(idx.date()), "value": round(float(val), 4)}
        for idx, val in resampled.items()
    ]

    first_val = float(resampled.iloc[0])
    last_val = float(resampled.iloc[-1])
    change_pct = round(((last_val - first_val) / abs(first_val)) * 100, 2) if first_val != 0 else 0

    return {
        "date_col": date_col,
        "value_col": value_col,
        "frequency": freq_label,
        "data_points": data_points,
        "summary": {
            "first_value": round(first_val, 4),
            "last_value": round(last_val, 4),
            "change_pct": change_pct,
            "trend": "upward" if change_pct > 0 else "downward" if change_pct < 0 else "flat",
            "min": round(float(resampled.min()), 4),
            "max": round(float(resampled.max()), 4),
            "mean": round(float(resampled.mean()), 4),
        },
    }
