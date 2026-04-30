"""
Chart quality gates — reject misleading payloads before they reach the UI.

Time-series line charts require a real calendar-shaped X axis and a numeric Y
that is not a low-cardinality discrete count / model-year style field.
"""
from __future__ import annotations

import pandas as pd


# At least this many distinct calendar days (normalized) on the X axis.
_MIN_DISTINCT_CALENDAR_POINTS = 3

# Numeric Y must have enough distinct values that a connected line is not just
# a jittery ordinal / small integer field (e.g. accident counts 0–5).
_MIN_DISTINCT_NUMERIC_Y_VALUES = 22

_DISCRETE_YEAR_SUBSTR = (
    "vehicle_year",
    "vehicleyear",
    "car_year",
    "model_year",
    "modelyear",
    "policy_year",
    "registration_year",
)


def datetime_axis_suitable_for_line_chart(series: pd.Series) -> bool:
    """
    True when ``series`` is datetime64 and has meaningful span + distinct dates.

    Does not use row index or string labels — callers must pass an actual datetime
    column coerced by pandas (datetime64[ns] / tz-aware).
    """
    if not pd.api.types.is_datetime64_any_dtype(series):
        return False
    clean = series.dropna()
    if len(clean) < 4:
        return False
    s = pd.to_datetime(clean, errors="coerce").dropna()
    if len(s) < 4:
        return False
    try:
        dnorm = s.dt.normalize()
    except (AttributeError, TypeError):
        return False
    if dnorm.nunique() < _MIN_DISTINCT_CALENDAR_POINTS:
        return False
    span = s.max() - s.min()
    if span <= pd.Timedelta(0):
        return False
    return True


def column_name_suggests_discrete_year_metric(name: str) -> bool:
    """Vehicle / policy year fields are cross-sectional attributes, not trends."""
    key = name.lower().replace(" ", "_").replace("-", "_")
    for tok in _DISCRETE_YEAR_SUBSTR:
        if tok in key:
            return True
    if key.endswith("_year") and any(
        p in key for p in ("vehicle", "model", "policy", "registration", "car")
    ):
        return True
    return False


def column_name_blocked_for_timeseries_y(name: str) -> bool:
    """
    Y columns that are almost always cross-sectional or low-information over time.

    Even with a valid datetime X axis, these fields must not get “over time” line
    charts — use histograms / categorical frequency instead.
    """
    if column_name_suggests_discrete_year_metric(name):
        return True

    key = name.lower().replace(" ", "_").replace("-", "_")
    tokens = [t for t in key.split("_") if t]

    # Person-age style metrics (token match avoids most “wage”/substring false positives).
    if "age" in tokens:
        return True

    accident_frags = (
        "previous_accident",
        "prior_accident",
        "num_accident",
        "n_accident",
        "accident_count",
        "count_of_accident",
        "no_of_accidents",
        "number_of_previous_accidents",
    )
    if any(f in key for f in accident_frags):
        return True

    # Typical small discrete household / count features — not process time series.
    for frag in (
        "num_dependents",
        "n_dependents",
        "number_of_dependents",
        "number_of_children",
        "family_size",
        "household_size",
    ):
        if frag in key:
            return True

    return False


def numeric_y_suitable_for_timeseries(y: pd.Series, y_col: str) -> bool:
    """
    Block low-cardinality numerics and year-like metrics from line-over-date charts.

    Uses the same rows as the chart (caller should pass aligned ``y`` after dropna).
    """
    if column_name_blocked_for_timeseries_y(y_col):
        return False

    clean = pd.to_numeric(y, errors="coerce").dropna()
    if len(clean) < 4:
        return False
    nuniq = int(clean.nunique())
    if nuniq < _MIN_DISTINCT_NUMERIC_Y_VALUES:
        return False
    return True
