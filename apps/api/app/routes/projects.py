from fastapi import APIRouter
from app.schemas.project import ProjectCreate, ProjectResponse

router = APIRouter(prefix="/projects", tags=["projects"])

PROJECTS = [
    {"id": 1, "name": "Revenue Retention Audit", "status": "ready"},
    {"id": 2, "name": "Marketing Performance Review", "status": "ready"},
]

NEXT_ID = 3


@router.get("")
def list_projects():
    return PROJECTS


@router.post("", response_model=ProjectResponse)
def create_project(payload: ProjectCreate):
    global NEXT_ID

    project = {
        "id": NEXT_ID,
        "name": payload.name,
        "status": "created",
    }

    PROJECTS.append(project)
    NEXT_ID += 1

    return project