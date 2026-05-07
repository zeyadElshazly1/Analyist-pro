"""
Freemium plan enforcement — FastAPI dependencies.

HTTP 402 response contract
--------------------------
When a plan gate blocks a request the response body is always:

    {
        "detail": {
            "message":      "<human-readable upgrade prompt>",
            "feature":      "<feature key from PLAN_FEATURES>",
            "current_plan": "<user's current plan name>"
        }
    }

The frontend may rely on ``detail.feature`` and ``detail.current_plan``
to show targeted upgrade-wall UI.  The set of stable feature keys is
defined in ``PLAN_FEATURES`` below.

Usage in a route:

    from app.middleware.plans import require_feature, check_project_limit

    @router.post("/chat/query")
    def chat_query(
        req: ChatRequest,
        current_user: User = Depends(get_current_user),
        _: None = Depends(require_feature("ai_chat")),
    ): ...

    @router.post("/projects")
    def create_project(
        payload: ProjectCreate,
        current_user: User = Depends(get_current_user),
        _: None = Depends(check_project_limit),
        db: Session = Depends(get_db),
    ): ...
"""
from typing import Callable

from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.middleware.auth import get_current_user
from app.models import Project, User
from app.plan_names import PLAN_CONSULTANT, PLAN_FREE, PLAN_STUDIO, normalize_plan

# ── Stable feature keys ───────────────────────────────────────────────────────
# These are the canonical feature strings used in require_feature() calls and
# in HTTP 402 detail.feature responses.  Frontend upgrade-wall components and
# tests should reference this set rather than hard-coding strings.

PLAN_FEATURES: frozenset[str] = frozenset({
    "ai_chat",
    "ai_story",
    "file_compare",
    "report_export",
    "team",          # Studio-only: create/list/remove team invites
})

# ── Plan feature matrix ───────────────────────────────────────────────────────

PLAN_LIMITS: dict[str, dict] = {
    PLAN_FREE: {
        "max_projects":  3,
        "max_file_mb":   10,
        "ai_chat":       False,
        "ai_story":      False,
        "file_compare":  False,
        "report_export": False,
        "team":          False,
    },
    PLAN_CONSULTANT: {
        "max_projects":  None,   # unlimited
        "max_file_mb":   100,
        "ai_chat":       True,
        "ai_story":      True,
        "file_compare":  True,
        "report_export": True,
        "team":          False,  # team management is Studio-only
    },
    PLAN_STUDIO: {
        "max_projects":  None,
        "max_file_mb":   500,
        "ai_chat":       True,
        "ai_story":      True,
        "file_compare":  True,
        "report_export": True,
        "team":          True,
    },
}

UPGRADE_MESSAGES: dict[str, str] = {
    "ai_chat": (
        "AI Chat is a Consultant plan feature. Upgrade to ask questions about your data."
    ),
    "ai_story": (
        "Client summaries are a Consultant plan feature. Upgrade to generate AI-written executive summaries."
    ),
    "file_compare": (
        "File comparison is a Consultant plan feature. Upgrade to compare datasets and track changes."
    ),
    "report_export": (
        "Polished exports (PDF, Excel) are a Consultant plan feature. Upgrade to download client-ready reports."
    ),
    "projects": (
        "Free plan is limited to 3 workspaces. Upgrade to the Consultant plan for unlimited workspaces."
    ),
    "file_size": (
        "Your file exceeds your plan's size limit. Upgrade for larger file support."
    ),
    "team": (
        "Team management is a Studio plan feature. Upgrade to invite and manage team members."
    ),
}


def _limits(user: User) -> dict:
    """Return the plan limits for a user, normalizing legacy plan names and falling back to free."""
    plan = normalize_plan(user.plan)
    return PLAN_LIMITS.get(plan, PLAN_LIMITS[PLAN_FREE])


# ── Reusable dependencies ─────────────────────────────────────────────────────

def require_feature(feature: str) -> Callable:
    """
    Dependency factory — raises HTTP 402 if the user's plan doesn't include
    the named feature.  The error body includes the upgrade message and
    feature name so the frontend can show a targeted upgrade wall.
    """
    def _check(current_user: User = Depends(get_current_user)) -> None:
        if not _limits(current_user).get(feature, False):
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail={
                    "message": UPGRADE_MESSAGES.get(
                        feature, f"Feature '{feature}' requires a higher plan."
                    ),
                    "feature": feature,
                    "current_plan": current_user.plan or PLAN_FREE,
                },
            )
    return _check


def check_project_limit(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    """Dependency — raises HTTP 402 if a free user has reached their project cap."""
    max_p = _limits(current_user).get("max_projects")
    if max_p is None:
        return  # unlimited plan
    count = db.query(Project).filter(Project.user_id == current_user.id).count()
    if count >= max_p:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail={
                "message": UPGRADE_MESSAGES["projects"],
                "feature": "projects",
                "current_plan": current_user.plan or PLAN_FREE,
            },
        )


def plan_max_file_bytes(user: User) -> int:
    """Return the per-plan file size cap in bytes."""
    mb = _limits(user).get("max_file_mb", 10)
    return mb * 1024 * 1024
