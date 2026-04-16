"""
Analyst Pro analysis package.

Re-exports the three public symbols that all callers import from
app.services.analyzer. All logic lives in the sub-modules; this file
is a pure re-export shim.
"""
from .orchestrator import (  # noqa: F401
    analyze_dataset,
    generate_executive_panel,
    get_dataset_summary,
)

__all__ = [
    "analyze_dataset",
    "generate_executive_panel",
    "get_dataset_summary",
]
