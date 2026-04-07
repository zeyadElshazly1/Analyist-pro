from fastapi import APIRouter, Depends, HTTPException, Query
import pandas as pd
from pydantic import BaseModel

from app.middleware.auth import get_current_user
from app.models import User
from app.services.cleaner import clean_dataset
from app.services.cohort_service import retention_matrix, rfm_segmentation
from app.services.file_loader import load_dataset
from app.services.serializers import to_jsonable
from app.state import PROJECT_FILES

router = APIRouter(prefix="/cohorts", tags=["cohorts"])


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


class RfmRequest(BaseModel):
    project_id: int
    customer_col: str
    date_col: str
    revenue_col: str


class RetentionRequest(BaseModel):
    project_id: int
    cohort_col: str
    period_col: str
    user_col: str


@router.post("/rfm")
def rfm(req: RfmRequest, current_user: User = Depends(get_current_user)):
    df = _load(req.project_id)
    for col in [req.customer_col, req.date_col, req.revenue_col]:
        if col not in df.columns:
            raise HTTPException(status_code=400, detail=f"Column '{col}' not found.")
    try:
        result = rfm_segmentation(df, req.customer_col, req.date_col, req.revenue_col)
        return to_jsonable(result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"RFM analysis failed: {e}")


@router.post("/retention")
def retention(req: RetentionRequest, current_user: User = Depends(get_current_user)):
    df = _load(req.project_id)
    for col in [req.cohort_col, req.period_col, req.user_col]:
        if col not in df.columns:
            raise HTTPException(status_code=400, detail=f"Column '{col}' not found.")
    try:
        result = retention_matrix(df, req.cohort_col, req.period_col, req.user_col)
        return to_jsonable(result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Retention analysis failed: {e}")


@router.get("/columns")
def cohort_columns(project_id: int = Query(...), current_user: User = Depends(get_current_user)):
    df = _load(project_id)
    numeric = df.select_dtypes(include="number").columns.tolist()
    datetime_cols = df.select_dtypes(include=["datetime64"]).columns.tolist()
    # also detect string cols that look like dates
    for col in df.select_dtypes(include="object").columns:
        sample = df[col].dropna().head(5)
        try:
            pd_check = pd.to_datetime(sample, errors="coerce")
            if pd_check.notna().sum() >= 3:
                datetime_cols.append(col)
        except Exception:
            pass
    return {
        "all_columns": df.columns.tolist(),
        "numeric_columns": numeric,
        "datetime_columns": list(set(datetime_cols)),
    }
