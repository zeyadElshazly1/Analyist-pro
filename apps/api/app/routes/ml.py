from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.middleware.auth import get_current_user
from app.models import User
from app.services.automl_service import detect_problem_type, train_models
from app.services.cleaner import clean_dataset
from app.services.file_loader import load_dataset
from app.services.serializers import to_jsonable
from app.state import get_project_file_info

router = APIRouter(prefix="/ml", tags=["ml"])


def _load(project_id: int):
    info = get_project_file_info(project_id)
    if not info:
        raise HTTPException(status_code=404, detail="No uploaded file for this project.")
    path = info["path"]
    try:
        df = load_dataset(path)
        df_clean, _, _ = clean_dataset(df)
        return df_clean
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Uploaded file not found on disk.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load dataset: {e}")


class TrainRequest(BaseModel):
    project_id: int
    target_col: str


@router.post("/train")
def train(req: TrainRequest, current_user: User = Depends(get_current_user)):
    df = _load(req.project_id)
    if req.target_col not in df.columns:
        raise HTTPException(status_code=400, detail=f"Column '{req.target_col}' not found.")
    if len(df) < 10:
        raise HTTPException(status_code=400, detail="Need at least 10 rows to train models.")
    try:
        result = train_models(df, req.target_col)
        return to_jsonable(result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Training failed: {e}")


@router.get("/columns")
def get_columns(project_id: int = Query(...), current_user: User = Depends(get_current_user)):
    df = _load(project_id)
    return {"columns": df.columns.tolist()}
