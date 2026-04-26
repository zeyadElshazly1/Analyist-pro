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
from app.services.analyzer import analyze_dataset, generate_executive_panel
from app.services.audit import log_event
from app.services.cache import get_cached_analysis, set_cached_analysis
from app.services.cleaning_adapter import build_cleaning_result
from app.services.cleaner import clean_dataset
from app.services.file_loader import load_dataset
from app.services.health_adapter import build_health_result
from app.services.insight_adapter import build_insight_results
from app.services.profiler import calculate_health_score, profile_dataset
from app.services.run_tracker import create_run_stub, fail_run, finalise_run, set_run_status
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
    use_cleaned: bool = Query(True, description="Run analysis on cleaned data (true) or raw data (false)"),
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
            generator = _run_analysis_stream(project_id, use_cleaned=use_cleaned, user_id=user_id)
    else:
        generator = _run_analysis_stream(project_id, use_cleaned=use_cleaned, user_id=user_id)

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

async def _run_analysis_stream(
    project_id: int,
    use_cleaned: bool = True,
    user_id: Optional[str] = None,
) -> AsyncIterator[str]:
    """
    Original inline SSE generator — used when Redis/Celery is unavailable.
    Runs the entire analysis pipeline within the request.
    """

    def emit(step: str, progress: int, detail: str = "") -> str:
        return _sse({"step": step, "progress": progress, "detail": detail})

    db = SessionLocal()
    run: AnalysisResult | None = None
    try:
        yield emit("Reading your file", 5, "Resolving uploaded file...")
        info = get_project_file_info(project_id)
        if not info:
            yield _sse({"error": "No uploaded file found for this project."})
            return

        file_hash = info.get("file_hash")
        cached = get_cached_analysis(project_id, file_hash)
        if cached:
            yield emit("Reading your file", 80, "Previous analysis found — loading instantly")
            yield emit("Building your brief", 100, "Loaded from cache")
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

        yield emit("Reading your file", 10, f"{len(df):,} rows × {len(df.columns)} columns detected")

        # ── Create run stub ───────────────────────────────────────────────────
        run = create_run_stub(db, project_id, file_hash, user_id, trigger_source="user")

        yield _heartbeat()
        if use_cleaned:
            yield emit("Checking data quality", 20, "Detecting types, fixing inconsistencies...")
            try:
                original_cols = df.columns.tolist()
                df_clean, cleaning_report, cleaning_summary = clean_dataset(df)
            except Exception as e:
                logger.error(f"Data cleaning failed for project {project_id}: {e}", exc_info=True)
                fail_run(db, run, f"cleaning failed: {e}")
                yield _sse({"error": "Data cleaning failed. Please check your file format and try again."})
                return

            if df_clean.empty:
                fail_run(db, run, "dataset became empty after cleaning")
                yield _sse({"error": "Dataset became empty after cleaning."})
                return

            cleaning_result = build_cleaning_result(
                original_cols, df_clean.columns.tolist(), cleaning_report, cleaning_summary
            ).model_dump()
            yield emit("Checking data quality", 35, f"{cleaning_summary.get('steps', 0)} issues resolved")
        else:
            df_clean = df
            cleaning_report = []
            cleaning_summary = {"steps": 0, "note": "Skipped — raw data mode"}
            cleaning_result = {}
            yield emit("Checking data quality", 35, "Quality check skipped — using raw data")

        set_run_status(db, run, "cleaning_complete")

        yield _heartbeat()
        yield emit("Finding key patterns", 45, f"Scanning {len(df_clean.columns)} columns for signals...")
        try:
            profile = profile_dataset(df_clean)
            health_score = calculate_health_score(df_clean)
            health_result = build_health_result(df_clean, health_score, profile).model_dump()
        except Exception as e:
            logger.error(f"Column profiling failed for project {project_id}: {e}", exc_info=True)
            fail_run(db, run, f"profiling failed: {e}")
            yield _sse({"error": "Column profiling failed."})
            return

        grade = health_score.get("grade", "?")
        yield emit("Finding key patterns", 60, f"Data quality grade: {grade}")

        set_run_status(db, run, "profiling_complete")

        yield _heartbeat()
        yield emit("Finding key patterns", 70, "Running correlation, anomaly, and trend analysis...")
        try:
            insights, narrative = analyze_dataset(df_clean)
            insight_results = [r.model_dump() for r in build_insight_results(insights)]
            executive_panel = generate_executive_panel(insights)
        except Exception as e:
            logger.error(f"Insight generation failed for project {project_id}: {e}", exc_info=True)
            fail_run(db, run, f"insight generation failed: {e}")
            yield _sse({"error": "Insight generation failed. Please try running the analysis again."})
            return

        yield emit("Building your brief", 90, f"{len(insights)} findings ready for review")

        set_run_status(db, run, "insights_complete")

        result = {
            "project_id": project_id,
            "run_id": run.id if run else None,
            "cleaning_summary": to_jsonable(cleaning_summary),   # backward compat — CleaningSummaryCards legacy fallback
            "cleaning_result": cleaning_result,                  # canonical V1
            "profile_result": to_jsonable(profile),              # canonical V1
            "profile": to_jsonable(profile),                     # backward compat — old stored-result reads
            "health_result": health_result,                      # canonical V1
            "insight_results": insight_results,                  # canonical V1 (replaces insights)
            "narrative": narrative,
            "executive_panel": to_jsonable(executive_panel),
        }

        result_json_str = json.dumps(result, default=str)
        finalise_run(db, run, result_json_str)

        set_cached_analysis(project_id, file_hash, result)

        PROJECT_FILES.setdefault(project_id, {})["last_insights"] = [
            i.get("finding", "") for i in insights[:5] if isinstance(i, dict)
        ]

        try:
            log_event(
                db,
                action="analysis_completed",
                user_id=user_id,
                resource_type="project",
                resource_id=str(project_id),
                detail={"insights": len(insights), "run_id": run.id if run else None},
                category="activation",
            )
        except Exception:
            pass

        logger.info(
            f"Stream run {run.id if run else 'untracked'} completed for project {project_id}: "
            f"{len(insights)} insights"
        )

        yield emit("Building your brief", 100, "Ready to review")
        yield _sse({"step": "result", "progress": 100, "result": result})

    finally:
        db.close()
