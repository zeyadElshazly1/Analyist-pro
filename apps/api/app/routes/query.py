from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import get_db
from app.middleware.auth import get_current_user
from app.models import User
from app.services.access_guards import get_project_for_user
from app.services.dataset_loader import load_prepared
from app.services.serializers import to_jsonable
from app.services.sql_engine import execute_query, get_schema, validate_sql

router = APIRouter(prefix="/query", tags=["query"])


def _load_owned(db: Session, user: User, project_id: int):
    """Verify ownership, then load + clean the dataset."""
    get_project_for_user(db, project_id, user)
    return load_prepared(project_id)


class QueryRequest(BaseModel):
    project_id: int
    sql: str


@router.post("/execute")
def query_execute(
    req: QueryRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not req.sql.strip():
        raise HTTPException(status_code=400, detail="SQL query cannot be empty.")
    try:
        validate_sql(req.sql)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    df = _load_owned(db, current_user, req.project_id)

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
def query_schema(
    project_id: int = Query(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    df = _load_owned(db, current_user, project_id)
    return {"columns": get_schema(df), "table_name": "data"}
