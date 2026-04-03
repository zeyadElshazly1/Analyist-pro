import json
import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import AnalysisResult, ProjectFile
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
def run_analysis(payload: AnalysisRequest, db: Session = Depends(get_db)):
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
def get_analysis_history(project_id: int, limit: int = Query(10, ge=1, le=50), db: Session = Depends(get_db)):
    """Return the N most recent analysis runs for a project."""
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


@router.get("/preview/{project_id}")
def preview_dataset(project_id: int, rows: int = Query(10, ge=1, le=100)):
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
def create_share_link(project_id: int, db: Session = Depends(get_db)):
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
    """Public endpoint — returns a full analysis result by share token."""
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
