"""
Team management endpoints — invite members, list team, remove members.
Only available to Team-plan subscribers (max 5 seats total).
"""
import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from app.db import get_db
from app.middleware.auth import get_current_user, optional_current_user
from app.models import TeamInvite, User
from app.plan_names import PLAN_FREE, PLAN_STUDIO, normalize_plan

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/team", tags=["team"])

TEAM_SEAT_LIMIT = 5  # total seats including owner


# ── Helpers ───────────────────────────────────────────────────────────────────

def _require_team_plan(user: User) -> None:
    if normalize_plan(user.plan) != PLAN_STUDIO:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail={
                "message": "Team management requires a Studio plan.",
                "feature": "team",
                "current_plan": user.plan or PLAN_FREE,
            },
        )


def _active_member_count(owner_id: str, db: Session) -> int:
    """Returns number of active (accepted) members — NOT including the owner."""
    return (
        db.query(TeamInvite)
        .filter(TeamInvite.owner_id == owner_id, TeamInvite.status == "active")
        .count()
    )


# ── Schemas ───────────────────────────────────────────────────────────────────

class InviteBody(BaseModel):
    email: str | None = None  # optional hint; no email sending yet


# ── Routes ────────────────────────────────────────────────────────────────────

@router.post("/invite", status_code=201)
def create_invite(
    body: InviteBody,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Generate a team invite link. Caller must have a Team plan."""
    _require_team_plan(current_user)

    active = _active_member_count(current_user.id, db)
    if active >= TEAM_SEAT_LIMIT - 1:  # -1 for the owner seat
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail={
                "message": f"Team seat limit reached ({TEAM_SEAT_LIMIT} seats total, including owner).",
                "feature": "team_seats",
                "current_plan": current_user.plan,
            },
        )

    token = uuid.uuid4().hex  # 32-char hex, URL-safe
    invite = TeamInvite(
        owner_id=current_user.id,
        email=body.email,
        token=token,
        status="pending",
    )
    db.add(invite)
    db.commit()
    db.refresh(invite)
    logger.info(f"Team invite created: owner={current_user.id[:8]}… token={token[:8]}…")
    return {"invite_id": invite.id, "token": token}


@router.get("/members")
def list_members(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all pending + active invites for the current team owner."""
    _require_team_plan(current_user)

    invites = (
        db.query(TeamInvite)
        .filter(TeamInvite.owner_id == current_user.id)
        .order_by(TeamInvite.created_at.desc())
        .all()
    )

    items = []
    for inv in invites:
        item = inv.to_dict()
        if inv.member_id:
            member = db.query(User).filter(User.id == inv.member_id).first()
            item["member_email"] = member.email if member else None
        else:
            item["member_email"] = None
        items.append(item)

    active = sum(1 for i in invites if i.status == "active")
    return {
        "members": items,
        "seats_used": active + 1,   # +1 for owner
        "seat_limit": TEAM_SEAT_LIMIT,
    }


@router.delete("/members/{invite_id}", status_code=204)
def remove_member(
    invite_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Revoke an invite or remove an active member."""
    _require_team_plan(current_user)

    invite = (
        db.query(TeamInvite)
        .filter(TeamInvite.id == invite_id, TeamInvite.owner_id == current_user.id)
        .first()
    )
    if not invite:
        raise HTTPException(status_code=404, detail="Invite not found.")
    db.delete(invite)
    db.commit()
    logger.info(f"Team invite {invite_id} removed by owner {current_user.id[:8]}…")


@router.get("/invite/{token}")
def get_invite_info(
    token: str,
    db: Session = Depends(get_db),
):
    """Public endpoint — returns invite metadata for the join page."""
    invite = db.query(TeamInvite).filter(TeamInvite.token == token).first()
    if not invite or invite.status == "revoked":
        raise HTTPException(status_code=404, detail="Invite not found or expired.")
    owner = db.query(User).filter(User.id == invite.owner_id).first()
    return {
        "token": token,
        "status": invite.status,
        "owner_email": owner.email if owner else "Unknown",
    }


@router.post("/invite/{token}/accept")
def accept_invite(
    token: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Accept a team invite. The caller becomes a member of the team."""
    invite = db.query(TeamInvite).filter(TeamInvite.token == token).first()
    if not invite:
        raise HTTPException(status_code=404, detail="Invite not found.")
    if invite.status != "pending":
        raise HTTPException(status_code=400, detail="This invite has already been used or revoked.")
    if invite.owner_id == current_user.id:
        raise HTTPException(status_code=400, detail="You cannot accept your own team invite.")

    # Check if user is already a member of this team
    existing = (
        db.query(TeamInvite)
        .filter(
            TeamInvite.owner_id == invite.owner_id,
            TeamInvite.member_id == current_user.id,
            TeamInvite.status == "active",
        )
        .first()
    )
    if existing:
        raise HTTPException(status_code=400, detail="You are already a member of this team.")

    # Verify seat limit hasn't been reached since invite was created
    active = _active_member_count(invite.owner_id, db)
    if active >= TEAM_SEAT_LIMIT - 1:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail={"message": "This team has reached its seat limit.", "feature": "team_seats"},
        )

    invite.member_id = current_user.id
    invite.status = "active"
    invite.accepted_at = datetime.now(timezone.utc)
    db.commit()

    owner = db.query(User).filter(User.id == invite.owner_id).first()
    logger.info(
        f"Team invite accepted: member={current_user.id[:8]}… owner={invite.owner_id[:8]}…"
    )
    return {
        "message": "Welcome to the team!",
        "owner_email": owner.email if owner else None,
    }
