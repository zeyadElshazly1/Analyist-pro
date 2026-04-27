"""
Project ownership / access guards.

Centralised helpers used by every API route that accepts ``project_id``,
``run_id``, ``analysis_result_id`` or ``report_draft_id``.  All helpers
return the requested ORM object only when the current user owns the
underlying project; otherwise they raise ``HTTPException(404)`` so we
never leak whether another user's resource exists.

These helpers are intentionally tiny — they exist so route bodies stay
focussed on their actual work and ownership enforcement is consistent
across the whole backend.

Public API
----------
get_project_for_user(db, project_id, user)        -> Project
get_run_for_user(db, run_id, user, *, options=…)  -> AnalysisResult
get_analysis_for_user(db, analysis_id, user)      -> AnalysisResult   (alias of get_run_for_user)
get_report_draft_for_user(db, draft_id, user)     -> ReportDraft
"""
from __future__ import annotations

from typing import Iterable, Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models import AnalysisResult, Project, ReportDraft, User


# ── Project ──────────────────────────────────────────────────────────────────

def get_project_for_user(
    db: Session,
    project_id: int,
    user: User,
) -> Project:
    """Return the project iff it belongs to the current user.

    Raises 404 ("Project not found.") otherwise.  We use 404 rather than
    403 so we never reveal the existence of another user's project.
    """
    project = (
        db.query(Project)
        .filter(Project.id == project_id, Project.user_id == user.id)
        .first()
    )
    if not project:
        raise HTTPException(status_code=404, detail="Project not found.")
    return project


# ── Run / AnalysisResult ─────────────────────────────────────────────────────

def get_run_for_user(
    db: Session,
    run_id: int,
    user: User,
    *,
    options: Optional[Iterable] = None,
) -> AnalysisResult:
    """Return the analysis run iff its project belongs to the current user.

    Optional ``options`` is passed straight through to ``Query.options``
    so callers can request joinedload(...) eager loading.
    """
    q = db.query(AnalysisResult)
    if options:
        q = q.options(*options)
    run = (
        q.join(Project, AnalysisResult.project_id == Project.id)
        .filter(AnalysisResult.id == run_id, Project.user_id == user.id)
        .first()
    )
    if not run:
        raise HTTPException(status_code=404, detail="Run not found.")
    return run


def get_analysis_for_user(
    db: Session,
    analysis_id: int,
    user: User,
    *,
    options: Optional[Iterable] = None,
) -> AnalysisResult:
    """Alias of ``get_run_for_user`` for routes that talk about
    ``analysis_id`` / ``analysis_result_id`` rather than runs."""
    try:
        return get_run_for_user(db, analysis_id, user, options=options)
    except HTTPException as exc:
        if exc.status_code == 404:
            raise HTTPException(status_code=404, detail="Analysis result not found.") from exc
        raise


# ── Report draft ─────────────────────────────────────────────────────────────

def get_report_draft_for_user(
    db: Session,
    draft_id: int,
    user: User,
) -> ReportDraft:
    """Return the report draft iff its project belongs to the current user."""
    draft = (
        db.query(ReportDraft)
        .join(Project, ReportDraft.project_id == Project.id)
        .filter(ReportDraft.id == draft_id, Project.user_id == user.id)
        .first()
    )
    if not draft:
        raise HTTPException(status_code=404, detail="Report not found.")
    return draft
