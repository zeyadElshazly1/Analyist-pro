"""
Server-Sent Events (SSE) endpoint for streaming analysis progress.

Frontend connects to GET /analysis/stream/{project_id} and receives
real-time progress updates as each analysis step completes.
Results are persisted to the database after each successful run.

Usage (frontend):
  const evtSource = new EventSource(`/analysis/stream/${projectId}`);
  evtSource.onmessage = (e) => {
    const { step, progress, result } = JSON.parse(e.data);
    if (result) { evtSource.close(); setAnalysisResult(result); }
  };
"""
import json
import logging
from typing import AsyncIterator, Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse

from app.db import SessionLocal
from app.models import AnalysisResult
from app.services.analyzer import analyze_dataset, get_dataset_summary
from app.services.cleaner import clean_dataset
from app.services.file_loader import load_dataset
from app.services.profiler import calculate_health_score, profile_dataset
from app.services.serializers import to_jsonable
from app.state import PROJECT_FILES, get_project_file_info

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/analysis", tags=["analysis-stream"])


def _sse(data: dict) -> str:
    """Format a dict as an SSE message."""
    return f"data: {json.dumps(data, default=str)}\n\n"


async def _run_analysis_stream(project_id: int) -> AsyncIterator[str]:
    """Generator that yields SSE messages as analysis steps complete,
    then persists the result to the database."""

    def emit(step: str, progress: int, detail: str = "") -> str:
        return _sse({"step": step, "progress": progress, "detail": detail})

    # Step 0: resolve file
    yield emit("Loading dataset", 5, "Resolving uploaded file...")
    info = get_project_file_info(project_id)
    if not info:
        yield _sse({"error": "No uploaded file found for this project."})
        return

    try:
        df = load_dataset(info["path"])
    except Exception as e:
        yield _sse({"error": f"Failed to load dataset: {e}"})
        return

    if df.empty:
        yield _sse({"error": "Uploaded dataset is empty."})
        return

    yield emit("Dataset loaded", 10, f"{len(df):,} rows × {len(df.columns)} columns")

    # Step 1: Clean
    yield emit("Cleaning data", 20, "Detecting types, imputing missing values...")
    try:
        df_clean, cleaning_report, cleaning_summary = clean_dataset(df)
    except Exception as e:
        yield _sse({"error": f"Cleaning failed: {e}"})
        return

    if df_clean.empty:
        yield _sse({"error": "Dataset became empty after cleaning."})
        return

    yield emit("Data cleaned", 35, f"{cleaning_summary.get('steps', 0)} cleaning operations applied")

    # Step 2: Profile
    yield emit("Profiling columns", 45, f"Analyzing {len(df_clean.columns)} columns...")
    try:
        profile = profile_dataset(df_clean)
        health_score = calculate_health_score(df_clean)
    except Exception as e:
        yield _sse({"error": f"Profiling failed: {e}"})
        return

    grade = health_score.get("grade", "?")
    yield emit("Profile complete", 60, f"Data health grade: {grade}")

    # Step 3: Insights
    yield emit("Detecting insights", 70, "Running correlation, anomaly, and segment analysis...")
    try:
        insights, narrative = analyze_dataset(df_clean)
        dataset_summary = get_dataset_summary(df_clean)
    except Exception as e:
        yield _sse({"error": f"Insight generation failed: {e}"})
        return

    yield emit("Insights ready", 90, f"{len(insights)} insights found")

    # Step 4: Build final result
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

    # ── Persist to database ───────────────────────────────────────────────────
    file_info = PROJECT_FILES.get(project_id) or {}
    file_hash = file_info.get("file_hash")
    analysis_id = None
    db = SessionLocal()
    try:
        analysis = AnalysisResult(
            project_id=project_id,
            file_hash=file_hash,
            result_json=json.dumps(result, default=str),
        )
        db.add(analysis)
        db.commit()
        db.refresh(analysis)
        analysis_id = analysis.id
        logger.info(f"Stream analysis persisted for project {project_id}: {len(insights)} insights, id={analysis_id}")
    except Exception as e:
        logger.error(f"Failed to persist stream analysis for project {project_id}: {e}", exc_info=True)
        db.rollback()
    finally:
        db.close()

    # Cache last insights for AI chat
    PROJECT_FILES.setdefault(project_id, {})["last_insights"] = [
        i.get("finding", "") for i in insights[:5]
    ]

    # Include analysis_id in result so frontend can use it for story generation
    if analysis_id:
        result["analysis_id"] = analysis_id

    yield emit("Complete", 100, "Analysis finished")
    yield _sse({"step": "result", "progress": 100, "result": result})


@router.get("/stream/{project_id}")
async def stream_analysis(
    project_id: int,
    token: Optional[str] = Query(None, description="JWT token (EventSource can't send headers)"),
):
    """
    SSE endpoint — streams analysis progress in real time.
    Auth token passed as ?token= query param (EventSource doesn't support Authorization headers).
    Returns `data: {...}` messages, ending with a `result` message containing
    the full analysis payload. Results are persisted to the database.
    """
    # Validate token and verify project belongs to user
    if token:
        from app.middleware.auth import _decode_token
        from app.models import Project
        payload = _decode_token(token)
        if payload is None:
            raise HTTPException(status_code=401, detail="Invalid or expired token")
        user_id: str = payload.get("sub", "")
        if not user_id:
            raise HTTPException(status_code=401, detail="Token missing subject claim")
        db = SessionLocal()
        try:
            project = db.query(Project).filter(
                Project.id == project_id,
                Project.user_id == user_id,
            ).first()
            if not project:
                raise HTTPException(status_code=404, detail="Project not found.")
        finally:
            db.close()
    else:
        raise HTTPException(status_code=401, detail="Authentication required")

    return StreamingResponse(
        _run_analysis_stream(project_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        },
    )
