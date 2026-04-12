from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
import pandas as pd

from app.middleware.auth import get_current_user
from app.models import User
from app.state import PROJECT_FILES, get_project_file_info
from app.services.file_loader import load_dataset
from app.services.cleaner import clean_dataset
from app.services.serializers import to_jsonable
from app.services.timeseries import detect_date_columns, run_timeseries
from app.services.outlier_explorer import get_numeric_columns, explore_outliers
from app.services.correlation_matrix import build_correlation_matrix
from app.services.duplicate_detector import detect_duplicates
from app.services.column_compare import get_columns, compare_columns
from app.services.multifile_compare import compare_files

router = APIRouter(prefix="/explore", tags=["explore"])


def _load(project_id: int):
    """Load + clean a dataset by project_id. Raises HTTPException on failure."""
    file_info = get_project_file_info(project_id)
    if not file_info:
        raise HTTPException(status_code=404, detail="No uploaded file for this project.")
    path = file_info["path"]
    try:
        df = load_dataset(path)
        df_clean, _, _ = clean_dataset(df)
        return df_clean
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Uploaded file not found on disk.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load dataset: {e}")


# ── Time Series ───────────────────────────────────────────────────────────────

@router.get("/timeseries/columns")
def timeseries_columns(project_id: int = Query(...), current_user: User = Depends(get_current_user)):
    df = _load(project_id)
    date_cols = detect_date_columns(df)
    numeric_cols = df.select_dtypes(include=["number"]).columns.tolist()
    return {"date_columns": date_cols, "value_columns": numeric_cols}


class TimeseriesRequest(BaseModel):
    project_id: int
    date_col: str
    value_col: str
    aggregation: str = "mean"


@router.post("/timeseries/run")
def timeseries_run(payload: TimeseriesRequest, current_user: User = Depends(get_current_user)):
    df = _load(payload.project_id)
    try:
        result = run_timeseries(df, payload.date_col, payload.value_col, payload.aggregation)
        return to_jsonable(result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Time series analysis failed: {e}")


# ── Duplicates ────────────────────────────────────────────────────────────────

class ProjectRequest(BaseModel):
    project_id: int


@router.post("/duplicates")
def duplicates(payload: ProjectRequest, current_user: User = Depends(get_current_user)):
    df = _load(payload.project_id)
    try:
        result = detect_duplicates(df)
        return to_jsonable(result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Duplicate detection failed: {e}")


# ── Outliers ──────────────────────────────────────────────────────────────────

@router.get("/outliers/columns")
def outlier_columns(project_id: int = Query(...), current_user: User = Depends(get_current_user)):
    df = _load(project_id)
    return {"numeric_columns": get_numeric_columns(df)}


class OutlierRequest(BaseModel):
    project_id: int
    column: str


@router.post("/outliers/run")
def outliers_run(payload: OutlierRequest, current_user: User = Depends(get_current_user)):
    df = _load(payload.project_id)
    try:
        result = explore_outliers(df, payload.column)
        return to_jsonable(result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Outlier analysis failed: {e}")


# ── Correlations ──────────────────────────────────────────────────────────────

@router.post("/correlations")
def correlations(payload: ProjectRequest, current_user: User = Depends(get_current_user)):
    df = _load(payload.project_id)
    try:
        result = build_correlation_matrix(df)
        return to_jsonable(result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Correlation analysis failed: {e}")


# ── Column Compare ────────────────────────────────────────────────────────────

@router.get("/compare-columns/columns")
def compare_columns_options(project_id: int = Query(...), current_user: User = Depends(get_current_user)):
    df = _load(project_id)
    return {"columns": get_columns(df)}


class ColumnCompareRequest(BaseModel):
    project_id: int
    col_a: str
    col_b: str


@router.post("/compare-columns/run")
def compare_columns_run(payload: ColumnCompareRequest, current_user: User = Depends(get_current_user)):
    df = _load(payload.project_id)
    try:
        result = compare_columns(df, payload.col_a, payload.col_b)
        return to_jsonable(result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Column comparison failed: {e}")


# ── Multi-file Compare ────────────────────────────────────────────────────────

class MultifileRequest(BaseModel):
    project_id_a: int
    project_id_b: int


@router.post("/multifile")
def multifile_compare(payload: MultifileRequest, current_user: User = Depends(get_current_user)):
    file_a = get_project_file_info(payload.project_id_a)
    if not file_a:
        raise HTTPException(status_code=404, detail=f"No file for project {payload.project_id_a}")
    file_b = get_project_file_info(payload.project_id_b)
    if not file_b:
        raise HTTPException(status_code=404, detail=f"No file for project {payload.project_id_b}")

    path_a = file_a["path"]
    path_b = file_b["path"]
    label_a = file_a.get("filename", f"Project {payload.project_id_a}")
    label_b = file_b.get("filename", f"Project {payload.project_id_b}")

    try:
        result = compare_files(path_a, path_b, label_a=label_a, label_b=label_b)
        return to_jsonable(result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Multi-file comparison failed: {e}")


# ── Join ─────────────────────────────────────────────────────────────────────

_VALID_HOW = {"inner", "left", "right", "outer"}


@router.get("/join/columns")
def join_columns(
    project_id_left: int = Query(...),
    project_id_right: int = Query(...),
    current_user: User = Depends(get_current_user),
):
    """Return column lists for both projects + suggested join keys (common names)."""
    df_left = _load(project_id_left)
    df_right = _load(project_id_right)
    left_cols = df_left.columns.tolist()
    right_cols = df_right.columns.tolist()
    suggested = sorted(set(left_cols) & set(right_cols))
    return {
        "left_columns": left_cols,
        "right_columns": right_cols,
        "suggested_join_keys": suggested,
    }


class JoinRequest(BaseModel):
    project_id_left: int
    project_id_right: int
    left_on: str
    right_on: str
    how: str = "inner"  # inner | left | right | outer


@router.post("/join/run")
def join_run(payload: JoinRequest, current_user: User = Depends(get_current_user)):
    """Join two project datasets on specified keys and return a preview + stats."""
    if payload.how not in _VALID_HOW:
        raise HTTPException(
            status_code=400,
            detail=f"'how' must be one of: {', '.join(sorted(_VALID_HOW))}",
        )
    df_left = _load(payload.project_id_left)
    df_right = _load(payload.project_id_right)

    if payload.left_on not in df_left.columns:
        raise HTTPException(status_code=400, detail=f"Column '{payload.left_on}' not in left dataset.")
    if payload.right_on not in df_right.columns:
        raise HTTPException(status_code=400, detail=f"Column '{payload.right_on}' not in right dataset.")

    try:
        merged = pd.merge(
            df_left,
            df_right,
            left_on=payload.left_on,
            right_on=payload.right_on,
            how=payload.how,
            suffixes=("_left", "_right"),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Join failed: {e}")

    preview = merged.head(200).fillna("").astype(str).to_dict(orient="records")
    return to_jsonable({
        "rows": len(merged),
        "left_rows": len(df_left),
        "right_rows": len(df_right),
        "columns": merged.columns.tolist(),
        "how": payload.how,
        "left_on": payload.left_on,
        "right_on": payload.right_on,
        "preview": preview,
    })


# ── Segments ──────────────────────────────────────────────────────────────────

@router.get("/segments/columns")
def segment_columns(project_id: int = Query(...), current_user: User = Depends(get_current_user)):
    df = _load(project_id)
    categorical = df.select_dtypes(include=["object", "category"]).columns.tolist()
    numeric = df.select_dtypes(include="number").columns.tolist()
    return {"categorical_columns": categorical, "numeric_columns": numeric}


class SegmentRequest(BaseModel):
    project_id: int
    segment_col: str
    metric_col: str


@router.post("/segments/run")
def segment_run(payload: SegmentRequest, current_user: User = Depends(get_current_user)):
    df = _load(payload.project_id)
    if payload.segment_col not in df.columns:
        raise HTTPException(status_code=400, detail=f"Column '{payload.segment_col}' not found.")
    if payload.metric_col not in df.columns:
        raise HTTPException(status_code=400, detail=f"Column '{payload.metric_col}' not found.")
    try:
        grouped = df.groupby(payload.segment_col)[payload.metric_col].agg(
            count="count", mean="mean", median="median", std="std", min="min", max="max"
        ).reset_index()
        grouped.columns = ["segment", "count", "mean", "median", "std", "min", "max"]
        return to_jsonable({
            "segment_col": payload.segment_col,
            "metric_col": payload.metric_col,
            "segments": grouped.to_dict(orient="records"),
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Segment analysis failed: {e}")
