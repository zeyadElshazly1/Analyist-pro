"""Post-load schema normalization."""
from __future__ import annotations

import pandas as pd

from .report import ParseReport


def normalize_schema(df: pd.DataFrame, report: ParseReport) -> pd.DataFrame:
    """
    Clean up structural issues introduced by messy source files:

    1. Drop fully blank rows and columns
    2. Strip leading/trailing 'Unnamed: X' edge columns (openpyxl/pandas artefact)
    3. Coerce column names to clean strings
    4. Deduplicate column names (age → age, age_1, age_2 …)
    5. Remove rows that repeat the header (pagination artefact)
    """
    # 1. Drop fully blank rows and columns
    df = df.dropna(how="all", axis=0).dropna(how="all", axis=1)

    if df.empty:
        return df

    # 2. Strip Unnamed: X edge columns
    cols = list(df.columns)
    while cols and str(cols[0]).startswith("Unnamed:"):
        cols.pop(0)
        df = df.iloc[:, 1:]
    while cols and str(cols[-1]).startswith("Unnamed:"):
        cols.pop()
        df = df.iloc[:, :-1]

    if df.empty:
        return df

    # 3. Coerce to clean strings
    df.columns = [str(c).strip() for c in df.columns]

    # 4. Deduplicate column names
    seen: dict[str, int] = {}
    new_cols: list[str] = []
    for c in df.columns:
        if c in seen:
            seen[c] += 1
            new_cols.append(f"{c}_{seen[c]}")
        else:
            seen[c] = 0
            new_cols.append(c)
    df.columns = new_cols

    # 5. Remove repeated header rows inside data body
    header_set = {c.lower().strip() for c in df.columns}

    def _looks_like_header(row: pd.Series) -> bool:
        vals = [str(v).lower().strip() for v in row if str(v).strip()]
        if len(vals) < 2:
            return False
        return sum(v in header_set for v in vals) / len(vals) > 0.7

    mask = df.apply(_looks_like_header, axis=1)
    n_removed = int(mask.sum())
    if n_removed:
        df = df[~mask]
        report.warnings.append(
            f"Removed {n_removed} repeated header row(s) inside data body"
        )

    return df.reset_index(drop=True)
