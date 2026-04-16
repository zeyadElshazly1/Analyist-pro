"""Column comparison dispatcher."""
from __future__ import annotations

import pandas as pd

from .cat_cat import compare_cat_cat
from .num_cat import compare_num_cat
from .num_num import compare_num_num


def get_columns(df: pd.DataFrame) -> list[str]:
    return df.columns.tolist()


def compare_columns(df: pd.DataFrame, col_a: str, col_b: str) -> dict:
    if col_a not in df.columns:
        raise ValueError(f"Column '{col_a}' not found")
    if col_b not in df.columns:
        raise ValueError(f"Column '{col_b}' not found")
    if col_a == col_b:
        raise ValueError("Please select two different columns")

    a_is_numeric = pd.api.types.is_numeric_dtype(df[col_a])
    b_is_numeric = pd.api.types.is_numeric_dtype(df[col_b])

    if a_is_numeric and b_is_numeric:
        return compare_num_num(df, col_a, col_b)
    elif a_is_numeric and not b_is_numeric:
        return compare_num_cat(df, col_a, col_b)
    elif not a_is_numeric and b_is_numeric:
        return compare_num_cat(df, col_b, col_a, flipped=True)
    else:
        return compare_cat_cat(df, col_a, col_b)
