"""
Canonical plan name constants for the entire backend.

All plan string literals must come from here.
Do not hardcode "pro", "team", "consultant", "studio", or "free" anywhere else.
"""
from __future__ import annotations

PLAN_FREE       = "free"
PLAN_CONSULTANT = "consultant"
PLAN_STUDIO     = "studio"

PLAN_VALUES: set[str] = {
    PLAN_FREE,
    PLAN_CONSULTANT,
    PLAN_STUDIO,
}

PLAN_LABELS: dict[str, str] = {
    PLAN_FREE:       "Free",
    PLAN_CONSULTANT: "Consultant",
    PLAN_STUDIO:     "Studio",
}

PLAN_ORDER: list[str] = [PLAN_FREE, PLAN_CONSULTANT, PLAN_STUDIO]

# Legacy DB values → canonical names.  Remove once the DB migration runs.
_LEGACY_NAME_MAP: dict[str, str] = {
    "pro":  PLAN_CONSULTANT,
    "team": PLAN_STUDIO,
}


def normalize_plan(plan: str | None) -> str:
    """Return the canonical plan name, mapping legacy 'pro'/'team' if needed.

    Unknown / unrecognised values fall back to ``PLAN_FREE`` so downstream
    plan checks never raise on dirty data (legacy DB rows, typos in env
    overrides, etc.).
    """
    if not plan:
        return PLAN_FREE
    canonical = _LEGACY_NAME_MAP.get(plan, plan)
    if canonical not in PLAN_VALUES:
        return PLAN_FREE
    return canonical


def plan_at_least(user_plan: str | None, required: str | None) -> bool:
    """Return True if ``user_plan`` is at or above ``required`` in the hierarchy.

    Both inputs are normalised first so legacy values like ``"pro"`` /
    ``"team"`` and unknown / empty plans never raise.  An unknown
    ``required`` plan returns ``False`` defensively (callers should pass a
    canonical plan name).
    """
    user_canonical = normalize_plan(user_plan)
    required_canonical = normalize_plan(required)
    try:
        return PLAN_ORDER.index(user_canonical) >= PLAN_ORDER.index(required_canonical)
    except ValueError:
        return False
