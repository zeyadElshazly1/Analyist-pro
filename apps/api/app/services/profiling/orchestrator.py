"""
Profile dataset orchestrator.

profile_dataset(df) → list[dict]

Two enhancements over the original monolith:

1. Sampling engine: for datasets with > 100k rows, expensive per-column
   inference (normality test, distribution fitting, pattern regex, format
   check) runs on a 20k-row sample.  Exact aggregates (missing count, unique
   count, top values) always use the full DataFrame.

2. Semantic integration: calls detect_semantic_columns() from the cleaning
   package and attaches a ``semantic_type`` field to each column profile so
   users can see "this column is an email / ID / revenue field".
"""
import pandas as pd
import pandas.api.types as pat

from .column_profiler import (
    _profile_numeric_col,
    _profile_datetime_col,
    _profile_categorical_col,
    _build_flags,
)
from .constants import LARGE_THRESHOLD, LARGE_SAMPLE_SIZE


def _get_sample(df: pd.DataFrame) -> pd.DataFrame:
    """Return a sample of df for expensive inference; full df for small datasets."""
    if len(df) > LARGE_THRESHOLD:
        return df.sample(n=LARGE_SAMPLE_SIZE, random_state=42)
    return df


def profile_dataset(df: pd.DataFrame) -> list[dict]:
    """
    Return a list of column profile dicts — one per column in df.

    Each dict contains at minimum:
        column, dtype, missing, missing_pct, unique, unique_pct, type, flags
    Plus type-specific fields for numeric / datetime / categorical columns.
    Plus ``semantic_type`` (nullable str) from detect_semantic_columns().
    """
    if df.empty:
        return []

    # ── Semantic detection (cross-package reuse) ──────────────────────────────
    try:
        from app.services.cleaning.semantic import detect_semantic_columns
        semantic_map = detect_semantic_columns(df)
    except Exception:
        semantic_map = {}

    sample_df = _get_sample(df)
    profile: list[dict] = []

    for col in df.columns:
        col_data   = df[col]
        col_sample = sample_df[col]

        missing    = int(col_data.isnull().sum())
        n_rows     = max(len(df), 1)
        missing_pct = round(missing / n_rows * 100, 1)
        unique     = int(col_data.nunique())
        unique_pct = round(unique / n_rows * 100, 1)

        col_profile: dict = {
            "column":      col,
            "dtype":       str(col_data.dtype),
            "missing":     missing,
            "missing_pct": missing_pct,
            "unique":      unique,
            "unique_pct":  unique_pct,
            "semantic_type": semantic_map.get(col),  # None if not a recognised semantic type
        }

        if pat.is_numeric_dtype(col_data):
            col_profile.update(
                _profile_numeric_col(col_data, col_sample, unique, n_rows)
            )
        elif pat.is_datetime64_any_dtype(col_data):
            col_profile.update(_profile_datetime_col(col_data))
        else:
            col_profile.update(
                _profile_categorical_col(col_data, col_sample, unique, n_rows)
            )

        col_profile["flags"] = _build_flags(col_profile, col_data)
        profile.append(col_profile)

    return profile
