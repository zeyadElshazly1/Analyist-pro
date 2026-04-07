from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.middleware.auth import get_current_user
from app.models import User
from app.services.cleaner import clean_dataset
from app.services.file_loader import load_dataset
from app.services.serializers import to_jsonable
from app.services.stats_tests_service import power_analysis, run_test
from app.state import PROJECT_FILES

router = APIRouter(prefix="/stats", tags=["stats"])


def _load(project_id: int):
    if project_id not in PROJECT_FILES:
        raise HTTPException(status_code=404, detail="No uploaded file for this project.")
    path = PROJECT_FILES[project_id]["path"]
    try:
        df = load_dataset(path)
        df_clean, _, _ = clean_dataset(df)
        return df_clean
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Uploaded file not found on disk.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load dataset: {e}")


class TestRequest(BaseModel):
    project_id: int
    test_type: str
    col_a: str
    col_b: str | None = None
    alpha: float = 0.05


class PowerRequest(BaseModel):
    effect_size: float
    alpha: float = 0.05
    power: float = 0.8
    test_type: str = "ttest"


@router.post("/test")
def stats_test(req: TestRequest, current_user: User = Depends(get_current_user)):
    df = _load(req.project_id)
    try:
        result = run_test(df, req.test_type, req.col_a, req.col_b, req.alpha)
        return to_jsonable(result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Test failed: {e}")


@router.post("/power")
def stats_power(req: PowerRequest):
    try:
        result = power_analysis(req.effect_size, req.alpha, req.power, req.test_type)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Power analysis failed: {e}")


@router.get("/columns")
def stats_columns(project_id: int = Query(...), current_user: User = Depends(get_current_user)):
    df = _load(project_id)
    numeric = df.select_dtypes(include="number").columns.tolist()
    categorical = df.select_dtypes(include=["object", "category"]).columns.tolist()
    return {"numeric_columns": numeric, "categorical_columns": categorical}
