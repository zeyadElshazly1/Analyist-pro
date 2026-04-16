"""
Excel data-rectangle finder.

Uses openpyxl in read-only mode to scan the first 50 rows × 30 cols and
locate the first row that contains ≥3 non-null, non-empty cells.
That row is assumed to be the actual header, so `skiprows` returns the number
of decorative/blank rows before it.
"""
from __future__ import annotations

from pathlib import Path


def find_data_region(path: Path, sheet_index: int = 0) -> dict:
    """
    Returns {"skiprows": N | None} where N is the number of rows to skip
    before the real header, detected by scanning the sheet for the first
    row with ≥3 non-null cells.
    """
    try:
        import openpyxl
        wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
        if not wb.worksheets:
            wb.close()
            return {"skiprows": None}

        idx = min(sheet_index, len(wb.worksheets) - 1)
        ws = wb.worksheets[idx]

        skiprows: int | None = None
        for row_idx, row in enumerate(ws.iter_rows(max_row=50, max_col=30, values_only=True)):
            non_null = sum(
                1 for c in row if c is not None and str(c).strip()
            )
            if non_null >= 3:
                skiprows = row_idx if row_idx > 0 else None
                break

        wb.close()
        return {"skiprows": skiprows}

    except Exception:
        return {"skiprows": None}
