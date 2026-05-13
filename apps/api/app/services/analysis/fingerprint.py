"""
90C — Deterministic dataset fingerprint extractor.

Computes objective, structural facts about a DataFrame before any
analysis detector runs.  Pure functions, no I/O, no side effects.
"""
from __future__ import annotations

import re

import pandas as pd

from app.schemas.pre_analysis import DatasetFingerprint

# ── Token sets used by the shape classifier ───────────────────────────────────

_EVENT_TOKENS = frozenset({
    "event", "action", "activity", "type", "kind", "category",
    "status", "state", "operation", "op", "event_type", "action_type",
})
_ENTITY_TOKENS = frozenset({
    "id", "uuid", "guid", "key", "customer", "user", "account",
    "client", "member", "person", "employee", "staff", "vendor",
    "supplier", "partner", "contact",
})
_TRANSACTION_TOKENS = frozenset({
    "transaction", "txn", "order", "purchase", "payment", "invoice",
    "sale", "receipt", "booking", "reservation", "amount", "price",
    "cost", "revenue", "qty", "quantity", "units", "total",
})
_BOOLEAN_PAIRS: list[frozenset[str]] = [
    frozenset({"true", "false"}),
    frozenset({"yes", "no"}),
    frozenset({"y", "n"}),
    frozenset({"1", "0"}),
    frozenset({"t", "f"}),
    frozenset({"on", "off"}),
]


# ── Column-level helpers ──────────────────────────────────────────────────────

def _has_token(name: str, tokens: frozenset[str]) -> bool:
    """Return True if any token in *tokens* appears as a word in *name*."""
    parts = re.split(r"[_\s\-\.]+", name.lower())
    return bool(parts and tokens.intersection(parts))


def _is_boolean_like(series: pd.Series) -> bool:
    """True if the series looks like a boolean column.

    Covers:
    - actual bool dtype
    - numeric columns with only {0, 1}
    - object/string columns whose non-null unique values form a known
      true/false pair (case-insensitive)
    """
    if series.dtype == bool:
        return True

    non_null = series.dropna()
    if len(non_null) == 0:
        return False

    unique_vals = non_null.unique()
    if len(unique_vals) > 2:
        return False

    # Numeric {0, 1}
    if pd.api.types.is_numeric_dtype(series):
        return set(unique_vals).issubset({0, 1, 0.0, 1.0})

    # String pairs
    if pd.api.types.is_object_dtype(series) or pd.api.types.is_string_dtype(series):
        str_vals = frozenset(str(v).strip().lower() for v in unique_vals)
        return any(str_vals == pair for pair in _BOOLEAN_PAIRS)

    return False


def _is_free_text(series: pd.Series) -> bool:
    """True if the series looks like a free-text column.

    Heuristic: object/string dtype, average non-null string length >= 30,
    and unique rate >= 0.5.
    """
    if not (pd.api.types.is_object_dtype(series) or pd.api.types.is_string_dtype(series)):
        return False

    non_null = series.dropna().astype(str)
    if len(non_null) == 0:
        return False

    avg_len = non_null.str.len().mean()
    unique_rate = non_null.nunique() / len(non_null)

    return avg_len >= 30 and unique_rate >= 0.5


def _is_entity_like_column(name: str, series: pd.Series) -> bool:
    """True if the column looks like a high-cardinality entity/ID column."""
    if not _has_token(name, _ENTITY_TOKENS):
        return False
    non_null = series.dropna()
    if len(non_null) == 0:
        return False
    unique_rate = non_null.nunique() / len(non_null)
    return unique_rate >= 0.8


# ── Column type counts ────────────────────────────────────────────────────────

def _count_column_types(df: pd.DataFrame) -> dict[str, int]:
    """Classify each column and return counts per category."""
    counts = {
        "numeric": 0,
        "datetime": 0,
        "boolean": 0,
        "free_text": 0,
        "categorical": 0,
    }
    for col in df.columns:
        s = df[col]

        if pd.api.types.is_datetime64_any_dtype(s):
            counts["datetime"] += 1
            continue

        if _is_boolean_like(s):
            counts["boolean"] += 1
            continue

        if pd.api.types.is_numeric_dtype(s):
            counts["numeric"] += 1
            continue

        if _is_free_text(s):
            counts["free_text"] += 1
            continue

        # object, category, string, or anything else
        counts["categorical"] += 1

    return counts


# ── Missingness and density ───────────────────────────────────────────────────

def _compute_missing_rate(df: pd.DataFrame) -> float:
    total = df.size
    if total == 0:
        return 0.0
    return float(df.isna().sum().sum()) / total


def _compute_data_density(df: pd.DataFrame) -> float:
    total = df.size
    if total == 0:
        return 0.0

    non_empty = df.notna()
    for col in df.columns:
        if pd.api.types.is_object_dtype(df[col]) or pd.api.types.is_string_dtype(df[col]):
            non_empty[col] = non_empty[col] & df[col].astype(str).str.strip().ne("")

    return float(non_empty.sum().sum()) / total


# ── Shape classifier ──────────────────────────────────────────────────────────

def _classify_dataset_shape(
    df: pd.DataFrame,
    counts: dict[str, int],
) -> str:
    """Deterministic, domain-generic dataset shape classification."""
    rows = len(df)
    cols = len(df.columns)

    if rows == 0 or cols == 0:
        return "unknown"

    n_datetime = counts["datetime"]
    n_numeric = counts["numeric"]
    n_categorical = counts["categorical"]
    n_boolean = counts["boolean"]

    # ── event_log: timestamp + event/action/status column ─────────────────────
    if n_datetime >= 1 and rows >= 5:
        if any(_has_token(c, _EVENT_TOKENS) for c in df.columns):
            return "event_log"

    # ── panel_data: datetime + entity-named column (checked before time_series
    #    because panel entity columns are often numeric IDs with moderate
    #    cardinality — too low for _is_entity_like_column's 0.8 threshold) ─────
    if n_datetime >= 1 and rows >= 5:
        if any(_has_token(c, _ENTITY_TOKENS) for c in df.columns):
            return "panel_data"

    # ── time_series: datetime + numerics, few categorical columns ─────────────
    if n_datetime >= 1 and n_numeric >= 1 and n_categorical <= 2 and rows >= 5:
        return "time_series"

    # ── survey: many categorical/boolean columns, few numerics ────────────────
    if cols >= 5 and (n_categorical + n_boolean) >= 4 and n_numeric <= 2:
        return "survey"

    # ── transactional: transaction/order/payment token in columns (checked
    #    before entity_table so "order_id" routes here, not entity_table) ──────
    if rows >= 5:
        if any(_has_token(c, _TRANSACTION_TOKENS) for c in df.columns):
            return "transactional"

    # ── entity_table: high-cardinality entity-ID column, no datetime ──────────
    if n_datetime == 0:
        if any(_is_entity_like_column(c, df[c]) for c in df.columns):
            return "entity_table"

    # ── snapshot: non-empty, unclassified ─────────────────────────────────────
    if rows > 0 and cols > 0:
        return "snapshot"

    return "unknown"


# ── Public API ────────────────────────────────────────────────────────────────

def extract_dataset_fingerprint(df: pd.DataFrame) -> DatasetFingerprint:
    """Return a :class:`DatasetFingerprint` for *df*.

    Deterministic — produces the same result for the same DataFrame on every
    call.  No I/O, no side effects.
    """
    row_count = len(df)
    column_count = len(df.columns)

    if column_count == 0:
        return DatasetFingerprint(
            row_count=row_count,
            column_count=0,
            dataset_shape="unknown",
            overall_data_density=0.0,
        )

    counts = _count_column_types(df)
    missing_rate = _compute_missing_rate(df)
    data_density = _compute_data_density(df)
    duplicate_count = int(df.duplicated().sum()) if row_count > 0 else 0
    shape = _classify_dataset_shape(df, counts)

    return DatasetFingerprint(
        row_count=row_count,
        column_count=column_count,
        numeric_column_count=counts["numeric"],
        categorical_column_count=counts["categorical"],
        datetime_column_count=counts["datetime"],
        boolean_column_count=counts["boolean"],
        free_text_column_count=counts["free_text"],
        overall_missing_rate=missing_rate,
        duplicate_row_count=duplicate_count,
        overall_data_density=data_density,
        dataset_shape=shape,
    )
