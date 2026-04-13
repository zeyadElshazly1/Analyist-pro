"""
Server-Sent Events (SSE) endpoint for streaming analysis progress.

When Redis is available the analysis runs in a Celery worker process so
the FastAPI event loop is never blocked.  The SSE generator dispatches the
Celery task and then polls a Redis progress list that the task writes to.

If Redis / Celery is unavailable (e.g. local dev without Redis) the
endpoint automatically falls back to the original inline execution path
so the platform keeps working without any external services.

Frontend usage (unchanged):
  const es = new EventSource(`/analysis/stream/${projectId}?token=${token}`);
  es.onmessage = (e) => {
    const { step, progress, result, error } = JSON.parse(e.data);
    if (result) { es.close(); setResult(result); }
    if (error)  { es.close(); setError(error);   }
  };
"""
import asyncio
import json
import logging
import uuid
from typing import AsyncIterator, Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse

from app.db import SessionLocal
from app.models import AnalysisResult
from app.services.analyzer import analyze_dataset, get_dataset_summary
from app.services.audit import log_event
from app.services.cache import get_cached_analysis, set_cached_analysis
from app.services.cleaner import clean_dataset
from app.services.file_loader import load_dataset
from app.services.profiler import calculate_health_score, profile_dataset
from app.services.serializers import to_jsonable
from app.state import PROJECT_FILES, get_project_file_info

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/analysis", tags=["analysis-stream"])


# ── SSE helpers ───────────────────────────────────────────────────────────────

def _sse(data: dict) -> str:
    return f"data: {json.dumps(data, default=str)}\n\n"


def _heartbeat() -> str:
    return ": keep-alive\n\n"


# ── Route ─────────────────────────────────────────────────────────────────────

@router.get("/stream/{project_id}")
async def stream_analysis(
    project_id: int,
    token: Optional[str] = Query(None, description="JWT token (EventSource can't send headers)"),
):
    """
    SSE endpoint — streams analysis progress in real time.

    With Redis: dispatches a Celery task and polls the Redis progress list.
    Without Redis: runs the analysis pipeline inline (fallback mode).
    """
    # ── Auth ──────────────────────────────────────────────────────────────────
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

    # ── Dispatch to Celery or fall back to inline ─────────────────────────────
    from app.config import REDIS_URL

    if REDIS_URL:
        run_key = f"analysis:run:{project_id}:{uuid.uuid4().hex}"
        try:
            from app.tasks import run_analysis_task
            run_analysis_task.delay(project_id, run_key)
            generator = _poll_celery_stream(project_id, run_key)
        except Exception as e:
            logger.warning(
                f"Celery dispatch failed ({e}), falling back to inline analysis"
            )
            generator = _run_analysis_stream(project_id)
    else:
        generator = _run_analysis_stream(project_id)

    return StreamingResponse(
        generator,
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


# ── Celery-backed stream: poll Redis progress list ────────────────────────────

async def _poll_celery_stream(project_id: int, run_key: str) -> AsyncIterator[str]:
    """
    Polls the Redis list written by ``run_analysis_task`` and forwards
    every progress event to the browser via SSE.

    Polling interval: 500 ms.  Max wait: 3 minutes (360 polls).
    """
    import redis as _redis
    from app.config import REDIS_URL

    offset = 0
    max_polls = 360  # 360 × 0.5 s = 3 minutes

    for _ in range(max_polls):
        # Read any new events since last poll
        try:
            r = _redis.from_url(
                REDIS_URL, decode_responses=True, socket_timeout=1
            )
            new_events = r.lrange(run_key, offset, -1)
            r.close()
        except Exception:
            new_events = []

        for event_json in new_events:
            offset += 1
            try:
                event = json.loads(event_json)
            except Exception:
                continue

            if "__done__" in event:
                yield _sse({
                    "step": "result",
                    "progress": 100,
                    "result": event["result"],
                })
                return

            if "__error__" in event:
                yield _sse({"error": event["__error__"]})
                return

            # Normal progress event
            yield _sse(event)

        yield _heartbeat()
        await asyncio.sleep(0.5)

    yield _sse({"error": "Analysis timed out after 3 minutes. Please try again."})


# ── Inline fallback: run analysis synchronously in the async generator ────────

async def _run_analysis_stream(project_id: int) -> AsyncIterator[str]:
    """
    Original inline SSE generator — used when Redis/Celery is unavailable.
    Runs the entire analysis pipeline within the request.
    """

    def emit(step: str, progress: int, detail: str = "") -> str:
        return _sse({"step": step, "progress": progress, "detail": detail})

    yield emit("Loading dataset", 5, "Resolving uploaded file...")
    info = get_project_file_info(project_id)
    if not info:
        yield _sse({"error": "No uploaded file found for this project."})
        return

    file_hash = info.get("file_hash")
    cached = get_cached_analysis(project_id, file_hash)
    if cached:
        yield emit("Loading from cache", 80, "Previous analysis found — loading instantly")
        yield emit("Complete", 100, "Loaded from cache")
        yield _sse({"step": "result", "progress": 100, "result": cached, "from_cache": True})
        return

    yield _heartbeat()
    try:
        df = load_dataset(info["path"])
    except Exception as e:
        logger.error(f"Failed to load dataset for project {project_id}: {e}", exc_info=True)
        yield _sse({"error": "Could not read the uploaded file. It may be corrupted or in an unsupported format."})
        return

    if df.empty:
        yield _sse({"error": "Uploaded dataset is empty. Please upload a file with at least one row of data."})
        return

    yield emit("Dataset loaded", 10, f"{len(df):,} rows × {len(df.columns)} columns")

    yield _heartbeat()
    yield emit("Cleaning data", 20, "Detecting types, imputing missing values...")
    try:
        df_clean, cleaning_report, cleaning_summary = clean_dataset(df)
    except Exception as e:
        logger.error(f"Data cleaning failed for project {project_id}: {e}", exc_info=True)
        yield _sse({"error": "Data cleaning failed. Please check your file format and try again."})
        return

    if df_clean.empty:
        yield _sse({"error": "Dataset became empty after cleaning."})
        return

    yield emit("Data cleaned", 35, f"{cleaning_summary.get('steps', 0)} cleaning operations applied")

    yield _heartbeat()
    yield emit("Profiling columns", 45, f"Analyzing {len(df_clean.columns)} columns...")
    try:
        profile = profile_dataset(df_clean)
        health_score = calculate_health_score(df_clean)
    except Exception as e:
        logger.error(f"Column profiling failed for project {project_id}: {e}", exc_info=True)
        yield _sse({"error": "Column profiling failed."})
        return

    grade = health_score.get("grade", "?")
    yield emit("Profile complete", 60, f"Data health grade: {grade}")

    yield _heartbeat()
    yield emit("Detecting insights", 70, "Running correlation, anomaly, and segment analysis...")
    try:
        insights, narrative = analyze_dataset(df_clean)
        dataset_summary = get_dataset_summary(df_clean)
    except Exception as e:
        logger.error(f"Insight generation failed for project {project_id}: {e}", exc_info=True)
        yield _sse({"error": "Insight generation failed. Please try running the analysis again."})
        return

    yield emit("Insights ready", 90, f"{len(insights)} insights found")

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
        from app.models import Project as ProjectModel
        proj = db.query(ProjectModel).filter(ProjectModel.id == project_id).first()
        log_event(
            db,
            action="analysis",
            user_id=proj.user_id if proj else None,
            resource_type="analysis",
            resource_id=str(analysis_id),
            detail={"project_id": project_id, "insight_count": len(insights)},
        )
    except Exception as e:
        logger.error(f"Failed to persist stream analysis: {e}", exc_info=True)
        db.rollback()
    finally:
        db.close()

    set_cached_analysis(project_id, file_hash, result)

    PROJECT_FILES.setdefault(project_id, {})["last_insights"] = [
        i.get("finding", "") for i in insights[:5]
    ]

    if analysis_id:
        result["analysis_id"] = analysis_id

    yield emit("Complete", 100, "Analysis finished")
    yield _sse({"step": "result", "progress": 100, "result": result})
