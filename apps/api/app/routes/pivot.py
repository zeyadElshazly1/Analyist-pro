from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.middleware.auth import get_current_user
from app.models import User
from app.services.dataset_loader import load_prepared
from app.services.pivot_service import run_pivot
from app.services.serializers import to_jsonable

router = APIRouter(prefix="/pivot", tags=["pivot"])


def _load(project_id: int):
    return load_prepared(project_id)


class PivotRequest(BaseModel):
    project_id: int
    rows: list[str]
    cols: list[str] = []
    values: str
    aggfunc: str = "sum"
    top_n: int = 20


@router.post("/run")
def pivot_run(req: PivotRequest, current_user: User = Depends(get_current_user)):
    df = _load(req.project_id)
    try:
        result = run_pivot(df, req.rows, req.cols, req.values, req.aggfunc, req.top_n)
        return to_jsonable(result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Pivot failed: {e}")


@router.get("/columns")
def pivot_columns(project_id: int = Query(...), current_user: User = Depends(get_current_user)):
    df = _load(project_id)
    numeric = df.select_dtypes(include="number").columns.tolist()
    return {
        "all_columns": df.columns.tolist(),
        "numeric_columns": numeric,
    }
