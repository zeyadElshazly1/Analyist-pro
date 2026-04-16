"""
Backward-compatibility shim for app.services.report_service.

All production callers do:
    from app.services.report_service import generate_excel_report, generate_html_report, generate_pdf_report

All logic lives in app.services.reporting.
Do not add logic to this file.
"""
from app.services.reporting import (  # noqa: F401
    generate_excel_report,
    generate_html_report,
    generate_pdf_report,
)

__all__ = ["generate_html_report", "generate_pdf_report", "generate_excel_report"]
