from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel

from app.limiter import limiter
from app.middleware.auth import get_current_user
from app.models import User
from app.services.automl_service import (
    detect_problem_type,
    load_model_artifacts,
    save_model_artifacts,
    score_rows,
    train_models,
)
from app.services.dataset_loader import load_prepared
from app.services.serializers import to_jsonable
from app.state import get_project_file_info

router = APIRouter(prefix="/ml", tags=["ml"])


def _load(project_id: int):
    return load_prepared(project_id)


class TrainRequest(BaseModel):
    project_id: int
    target_col: str


@router.post("/train")
@limiter.limit("4/minute")
def train(request: Request, req: TrainRequest, current_user: User = Depends(get_current_user)):
    df = _load(req.project_id)
    if req.target_col not in df.columns:
        raise HTTPException(status_code=400, detail=f"Column '{req.target_col}' not found.")
    if len(df) < 10:
        raise HTTPException(status_code=400, detail="Need at least 10 rows to train models.")
    try:
        result = train_models(df, req.target_col)
        # Persist model artifacts for later prediction; strip before serialising.
        artifacts = result.pop("_artifacts", None)
        if artifacts is not None and artifacts.get("pipeline") is not None:
            save_model_artifacts(req.project_id, artifacts)
        return to_jsonable(result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Training failed: {e}")


@router.get("/model-info/{project_id}")
def model_info(project_id: int, current_user: User = Depends(get_current_user)):
    """Return metadata about the saved model for this project, if any."""
    arts = load_model_artifacts(project_id)
    if arts is None:
        raise HTTPException(status_code=404, detail="No trained model found. Run /ml/train first.")
    return {
        "project_id": project_id,
        "problem_type": arts["problem_type"],
        "target_col": arts["target_col"],
        "best_model_name": arts["best_model_name"],
        "feature_names": arts["feature_names"],
        "class_labels": arts.get("class_labels"),
    }


class PredictRequest(BaseModel):
    rows: list[dict]  # list of records {column: value}


@router.post("/predict/{project_id}")
def predict(
    project_id: int,
    req: PredictRequest,
    current_user: User = Depends(get_current_user),
):
    """Score new rows against the trained model for this project."""
    if not req.rows:
        raise HTTPException(status_code=400, detail="No rows provided.")
    arts = load_model_artifacts(project_id)
    if arts is None:
        raise HTTPException(status_code=404, detail="No trained model found. Run /ml/train first.")
    try:
        predictions = score_rows(arts, req.rows)
        return {
            "problem_type": arts["problem_type"],
            "target_col": arts["target_col"],
            "best_model_name": arts["best_model_name"],
            "predictions": predictions,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Prediction failed: {e}")


@router.get("/columns")
def get_columns(project_id: int = Query(...), current_user: User = Depends(get_current_user)):
    df = _load(project_id)
    return {"columns": df.columns.tolist()}
