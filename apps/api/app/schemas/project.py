from pydantic import BaseModel


class ProjectCreate(BaseModel):
    name: str
    intent: str = "general"


class ProjectResponse(BaseModel):
    id: int
    name: str
    status: str
    intent: str = "general"
