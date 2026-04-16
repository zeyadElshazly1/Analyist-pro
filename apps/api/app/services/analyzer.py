"""
Backward-compatibility shim for app.services.analyzer.

All production callers do:
    from app.services.analyzer import analyze_dataset            # 5+ callers
    from app.services.analyzer import generate_executive_panel   # 1 caller
    from app.services.analyzer import get_dataset_summary        # 4+ callers

All symbols are re-exported from the analysis sub-package.
Do not add logic to this file — all logic lives in app.services.analysis.
"""
from app.services.analysis import (  # noqa: F401
    analyze_dataset,
    generate_executive_panel,
    get_dataset_summary,
)

__all__ = [
    "analyze_dataset",
    "generate_executive_panel",
    "get_dataset_summary",
]
