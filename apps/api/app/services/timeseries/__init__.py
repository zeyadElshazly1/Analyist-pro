"""
Analyst Pro time-series package.

Re-exports the public API used by app.services.timeseries (shim)
and app.routes.explore.
"""
from .engine import detect_date_columns, run_timeseries  # noqa: F401

__all__ = ["detect_date_columns", "run_timeseries"]
