import json
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.middleware.auth import get_current_user, optional_current_user
from app.models import AnalysisResult, Project, ProjectFile, User
from app.schemas.project import ProjectCreate, ProjectResponse
from app.state import PROJECT_FILES

router = APIRouter(prefix="/projects", tags=["projects"])


@router.get("")
def list_projects(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    projects = (
        db.query(Project)
        .filter(Project.user_id == current_user.id)
        .order_by(Project.created_at.desc())
        .all()
    )
    return [p.to_dict() for p in projects]


@router.post("", response_model=ProjectResponse)
def create_project(
    payload: ProjectCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    project = Project(name=payload.name, status="created", user_id=current_user.id)
    db.add(project)
    db.commit()
    db.refresh(project)
    return project.to_dict()


# NOTE: /stats must be declared before /{project_id} so FastAPI matches it first
@router.get("/stats")
def project_stats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Aggregate counts for the dashboard overview cards (scoped to current user)."""
    total_projects = db.query(Project).filter(Project.user_id == current_user.id).count()
    total_files = (
        db.query(ProjectFile)
        .join(Project)
        .filter(Project.user_id == current_user.id)
        .count()
    )
    total_analyses = (
        db.query(AnalysisResult)
        .join(Project)
        .filter(Project.user_id == current_user.id)
        .count()
    )
    ready_projects = (
        db.query(Project)
        .filter(Project.user_id == current_user.id, Project.status == "ready")
        .count()
    )
    return {
        "total_projects": total_projects,
        "total_files": total_files,
        "total_analyses": total_analyses,
        "ready_projects": ready_projects,
    }


@router.get("/{project_id}")
def get_project(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    project = (
        db.query(Project)
        .filter(Project.id == project_id, Project.user_id == current_user.id)
        .first()
    )
    if not project:
        raise HTTPException(status_code=404, detail="Project not found.")
    return project.to_dict()


@router.delete("/{project_id}", status_code=204)
def delete_project(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    project = (
        db.query(Project)
        .filter(Project.id == project_id, Project.user_id == current_user.id)
        .first()
    )
    if not project:
        raise HTTPException(status_code=404, detail="Project not found.")
    db.delete(project)
    PROJECT_FILES.pop(project_id, None)
    db.commit()


@router.get("/{project_id}/latest-insights")
def get_latest_insights(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return the top insights from the most recent analysis run for a project."""
    project = (
        db.query(Project)
        .filter(Project.id == project_id, Project.user_id == current_user.id)
        .first()
    )
    if not project:
        raise HTTPException(status_code=404, detail="Project not found.")

    analysis = (
        db.query(AnalysisResult)
        .filter(AnalysisResult.project_id == project_id)
        .order_by(AnalysisResult.created_at.desc())
        .first()
    )
    if not analysis:
        return {"project_id": project_id, "project_name": project.name, "insights": [], "analysis_id": None}

    result = json.loads(analysis.result_json)
    insights = result.get("insights", [])[:5]  # top 5 only for dashboard widget
    return {
        "project_id": project_id,
        "project_name": project.name,
        "analysis_id": analysis.id,
        "created_at": analysis.created_at.isoformat() if analysis.created_at else None,
        "health_score": result.get("health_score", {}).get("score"),
        "insights": insights,
    }
