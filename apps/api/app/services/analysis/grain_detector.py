"""
90E — Deterministic grain/entity detector.

Answers: "What does one row in this dataset represent?"
Returns (grain_label, grain_confidence).  Pure functions, no I/O.
"""
from __future__ import annotations

import re

from app.schemas.pre_analysis import ColumnSemanticRole, DatasetFingerprint

# ── Allowed grain labels (matches PreAnalysisProfile.grain_label) ─────────────

_GRAIN_LABELS = frozenset({
    "customer", "order", "policy", "transaction", "event",
    "product", "employee", "time_period", "session", "survey_response", "unknown",
})

# ── Token sets for name-based detection ───────────────────────────────────────

_SESSION_TOKENS    = frozenset({"session"})
_ORDER_TOKENS      = frozenset({"order", "purchase", "invoice", "receipt"})
_POLICY_TOKENS     = frozenset({"policy", "subscription", "contract"})
_TRANSACTION_TOKENS = frozenset({"transaction", "txn", "payment", "amount"})
_CUSTOMER_TOKENS   = frozenset({"customer", "user", "client", "account", "member"})
_PRODUCT_TOKENS    = frozenset({"product", "sku", "item"})
_EMPLOYEE_TOKENS   = frozenset({"employee", "staff", "worker"})
_EVENT_TOKENS      = frozenset({"event", "action", "activity"})
_QUESTION_TOKENS   = frozenset({"question", "survey", "q"})
_QUESTION_PATTERN  = re.compile(r"^(q\d+|question_?\d+|survey_.+)$")


# ── Helpers ───────────────────────────────────────────────────────────────────

def _norm(name: str) -> str:
    return name.strip().lower()


def _parts(name: str) -> set[str]:
    return set(re.split(r"[_\s\-\.]+", _norm(name)))


def _has_any(name: str, tokens: frozenset[str]) -> bool:
    return bool(_parts(name) & tokens)


def _role_names(column_roles: list[ColumnSemanticRole], primary_role: str) -> list[str]:
    """Return column names whose primary_role matches."""
    return [r.column_name for r in column_roles if r.primary_role == primary_role]


def _any_col_has(column_roles: list[ColumnSemanticRole], tokens: frozenset[str]) -> bool:
    """True if any column name contains a token from *tokens*."""
    return any(_has_any(r.column_name, tokens) for r in column_roles)


def _any_role_col_has(
    column_roles: list[ColumnSemanticRole],
    primary_role: str,
    tokens: frozenset[str],
) -> bool:
    """True if any column with *primary_role* has a name token in *tokens*."""
    return any(
        _has_any(r.column_name, tokens)
        for r in column_roles
        if r.primary_role == primary_role
    )


# ── Grain detection ───────────────────────────────────────────────────────────

def detect_grain(
    fingerprint: DatasetFingerprint,
    column_roles: list[ColumnSemanticRole],
) -> tuple[str, float]:
    """Return ``(grain_label, grain_confidence)`` for the dataset.

    Deterministic, non-mutating.  Falls back to ``("unknown", 0.0)`` when
    no signal is strong enough.
    """
    shape = fingerprint.dataset_shape
    has_time  = any(r.primary_role == "time"           for r in column_roles)
    has_tx_id = any(r.primary_role == "transaction_id" for r in column_roles)
    has_ent_id = any(r.primary_role == "entity_id"     for r in column_roles)

    # ── 1. survey_response ────────────────────────────────────────────────────
    if shape == "survey":
        return "survey_response", 0.9

    # Question-field pattern: multiple columns whose names look like q1, q2,
    # question_3, survey_satisfaction, etc.
    question_cols = [
        r for r in column_roles
        if _QUESTION_PATTERN.match(_norm(r.column_name))
        or (_parts(r.column_name) & _QUESTION_TOKENS)
    ]
    if len(question_cols) >= 2:
        return "survey_response", 0.75

    # ── 2. time_period ────────────────────────────────────────────────────────
    if shape == "time_series":
        return "time_period", 0.85

    time_col_count = sum(1 for r in column_roles if r.primary_role == "time")
    if time_col_count >= 1 and not has_tx_id and not has_ent_id:
        # Only classify as time_period when no more specific entity/event/
        # transactional signals exist in column names.
        has_specific = (
            _any_col_has(column_roles, _EVENT_TOKENS)
            or _any_col_has(column_roles, _SESSION_TOKENS)
            or _any_col_has(column_roles, _ORDER_TOKENS)
            or _any_col_has(column_roles, _POLICY_TOKENS)
            or _any_col_has(column_roles, _CUSTOMER_TOKENS)
            or _any_col_has(column_roles, _PRODUCT_TOKENS)
            or _any_col_has(column_roles, _EMPLOYEE_TOKENS)
        )
        if not has_specific:
            return "time_period", 0.7

    # ── 3. event ──────────────────────────────────────────────────────────────
    if shape == "event_log":
        return "event", 0.9

    if has_time and _any_col_has(column_roles, _EVENT_TOKENS):
        return "event", 0.75

    # ── 4. session ────────────────────────────────────────────────────────────
    if _any_role_col_has(column_roles, "transaction_id", _SESSION_TOKENS):
        return "session", 0.85

    if _any_col_has(column_roles, _SESSION_TOKENS):
        return "session", 0.7

    # ── 5. order ──────────────────────────────────────────────────────────────
    if _any_role_col_has(column_roles, "transaction_id", _ORDER_TOKENS):
        return "order", 0.9

    if _any_col_has(column_roles, _ORDER_TOKENS):
        return "order", 0.75

    # ── 6. policy ─────────────────────────────────────────────────────────────
    if _any_role_col_has(column_roles, "transaction_id", _POLICY_TOKENS):
        return "policy", 0.85

    if _any_col_has(column_roles, _POLICY_TOKENS):
        return "policy", 0.7

    # ── 7. transaction ────────────────────────────────────────────────────────
    if shape == "transactional":
        return "transaction", 0.85

    if has_tx_id:
        return "transaction", 0.8

    if _any_col_has(column_roles, _TRANSACTION_TOKENS):
        return "transaction", 0.65

    # ── 8. customer ───────────────────────────────────────────────────────────
    if _any_role_col_has(column_roles, "entity_id", _CUSTOMER_TOKENS):
        return "customer", 0.8

    if _any_col_has(column_roles, _CUSTOMER_TOKENS):
        return "customer", 0.65

    # ── 9. product ────────────────────────────────────────────────────────────
    if _any_role_col_has(column_roles, "entity_id", _PRODUCT_TOKENS):
        return "product", 0.8

    if _any_col_has(column_roles, _PRODUCT_TOKENS):
        return "product", 0.65

    # ── 10. employee ──────────────────────────────────────────────────────────
    if _any_role_col_has(column_roles, "entity_id", _EMPLOYEE_TOKENS):
        return "employee", 0.8

    if _any_col_has(column_roles, _EMPLOYEE_TOKENS):
        return "employee", 0.65

    # ── 11. unknown ───────────────────────────────────────────────────────────
    return "unknown", 0.0
