"""
Backward-compatibility shim for app.services.chart_builder.

All production callers do:
    from app.services.chart_builder import build_chart_data

All logic lives in app.services.charting.
Do not add logic to this file.
"""
from app.services.charting import build_chart_data  # noqa: F401

__all__ = ["build_chart_data"]
