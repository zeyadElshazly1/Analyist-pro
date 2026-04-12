"""
Auth routes.
Registration and login are handled entirely by Supabase on the frontend.
This module exposes /auth/me (get user metadata), /auth/me/export (GDPR data
export), and DELETE /auth/me (GDPR account deletion).
"""
import json
from typing import Optional

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import User, Project, ProjectFile, AnalysisResult
from app.middleware.auth import get_current_user
from app.services.audit import log_event
from app.services.storage import delete_file as storage_delete_file

router = APIRouter(prefix="/auth", tags=["auth"])


class NotificationPrefsUpdate(BaseModel):
    analysis_complete: Optional[bool] = None
    weekly_digest: Optional[bool] = None
    product_updates: Optional[bool] = None
    marketing_emails: Optional[bool] = None


@router.get("/me")
def get_me(current_user: User = Depends(get_current_user)):
    return current_user.to_dict()


@router.patch("/me/notifications")
def update_notification_prefs(
    payload: NotificationPrefsUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Persist notification preference flags for the current user."""
    prefs = current_user.notification_prefs
    updates = payload.model_dump(exclude_none=True)
    prefs.update(updates)
    current_user.notification_prefs_json = json.dumps(prefs)
    db.commit()
    return {"notification_prefs": prefs}


@router.get("/me/export")
def export_my_data(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    GDPR data export — returns all data we hold for this user as JSON.
    Includes account info, all projects, uploaded file metadata, and
    analysis results.
    """
    projects = db.query(Project).filter(Project.user_id == current_user.id).all()

    project_data = []
    for project in projects:
        files = db.query(ProjectFile).filter(ProjectFile.project_id == project.id).all()
        analyses = db.query(AnalysisResult).filter(AnalysisResult.project_id == project.id).all()
        project_data.append({
            **project.to_dict(),
            "files": [f.to_dict() for f in files],
            "analyses": [
                {
                    "id": a.id,
                    "file_hash": a.file_hash,
                    "created_at": a.created_at.isoformat() if a.created_at else None,
                    # Include full result for completeness but keep it parseable
                    "result": json.loads(a.result_json) if a.result_json else None,
                }
                for a in analyses
            ],
        })

    payload = {
        "account": current_user.to_dict(),
        "projects": project_data,
    }

    return JSONResponse(
        content=payload,
        headers={
            "Content-Disposition": 'attachment; filename="analyistpro-data-export.json"',
            "Content-Type": "application/json",
        },
    )


@router.delete("/me", status_code=204)
def delete_my_account(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    GDPR right to erasure — permanently deletes the user and all associated
    data (projects, files, analyses) via cascade delete.  Uploaded files are
    also removed from storage (disk or S3).
    """
    # Remove physical files first (cascade delete will remove DB rows)
    projects = db.query(Project).filter(Project.user_id == current_user.id).all()
    for project in projects:
        files = db.query(ProjectFile).filter(ProjectFile.project_id == project.id).all()
        for pf in files:
            try:
                storage_delete_file(pf.stored_path)
            except Exception:
                pass  # Best-effort file removal; DB deletion proceeds regardless

    # Audit before deletion (user_id will become NULL via SET NULL after delete)
    log_event(
        db,
        action="delete_account",
        user_id=current_user.id,
        resource_type="user",
        resource_id=current_user.id,
        detail={"email": current_user.email},
    )

    # Delete user — cascade removes projects → files, analyses, features
    db.delete(current_user)
    db.commit()
    # 204 No Content
