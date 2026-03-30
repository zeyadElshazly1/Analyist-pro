from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.services.cleaner import clean_dataset
from app.services.file_loader import load_dataset
from app.services.serializers import to_jsonable
from app.services.sql_engine import execute_query, get_schema, validate_sql
from app.state import PROJECT_FILES

router = APIRouter(prefix="/query", tags=["query"])


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


class QueryRequest(BaseModel):
    project_id: int
    sql: str


@router.post("/query/execute")
def query_execute(req: QueryRequest):
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


@router.get("/query/schema")
def query_schema(project_id: int = Query(...)):
    df = _load(project_id)
    return {"columns": get_schema(df), "table_name": "data"}
