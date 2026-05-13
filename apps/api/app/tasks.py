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
    from app.services.analyzer import analyze_dataset, generate_executive_panel, get_dataset_summary
    from app.services.cleaning_adapter import build_cleaning_result
    from app.services.health_adapter import build_health_result
    from app.services.insight_adapter import build_insight_results
    from app.services.intake_for_analysis import build_intake_for_project
    from app.services.serializers import to_jsonable
    from app.services.analysis.large_dataset_mode import (
        LARGE_DATASET_NARRATIVE_NOTE,
        attach_large_dataset_meta,
        prepare_analysis_frame,
    )
    from app.services.analysis.analysis_planner import build_analysis_plan
    from app.services.analysis.analysis_plan_hygiene import apply_analysis_plan_hygiene
    from app.services.analysis.ranking import rerank_after_plan_hygiene
    from app.services.analysis.narrative import generate_narrative
    from app.services.analysis.finalize_insights import final_cap_with_candidate_count, build_insight_selection_meta
    from app.services.analysis.pre_analysis import build_pre_analysis_profile
    from app.services.analysis.profile_hygiene import apply_pre_analysis_profile_hygiene
    from app.config import MAX_INSIGHTS, PRE_ANALYSIS_PROFILE_HYGIENE_ENABLED
    from app.db import SessionLocal as _SessionLocal

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
        # Backfill intake_result on cache hits if the cached payload predates
        # the intake-persistence change (best-effort).
        if not cached.get("intake_result"):
            _db = _SessionLocal()
            try:
                intake_snapshot = build_intake_for_project(
                    _db, project_id, file_path=info.get("path"), file_hash=file_hash
                )
            finally:
                _db.close()
            if intake_snapshot:
                cached = {**cached, "intake_result": intake_snapshot}
                set_cached_analysis(project_id, file_hash, cached)
        # Backfill analysis_plan on cache hits that predate 86C.
        if not cached.get("analysis_plan"):
            try:
                _cols = list((cached.get("intake_result") or {}).get("columns") or [])
                if _cols:
                    cached = {**cached, "analysis_plan": build_analysis_plan(_cols).model_dump()}
                    set_cached_analysis(project_id, file_hash, cached)
            except Exception:
                pass
        # Backfill insight_selection_meta on cache hits that predate 88M.
        if not cached.get("insight_selection_meta"):
            try:
                from app.services.analysis.finalize_insights import build_cached_insight_selection_meta
                meta = build_cached_insight_selection_meta(cached)
                if meta:
                    cached = {**cached, "insight_selection_meta": meta}
                    set_cached_analysis(project_id, file_hash, cached)
            except Exception:
                pass
        # Backfill pre_analysis_profile on cache hits that predate 90G.
        if not cached.get("pre_analysis_profile"):
            try:
                _df_back = load_dataset(info["path"])
                _df_back_clean, _, _ = clean_dataset(_df_back)
                _profile = build_pre_analysis_profile(_df_back_clean)
                cached = {**cached, "pre_analysis_profile": _profile.model_dump()}
                set_cached_analysis(project_id, file_hash, cached)
            except Exception:
                pass
        # Record a run-history entry for this cache-hit invocation.
        from app.services.run_tracker import create_run_stub, finalise_run as _finalise_run
        _cache_db = _SessionLocal()
        try:
            cache_run = create_run_stub(_cache_db, project_id, file_hash, None, trigger_source="user")
            cache_result = {**cached, "run_id": cache_run.id if cache_run else cached.get("run_id")}
            _finalise_run(_cache_db, cache_run, json.dumps(cache_result, default=str))
        except Exception:
            cache_result = cached
        finally:
            _cache_db.close()
        emit("Complete", 100, "Loaded from cache")
        _publish(r, run_key, {"__done__": True, "result": cache_result, "from_cache": True})
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
        df_analysis, ld_meta = prepare_analysis_frame(df_clean)
        profile = profile_dataset(df_clean)
        health_score = calculate_health_score(df_clean)
        health_result = build_health_result(df_clean, health_score, profile, df_raw=df).model_dump()
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
        insights, _pre_hygiene_narrative = analyze_dataset(df_analysis)
        # Pre-Analysis V2 profile — built before hygiene so it can be used (90K)
        try:
            _pre_analysis_profile = build_pre_analysis_profile(df_clean).model_dump()
        except Exception:
            _pre_analysis_profile = None
        # Dataset Intelligence Layer — hygiene before adapter/ranking
        _dtypes = {c: str(t) for c, t in df_clean.dtypes.items()}
        _plan = build_analysis_plan(columns=df_clean.columns.tolist(), dtypes=_dtypes)
        insights = apply_analysis_plan_hygiene(insights, _plan)
        insights = apply_pre_analysis_profile_hygiene(
            insights,
            _pre_analysis_profile,
            enabled=PRE_ANALYSIS_PROFILE_HYGIENE_ENABLED,
        )
        insights = rerank_after_plan_hygiene(insights)
        post_hygiene_candidates = list(insights)
        insights, post_hygiene_candidate_count = final_cap_with_candidate_count(insights)
        insight_selection_meta = build_insight_selection_meta(post_hygiene_candidates, insights)
        narrative = generate_narrative(insights, df_analysis, total_found=post_hygiene_candidate_count)
        if ld_meta["large_dataset_mode"]:
            narrative = narrative + LARGE_DATASET_NARRATIVE_NOTE
        insight_results = [ir.model_dump() for ir in build_insight_results(insights, analysis_plan=_plan)]
        executive_panel = generate_executive_panel(insights)
    except Exception as e:
        logger.error(f"Insight generation failed for project {project_id}: {e}", exc_info=True)
        _publish(r, run_key, {
            "__error__": "Insight generation failed. Please try running the analysis again."
        })
        return

    emit("Building your brief", 90, f"{len(insights)} findings ready for review")

    # ── Intake snapshot (canonical, best-effort) ──────────────────────────────
    _db = _SessionLocal()
    try:
        intake_result = build_intake_for_project(
            _db, project_id, file_path=info.get("path"), file_hash=file_hash
        )
    finally:
        _db.close()

    # ── Build canonical result ────────────────────────────────────────────────
    result = {
        "project_id": project_id,
        "intake_result": intake_result,                      # canonical V1 (None if unavailable)
        "cleaning_summary": to_jsonable(cleaning_summary),   # backward compat — CleaningSummaryCards legacy fallback
        "cleaning_result": cleaning_result,                  # canonical V1
        "profile_result": to_jsonable(profile),              # canonical V1
        "health_result": health_result,                      # canonical V1
        "insight_results": insight_results,                  # canonical V1 (replaces insights)
        "narrative": narrative,
        "executive_panel": to_jsonable(executive_panel),
        "dataset_summary": get_dataset_summary(df_analysis), # large-dataset transparency metadata
        "analysis_plan": _plan.model_dump(),                 # Dataset Intelligence Layer (86C)
        "insight_selection_meta": insight_selection_meta,   # 88M — candidate-pool transparency
        "pre_analysis_profile": _pre_analysis_profile,      # 90G — V2 dataset understanding
    }
    attach_large_dataset_meta(result, ld_meta)

    # ── Persist to DB via run_tracker ─────────────────────────────────────────
    from app.db import SessionLocal
    from app.models import Project as ProjectModel
    from app.services.audit import log_event
    from app.services.run_tracker import create_run_stub, finalise_run

    db = SessionLocal()
    try:
        run = create_run_stub(db, project_id, file_hash, None, trigger_source="user")
        result["run_id"] = run.id if run else None
        result_json_str = json.dumps(result, default=str)
        finalise_run(db, run, result_json_str)
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

    # ── Cache (run_id now in result) ──────────────────────────────────────────
    set_cached_analysis(project_id, file_hash, result)

    from app.state import PROJECT_FILES
    PROJECT_FILES.setdefault(project_id, {})["last_insights"] = [
        i.get("finding", "") for i in insights[:5]
    ]

    emit("Complete", 100, "Analysis finished")
    _publish(r, run_key, {"__done__": True, "result": result})
