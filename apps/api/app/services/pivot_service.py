from __future__ import annotations

import numpy as np
import pandas as pd


def run_pivot(
    df: pd.DataFrame,
    rows: list[str],
    cols: list[str],
    values: str,
    aggfunc: str = "sum",
    top_n: int = 20,
) -> dict:
    if not rows:
        raise ValueError("At least one row field is required.")
    if values not in df.columns:
        raise ValueError(f"Values column '{values}' not found.")
    for r in rows:
        if r not in df.columns:
            raise ValueError(f"Row column '{r}' not found.")
    for c in cols:
        if c not in df.columns:
            raise ValueError(f"Column field '{c}' not found.")

    func_map = {
        "sum": "sum",
        "mean": "mean",
        "count": "count",
        "median": "median",
        "min": "min",
        "max": "max",
        "std": "std",
    }
    agg = func_map.get(aggfunc, "sum")

    # for count, any column works; otherwise ensure numeric
    if agg != "count" and not pd.api.types.is_numeric_dtype(df[values]):
        agg = "count"

    index_cols = rows
    column_cols = cols if cols else None

    try:
        pivot = pd.pivot_table(
            df,
            values=values,
            index=index_cols,
            columns=column_cols,
            aggfunc=agg,
            fill_value=0,
            margins=True,
            margins_name="Grand Total",
            observed=True,
        )
    except Exception as e:
        raise ValueError(f"Pivot computation failed: {e}")

    # flatten MultiIndex columns if present
    if isinstance(pivot.columns, pd.MultiIndex):
        pivot.columns = [" | ".join(str(c) for c in col).strip() for col in pivot.columns]

    # limit size
    data_rows = pivot.drop(index="Grand Total", errors="ignore")
    if len(data_rows) > top_n:
        # keep top N by grand total row values or last column
        try:
            last_col = pivot.columns[-1]
            top_idx = data_rows[last_col].nlargest(top_n).index
            pivot = pd.concat([pivot.loc[top_idx], pivot.loc[["Grand Total"]]], axis=0)
        except Exception:
            pivot = pivot.iloc[: top_n + 1]

    # convert to serializable format
    row_labels = [str(idx) if not isinstance(idx, tuple) else " | ".join(str(i) for i in idx) for idx in pivot.index.tolist()]
    col_labels = [str(c) for c in pivot.columns.tolist()]

    pivot_data = []
    for row in pivot.values.tolist():
        pivot_data.append([round(v, 4) if isinstance(v, float) else v for v in row])

    grand_total = None
    try:
        gt_row = pivot.loc["Grand Total"]
        grand_total = float(gt_row.iloc[-1]) if len(gt_row) > 0 else None
    except Exception:
        pass

    return {
        "pivot_data": pivot_data,
        "row_labels": row_labels,
        "col_labels": col_labels,
        "grand_total": grand_total,
        "aggfunc": aggfunc,
        "values_col": values,
        "n_rows": len(pivot),
        "n_cols": len(pivot.columns),
    }
