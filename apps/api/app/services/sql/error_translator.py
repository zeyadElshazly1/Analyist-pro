"""
DuckDB error translator.

translate_error(exc, df_columns) → human-readable str

Uses difflib fuzzy matching to suggest correct column names when DuckDB
reports a "column not found" error with a typo.
"""
from __future__ import annotations

import difflib
import re


def translate_error(exc: Exception, df_columns: list[str]) -> str:
    msg = str(exc)

    # Column not found — fuzzy-match against actual column names
    col_m = re.search(
        r'(?:column|field)\s+"?([^"]+?)"?\s+(?:not found|does not exist)',
        msg,
        re.IGNORECASE,
    )
    if col_m:
        bad = col_m.group(1).strip()
        close = difflib.get_close_matches(bad, df_columns, n=1, cutoff=0.6)
        if close:
            return f"Column '{bad}' not found. Did you mean '{close[0]}'?"
        cols_preview = ", ".join(df_columns[:10])
        suffix = f" and {len(df_columns) - 10} more" if len(df_columns) > 10 else ""
        return f"Column '{bad}' not found. Available columns: {cols_preview}{suffix}."

    # Table not found — remind the user of the registered table name
    if re.search(r"table.*(?:not found|does not exist)", msg, re.IGNORECASE):
        return "Table not found. Use 'data' as the table name (e.g. SELECT * FROM data)."

    # Syntax error — strip noisy token positions
    if "syntax error" in msg.lower():
        clean = msg.split("LINE")[0].strip()
        return f"SQL syntax error: {clean}"

    return f"Query failed: {msg}"
