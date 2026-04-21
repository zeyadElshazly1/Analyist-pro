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
    """Return the canonical plan name, mapping legacy 'pro'/'team' if needed."""
    if not plan:
        return PLAN_FREE
    return _LEGACY_NAME_MAP.get(plan, plan)


def plan_at_least(user_plan: str, required: str) -> bool:
    """Return True if user_plan is at or above required in the plan hierarchy."""
    try:
        return PLAN_ORDER.index(user_plan) >= PLAN_ORDER.index(required)
    except ValueError:
        return False
