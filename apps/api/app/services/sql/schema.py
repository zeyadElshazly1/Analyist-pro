"""
Dataset schema builder.

get_schema(df) → list[dict]

Returns per-column metadata. Original keys (name, dtype, sample_values)
are preserved; null_pct, cardinality, min, max are additive new keys.
"""
from __future__ import annotations

import pandas as pd


def get_schema(df: pd.DataFrame) -> list[dict]:
    schema: list[dict] = []
    for col in df.columns:
        s = df[col]
        sample = [str(v) for v in s.dropna().unique()[:3].tolist()]
        entry: dict = {
            "name":         col,
            "dtype":        str(s.dtype),
            "sample_values": sample,
            "null_pct":     round(s.isnull().mean() * 100, 1),
            "cardinality":  int(s.nunique()),
        }
        if pd.api.types.is_numeric_dtype(s):
            clean = s.dropna()
            if len(clean):
                entry["min"] = clean.min()
                entry["max"] = clean.max()
        schema.append(entry)
    return schema
