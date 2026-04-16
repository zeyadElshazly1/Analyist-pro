"""
Analyst Pro charting package.

Re-exports the public API used by app.services.chart_builder and
app.routes.charts.  All logic lives in sub-modules; do not add logic here.
"""
from .orchestrator import build_chart_data  # noqa: F401

__all__ = ["build_chart_data"]
