"""
Canonical plan name constants for the entire backend.

All plan string literals must come from here.
Do not hardcode "pro", "team", "consultant", "studio", or "free" anywhere else.
"""
from __future__ import annotations


class PlanName:
    FREE       = "free"
    CONSULTANT = "consultant"
    STUDIO     = "studio"


PLAN_ORDER: list[str] = [PlanName.FREE, PlanName.CONSULTANT, PlanName.STUDIO]

PLAN_LABELS: dict[str, str] = {
    PlanName.FREE:       "Free",
    PlanName.CONSULTANT: "Consultant",
    PlanName.STUDIO:     "Studio",
}


def plan_at_least(user_plan: str, required: str) -> bool:
    """Return True if user_plan is at or above required in the plan hierarchy."""
    try:
        return PLAN_ORDER.index(user_plan) >= PLAN_ORDER.index(required)
    except ValueError:
        return False
