"""
Backward-compatibility shim for app.services.profiler.

All production callers do:
    from app.services.profiler import profile_dataset, calculate_health_score

test_profiler_edge_cases.py also imports private helpers directly:
    from app.services.profiler import _detect_pattern, _fit_distribution

All symbols are re-exported from the profiling sub-package.
Do not add logic to this file — all logic lives in app.services.profiling.
"""
from app.services.profiling import (  # noqa: F401
    profile_dataset,
    calculate_health_score,
    _detect_pattern,
    _fit_distribution,
)

__all__ = [
    "profile_dataset",
    "calculate_health_score",
    "_detect_pattern",
    "_fit_distribution",
]
