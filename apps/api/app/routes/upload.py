from fastapi import APIRouter, File, Form, UploadFile

from app.routes.datasets import upload_project_dataset

router = APIRouter(prefix="/upload", tags=["upload"])


@router.post("")
async def upload_file(
    project_id: int = Form(...),
    file: UploadFile = File(...),
):
    return await upload_project_dataset(project_id=project_id, file=file)
