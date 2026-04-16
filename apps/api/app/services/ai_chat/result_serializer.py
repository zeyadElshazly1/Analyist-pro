"""
Result serialization and chart hint helpers.

_result_to_serializable — convert any pandas/numpy/python result to JSON-safe types
_suggest_chart          — heuristically suggest a chart type from result shape
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def _result_to_serializable(result: object) -> tuple[str, list | None, float | str | None]:
    """
    Convert an arbitrary query result to (result_type, table_data, number_result).

    result_type  : "table" | "number" | "text"
    table_data   : list[dict] (up to 20 rows) or None
    number_result: float | str | None
    """
    if result is None:
        return "text", None, None

    if isinstance(result, pd.DataFrame):
        return "table", result.head(20).to_dict(orient="records"), None

    if isinstance(result, pd.Series):
        df_res = result.reset_index().head(20)
        return "table", df_res.to_dict(orient="records"), None

    if isinstance(result, (int, float, np.integer, np.floating)):
        return "number", None, round(float(result), 6)

    if isinstance(result, str):
        return "text", None, None

    # Try coercing to DataFrame
    try:
        df_res = pd.DataFrame(result)
        return "table", df_res.head(20).to_dict(orient="records"), None
    except Exception:
        return "text", None, str(result)


def _suggest_chart(
    result_type: str,
    table_data: list | None,
) -> dict | None:
    """
    Heuristically suggest a chart type from the query result shape.
    Returns a hint dict consumed by the frontend, or None.
    """
    if result_type == "number":
        return {"type": "kpi"}

    if result_type != "table" or not table_data or len(table_data) < 2:
        return None

    cols = list(table_data[0].keys())
    if len(cols) < 2:
        return None

    def _is_numeric(col: str) -> bool:
        for row in table_data[:10]:
            v = row.get(col)
            if v is None or v == "":
                continue
            try:
                float(v)
            except (TypeError, ValueError):
                return False
        return True

    numeric_cols = [c for c in cols if _is_numeric(c)]
    cat_cols     = [c for c in cols if c not in numeric_cols]

    # categorical + numeric → bar
    if cat_cols and numeric_cols:
        return {"type": "bar", "x_col": cat_cols[0], "y_col": numeric_cols[0]}

    # 2+ numeric → scatter (large) or bar (small)
    if len(numeric_cols) >= 2:
        if len(table_data) > 20:
            return {"type": "scatter", "x_col": numeric_cols[0], "y_col": numeric_cols[1]}
        return {"type": "bar", "x_col": numeric_cols[0], "y_col": numeric_cols[1]}

    return None
