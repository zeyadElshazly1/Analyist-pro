"""
Analyst Pro profiling package.

Re-exports the public API and the private helpers that tests import directly
from app.services.profiler. All production callers should use profile_dataset
and calculate_health_score.
"""
from .orchestrator import profile_dataset          # noqa: F401
from .health_scorer import calculate_health_score  # noqa: F401
from .patterns import _detect_pattern             # noqa: F401
from .distributions import _fit_distribution      # noqa: F401

__all__ = [
    "profile_dataset",
    "calculate_health_score",
    "_detect_pattern",
    "_fit_distribution",
]
