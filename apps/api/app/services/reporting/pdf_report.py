"""
PDF report generator.

generate_pdf_report(df, analysis_result, project_name) → bytes

Fallback chain:
  1. WeasyPrint  (if installed)
  2. pdfkit      (if wkhtmltopdf binary is available)
  3. HTML bytes  (caller already handles via b"%PDF" MIME sniff in the route)
"""
from __future__ import annotations

import logging

import pandas as pd

from .html_report import generate_html_report

logger = logging.getLogger(__name__)


def generate_pdf_report(
    df: pd.DataFrame,
    analysis_result: dict,
    project_name: str = "Dataset Analysis",
) -> bytes:
    html = generate_html_report(df, analysis_result, project_name)

    # 1. WeasyPrint
    try:
        from weasyprint import HTML  # noqa: PLC0415
        return HTML(string=html).write_pdf()
    except ImportError:
        pass
    except Exception as exc:
        logger.warning("WeasyPrint failed: %s — trying pdfkit", exc)

    # 2. pdfkit / wkhtmltopdf
    try:
        import pdfkit  # noqa: PLC0415
        return pdfkit.from_string(html, False)
    except ImportError:
        pass
    except Exception as exc:
        logger.warning("pdfkit failed: %s — returning HTML bytes", exc)

    # No PDF renderer available — raise so the route returns a proper error
    raise RuntimeError(
        "PDF generation unavailable: neither WeasyPrint nor wkhtmltopdf is installed. "
        "Use the Excel or HTML export instead."
    )
