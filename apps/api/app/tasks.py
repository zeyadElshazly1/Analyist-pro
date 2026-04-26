"""
Celery task definitions.

Background task for running the analysis pipeline so the FastAPI event
loop is never blocked during the 30–90 s analysis window.

Progress events are published to a Redis list keyed by ``run_key``
(a unique key generated per run by the SSE endpoint).  The SSE endpoint
polls this list and forwards events to the browser in real time.

Event envelope:
  Progress  → {"step": str, "progress": int, "detail": str}
  Done      → {"__done__": true, "result": {...}}
  Error     → {"__error__": "message string"}
"""
import json
import logging

from app.worker import celery_app

logger = logging.getLogger(__name__)

_PROGRESS_TTL = 7200   # 2 hours — matches result_expires


# ── Internal helpers ──────────────────────────────────────────────────────────

def _publish(r, run_key: str, event: dict) -> None:
    """Append one JSON event to the Redis progress list."""
    r.rpush(run_key, json.dumps(event, default=str))
    r.expire(run_key, _PROGRESS_TTL)


# ── Task ──────────────────────────────────────────────────────────────────────

@celery_app.task(bind=True, name="tasks.run_analysis", max_retries=0)
def run_analysis_task(self, project_id: int, run_key: str) -> None:
    """
    Run the full analysis pipeline for *project_id* in a Celery worker
    process and publish step-by-step progress to ``run_key`` in Redis.

    The SSE endpoint (``GET /analysis/stream/{project_id}``) polls
    ``run_key`` and forwards events to the browser.
    """
    import redis as _redis
    from app.config import REDIS_URL

    r = _redis.from_url(
        REDIS_URL or "redis://localhost:6379/0",
        decode_responses=True,
        socket_connect_timeout=5,
        socket_timeout=5,
    )

    def emit(step: str, progress: int, detail: str = "") -> None:
        _publish(r, run_key, {"step": step, "progress": progress, "detail": detail})
        self.update_state(state="PROGRESS", meta={"step": step, "progress": progress})

    try:
        _run_pipeline(project_id, run_key, r, emit)
    except Exception as exc:
        logger.error(
            f"Analysis task failed for project {project_id}: {exc}", exc_info=True
        )
        _publish(r, run_key, {"__error__": "Analysis failed unexpectedly. Please try again."})
    finally:
        r.close()


# ── Pipeline (mirrors analysis_stream._run_analysis_stream) ──────────────────

def _run_pipeline(project_id: int, run_key: str, r, emit) -> None:
    """Full analysis pipeline — emits the same canonical result as analysis.py."""
    from app.state import get_project_file_info
    from app.services.cache import get_cached_analysis, set_cached_analysis
    from app.services.file_loader import load_dataset
    from app.services.cleaner import clean_dataset
    from app.services.profiler import profile_dataset, calculate_health_score
    from app.services.analyzer import analyze_dataset, generate_executive_panel
    from app.services.cleaning_adapter import build_cleaning_result
    from app.services.health_adapter import build_health_result
    from app.services.insight_adapter import build_insight_results
    from app.services.serializers import to_jsonable

    # ── Step 0: resolve file ──────────────────────────────────────────────────
    emit("Loading dataset", 5, "Resolving uploaded file...")
    info = get_project_file_info(project_id)
    if not info:
        _publish(r, run_key, {"__error__": "No uploaded file found for this project."})
        return

    file_hash = info.get("file_hash")

    # ── Cache check ───────────────────────────────────────────────────────────
    cached = get_cached_analysis(project_id, file_hash)
    if cached:
        emit("Loading from cache", 80, "Previous analysis found — loading instantly")
        emit("Complete", 100, "Loaded from cache")
        _publish(r, run_key, {"__done__": True, "result": cached, "from_cache": True})
        return

    # ── Step 1: load ──────────────────────────────────────────────────────────
    try:
        df = load_dataset(info["path"])
    except Exception as e:
        logger.error(f"Failed to load dataset for project {project_id}: {e}", exc_info=True)
        _publish(r, run_key, {
            "__error__": "Could not read the uploaded file. It may be corrupted or in an unsupported format."
        })
        return

    if df.empty:
        _publish(r, run_key, {
            "__error__": "Uploaded dataset is empty. Please upload a file with at least one row of data."
        })
        return

    emit("Dataset loaded", 10, f"{len(df):,} rows × {len(df.columns)} columns")

    # ── Step 2: clean ─────────────────────────────────────────────────────────
    original_cols = df.columns.tolist()
    try:
        df_clean, cleaning_report, cleaning_summary = clean_dataset(df)
    except Exception as e:
        logger.error(f"Data cleaning failed for project {project_id}: {e}", exc_info=True)
        _publish(r, run_key, {
            "__error__": "Data cleaning failed. Please check your file format and try again."
        })
        return

    if df_clean.empty:
        _publish(r, run_key, {
            "__error__": "Dataset became empty after cleaning. Your file may contain only headers or invalid rows."
        })
        return

    cleaning_result = build_cleaning_result(
        original_cols, df_clean.columns.tolist(), cleaning_report, cleaning_summary
    ).model_dump()
    emit("Data cleaned", 35, f"{cleaning_summary.get('steps', 0)} cleaning operations applied")

    # ── Step 3: profile ───────────────────────────────────────────────────────
    try:
        profile = profile_dataset(df_clean)
        health_score = calculate_health_score(df_clean)
        health_result = build_health_result(df_clean, health_score, profile).model_dump()
    except Exception as e:
        logger.error(f"Column profiling failed for project {project_id}: {e}", exc_info=True)
        _publish(r, run_key, {
            "__error__": "Column profiling failed. The dataset may contain unsupported data types."
        })
        return

    grade = health_score.get("grade", "?")
    emit("Finding key patterns", 60, f"Data quality grade: {grade}")

    # ── Step 4: insights ──────────────────────────────────────────────────────
    try:
        insights, narrative = analyze_dataset(df_clean)
        insight_results = [ir.model_dump() for ir in build_insight_results(insights)]
        executive_panel = generate_executive_panel(insights)
    except Exception as e:
        logger.error(f"Insight generation failed for project {project_id}: {e}", exc_info=True)
        _publish(r, run_key, {
            "__error__": "Insight generation failed. Please try running the analysis again."
        })
        return

    emit("Building your brief", 90, f"{len(insights)} findings ready for review")

    # ── Build canonical result ────────────────────────────────────────────────
    result = {
        "project_id": project_id,
        "cleaning_summary": to_jsonable(cleaning_summary),   # backward compat — CleaningSummaryCards legacy fallback
        "cleaning_result": cleaning_result,                  # canonical V1
        "profile_result": to_jsonable(profile),              # canonical V1
        "health_result": health_result,                      # canonical V1
        "insight_results": insight_results,                  # canonical V1 (replaces insights)
        "narrative": narrative,
        "executive_panel": to_jsonable(executive_panel),
    }

    # ── Persist to DB ─────────────────────────────────────────────────────────
    from app.db import SessionLocal
    from app.models import AnalysisResult, Project as ProjectModel
    from app.services.audit import log_event

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
        proj = db.query(ProjectModel).filter(ProjectModel.id == project_id).first()
        log_event(
            db,
            action="analysis_completed",
            user_id=proj.user_id if proj else None,
            resource_type="project",
            resource_id=str(project_id),
            detail={"project_id": project_id, "insight_count": len(insights)},
            category="activation",
        )
    except Exception as e:
        logger.error(
            f"Failed to persist analysis for project {project_id}: {e}", exc_info=True
        )
        db.rollback()
    finally:
        db.close()

    # ── Cache and finalise ────────────────────────────────────────────────────
    set_cached_analysis(project_id, file_hash, result)

    from app.state import PROJECT_FILES
    PROJECT_FILES.setdefault(project_id, {})["last_insights"] = [
        i.get("finding", "") for i in insights[:5]
    ]

    if analysis_id:
        result["run_id"] = analysis_id

    emit("Complete", 100, "Analysis finished")
    _publish(r, run_key, {"__done__": True, "result": result})
