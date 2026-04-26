import json
import logging
import math
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db import get_db
from app.limiter import limiter
from app.middleware.auth import get_current_user, optional_current_user
from app.middleware.plans import require_feature
from app.models import AnalysisResult, Project, ProjectFile, User
from app.schemas.analysis_schema import AnalysisRequest
from app.schemas.run_summary import RunDetail, RunResults, RunSummary
from app.services.run_resolver import build_run_detail, resolve_latest_run
from app.services.analyzer import analyze_dataset, generate_executive_panel
from app.services.cache import get_cached_analysis, set_cached_analysis
from app.services.cleaner import clean_dataset
from app.services.file_loader import load_dataset
from app.services.profiler import calculate_health_score, profile_dataset
from app.services.run_tracker import create_run_stub, fail_run, finalise_run, set_run_status
from app.services.serializers import to_jsonable
from app.state import PROJECT_FILES, get_project_file_info

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/analysis", tags=["analysis"])


# ── Route helpers ─────────────────────────────────────────────────────────────

def _get_file_path(project_id: int) -> str:
    """Resolve the uploaded file path for a project (cache → DB → disk)."""
    info = get_project_file_info(project_id)
    if not info:
        raise HTTPException(
            status_code=404,
            detail="No uploaded file found for this project. Please upload a dataset first.",
        )
    return info["path"]


# ── Main analysis endpoint ────────────────────────────────────────────────────

@router.post("/run")
@limiter.limit("6/minute")
def run_analysis(
    request: Request,
    payload: AnalysisRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    project_id = payload.project_id
    file_path = _get_file_path(project_id)

    # ── Cache check ───────────────────────────────────────────────────────────
    _file_info = PROJECT_FILES.get(project_id) or {}
    _file_hash = _file_info.get("file_hash")
    cached = get_cached_analysis(project_id, _file_hash)
    if cached:
        logger.info(f"Cache hit for project {project_id} — returning cached result")
        return cached

    try:
        df = load_dataset(file_path)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Uploaded file not found on disk.")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to load dataset for project {project_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Could not read the uploaded file. It may be corrupted or in an unsupported format.",
        )

    # ── Create run stub ───────────────────────────────────────────────────────
    run = create_run_stub(db, project_id, _file_hash, current_user.id, trigger_source="user")

    # ── Pipeline ──────────────────────────────────────────────────────────────
    try:
        if df.empty:
            raise HTTPException(status_code=400, detail="Uploaded dataset is empty.")

        from app.services.cleaning_adapter import build_cleaning_result
        from app.services.health_adapter import build_health_result
        from app.services.insight_adapter import build_insight_results

        original_cols = df.columns.tolist()
        if payload.use_cleaned:
            df_clean, cleaning_report, cleaning_summary = clean_dataset(df)
            if df_clean.empty or len(df_clean.columns) == 0:
                raise HTTPException(status_code=400, detail="Dataset became empty after cleaning.")
            cleaning_result = build_cleaning_result(
                original_cols, df_clean.columns.tolist(), cleaning_report, cleaning_summary
            ).model_dump()
        else:
            df_clean = df
            cleaning_report = []
            cleaning_summary = {"steps": 0, "note": "Skipped — raw data mode"}
            cleaning_result = {}

        set_run_status(db, run, "cleaning_complete")

        profile = profile_dataset(df_clean)
        health_score = calculate_health_score(df_clean)
        health_result = build_health_result(df_clean, health_score, profile).model_dump()

        set_run_status(db, run, "profiling_complete")

        insights, narrative = analyze_dataset(df_clean)
        insight_results = [r.model_dump() for r in build_insight_results(insights)]
        executive_panel = generate_executive_panel(insights)

        set_run_status(db, run, "insights_complete")

        result = {
            "project_id": project_id,
            "run_id": run.id if run else None,
            "cleaning_summary": to_jsonable(cleaning_summary),   # backward compat — CleaningSummaryCards legacy fallback
            "cleaning_result": cleaning_result,                  # canonical V1
            "profile_result": to_jsonable(profile),              # canonical V1
            "health_result": health_result,                      # canonical V1
            "insight_results": insight_results,                  # canonical V1 (replaces insights)
            "narrative": narrative,
            "executive_panel": to_jsonable(executive_panel),
        }

        # ── Warm Redis cache before final DB commit ───────────────────────────
        set_cached_analysis(project_id, _file_hash, result)

        # ── Finalise run record ───────────────────────────────────────────────
        result_json_str = json.dumps(result, default=str)
        finalise_run(db, run, result_json_str)
        if run is None:
            # Run tracking unavailable — persist a plain AnalysisResult (fallback)
            fallback = AnalysisResult(
                project_id=project_id,
                file_hash=_file_hash,
                result_json=result_json_str,
                status="report_ready",
            )
            db.add(fallback)
            try:
                db.commit()
            except SQLAlchemyError as e:
                db.rollback()
                logger.error(f"DB commit failed (fallback) for project {project_id}: {e}", exc_info=True)
                raise HTTPException(
                    status_code=503,
                    detail="Analysis completed but could not be saved. Please try again.",
                )

        # ── Post-commit ───────────────────────────────────────────────────────
        PROJECT_FILES.setdefault(project_id, {})["last_insights"] = [
            i.get("finding", "") for i in insights[:5] if isinstance(i, dict)
        ]

        logger.info(
            f"Run {run.id if run else 'fallback'} completed for project {project_id}: "
            f"{len(insights)} insights"
        )

        from app.services.audit import log_event
        try:
            log_event(
                db,
                action="analysis_completed",
                user_id=current_user.id,
                resource_type="project",
                resource_id=str(project_id),
                detail={"insights": len(insights), "run_id": run.id if run else None},
                category="activation",
            )
        except Exception:
            pass

        return result

    except HTTPException:
        fail_run(db, run, "HTTPException raised during pipeline")
        raise
    except MemoryError:
        fail_run(db, run, "MemoryError: dataset too large for available memory")
        logger.error(f"Out of memory during analysis for project {project_id}", exc_info=True)
        raise HTTPException(
            status_code=503,
            detail="The dataset is too large to analyze with the current server resources. Try a smaller file.",
        )
    except Exception as e:
        fail_run(db, run, f"{type(e).__name__}: {e}")
        logger.error(f"Analysis failed for project {project_id}: {type(e).__name__}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Analysis failed due to an unexpected error. Please try again.",
        )

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


@router.get("/runs/{project_id}", response_model=list[RunSummary])
def list_runs(
    project_id: int,
    limit: int = Query(20, ge=1, le=100),
    status: Optional[str] = Query(None, description="Filter by status, e.g. 'failed'"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Return recent analysis runs for a project, newest first.

    Lightweight — never includes result_json blobs.
    Supports run-history UI, failure debugging, and execution comparison.
    """
    from sqlalchemy.orm import joinedload

    project = db.query(Project).filter(
        Project.id == project_id, Project.user_id == current_user.id
    ).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found.")

    q = (
        db.query(AnalysisResult)
        .options(joinedload(AnalysisResult.source_file))
        .filter(AnalysisResult.project_id == project_id)
    )
    if status:
        q = q.filter(AnalysisResult.status == status)

    runs = q.order_by(AnalysisResult.id.desc()).limit(limit).all()

    summaries: list[RunSummary] = []
    for r in runs:
        started = r.started_at
        finished = r.created_at  # created_at is stamped at completion by finalise_run

        duration: Optional[float] = None
        if started and finished and finished > started:
            duration = (finished - started).total_seconds()

        summaries.append(RunSummary(
            run_id=r.id,
            project_id=r.project_id,
            status=r.status,
            trigger_source=r.trigger_source,
            started_at=started,
            finished_at=finished if r.status == "report_ready" else None,
            error_summary=r.error_summary,
            file_id=r.file_id,
            file_hash=r.file_hash,
            filename=r.source_file.filename if r.source_file else None,
            has_result=r.status == "report_ready",
            duration_seconds=duration,
        ))

    return summaries


@router.get("/run/{run_id}", response_model=RunDetail)
def get_run(
    run_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Fetch a single analysis run by id.

    Ownership is enforced via a project join.
    Returns RunDetail: all RunSummary fields plus has_* payload-presence flags.
    """
    from sqlalchemy.orm import joinedload

    r = (
        db.query(AnalysisResult)
        .options(joinedload(AnalysisResult.source_file))
        .join(Project, AnalysisResult.project_id == Project.id)
        .filter(AnalysisResult.id == run_id, Project.user_id == current_user.id)
        .first()
    )
    if not r:
        raise HTTPException(status_code=404, detail="Run not found.")
    return build_run_detail(r)


@router.get("/run/{run_id}/results", response_model=RunResults)
def get_run_results(
    run_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Return the canonical result blocks for a completed run.

    Behaves like "open previous run outputs" — never triggers recomputation.
    All block fields are None for runs that did not reach report_ready status.

    Canonical blocks returned:
      cleaning_result   — CleaningResult (what was fixed/flagged/skipped)
      health_result     — HealthResult (scores, warnings, column health)
      insight_results   — list of InsightResult (findings, evidence, severity)
      profile_result    — list of column profile dicts (type, stats, flags)
      executive_panel   — high-level summary panel
      narrative         — plain-text analysis narrative
      report_result     — AI data story if generated (story_result_json)

    Legacy fields (health_score, insights, cleaning_report) are
    intentionally excluded; use canonical blocks above instead.
    """
    r = (
        db.query(AnalysisResult)
        .join(Project, AnalysisResult.project_id == Project.id)
        .filter(AnalysisResult.id == run_id, Project.user_id == current_user.id)
        .first()
    )
    if not r:
        raise HTTPException(status_code=404, detail="Run not found.")

    # Runs that haven't completed return status context with all blocks null.
    if r.status != "report_ready":
        return RunResults(
            run_id=r.id,
            project_id=r.project_id,
            status=r.status,
            error_summary=r.error_summary,
            cleaning_result=None,
            health_result=None,
            insight_results=None,
            profile_result=None,
            executive_panel=None,
            narrative=None,
            story_result=None,
        )

    # Parse result_json once; extract canonical blocks only.
    try:
        stored = json.loads(r.result_json)
    except (json.JSONDecodeError, TypeError):
        stored = {}

    story_result = None
    if r.story_result_json:
        try:
            story_result = json.loads(r.story_result_json)
        except (json.JSONDecodeError, TypeError):
            pass

    def _block(key: str):
        """Return the block value, or None if absent / empty."""
        val = stored.get(key)
        return val if val else None

    return RunResults(
        run_id=r.id,
        project_id=r.project_id,
        status=r.status,
        error_summary=None,
        cleaning_result=_block("cleaning_result"),
        health_result=_block("health_result"),
        insight_results=_block("insight_results"),
        profile_result=_block("profile_result") or _block("profile"),
        executive_panel=_block("executive_panel"),
        narrative=stored.get("narrative") or None,
        story_result=story_result,
    )


@router.get("/runs/{project_id}/latest", response_model=RunDetail)
def get_latest_run(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Return the latest usable run for a project.

    Selection priority (single query):
      1. Most recent report_ready run
      2. Most recent non-failed run
      3. Most recent run of any status

    Returns 404 when the project has no runs at all.
    """
    project = db.query(Project).filter(
        Project.id == project_id, Project.user_id == current_user.id
    ).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found.")

    r = resolve_latest_run(db, project_id)
    if not r:
        raise HTTPException(status_code=404, detail="No runs found for this project.")
    return build_run_detail(r)


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
        logger.error(f"Failed to load dataset for preview (project {project_id}): {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Could not read the uploaded file for preview.")

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
    """Generate (or refresh) a public share token for the latest analysis. Expires in 30 days."""
    from datetime import datetime, timezone
    analysis = (
        db.query(AnalysisResult)
        .filter(AnalysisResult.project_id == project_id)
        .order_by(AnalysisResult.created_at.desc())
        .first()
    )
    if not analysis:
        raise HTTPException(status_code=404, detail="No analysis results found. Run analysis first.")

    now = datetime.now(timezone.utc)
    if not analysis.share_token or analysis.share_revoked:
        analysis.share_token = uuid.uuid4().hex
        analysis.share_revoked = False
        analysis.share_expires_at = now + timedelta(days=30)
        db.commit()
        db.refresh(analysis)

    return {
        "share_token": analysis.share_token,
        "expires_at": analysis.share_expires_at.isoformat() if analysis.share_expires_at else None,
    }


@router.delete("/share/{project_id}")
def revoke_share_link(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Revoke the share link for the latest analysis of a project."""
    analysis = (
        db.query(AnalysisResult)
        .filter(AnalysisResult.project_id == project_id)
        .order_by(AnalysisResult.created_at.desc())
        .first()
    )
    if not analysis or not analysis.share_token:
        raise HTTPException(status_code=404, detail="No active share link found.")

    analysis.share_revoked = True
    db.commit()
    return {"detail": "Share link revoked."}


@router.get("/shared/{token}")
def get_shared_analysis(token: str, db: Session = Depends(get_db)):
    """Public endpoint — returns a full analysis result by share token (no auth required)."""
    from datetime import datetime, timezone
    analysis = (
        db.query(AnalysisResult)
        .filter(AnalysisResult.share_token == token)
        .first()
    )
    if not analysis:
        raise HTTPException(status_code=404, detail="Share link not found or expired.")

    if analysis.share_revoked:
        raise HTTPException(status_code=404, detail="Share link not found or expired.")

    expires = analysis.share_expires_at
    if expires is not None and expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    if expires is not None and expires < datetime.now(timezone.utc):
        raise HTTPException(status_code=404, detail="Share link not found or expired.")

    result = json.loads(analysis.result_json)
    return {
        "project_id": analysis.project_id,
        "created_at": analysis.created_at.isoformat() if analysis.created_at else None,
        "expires_at": analysis.share_expires_at.isoformat() if analysis.share_expires_at else None,
        "result": result,
    }


@router.post("/story/{analysis_id}")
@limiter.limit("10/hour")
def generate_story(
    request: Request,
    analysis_id: int,
    current_user: User = Depends(get_current_user),
    _plan: None = Depends(require_feature("ai_story")),
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


@router.get("/diff")
def get_analysis_diff(
    run_a: int = Query(..., description="ID of the baseline analysis run"),
    run_b: int = Query(..., description="ID of the comparison analysis run"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Compare two analysis runs for the same project.
    Returns changed metrics, new/resolved insights, and column-level changes.
    Both runs must belong to projects owned by the current user.
    """
    def _fetch(run_id: int) -> AnalysisResult:
        r = (
            db.query(AnalysisResult)
            .join(Project)
            .filter(AnalysisResult.id == run_id, Project.user_id == current_user.id)
            .first()
        )
        if not r:
            raise HTTPException(status_code=404, detail=f"Analysis run {run_id} not found.")
        return r

    a_row = _fetch(run_a)
    b_row = _fetch(run_b)

    if a_row.project_id != b_row.project_id:
        raise HTTPException(
            status_code=400,
            detail="Both runs must belong to the same project.",
        )

    a = json.loads(a_row.result_json)
    b = json.loads(b_row.result_json)

    # ── Metric deltas ─────────────────────────────────────────────────────────
    def _num(d: dict, *keys, default=None):
        val = d
        for k in keys:
            if not isinstance(val, dict):
                return default
            val = val.get(k, default)
        try:
            return float(val) if val is not None else default
        except (TypeError, ValueError):
            return default

    metrics = []
    for label, path in [
        ("Health Score",   ("health_result", "health_score", "total_score")),
        ("Rows",           ("health_result", "row_count")),
        ("Columns",        ("health_result", "column_count")),
        ("Missing %",      ("health_result", "missingness_stats", "missing_cell_pct")),
        ("Cleaning Steps", ("cleaning_summary", "steps")),
    ]:
        va = _num(a, *path)
        vb = _num(b, *path)
        if va is None and vb is None:
            continue
        delta = round((vb or 0) - (va or 0), 2)
        metrics.append({
            "name": label,
            "a": va,
            "b": vb,
            "delta": delta,
            "direction": "up" if delta > 0 else ("down" if delta < 0 else "unchanged"),
        })

    # ── Insight diff ──────────────────────────────────────────────────────────
    def _insight_keys(result: dict) -> dict[str, dict]:
        """Map explanation text → insight dict for quick lookup."""
        out = {}
        for ins in result.get("insight_results", result.get("insights", [])):
            if isinstance(ins, dict):
                key = str(ins.get("explanation", ins.get("finding", ""))).strip().lower()
                if key:
                    out[key] = ins
        return out

    a_insights = _insight_keys(a)
    b_insights = _insight_keys(b)

    new_insights = [v for k, v in b_insights.items() if k not in a_insights]
    resolved_insights = [v for k, v in a_insights.items() if k not in b_insights]
    unchanged_insights = [v for k, v in b_insights.items() if k in a_insights]

    # ── Column profile diff ───────────────────────────────────────────────────
    def _col_map(result: dict) -> dict[str, dict]:
        cols = result.get("profile_result") or result.get("profile", [])
        if isinstance(cols, list):
            return {c.get("name", ""): c for c in cols if isinstance(c, dict)}
        return {}

    a_cols = _col_map(a)
    b_cols = _col_map(b)

    added_cols = [b_cols[k] for k in b_cols if k not in a_cols]
    removed_cols = [a_cols[k] for k in a_cols if k not in b_cols]
    changed_cols = []
    for name in set(a_cols) & set(b_cols):
        ac = a_cols[name]
        bc = b_cols[name]
        changes = {}
        for field in ("dtype", "missing_pct", "unique_count"):
            av, bv = ac.get(field), bc.get(field)
            if av != bv:
                changes[field] = {"a": av, "b": bv}
        if changes:
            changed_cols.append({"name": name, "changes": changes})

    return {
        "run_a": {
            "id": a_row.id,
            "created_at": a_row.created_at.isoformat() if a_row.created_at else None,
            "file_hash": a_row.file_hash,
        },
        "run_b": {
            "id": b_row.id,
            "created_at": b_row.created_at.isoformat() if b_row.created_at else None,
            "file_hash": b_row.file_hash,
        },
        "same_file": a_row.file_hash == b_row.file_hash and a_row.file_hash is not None,
        "metrics": metrics,
        "insights": {
            "new":      new_insights,
            "resolved": resolved_insights,
            "unchanged_count": len(unchanged_insights),
        },
        "columns": {
            "added":   added_cols,
            "removed": removed_cols,
            "changed": changed_cols,
        },
    }


@router.get("/data-table")
def get_data_table(
    project_id: int = Query(...),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=10, le=500),
    sort_col: Optional[str] = Query(None),
    sort_dir: str = Query("asc", pattern="^(asc|desc)$"),
    search: Optional[str] = Query(None, max_length=200),
    column_filters: Optional[str] = Query(None, max_length=4000),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Return a paginated, sortable, searchable, filterable view of the raw dataset.

    - page / per_page: pagination controls
    - sort_col / sort_dir: column sorting (asc | desc)
    - search: full-text search across all string columns (case-insensitive)
    - column_filters: JSON array of filter objects, each with:
        { "col": str, "op": "eq"|"neq"|"contains"|"gt"|"gte"|"lt"|"lte"|"is_null"|"not_null", "value": str }
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
        logger.error(f"Failed to load dataset for data-table (project {project_id}): {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Could not read the uploaded file.")

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

    # ── Column-level filters ──────────────────────────────────────────────────
    active_filters: list[dict] = []
    if column_filters and column_filters.strip():
        try:
            raw_filters = json.loads(column_filters)
            if isinstance(raw_filters, list):
                for f in raw_filters:
                    col_name = f.get("col", "")
                    op = f.get("op", "")
                    val = str(f.get("value", ""))
                    if col_name not in df.columns or not op:
                        continue
                    series = df[col_name]
                    try:
                        if op == "is_null":
                            df = df[series.isnull()]
                        elif op == "not_null":
                            df = df[series.notnull()]
                        elif op == "contains":
                            df = df[series.astype(str).str.lower().str.contains(val.lower(), na=False, regex=False)]
                        elif op == "eq":
                            numeric = pd.to_numeric(series, errors="coerce")
                            if numeric.notna().any():
                                df = df[pd.to_numeric(series, errors="coerce") == float(val)]
                            else:
                                df = df[series.astype(str).str.lower() == val.lower()]
                        elif op == "neq":
                            numeric = pd.to_numeric(series, errors="coerce")
                            if numeric.notna().any():
                                df = df[pd.to_numeric(series, errors="coerce") != float(val)]
                            else:
                                df = df[series.astype(str).str.lower() != val.lower()]
                        elif op == "gt":
                            df = df[pd.to_numeric(series, errors="coerce") > float(val)]
                        elif op == "gte":
                            df = df[pd.to_numeric(series, errors="coerce") >= float(val)]
                        elif op == "lt":
                            df = df[pd.to_numeric(series, errors="coerce") < float(val)]
                        elif op == "lte":
                            df = df[pd.to_numeric(series, errors="coerce") <= float(val)]
                        active_filters.append(f)
                    except (ValueError, TypeError):
                        pass  # Skip unparseable filter values silently
        except (json.JSONDecodeError, TypeError):
            logger.warning(f"Invalid column_filters JSON for project {project_id}")

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
        "active_filters": active_filters,
    }


@router.get("/download-cleaned/{project_id}")
def download_cleaned_dataset(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Run the cleaning pipeline on the project's uploaded file and return the
    result as a CSV file download.  Useful for inspecting or re-using the
    cleaned data outside Analyist Pro.
    """
    import io
    from fastapi.responses import StreamingResponse as _StreamingResponse

    # Verify project ownership
    project = db.query(Project).filter(
        Project.id == project_id, Project.user_id == current_user.id
    ).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found.")

    file_path = _get_file_path(project_id)
    try:
        df = load_dataset(file_path)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Uploaded file not found on disk.")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to load dataset for download (project {project_id}): {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Could not read the uploaded file.")

    if df.empty:
        raise HTTPException(status_code=400, detail="Uploaded dataset is empty.")

    try:
        df_clean, _report, _summary = clean_dataset(df)
    except Exception as e:
        logger.error(f"Cleaning failed for project {project_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Data cleaning failed.")

    if df_clean.empty:
        raise HTTPException(status_code=400, detail="Dataset became empty after cleaning.")

    # Resolve original filename for the Content-Disposition header
    _file_info = PROJECT_FILES.get(project_id) or {}
    original_name = _file_info.get("filename", f"project_{project_id}")
    import pathlib
    stem = pathlib.Path(original_name).stem
    download_name = f"cleaned_{stem}.csv"

    buf = io.StringIO()
    df_clean.to_csv(buf, index=False)
    buf.seek(0)

    return _StreamingResponse(
        iter([buf.read()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{download_name}"'},
    )
