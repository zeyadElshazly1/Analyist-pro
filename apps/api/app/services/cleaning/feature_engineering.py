"""
Feature engineering helpers.

Handles: date feature extraction from datetime columns.
"""
import pandas as pd


def _extract_date_features(df: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    """
    For each datetime column, extract calendar features as new numeric columns:
    year, month, day, day_of_week (0=Mon … 6=Sun), quarter, is_weekend.

    Returns the augmented DataFrame and a list of newly created column names.
    """
    created: list[str] = []
    datetime_cols = df.select_dtypes(include=["datetime64"]).columns.tolist()
    for col in datetime_cols:
        series = df[col]
        base = col  # already snake_case after step 3
        features = {
            f"{base}_year":        series.dt.year,
            f"{base}_month":       series.dt.month,
            f"{base}_day":         series.dt.day,
            f"{base}_day_of_week": series.dt.dayofweek,
            f"{base}_quarter":     series.dt.quarter,
            f"{base}_is_weekend":  series.dt.dayofweek.isin([5, 6]).astype(int),
        }
        for feat_name, feat_series in features.items():
            if feat_name not in df.columns:
                df[feat_name] = feat_series
                created.append(feat_name)
    return df, created
