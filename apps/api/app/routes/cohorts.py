from fastapi import APIRouter, Depends, HTTPException, Query
import pandas as pd
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import get_db
from app.middleware.auth import get_current_user
from app.models import User
from app.services.access_guards import get_project_for_user
from app.services.cohort_service import retention_matrix, rfm_segmentation
from app.services.dataset_loader import load_prepared
from app.services.serializers import to_jsonable

router = APIRouter(prefix="/cohorts", tags=["cohorts"])


def _load_owned(db: Session, user: User, project_id: int):
    """Verify ownership, then load + clean the dataset."""
    get_project_for_user(db, project_id, user)
    return load_prepared(project_id)


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
def rfm(
    req: RfmRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    df = _load_owned(db, current_user, req.project_id)
    for col in [req.customer_col, req.date_col, req.revenue_col]:
        if col not in df.columns:
            raise HTTPException(status_code=400, detail=f"Column '{col}' not found.")
    try:
        result = rfm_segmentation(df, req.customer_col, req.date_col, req.revenue_col)
        return to_jsonable(result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"RFM analysis failed: {e}")


@router.post("/retention")
def retention(
    req: RetentionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    df = _load_owned(db, current_user, req.project_id)
    for col in [req.cohort_col, req.period_col, req.user_col]:
        if col not in df.columns:
            raise HTTPException(status_code=400, detail=f"Column '{col}' not found.")
    try:
        result = retention_matrix(df, req.cohort_col, req.period_col, req.user_col)
        return to_jsonable(result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Retention analysis failed: {e}")


@router.get("/columns")
def cohort_columns(
    project_id: int = Query(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    df = _load_owned(db, current_user, project_id)
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
