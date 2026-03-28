from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.state import PROJECT_FILES
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


# ── Time Series ───────────────────────────────────────────────────────────────

@router.get("/timeseries/columns")
def timeseries_columns(project_id: int = Query(...)):
    df = _load(project_id)
    date_cols = detect_date_columns(df)
    numeric_cols = df.select_dtypes(include=["number"]).columns.tolist()
    return {"date_columns": date_cols, "value_columns": numeric_cols}


class TimeseriesRequest(BaseModel):
    project_id: int
    date_col: str
    value_col: str


@router.post("/timeseries/run")
def timeseries_run(payload: TimeseriesRequest):
    df = _load(payload.project_id)
    try:
        result = run_timeseries(df, payload.date_col, payload.value_col)
        return to_jsonable(result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Time series analysis failed: {e}")


# ── Duplicates ────────────────────────────────────────────────────────────────

class ProjectRequest(BaseModel):
    project_id: int


@router.post("/duplicates")
def duplicates(payload: ProjectRequest):
    df = _load(payload.project_id)
    try:
        result = detect_duplicates(df)
        return to_jsonable(result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Duplicate detection failed: {e}")


# ── Outliers ──────────────────────────────────────────────────────────────────

@router.get("/outliers/columns")
def outlier_columns(project_id: int = Query(...)):
    df = _load(project_id)
    return {"numeric_columns": get_numeric_columns(df)}


class OutlierRequest(BaseModel):
    project_id: int
    column: str


@router.post("/outliers/run")
def outliers_run(payload: OutlierRequest):
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
def correlations(payload: ProjectRequest):
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
def compare_columns_options(project_id: int = Query(...)):
    df = _load(project_id)
    return {"columns": get_columns(df)}


class ColumnCompareRequest(BaseModel):
    project_id: int
    col_a: str
    col_b: str


@router.post("/compare-columns/run")
def compare_columns_run(payload: ColumnCompareRequest):
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
def multifile_compare(payload: MultifileRequest):
    if payload.project_id_a not in PROJECT_FILES:
        raise HTTPException(status_code=404, detail=f"No file for project {payload.project_id_a}")
    if payload.project_id_b not in PROJECT_FILES:
        raise HTTPException(status_code=404, detail=f"No file for project {payload.project_id_b}")

    path_a = PROJECT_FILES[payload.project_id_a]["path"]
    path_b = PROJECT_FILES[payload.project_id_b]["path"]
    label_a = PROJECT_FILES[payload.project_id_a].get("filename", f"Project {payload.project_id_a}")
    label_b = PROJECT_FILES[payload.project_id_b].get("filename", f"Project {payload.project_id_b}")

    try:
        result = compare_files(path_a, path_b, label_a=label_a, label_b=label_b)
        return to_jsonable(result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Multi-file comparison failed: {e}")
