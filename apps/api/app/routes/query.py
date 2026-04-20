from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.middleware.auth import get_current_user
from app.models import User
from app.services.dataset_loader import load_prepared
from app.services.serializers import to_jsonable
from app.services.sql_engine import execute_query, get_schema, validate_sql

router = APIRouter(prefix="/query", tags=["query"])


def _load(project_id: int):
    return load_prepared(project_id)


class QueryRequest(BaseModel):
    project_id: int
    sql: str


@router.post("/execute")
def query_execute(req: QueryRequest, current_user: User = Depends(get_current_user)):
    if not req.sql.strip():
        raise HTTPException(status_code=400, detail="SQL query cannot be empty.")
    try:
        validate_sql(req.sql)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    df = _load(req.project_id)

    try:
        result = execute_query(df, req.sql)
        return to_jsonable(result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ImportError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Query failed: {e}")


@router.get("/schema")
def query_schema(project_id: int = Query(...), current_user: User = Depends(get_current_user)):
    df = _load(project_id)
    return {"columns": get_schema(df), "table_name": "data"}
