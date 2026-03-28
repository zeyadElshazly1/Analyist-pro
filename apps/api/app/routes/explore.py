from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.routes.upload import PROJECT_FILES
from app.services.file_loader import load_dataset
from app.services.cleaner import clean_dataset
from app.services.serializers import to_jsonable
from app.services.timeseries import detect_date_columns, run_timeseries
from app.services.duplicate_detector import detect_duplicates
from app.services.outlier_explorer import explore_outliers
from app.services.correlation_matrix import build_correlation_matrix
from app.services.column_compare import compare_columns
from app.services.multifile_compare import compare_files

router = APIRouter(prefix="/explore", tags=["explore"])


def _load(project_id: int):
    if project_id not in PROJECT_FILES:
        raise HTTPException(status_code=404, detail="No uploaded file for this project.")
    try:
        df = load_dataset(PROJECT_FILES[project_id]["path"])
        df_clean, _, _ = clean_dataset(df)
        return df_clean
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class Proj(BaseModel):
    project_id: int

class TimeseriesRun(BaseModel):
    project_id: int
    date_col: str
    value_col: str

class OutlierRun(BaseModel):
    project_id: int
    column: str

class ColCompareRun(BaseModel):
    project_id: int
    col_a: str
    col_b: str

class MultifileRun(BaseModel):
    project_id_a: int
    project_id_b: int


@router.post("/timeseries/columns")
def timeseries_columns(payload: Proj):
    df = _load(payload.project_id)
    return {
        "date_columns": detect_date_columns(df),
        "value_columns": df.select_dtypes(include=["number"]).columns.tolist(),
    }

@router.post("/timeseries/run")
def timeseries_run(payload: TimeseriesRun):
    df = _load(payload.project_id)
    try:
        return to_jsonable(run_timeseries(df, payload.date_col, payload.value_col))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/duplicates")
def duplicates(payload: Proj):
    return to_jsonable(detect_duplicates(_load(payload.project_id)))

@router.post("/outliers/columns")
def outlier_columns(payload: Proj):
    df = _load(payload.project_id)
    return {"columns": df.select_dtypes(include=["number"]).columns.tolist()}

@router.post("/outliers/run")
def outliers_run(payload: OutlierRun):
    df = _load(payload.project_id)
    try:
        return to_jsonable(explore_outliers(df, payload.column))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/correlations")
def correlations(payload: Proj):
    return to_jsonable(build_correlation_matrix(_load(payload.project_id)))

@router.post("/compare-columns/columns")
def compare_cols_list(payload: Proj):
    return {"columns": _load(payload.project_id).columns.tolist()}

@router.post("/compare-columns/run")
def compare_cols_run(payload: ColCompareRun):
    df = _load(payload.project_id)
    try:
        return to_jsonable(compare_columns(df, payload.col_a, payload.col_b))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/multifile")
def multifile(payload: MultifileRun):
    for pid in [payload.project_id_a, payload.project_id_b]:
        if pid not in PROJECT_FILES:
            raise HTTPException(status_code=404, detail=f"No file for project {pid}")
    try:
        return to_jsonable(compare_files(
            PROJECT_FILES[payload.project_id_a]["path"],
            PROJECT_FILES[payload.project_id_b]["path"],
        ))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
