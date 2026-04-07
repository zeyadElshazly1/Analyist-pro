import json
import logging
import math
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.middleware.auth import get_current_user, optional_current_user
from app.models import AnalysisResult, Project, ProjectFile, User
from app.schemas.analysis import AnalysisRequest
from app.services.analyzer import analyze_dataset, get_dataset_summary
from app.services.cleaner import clean_dataset
from app.services.file_loader import load_dataset
from app.services.profiler import calculate_health_score, profile_dataset
from app.services.serializers import to_jsonable
from app.state import PROJECT_FILES, get_project_file_info

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/analysis", tags=["analysis"])


def _get_file_path(project_id: int) -> str:
    """Resolve the uploaded file path for a project (cache → DB → disk)."""
    info = get_project_file_info(project_id)
    if not info:
        raise HTTPException(
            status_code=404,
            detail="No uploaded file found for this project. Please upload a dataset first.",
        )
    return info["path"]


@router.post("/run")
def run_analysis(
    payload: AnalysisRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    project_id = payload.project_id
    file_path = _get_file_path(project_id)

    try:
        df = load_dataset(file_path)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Uploaded file not found on disk.")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load dataset: {e}")

    try:
        if df.empty:
            raise HTTPException(status_code=400, detail="Uploaded dataset is empty.")

        df_clean, cleaning_report, cleaning_summary = clean_dataset(df)

        if df_clean.empty or len(df_clean.columns) == 0:
            raise HTTPException(status_code=400, detail="Dataset became empty after cleaning.")

        profile = profile_dataset(df_clean)
        health_score = calculate_health_score(df_clean)
        insights, narrative = analyze_dataset(df_clean)
        dataset_summary = get_dataset_summary(df_clean)

        result = {
            "project_id": project_id,
            "dataset_summary": to_jsonable(dataset_summary),
            "cleaning_summary": to_jsonable(cleaning_summary),
            "cleaning_report": to_jsonable(cleaning_report),
            "health_score": to_jsonable(health_score),
            "profile": to_jsonable(profile),
            "insights": to_jsonable(insights),
            "narrative": narrative,
        }

        # ── Persist analysis result to DB ─────────────────────────────────────
        file_info = PROJECT_FILES.get(project_id) or {}
        file_hash = file_info.get("file_hash")
        analysis = AnalysisResult(
            project_id=project_id,
            file_hash=file_hash,
            result_json=json.dumps(result, default=str),
        )
        db.add(analysis)

        # Cache last insights for AI chat context
        PROJECT_FILES.setdefault(project_id, {})["last_insights"] = [
            i.get("finding", "") for i in insights[:5]
        ]

        db.commit()
        logger.info(f"Analysis completed for project {project_id}: {len(insights)} insights")
        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Analysis failed for project {project_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Analysis failed: {e}")


@router.get("/history/{project_id}")
def get_analysis_history(
    project_id: int,
    limit: int = Query(10, ge=1, le=50),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return the N most recent analysis runs for a project (scoped to current user)."""
    # Verify project belongs to the current user before returning history
    project = db.query(Project).filter(
        Project.id == project_id, Project.user_id == current_user.id
    ).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found.")
    results = (
        db.query(AnalysisResult)
        .filter(AnalysisResult.project_id == project_id)
        .order_by(AnalysisResult.created_at.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id": r.id,
            "project_id": r.project_id,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "file_hash": r.file_hash,
        }
        for r in results
    ]


@router.get("/result/{analysis_id}")
def get_analysis_result(
    analysis_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return the full result JSON for a specific stored analysis run (scoped to current user)."""
    analysis = (
        db.query(AnalysisResult)
        .join(Project)
        .filter(AnalysisResult.id == analysis_id, Project.user_id == current_user.id)
        .first()
    )
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis result not found.")
    return {
        "id": analysis.id,
        "project_id": analysis.project_id,
        "created_at": analysis.created_at.isoformat() if analysis.created_at else None,
        "file_hash": analysis.file_hash,
        "result": json.loads(analysis.result_json),
    }


@router.get("/preview/{project_id}")
def preview_dataset(
    project_id: int,
    rows: int = Query(10, ge=1, le=100),
    current_user: User = Depends(get_current_user),
):
    """
    Return the first N rows of the raw uploaded dataset (before cleaning).
    Returns columns as a list and rows as a list-of-lists (frontend-friendly).
    """
    file_path = _get_file_path(project_id)

    try:
        df = load_dataset(file_path)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load dataset: {e}")

    preview = df.head(rows)
    columns = df.columns.tolist()
    row_data = to_jsonable(preview.values.tolist())
    return {
        "project_id": project_id,
        "columns": columns,
        "rows": row_data,
        "total_rows": len(df),
        "total_columns": len(df.columns),
        "missing_pct": round(df.isnull().sum().sum() / max(len(df) * len(df.columns), 1) * 100, 1),
    }


@router.post("/share/{project_id}")
def create_share_link(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Generate (or return existing) a public share token for the latest analysis."""
    analysis = (
        db.query(AnalysisResult)
        .filter(AnalysisResult.project_id == project_id)
        .order_by(AnalysisResult.created_at.desc())
        .first()
    )
    if not analysis:
        raise HTTPException(status_code=404, detail="No analysis results found. Run analysis first.")

    if not analysis.share_token:
        analysis.share_token = uuid.uuid4().hex
        db.commit()
        db.refresh(analysis)

    return {"share_token": analysis.share_token}


@router.get("/shared/{token}")
def get_shared_analysis(token: str, db: Session = Depends(get_db)):
    """Public endpoint — returns a full analysis result by share token (no auth required)."""
    analysis = (
        db.query(AnalysisResult)
        .filter(AnalysisResult.share_token == token)
        .first()
    )
    if not analysis:
        raise HTTPException(status_code=404, detail="Share link not found or expired.")

    result = json.loads(analysis.result_json)
    return {
        "project_id": analysis.project_id,
        "created_at": analysis.created_at.isoformat() if analysis.created_at else None,
        "result": result,
    }


@router.post("/story/{analysis_id}")
def generate_story(
    analysis_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Use Claude to generate a 5-slide data story from a stored analysis result."""
    analysis = (
        db.query(AnalysisResult)
        .join(Project)
        .filter(AnalysisResult.id == analysis_id, Project.user_id == current_user.id)
        .first()
    )
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis result not found.")

    try:
        result = json.loads(analysis.result_json)
        from app.services.ai_chat_service import generate_data_story
        story = generate_data_story(result)
        return story
    except Exception as e:
        logger.error(f"Story generation failed for analysis {analysis_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Story generation failed: {e}")


@router.get("/data-table")
def get_data_table(
    project_id: int = Query(...),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=10, le=500),
    sort_col: Optional[str] = Query(None),
    sort_dir: str = Query("asc", pattern="^(asc|desc)$"),
    search: Optional[str] = Query(None, max_length=200),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Return a paginated, sortable, searchable view of the raw dataset.

    - page / per_page: pagination controls
    - sort_col / sort_dir: column sorting (asc | desc)
    - search: full-text search across all string columns (case-insensitive)
    """
    # Verify project ownership
    project = db.query(Project).filter(
        Project.id == project_id, Project.user_id == current_user.id
    ).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found.")

    file_path = _get_file_path(project_id)
    try:
        df = load_dataset(file_path)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load dataset: {e}")

    if df.empty:
        raise HTTPException(status_code=404, detail="Dataset is empty.")

    # ── Build column metadata ─────────────────────────────────────────────────
    import pandas as pd
    import numpy as np

    def _col_dtype(series: pd.Series) -> str:
        if pd.api.types.is_integer_dtype(series):
            return "integer"
        if pd.api.types.is_float_dtype(series):
            return "float"
        if pd.api.types.is_bool_dtype(series):
            return "boolean"
        if pd.api.types.is_datetime64_any_dtype(series):
            return "datetime"
        return "text"

    columns_meta = []
    for col in df.columns:
        series = df[col]
        dtype = _col_dtype(series)
        null_count = int(series.isnull().sum())
        null_pct = round(null_count / max(len(series), 1) * 100, 1)
        unique_count = int(series.nunique(dropna=True))
        meta: dict = {
            "name": col,
            "dtype": dtype,
            "null_count": null_count,
            "null_pct": null_pct,
            "unique_count": unique_count,
        }
        if dtype in ("integer", "float"):
            valid = series.dropna()
            if len(valid) > 0:
                meta["min"] = to_jsonable(valid.min())
                meta["max"] = to_jsonable(valid.max())
                meta["mean"] = to_jsonable(round(float(valid.mean()), 4))
        columns_meta.append(meta)

    # ── Full-text search across string columns ────────────────────────────────
    if search and search.strip():
        q = search.strip().lower()
        str_cols = df.select_dtypes(include=["object", "string"]).columns.tolist()
        if str_cols:
            mask = df[str_cols].apply(
                lambda col: col.astype(str).str.lower().str.contains(q, na=False, regex=False)
            ).any(axis=1)
            df = df[mask]

    # ── Sorting ───────────────────────────────────────────────────────────────
    if sort_col and sort_col in df.columns:
        ascending = sort_dir == "asc"
        try:
            df = df.sort_values(by=sort_col, ascending=ascending, na_position="last")
        except Exception:
            pass  # Non-sortable column — leave unsorted

    # ── Pagination ────────────────────────────────────────────────────────────
    total_rows = len(df)
    total_pages = max(1, math.ceil(total_rows / per_page))
    page = min(page, total_pages)
    offset = (page - 1) * per_page
    page_df = df.iloc[offset : offset + per_page]

    # Serialize rows: convert NaN → None, numpy scalars → Python scalars
    raw_rows = page_df.where(pd.notna(page_df), other=None).values.tolist()
    rows = to_jsonable(raw_rows)

    return {
        "project_id": project_id,
        "columns": columns_meta,
        "rows": rows,
        "total_rows": total_rows,
        "total_pages": total_pages,
        "page": page,
        "per_page": per_page,
        "sort_col": sort_col,
        "sort_dir": sort_dir,
        "search": search or "",
    }
