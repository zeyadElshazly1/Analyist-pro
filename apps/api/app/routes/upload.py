import os
from fastapi import APIRouter, UploadFile, File, Form
from app.state import PROJECT_FILES

router = APIRouter(prefix="/upload", tags=["upload"])

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)


@router.post("")
async def upload_file(
    project_id: int = Form(...),
    file: UploadFile = File(...),
):
    filename = file.filename
    safe_filename = f"project_{project_id}_{filename}"
    path = os.path.join(UPLOAD_DIR, safe_filename)

    with open(path, "wb") as f:
        content = await file.read()
        f.write(content)

    PROJECT_FILES[project_id] = {
        "filename": filename,
        "path": path,
    }

    return {
        "project_id": project_id,
        "filename": filename,
        "path": path,
    }