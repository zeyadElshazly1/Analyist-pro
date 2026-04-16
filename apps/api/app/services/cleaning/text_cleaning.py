"""
Text normalization helpers.

Handles: placeholder replacement, whitespace stripping, casing normalization.
"""
import numpy as np
import pandas as pd

from .constants import _PLACEHOLDER_STRINGS


def _replace_placeholders(df: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    """
    Replace known placeholder strings (N/A, None, null, -, ?, unknown, …)
    with NaN across all object/string columns.
    Returns the modified DataFrame and the total count of replacements.
    """
    total_replaced = 0
    for col in df.select_dtypes(include=["object"]).columns:
        lower = df[col].astype(str).str.strip().str.lower()
        mask = lower.isin(_PLACEHOLDER_STRINGS) & df[col].notna()
        n = int(mask.sum())
        if n > 0:
            df[col] = df[col].where(~mask, other=np.nan)
            total_replaced += n
    return df, total_replaced


def strip_whitespace(
    df: pd.DataFrame,
    protected_cols: set[str] | None = None,
) -> tuple[pd.DataFrame, int, list[str]]:
    """Strip leading/trailing whitespace from all object columns.

    protected_cols: semantic columns to skip (whitespace stripping is generally
    safe, but caller can still opt out for specific columns).
    """
    protected_cols = protected_cols or set()
    str_cols = df.select_dtypes(include="object").columns.tolist()
    total_stripped = 0
    cols_stripped: list[str] = []
    for col in str_cols:
        if col in protected_cols:
            continue
        before = df[col].copy()
        df[col] = df[col].str.strip()
        n_changed = int((before != df[col]).sum())
        if n_changed > 0:
            total_stripped += n_changed
            cols_stripped.append(col)
    return df, total_stripped, cols_stripped


def normalize_casing(
    df: pd.DataFrame,
    protected_cols: set[str] | None = None,
    mode: str = "aggressive",
) -> tuple[pd.DataFrame, list[str]]:
    """Normalize ALL-CAPS string columns to Title Case.

    Protected columns (IDs, SKUs, phone numbers, etc.) are never title-cased
    regardless of mode — reformatting them would corrupt their values.

    In safe mode, no mutations are applied.
    """
    protected_cols = protected_cols or set()
    cols_changed: list[str] = []
    for col in df.select_dtypes(include="object").columns:
        if col in protected_cols:
            continue
        sample = df[col].dropna().head(50)
        if len(sample) == 0:
            continue
        upper_ratio = sample.apply(lambda x: str(x).isupper()).mean()
        if upper_ratio > 0.7:
            if mode == "aggressive":
                df[col] = df[col].str.title()
            cols_changed.append(col)
    return df, cols_changed
