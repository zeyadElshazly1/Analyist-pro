"""
Adapter: ParseReport + DataFrame + ProjectFile → canonical IntakeResult.

This is the single place that translates the raw ingestion output into the
schema contract. All other code should consume IntakeResult, not ParseReport.
"""
from __future__ import annotations

import math
from typing import Any

import pandas as pd

from app.models import ProjectFile
from app.schemas.intake import IntakeResult
from app.services.ingestion.report import ParseReport

_PREVIEW_ROWS = 10


def build_intake_result(
    project_file: ProjectFile,
    df: pd.DataFrame,
    report: ParseReport,
) -> IntakeResult:
    """
    Convert ingestion output to a canonical IntakeResult.

    Args:
        project_file: The DB record for the uploaded file.
        df:           The loaded (post-cleanup) DataFrame.
        report:       ParseReport populated by file_loader.

    Returns:
        A fully-populated IntakeResult ready for serialisation.
    """
    footer_rows = _footer_rows(report)
    preview = _preview_sample(df)

    return IntakeResult(
        file_id=project_file.id,
        file_name=project_file.filename,
        parse_status=report.status,                        # type: ignore[arg-type]
        confidence=round(report.confidence, 4),
        file_kind=report.file_kind,                        # type: ignore[arg-type]
        detected_header_row=report.header_row or 0,
        preamble_rows=list(report.metadata_rows),
        footer_rows=footer_rows,
        delimiter=report.delimiter,
        encoding=report.encoding,
        n_columns=report.n_columns or len(df.columns),
        warnings=list(report.warnings),
        parsing_decisions=list(report.parsing_decisions),
        file_metadata=dict(report.metadata),
        preview_sample=preview,
    )


# ── Helpers ───────────────────────────────────────────────────────────────────

def _footer_rows(report: ParseReport) -> list[int]:
    """Convert the single footer_start_row int to a list[int]."""
    if report.footer_start_row is None:
        return []
    return [report.footer_start_row]


def _preview_sample(df: pd.DataFrame) -> list[dict[str, Any]]:
    """
    Return the first N rows as a list of column→value dicts.

    NaN / inf values are replaced with None so the result is always
    JSON-serialisable without a custom encoder.
    """
    sample = df.head(_PREVIEW_ROWS)
    records: list[dict[str, Any]] = []
    for _, row in sample.iterrows():
        record: dict[str, Any] = {}
        for col, val in row.items():
            if _is_scalar_nan(val):
                record[str(col)] = None
            elif isinstance(val, float) and math.isinf(val):
                record[str(col)] = None
            else:
                record[str(col)] = val
        records.append(record)
    return records


def _is_scalar_nan(val: Any) -> bool:
    try:
        return isinstance(val, float) and math.isnan(val)
    except (TypeError, ValueError):
        return False
