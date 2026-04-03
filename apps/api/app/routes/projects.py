from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import AnalysisResult, Project, ProjectFile
from app.schemas.project import ProjectCreate, ProjectResponse
from app.state import PROJECT_FILES

router = APIRouter(prefix="/projects", tags=["projects"])


@router.get("")
def list_projects(db: Session = Depends(get_db)):
    projects = db.query(Project).order_by(Project.created_at.desc()).all()
    return [p.to_dict() for p in projects]


@router.post("", response_model=ProjectResponse)
def create_project(payload: ProjectCreate, db: Session = Depends(get_db)):
    project = Project(name=payload.name, status="created")
    db.add(project)
    db.commit()
    db.refresh(project)
    return project.to_dict()


# NOTE: /stats must be declared before /{project_id} so FastAPI matches it first
@router.get("/stats")
def project_stats(db: Session = Depends(get_db)):
    """Aggregate counts for the dashboard overview cards."""
    total_projects = db.query(Project).count()
    total_files = db.query(ProjectFile).count()
    total_analyses = db.query(AnalysisResult).count()
    ready_projects = db.query(Project).filter(Project.status == "ready").count()
    return {
        "total_projects": total_projects,
        "total_files": total_files,
        "total_analyses": total_analyses,
        "ready_projects": ready_projects,
    }


@router.get("/{project_id}")
def get_project(project_id: int, db: Session = Depends(get_db)):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found.")
    return project.to_dict()


@router.delete("/{project_id}", status_code=204)
def delete_project(project_id: int, db: Session = Depends(get_db)):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found.")
    db.delete(project)
    PROJECT_FILES.pop(project_id, None)
    db.commit()
