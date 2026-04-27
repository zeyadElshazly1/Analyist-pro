"""
Analyst Pro reporting package.

Re-exports the public API used by app.services.report_service (shim)
and app.routes.reports.
"""
from .draft_context import apply_draft_to_result  # noqa: F401
from .excel_report import generate_excel_report  # noqa: F401
from .html_report import generate_html_report    # noqa: F401
from .pdf_report import generate_pdf_report      # noqa: F401

__all__ = [
    "generate_html_report",
    "generate_pdf_report",
    "generate_excel_report",
    "apply_draft_to_result",
]
