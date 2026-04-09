"""
Freemium plan enforcement — FastAPI dependencies.

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

# ── Plan feature matrix ───────────────────────────────────────────────────────

PLAN_LIMITS: dict[str, dict] = {
    "free": {
        "max_projects": 3,
        "max_file_mb":  10,
        "ai_chat":      False,
        "ai_story":     False,
    },
    "pro": {
        "max_projects": None,   # unlimited
        "max_file_mb":  100,
        "ai_chat":      True,
        "ai_story":     True,
    },
    "team": {
        "max_projects": None,
        "max_file_mb":  500,
        "ai_chat":      True,
        "ai_story":     True,
    },
}

UPGRADE_MESSAGES: dict[str, str] = {
    "ai_chat":  (
        "AI Chat is a Pro feature. Upgrade to ask unlimited questions about your data."
    ),
    "ai_story": (
        "AI Data Story is a Pro feature. Upgrade to generate 5-slide data narratives with Claude."
    ),
    "projects": (
        "Free plan is limited to 3 projects. Upgrade to Pro for unlimited projects."
    ),
    "file_size": (
        "Your file exceeds your plan's size limit. Upgrade for larger file support."
    ),
}


def _limits(user: User) -> dict:
    """Return the plan limits for a user, falling back to 'free' for unknown plans."""
    return PLAN_LIMITS.get(user.plan or "free", PLAN_LIMITS["free"])


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
                    "current_plan": current_user.plan or "free",
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
                "current_plan": current_user.plan or "free",
            },
        )


def plan_max_file_bytes(user: User) -> int:
    """Return the per-plan file size cap in bytes."""
    mb = _limits(user).get("max_file_mb", 10)
    return mb * 1024 * 1024
