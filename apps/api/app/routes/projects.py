from fastapi import APIRouter, HTTPException

from app.schemas.project import ProjectCreate, ProjectResponse
from app.services.persistence import (
    create_project as create_project_record,
    get_project,
    list_project_artifacts,
    list_projects as list_project_records,
    record_usage_event,
)

router = APIRouter(prefix="/projects", tags=["projects"])


@router.get("")
def list_projects():
    return list_project_records()


@router.post("", response_model=ProjectResponse)
def create_project(payload: ProjectCreate):
    project = create_project_record(payload.name, payload.intent)
    record_usage_event(
        "project_created",
        project_id=project["id"],
        metadata={"intent": payload.intent},
    )
    return project


@router.get("/{project_id}")
def project_detail(project_id: int):
    project = get_project(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found.")
    return project


@router.get("/{project_id}/artifacts")
def project_artifacts(project_id: int):
    project = get_project(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found.")
    return {"artifacts": list_project_artifacts(project_id)}
