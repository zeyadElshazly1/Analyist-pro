import json
import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db import get_db
from app.middleware.auth import get_current_user
from app.middleware.plans import check_project_limit
from app.models import AnalysisResult, Project, ProjectFile, User
from app.schemas.project import ProjectCreate, ProjectResponse
from app.services.run_resolver import build_run_detail, resolve_latest_run
from app.state import PROJECT_FILES

logger = logging.getLogger(__name__)
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
    _plan: None = Depends(check_project_limit),
    db: Session = Depends(get_db),
):
    try:
        project = Project(name=payload.name, status="created", user_id=current_user.id)
        db.add(project)
        db.commit()
        db.refresh(project)
        logger.info(f"Project created: id={project.id} user={current_user.id[:8]}…")
        return project.to_dict()
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Failed to create project for user {current_user.id[:8]}…: {e}", exc_info=True)
        raise HTTPException(
            status_code=503,
            detail="Could not create the project due to a database error. Please try again.",
        )


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


@router.get("/with-latest-run")
def projects_with_latest_run(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Returns all projects for the current user, each decorated with the date
    of their most recent analysis run — in a single round-trip to the DB.
    Eliminates the N+1 pattern on the Reports list page.
    """
    from sqlalchemy import func

    # Subquery: latest analysis created_at per project
    latest_run_sq = (
        db.query(
            AnalysisResult.project_id,
            func.max(AnalysisResult.created_at).label("latest_run_at"),
            func.max(AnalysisResult.id).label("latest_run_id"),
        )
        .group_by(AnalysisResult.project_id)
        .subquery()
    )

    rows = (
        db.query(Project, latest_run_sq.c.latest_run_at, latest_run_sq.c.latest_run_id)
        .outerjoin(latest_run_sq, Project.id == latest_run_sq.c.project_id)
        .filter(Project.user_id == current_user.id)
        .order_by(latest_run_sq.c.latest_run_at.desc().nulls_last(), Project.created_at.desc())
        .all()
    )

    return [
        {
            **p.to_dict(),
            "latest_run_at": run_at.isoformat() if run_at else None,
            "latest_run_id": run_id,
        }
        for p, run_at, run_id in rows
    ]


@router.get("/{project_id}")
def get_project(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Return project metadata plus the latest usable run context.

    latest_run is None when the project has never been analysed.
    When present it carries enough context for the UI to decide:
      - "Open previous analysis" (has_result=True)
      - "Continue from last run" (status != report_ready)
      - "See last failure"       (status == failed)
      - "Run again"              (always available)
    """
    project = (
        db.query(Project)
        .filter(Project.id == project_id, Project.user_id == current_user.id)
        .first()
    )
    if not project:
        raise HTTPException(status_code=404, detail="Project not found.")

    run = resolve_latest_run(db, project_id)
    result = project.to_dict()
    result["latest_run"] = build_run_detail(run).model_dump(mode="json") if run else None
    return result


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

    try:
        db.delete(project)
        db.commit()
        # Only clear the cache after a successful DB commit
        PROJECT_FILES.pop(project_id, None)
        logger.info(
            f"Project deleted: id={project_id} user={current_user.id[:8]}… name='{project.name}'"
        )
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Failed to delete project {project_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=503,
            detail="Could not delete the project due to a database error. Please try again.",
        )


@router.get("/{project_id}/annotations")
def get_annotations(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return column annotations for a project (dict of column→note)."""
    project = (
        db.query(Project)
        .filter(Project.id == project_id, Project.user_id == current_user.id)
        .first()
    )
    if not project:
        raise HTTPException(status_code=404, detail="Project not found.")
    return {"annotations": project.column_annotations}


class AnnotationBody(BaseModel):
    note: str  # empty string → remove annotation


@router.put("/{project_id}/annotations/{column}")
def set_annotation(
    project_id: int,
    column: str,
    body: AnnotationBody,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Set or clear an annotation for a single column."""
    project = (
        db.query(Project)
        .filter(Project.id == project_id, Project.user_id == current_user.id)
        .first()
    )
    if not project:
        raise HTTPException(status_code=404, detail="Project not found.")
    annotations = dict(project.column_annotations)
    if body.note.strip():
        annotations[column] = body.note.strip()
    else:
        annotations.pop(column, None)
    project.column_annotations = annotations
    db.commit()
    return {"annotations": annotations}


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
        return {
            "project_id": project_id,
            "project_name": project.name,
            "insights": [],
            "analysis_id": None,
            "created_at": None,
            "health_score": None,
        }

    try:
        result = json.loads(analysis.result_json)
    except (json.JSONDecodeError, TypeError) as e:
        logger.warning(f"Corrupted result_json for analysis {analysis.id}: {e}")
        return {
            "project_id": project_id,
            "project_name": project.name,
            "insights": [],
            "analysis_id": analysis.id,
            "created_at": analysis.created_at.isoformat() if analysis.created_at else None,
            "health_score": None,
        }

    insights = result.get("insights", [])[:5]  # top 5 for dashboard widget
    health = result.get("health_score", {})
    health_score = health.get("score") if isinstance(health, dict) else None

    return {
        "project_id": project_id,
        "project_name": project.name,
        "analysis_id": analysis.id,
        "created_at": analysis.created_at.isoformat() if analysis.created_at else None,
        "health_score": health_score,
        "insights": insights,
    }
