from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.services.cleaner import clean_dataset
from app.services.file_loader import load_dataset
from app.services.pivot_service import run_pivot
from app.services.serializers import to_jsonable
from app.state import PROJECT_FILES

router = APIRouter(prefix="/pivot", tags=["pivot"])


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


class PivotRequest(BaseModel):
    project_id: int
    rows: list[str]
    cols: list[str] = []
    values: str
    aggfunc: str = "sum"
    top_n: int = 20


@router.post("/run")
def pivot_run(req: PivotRequest):
    df = _load(req.project_id)
    try:
        result = run_pivot(df, req.rows, req.cols, req.values, req.aggfunc, req.top_n)
        return to_jsonable(result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Pivot failed: {e}")


@router.get("/columns")
def pivot_columns(project_id: int = Query(...)):
    df = _load(project_id)
    numeric = df.select_dtypes(include="number").columns.tolist()
    return {
        "all_columns": df.columns.tolist(),
        "numeric_columns": numeric,
    }
