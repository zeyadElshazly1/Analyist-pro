import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import Any, Optional

from app.db import get_db
from app.middleware.auth import get_current_user
from app.middleware.plans import require_feature
from app.models import AnalysisResult, AuditLog, Project, ReportDraft, User
from app.services.access_guards import get_project_for_user
from app.services.file_loader import load_dataset
from app.services.report_service import generate_excel_report, generate_html_report, generate_pdf_report
from app.services.reporting import apply_draft_to_result
from app.state import get_project_file_info

router = APIRouter(prefix="/reports", tags=["reports"])

logger = logging.getLogger(__name__)


def _load_export_statuses_from_audit(db: Session, project_id_str: str):
    """Build export history rows from audit log (most recent 10).

    Isolated helper so callers can catch DB/ORM mismatches without failing
    the rest of the draft payload.
    """
    from app.schemas.report import ExportRecord

    _ACTION_TO_STATUS = {
        "export_completed":   "completed",
        "export_failed":      "failed",
        "export_unavailable": "unavailable",
    }
    export_logs = (
        db.query(AuditLog)
        .filter(
            AuditLog.action.in_(list(_ACTION_TO_STATUS.keys())),
            AuditLog.resource_type == "project",
            AuditLog.resource_id == project_id_str,
        )
        .order_by(AuditLog.created_at.desc())
        .limit(10)
        .all()
    )
    export_statuses: list = []
    for log in export_logs:
        try:
            detail = json.loads(log.detail) if log.detail else {}
        except Exception:
            detail = {}
        fmt = detail.get("format")
        status = _ACTION_TO_STATUS.get(log.action)
        if fmt in ("html", "pdf", "xlsx") and status is not None:
            err = detail.get("error") if status in ("failed", "unavailable") else None
            export_statuses.append(ExportRecord(
                format=fmt,          # type: ignore[arg-type]
                status=status,       # type: ignore[arg-type]
                exported_at=log.created_at,
                error_message=err,
            ))
    return export_statuses


def _get_stored_analysis(project_id: int, current_user: User, db: Session) -> tuple:
    """Resolve the analysis result that the saved Report Builder draft is
    pinned to (or the latest run if there is no draft), with the draft's
    edits applied.

    Behaviour:
      1. Verify the project belongs to the current user (404 otherwise).
      2. Load the most recent ``ReportDraft`` for the project.
      3. If the draft is linked to a specific ``analysis_result_id``, use that
         exact run — *and* verify it belongs to this project so a tampered
         draft can never pull data from another project's analysis.
      4. Otherwise fall back to the project's latest analysis run.
      5. Apply the draft's selected findings + edited summary so the returned
         result is what export / preview should render.

    Returns ``(result_dict, report_title)`` where ``report_title`` is the
    draft's title when set (preferred for the report header), else the
    project name.
    """
    project = get_project_for_user(db, project_id, current_user)

    draft = (
        db.query(ReportDraft)
        .filter(ReportDraft.project_id == project_id)
        .order_by(ReportDraft.created_at.desc())
        .first()
    )

    analysis: AnalysisResult | None = None

    # Prefer the analysis the consultant actually built the draft against —
    # an export should never silently switch to a newer run if the draft is
    # pinned to an older one.
    if draft and draft.analysis_result_id:
        analysis = (
            db.query(AnalysisResult)
            .filter(
                AnalysisResult.id == draft.analysis_result_id,
                AnalysisResult.project_id == project_id,  # defence-in-depth
            )
            .first()
        )

    if analysis is None:
        analysis = (
            db.query(AnalysisResult)
            .filter(AnalysisResult.project_id == project_id)
            .order_by(AnalysisResult.created_at.desc())
            .first()
        )

    if not analysis:
        raise HTTPException(status_code=404, detail="No analysis found. Run analysis first.")

    result = json.loads(analysis.result_json)

    if draft is not None:
        result = apply_draft_to_result(
            result,
            draft_summary=draft.summary,
            draft_title=draft.title,
            # Only apply the selection when the draft actually recorded one;
            # a freshly created draft (no edits) keeps the full insight list.
            selected_indices=(
                draft.selected_insights
                if draft.selected_insight_ids_json is not None
                else None
            ),
            selected_chart_ids=_draft_selected_chart_ids_safe(draft),
        )

    title = (draft.title.strip() if draft and draft.title else "") or project.name
    return result, title


def _load_df(project_id: int):
    """Load the raw DataFrame for a project (used for Data Preview sheet)."""
    import pandas as pd
    try:
        info = get_project_file_info(project_id)
        if info:
            return load_dataset(info["path"])
    except Exception:
        pass
    return pd.DataFrame()


@router.get("/export/{project_id}")
def export_report(
    project_id: int,
    format: str = Query("html", pattern="^(html|pdf|xlsx)$"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    _plan: None = Depends(require_feature("report_export")),
):
    result, project_name = _get_stored_analysis(project_id, current_user, db)

    def _log_export(
        fmt: str,
        *,
        action: str = "export_completed",
        error: str | None = None,
    ) -> None:
        """Record an export attempt to the audit log.

        Synchronous (_sync=True) so the row is committed before the response
        returns — this is what makes the audit-backed export-history strip
        reliably rehydrate on the very next /reports/draft request.

        ``action`` is one of:
          * ``export_completed``    — the file was generated and streamed
          * ``export_failed``       — generation raised; ``error`` carries detail
          * ``export_unavailable``  — generator deps missing (PDF 501 path)
        """
        try:
            from app.services.audit import log_event
            detail: dict[str, str] = {"format": fmt}
            if error:
                detail["error"] = error[:500]   # cap to keep audit row sane
            log_event(
                db,
                action=action,
                user_id=current_user.id,
                resource_type="project",
                resource_id=str(project_id),
                detail=detail,
                category="export",
                _sync=True,
            )
        except Exception:
            # Audit must never break the export response — swallow.
            pass

    if format == "xlsx":
        try:
            df = _load_df(project_id)
            xlsx_bytes = generate_excel_report(df, result, project_name)
        except Exception as e:
            _log_export("xlsx", action="export_failed", error=str(e))
            raise HTTPException(status_code=500, detail=f"Excel generation failed: {e}")
        _log_export("xlsx")
        return Response(
            content=xlsx_bytes,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f'attachment; filename="analysis_report_{project_id}.xlsx"'},
        )

    if format == "html":
        try:
            html = generate_html_report(_load_df(project_id), result, project_name)
        except Exception as e:
            _log_export("html", action="export_failed", error=str(e))
            raise HTTPException(status_code=500, detail=f"HTML generation failed: {e}")
        _log_export("html")
        return Response(
            content=html,
            media_type="text/html",
            headers={"Content-Disposition": f'attachment; filename="analysis_report_{project_id}.html"'},
        )

    # pdf
    try:
        pdf_bytes = generate_pdf_report(_load_df(project_id), result, project_name)
    except RuntimeError as e:
        # PDF generator deps not installed (WeasyPrint / pdfkit) → record
        # honestly so the strip can show "unavailable" after a refresh.
        _log_export("pdf", action="export_unavailable", error=str(e))
        raise HTTPException(status_code=501, detail=str(e))
    except Exception as e:
        _log_export("pdf", action="export_failed", error=str(e))
        raise HTTPException(status_code=500, detail=f"PDF generation failed: {e}")
    _log_export("pdf")
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="analysis_report_{project_id}.pdf"'},
    )


@router.get("/preview/{project_id}")
def preview_report(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    result, _ = _get_stored_analysis(project_id, current_user, db)
    return result


# ── Report Result builder ─────────────────────────────────────────────────────


def _safe_json_list(raw: str | None) -> list[Any]:
    """Parse a JSON Text column expecting a list; never raises."""
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError, ValueError):
        return []
    return data if isinstance(data, list) else []


def _draft_selected_chart_ids_safe(draft: ReportDraft) -> list[Any]:
    """``selected_chart_ids_json`` decoded as list — survives malformed payloads."""
    return _safe_json_list(getattr(draft, "selected_chart_ids_json", None))


def _chart_block_from_run(result_data: dict[str, Any] | None) -> list[dict[str, Any]]:
    """Prefer the first non-empty canonical chart array on stored analysis."""
    if not isinstance(result_data, dict):
        return []
    for key in ("charts", "chart_results", "suggested_charts", "chart_gallery"):
        blk = result_data.get(key)
        if isinstance(blk, list):
            vals = [c for c in blk if isinstance(c, dict)]
            if vals:
                return vals
    return []


def _chart_catalog_by_id(charts: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for ch in charts:
        for field in ("chart_id", "id"):
            cid = ch.get(field)
            if isinstance(cid, str) and cid.strip():
                key = cid.strip()
                if key not in out:
                    out[key] = ch
                break
    return out


def _coerce_run_chart_meta(match: dict[str, Any] | None, *, fallback_title: str) -> tuple[str, str]:
    if match:
        t = match.get("title") or match.get("chart_title")
        if isinstance(t, str) and t.strip():
            title = t.strip()[:2048]
        else:
            title = fallback_title[:2048]
        ct = match.get("chart_type") or match.get("type")
        if isinstance(ct, str) and ct.strip():
            ctype = ct.strip()[:255]
        else:
            ctype = "unknown"
    else:
        title, ctype = fallback_title[:2048], "unknown"
    return title, ctype


def _one_included_chart(
    raw_item: Any,
    *,
    by_id: dict[str, dict[str, Any]],
    ordered: list[dict[str, Any]],
) -> tuple[str, str, str] | None:
    """Resolve one selection slot to ``(chart_id, chart_type, title)`` or skip."""
    if isinstance(raw_item, dict):
        cid_raw = raw_item.get("chart_id")
        if cid_raw is None:
            cid_raw = raw_item.get("id")
        if isinstance(cid_raw, float) and cid_raw == int(cid_raw):
            cid_raw = str(int(cid_raw))
        elif isinstance(cid_raw, int):
            cid_raw = str(cid_raw)
        cid = cid_raw.strip() if isinstance(cid_raw, str) else ""
        if not cid:
            return None
        match = by_id.get(cid)
        title, ctype_def = _coerce_run_chart_meta(match, fallback_title=cid)
        ct_override = raw_item.get("chart_type") or raw_item.get("type")
        if isinstance(ct_override, str) and ct_override.strip():
            ctype = ct_override.strip()[:255]
        else:
            ctype = ctype_def
        t_override = raw_item.get("title") or raw_item.get("chart_title")
        if isinstance(t_override, str) and t_override.strip():
            title = t_override.strip()[:2048]
        return (cid[:512], ctype, title)

    if isinstance(raw_item, str) and raw_item.strip():
        cid = raw_item.strip()[:512]
        match = by_id.get(cid)
        title, ctype = _coerce_run_chart_meta(match, fallback_title=cid)
        return (cid, ctype, title)

    if isinstance(raw_item, int) and ordered and raw_item >= 0 and raw_item < len(ordered):
        ch = ordered[raw_item]
        cid_inner: str | None = None
        for field in ("chart_id", "id"):
            v = ch.get(field)
            if isinstance(v, str) and v.strip():
                cid_inner = v.strip()
                break
        cid = cid_inner if cid_inner else f"idx_{raw_item}"
        title, ctype = _coerce_run_chart_meta(ch, fallback_title=cid)
        return (cid[:512], ctype, title)

    return None


def _result_data_for_draft(
    draft: ReportDraft,
    db: Session,
) -> dict[str, Any] | None:
    """Fetch and parse the analysis result linked to ``draft``.

    Returns ``None`` when no linked result exists, the result belongs to a
    different project (tampered draft), or the JSON is malformed.
    """
    if not draft.analysis_result_id:
        return None
    try:
        analysis = (
            db.query(AnalysisResult)
            .filter(
                AnalysisResult.id == draft.analysis_result_id,
                AnalysisResult.project_id == draft.project_id,
            )
            .first()
        )
        if analysis:
            return json.loads(analysis.result_json)
    except Exception:
        pass
    return None


def _build_available_charts_list(
    draft: ReportDraft,
    result_data: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    """Return an ordered catalog of all charts available in the linked run.

    Each entry: ``{chart_id, title, chart_type, selected}``.
    ``selected`` is ``True`` when the chart is present in the draft's
    ``selected_chart_ids_json`` list.  The list is in stored chart order
    (first non-empty chart block wins: charts / chart_results /
    suggested_charts / chart_gallery).  Charts without an explicit ID
    fall back to ``idx_N`` so every entry has a stable key.  Returns
    ``[]`` when no chart block is found.
    """
    ordered = _chart_block_from_run(result_data)
    if not ordered:
        return []

    by_id = _chart_catalog_by_id(ordered)

    # Resolve raw selection slots → set of selected chart_id strings.
    raw_selected = _draft_selected_chart_ids_safe(draft)
    selected_ids: set[str] = set()
    for slot in raw_selected:
        row = _one_included_chart(slot, by_id=by_id, ordered=ordered)
        if row is not None:
            selected_ids.add(row[0])

    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for idx, ch in enumerate(ordered):
        cid: str | None = None
        for field in ("chart_id", "id"):
            v = ch.get(field)
            if isinstance(v, str) and v.strip():
                cid = v.strip()[:512]
                break
        if cid is None:
            cid = f"idx_{idx}"
        if cid in seen:
            continue
        seen.add(cid)
        title, ctype = _coerce_run_chart_meta(ch, fallback_title=cid)
        out.append({
            "chart_id": cid,
            "title": title,
            "chart_type": ctype,
            "selected": cid in selected_ids,
        })

    return out


def _build_included_charts_list(draft: ReportDraft, result_data: dict[str, Any] | None) -> list:
    """Map draft.chart selection (+ optional persisted run chart payloads) to IncludedChart."""
    from app.schemas.report import IncludedChart

    selected = _draft_selected_chart_ids_safe(draft)
    if not selected:
        return []
    ordered = _chart_block_from_run(result_data)
    by_id = _chart_catalog_by_id(ordered)
    out: list[IncludedChart] = []
    seen: set[str] = set()
    for slot in selected:
        row = _one_included_chart(slot, by_id=by_id, ordered=ordered)
        if row is None:
            continue
        cid, ctype, title = row
        if cid in seen:
            continue
        seen.add(cid)
        out.append(IncludedChart(chart_id=cid, chart_type=ctype, title=title))
    return out


def _build_report_result(
    draft: ReportDraft,
    db: Session,
    *,
    result_data: dict[str, Any] | None = None,
) -> dict:
    """
    Assemble a canonical ReportResult from a draft, linked analysis, and audit log.

    All data already exists in the DB — this is a pure assembly step.
    Fields without V1 persistence (user_edits, export_artifact_refs) are empty lists.

    Pass ``result_data`` when the caller has already fetched the analysis
    result to avoid a second DB round-trip.
    """
    from app.schemas.report import IncludedInsight, ReportResult, ReportSection

    if result_data is None:
        result_data = _result_data_for_draft(draft, db)

    included_insights: list[IncludedInsight] = []
    if result_data is not None:
        try:
            raw = result_data.get("insight_results") or result_data.get("insights") or []
            # Resolve stable IDs (preferred) and legacy integer indices
            # against the same insight list the export will render, so
            # the draft response and the export agree on what's included.
            from app.services.reporting.draft_context import _select_indices
            resolved = _select_indices(raw, draft.selected_insights)
            for idx in resolved:
                ins = raw[idx]
                included_insights.append(IncludedInsight(
                    insight_id=ins.get("insight_id") or f"idx_{idx}",
                    title=(
                        ins.get("title") or ins.get("explanation")
                        or ins.get("finding") or f"Finding {idx + 1}"
                    ),
                    severity=ins.get("severity") or "medium",
                    index_in_run=idx,
                ))
        except Exception:
            pass

    included_charts = _build_included_charts_list(draft, result_data)

    # Default section list — all included; compare_summary excluded unless compare ran
    _SECTIONS = [
        ("executive_summary", "Executive Summary",  True,  True),
        ("data_quality",      "Data Quality",       True,  False),
        ("cleaning_steps",    "Cleaning Steps",     True,  False),
        ("top_insights",      "Top Insights",       True,  False),
        ("column_profiles",   "Column Profiles",    True,  False),
        ("chart_gallery",     "Chart Gallery",      True,  False),
        ("compare_summary",   "Compare Summary",    False, False),
    ]
    included_sections = [
        ReportSection(
            section_id=sid,      # type: ignore[arg-type]
            title=title,
            included=included,
            is_ai_generated=is_ai,
        )
        for sid, title, included, is_ai in _SECTIONS
    ]

    # Export history from audit log — best-effort only (schema drift or DB
    # errors must not 503 the whole draft).
    try:
        export_statuses = _load_export_statuses_from_audit(db, str(draft.project_id))
    except Exception:
        logger.warning(
            "Could not load export history from audit log for project %s",
            draft.project_id,
            exc_info=True,
        )
        export_statuses = []

    result = ReportResult(
        report_id=draft.id,
        run_id=draft.analysis_result_id,
        project_id=draft.project_id,
        title=draft.title or "",
        summary=draft.summary,
        template=draft.template,     # type: ignore[arg-type]
        included_sections=included_sections,
        included_insights=included_insights,
        included_charts=included_charts,
        user_edits=[],               # edit history not persisted in V1
        ai_generated_sections=["executive_summary"],
        export_statuses=export_statuses,
        export_artifact_refs=[],     # no artifact storage in V1
        created_at=draft.created_at,
        updated_at=draft.updated_at,
    )
    return result.model_dump()


def _draft_response(draft: ReportDraft, db: Session) -> dict:
    """Build the standard draft response dict with embedded canonical report_result."""
    result_data = _result_data_for_draft(draft, db)
    return {
        "id": draft.id,
        "project_id": draft.project_id,
        "title": draft.title,
        "summary": draft.summary,
        "selected_insight_ids": draft.selected_insights,
        "selected_chart_ids": _draft_selected_chart_ids_safe(draft),
        "available_charts": _build_available_charts_list(draft, result_data),
        "template": draft.template,
        "created_at": draft.created_at.isoformat() if draft.created_at else None,
        "updated_at": draft.updated_at.isoformat() if draft.updated_at else None,
        "report_result": _build_report_result(draft, db, result_data=result_data),
    }


# ── Report Draft ──────────────────────────────────────────────────────────────

class ReportDraftPayload(BaseModel):
    title: Optional[str] = None
    summary: Optional[str] = None
    selected_insight_ids: Optional[list] = None
    selected_chart_ids: Optional[list] = None
    template: Optional[str] = None


@router.post("/draft/{project_id}")
def upsert_report_draft(
    project_id: int,
    payload: ReportDraftPayload,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create or update a report draft for a project."""
    project = get_project_for_user(db, project_id, current_user)

    draft = (
        db.query(ReportDraft)
        .filter(ReportDraft.project_id == project_id)
        .order_by(ReportDraft.created_at.desc())
        .first()
    )

    if not draft:
        # Fetch latest analysis to link
        analysis = (
            db.query(AnalysisResult)
            .filter(AnalysisResult.project_id == project_id)
            .order_by(AnalysisResult.created_at.desc())
            .first()
        )
        draft = ReportDraft(
            project_id=project_id,
            analysis_result_id=analysis.id if analysis else None,
            title=payload.title or project.name,
        )
        db.add(draft)

    if payload.title is not None:
        draft.title = payload.title
    if payload.summary is not None:
        draft.summary = payload.summary
    if payload.selected_chart_ids is not None:
        draft.selected_chart_ids_json = json.dumps(payload.selected_chart_ids)

    # When a template is set, auto-populate insight selection if not explicitly provided
    if payload.template is not None and payload.template != draft.template:
        draft.template = payload.template
        if payload.selected_insight_ids is None:
            try:
                from app.services.reporting.templates import apply_template_to_draft
                analysis = (
                    db.query(AnalysisResult)
                    .filter(AnalysisResult.project_id == project_id)
                    .order_by(AnalysisResult.created_at.desc())
                    .first()
                )
                if analysis:
                    result_data = json.loads(analysis.result_json)
                    auto = apply_template_to_draft({}, payload.template, result_data)
                    draft.selected_insight_ids_json = json.dumps(
                        auto.get("selected_insight_ids", [])
                    )
            except Exception:
                pass

    if payload.selected_insight_ids is not None:
        draft.selected_insight_ids_json = json.dumps(payload.selected_insight_ids)

    db.commit()
    db.refresh(draft)

    from app.services.audit import log_event
    log_event(
        db,
        action="report_draft_created",
        user_id=current_user.id,
        resource_type="project",
        resource_id=str(project_id),
        category="activation",
    )

    return _draft_response(draft, db)


@router.get("/draft/{project_id}")
def get_report_draft(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Fetch the current report draft for a project.

    When no draft row exists yet but the project has at least one analysis
    result, a default draft is created, persisted, and returned so the Report
    Builder never opens empty after a successful run.
    """
    from app.services.reporting.default_draft import (
        build_fallback_executive_summary,
        select_default_chart_selection_for_result,
        select_default_insight_selection_for_result,
    )

    project = get_project_for_user(db, project_id, current_user)

    draft = (
        db.query(ReportDraft)
        .filter(ReportDraft.project_id == project_id)
        .order_by(ReportDraft.created_at.desc())
        .first()
    )
    if draft:
        return _draft_response(draft, db)

    analysis = (
        db.query(AnalysisResult)
        .filter(AnalysisResult.project_id == project_id)
        .order_by(AnalysisResult.created_at.desc())
        .first()
    )
    if not analysis:
        return None

    result_data = json.loads(analysis.result_json)

    summary = build_fallback_executive_summary(result_data)
    selected = select_default_insight_selection_for_result(result_data)
    selected_charts = select_default_chart_selection_for_result(result_data)

    draft = ReportDraft(
        project_id=project_id,
        analysis_result_id=analysis.id,
        title=project.name,
        summary=summary,
        selected_insight_ids_json=json.dumps(selected),
        selected_chart_ids_json=json.dumps(selected_charts),
    )
    db.add(draft)
    db.commit()
    db.refresh(draft)

    return _draft_response(draft, db)
