"""
90D — Deterministic column semantic role classifier.

Assigns one primary semantic role (plus optional secondary roles) to
every column in a DataFrame.  Pure functions, no I/O, no side effects.
"""
from __future__ import annotations

import re

import pandas as pd

from app.schemas.pre_analysis import ColumnSemanticRole, DatasetFingerprint

# ── Token sets ────────────────────────────────────────────────────────────────

_ID_TOKENS = frozenset({"id", "uuid", "guid", "key"})
# Tokens that carry "identifier" meaning even without "id" in the name.
_ID_ADJACENT_TOKENS = frozenset({
    "id", "uuid", "guid", "key", "num", "number", "ref", "code",
})
_ENTITY_TOKENS = frozenset({
    "customer", "user", "account", "member", "employee",
    "product", "client", "vendor", "supplier", "contact", "person",
})
_TRANSACTION_TOKENS = frozenset({
    "transaction", "txn", "order", "purchase", "payment", "invoice",
    "receipt", "booking", "claim", "event", "session",
})
_TIME_NAME_TOKENS = frozenset({"date", "datetime", "timestamp", "time"})
_HELPER_NAME_EXACT = frozenset({
    "index", "row_number", "row_num", "rowid", "row_id",
})
_HELPER_CONTENT_TOKENS = frozenset({"helper", "temp", "tmp", "artifact"})
_DATE_PART_SUFFIXES = frozenset({
    "month", "quarter", "year", "week", "day", "wday",
    "hour", "minute", "second",
})
_GEO_TOKENS = frozenset({
    "country", "region", "state", "province", "city",
    "postal", "postcode", "zip", "latitude", "longitude", "lat", "lon",
})
_RATE_TOKENS = frozenset({"rate", "pct", "percent", "percentage", "ratio"})
_CURRENCY_TOKENS = frozenset({
    "amount", "revenue", "sales", "price", "cost", "profit", "margin",
    "income", "spend", "budget", "fee", "premium",
})
_TARGET_EXPLICIT_TOKENS = frozenset({"target", "label", "outcome", "result"})
_TARGET_INFERRED_TOKENS = frozenset({
    "churn", "converted", "default", "fraud", "attrition",
})
_LEAKAGE_TOKENS = frozenset({
    "post", "after", "future", "leak", "predicted", "prediction",
    "probability", "prob",
})
# Exact substring phrases that signal leakage regardless of other tokens.
# These are checked *before* time-name detection so "closed_date" is not
# misclassified as a time column.
_LEAKAGE_PHRASES = (
    "score_model", "model_score", "outcome_date",
    "closed_date", "resolved_date",
)

_BOOLEAN_PAIRS: list[frozenset[str]] = [
    frozenset({"true", "false"}),
    frozenset({"yes", "no"}),
    frozenset({"y", "n"}),
    frozenset({"1", "0"}),
    frozenset({"t", "f"}),
    frozenset({"on", "off"}),
]


# ── Column-level helpers ──────────────────────────────────────────────────────

def _norm_col(name: str) -> str:
    return name.strip().lower()


def _token_parts(name: str) -> set[str]:
    return set(re.split(r"[_\s\-\.]+", _norm_col(name)))


def _missing_rate(series: pd.Series) -> float:
    if len(series) == 0:
        return 0.0
    return float(series.isna().sum()) / len(series)


def _cardinality(series: pd.Series) -> int:
    return int(series.nunique(dropna=True))


def _unique_rate(series: pd.Series) -> float:
    non_null = series.dropna()
    if len(non_null) == 0:
        return 0.0
    return non_null.nunique() / len(non_null)


def _is_boolean_like(series: pd.Series) -> bool:
    if series.dtype == bool:
        return True
    non_null = series.dropna()
    if len(non_null) == 0:
        return False
    unique_vals = non_null.unique()
    if len(unique_vals) > 2:
        return False
    if pd.api.types.is_numeric_dtype(series):
        return set(unique_vals).issubset({0, 1, 0.0, 1.0})
    if pd.api.types.is_object_dtype(series) or pd.api.types.is_string_dtype(series):
        str_vals = frozenset(str(v).strip().lower() for v in unique_vals)
        return any(str_vals == pair for pair in _BOOLEAN_PAIRS)
    return False


def _is_free_text(series: pd.Series) -> bool:
    if not (pd.api.types.is_object_dtype(series) or pd.api.types.is_string_dtype(series)):
        return False
    non_null = series.dropna().astype(str)
    if len(non_null) == 0:
        return False
    return non_null.str.len().mean() >= 30 and non_null.nunique() / len(non_null) >= 0.5


# ── Single-column classifier ──────────────────────────────────────────────────

def _classify_column(
    name: str,
    series: pd.Series,
    row_count: int,
) -> ColumnSemanticRole:
    """Return a :class:`ColumnSemanticRole` for one column."""
    norm = _norm_col(name)
    parts = _token_parts(name)
    miss_rate = _missing_rate(series)
    card = _cardinality(series)
    urate = _unique_rate(series)

    def _make(
        primary: str,
        confidence: float,
        notes: str | None = None,
        extra_secondary: list[str] | None = None,
    ) -> ColumnSemanticRole:
        sec = list(extra_secondary or [])
        seen: set[str] = set()
        deduped: list[str] = []
        for r in sec:
            if r != primary and r not in seen:
                seen.add(r)
                deduped.append(r)
        return ColumnSemanticRole(
            column_name=name,
            primary_role=primary,
            secondary_roles=deduped,
            role_confidence=confidence,
            cardinality=card,
            missing_rate=miss_rate,
            notes=notes,
        )

    # ── 0. Phrase-level leakage ────────────────────────────────────────────────
    # Checked first so "closed_date" / "resolved_date" are not misclassified
    # as time columns by the name-token check below.
    if any(phrase in norm for phrase in _LEAKAGE_PHRASES):
        return _make(
            "leakage_candidate", 0.7,
            notes="Potential target leakage or post-outcome signal.",
        )

    # ── 1. helper_artifact ────────────────────────────────────────────────────
    if norm.startswith("unnamed"):
        return _make("helper_artifact", 0.9, "Unnamed column — likely a pandas index artefact.")
    if norm in _HELPER_NAME_EXACT:
        return _make("helper_artifact", 0.9, "Row-index or surrogate key column.")
    if parts & _HELPER_CONTENT_TOKENS:
        return _make("helper_artifact", 0.9, "Temporary or helper column.")
    last_part = re.split(r"[_\s\-\.]+", norm)[-1]
    if last_part in _DATE_PART_SUFFIXES:
        return _make("helper_artifact", 0.75, "Possible date-part extraction artefact.")

    # ── 2. time ───────────────────────────────────────────────────────────────
    if pd.api.types.is_datetime64_any_dtype(series):
        return _make("time", 0.95)
    if parts & _TIME_NAME_TOKENS:
        return _make("time", 0.8)
    if norm.endswith("_at") or norm.endswith("_on"):
        return _make("time", 0.8)

    # ── 3. target (explicit names — before boolean_flag) ──────────────────────
    # Columns explicitly named as targets must not be demoted to boolean_flag
    # just because their values happen to be binary.
    if parts & _TARGET_EXPLICIT_TOKENS:
        extra = ["boolean_flag"] if _is_boolean_like(series) else []
        return _make("target", 0.75, extra_secondary=extra)

    # ── 4. target (inferred from known-target-name + boolean structure) ───────
    # Must come before generic boolean_flag so "churn", "fraud", etc. route here.
    if (parts & _TARGET_INFERRED_TOKENS) and _is_boolean_like(series):
        return _make("target", 0.65, extra_secondary=["boolean_flag"])

    # ── 5. boolean_flag ───────────────────────────────────────────────────────
    if _is_boolean_like(series):
        conf = 0.95 if series.dtype == bool else 0.85
        return _make("boolean_flag", conf, extra_secondary=["dimension"])

    # ── 6. transaction_id ─────────────────────────────────────────────────────
    # Require an id-adjacent token AND a transaction token to avoid false
    # positives on columns like "event_type" or "session_duration".
    if (parts & _ID_ADJACENT_TOKENS) and (parts & _TRANSACTION_TOKENS) and urate >= 0.75:
        return _make("transaction_id", 0.9)

    # ── 7. entity_id ──────────────────────────────────────────────────────────
    has_id_signal = bool(parts & _ID_TOKENS) or bool(parts & _ENTITY_TOKENS)
    if has_id_signal and urate >= 0.75:
        return _make("entity_id", 0.85)

    # ── 8. free_text ──────────────────────────────────────────────────────────
    if _is_free_text(series):
        return _make("free_text", 0.85)

    # ── 9. leakage_candidate (token-level) ────────────────────────────────────
    if parts & _LEAKAGE_TOKENS:
        return _make(
            "leakage_candidate", 0.7,
            notes="Potential target leakage or post-outcome signal.",
        )

    # ── 10. target (bounded score / probability signal) ───────────────────────
    if (parts & {"score", "probability", "prob"}) and pd.api.types.is_numeric_dtype(series):
        non_null = series.dropna()
        if len(non_null) > 0:
            if (non_null >= 0).all() and (non_null <= 1).all():
                return _make("target", 0.65, extra_secondary=["rate_percentage"])

    # ── 11. geographic ────────────────────────────────────────────────────────
    if parts & _GEO_TOKENS:
        return _make("geographic", 0.8, extra_secondary=["dimension"])

    # ── 12. rate_percentage ───────────────────────────────────────────────────
    if parts & _RATE_TOKENS:
        return _make("rate_percentage", 0.85, extra_secondary=["metric"])

    # ── 13. currency_amount ───────────────────────────────────────────────────
    if parts & _CURRENCY_TOKENS:
        return _make("currency_amount", 0.8, extra_secondary=["metric"])

    # ── 14. metric ────────────────────────────────────────────────────────────
    if pd.api.types.is_numeric_dtype(series) and not _is_boolean_like(series):
        extra: list[str] = []
        non_null = series.dropna()
        if len(non_null) >= 5 and (non_null >= 0).all() and (non_null <= 1).all():
            extra.append("rate_percentage")
        return _make("metric", 0.7, extra_secondary=extra)

    # ── 15. dimension ─────────────────────────────────────────────────────────
    is_cat = (
        pd.api.types.is_object_dtype(series)
        or pd.api.types.is_string_dtype(series)
        or hasattr(series, "cat")
    )
    if is_cat and not _is_free_text(series):
        upper = min(50, max(2, int(row_count * 0.5)))
        if 2 <= card <= upper:
            return _make("dimension", 0.7)

    # ── 16. unknown ───────────────────────────────────────────────────────────
    return _make("unknown", 0.2, notes="No strong semantic role detected.")


# ── Public API ────────────────────────────────────────────────────────────────

def classify_column_roles(
    df: pd.DataFrame,
    fingerprint: DatasetFingerprint | None = None,
) -> list[ColumnSemanticRole]:
    """Return one :class:`ColumnSemanticRole` per column in *df*.

    If *fingerprint* is None it is computed on the fly (cheap, deterministic).
    Does not mutate *df*.
    """
    if fingerprint is None:
        from app.services.analysis.fingerprint import extract_dataset_fingerprint
        fingerprint = extract_dataset_fingerprint(df)

    row_count = fingerprint.row_count
    return [
        _classify_column(col, df[col], row_count)
        for col in df.columns
    ]
