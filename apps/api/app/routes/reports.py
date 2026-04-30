import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import Optional

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

def _build_report_result(draft: ReportDraft, db: Session) -> dict:
    """
    Assemble a canonical ReportResult from a draft, linked analysis, and audit log.

    All data already exists in the DB — this is a pure assembly step.
    Fields without V1 persistence (user_edits, export_artifact_refs) are empty lists.
    """
    from app.schemas.report import IncludedInsight, ReportResult, ReportSection

    # Resolve selected insights from the linked analysis result.
    # Defensive: only consider the linked analysis if it actually belongs to
    # the draft's project, so a tampered draft can never pull data from an
    # analysis owned by a different project.
    included_insights: list[IncludedInsight] = []
    if draft.analysis_result_id:
        analysis = (
            db.query(AnalysisResult)
            .filter(
                AnalysisResult.id == draft.analysis_result_id,
                AnalysisResult.project_id == draft.project_id,
            )
            .first()
        )
        if analysis:
            try:
                result_data = json.loads(analysis.result_json)
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
        included_charts=[],          # chart resolution deferred to V2
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
    return {
        "id": draft.id,
        "project_id": draft.project_id,
        "title": draft.title,
        "summary": draft.summary,
        "selected_insight_ids": draft.selected_insights,
        "selected_chart_ids": draft.selected_charts,
        "template": draft.template,
        "created_at": draft.created_at.isoformat() if draft.created_at else None,
        "updated_at": draft.updated_at.isoformat() if draft.updated_at else None,
        "report_result": _build_report_result(draft, db),
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
        select_default_insight_selection,
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
    raw = result_data.get("insight_results") or result_data.get("insights") or []
    if not isinstance(raw, list):
        raw = []
    raw_dicts = [x for x in raw if isinstance(x, dict)]

    summary = build_fallback_executive_summary(result_data)
    selected = select_default_insight_selection(raw_dicts)

    draft = ReportDraft(
        project_id=project_id,
        analysis_result_id=analysis.id,
        title=project.name,
        summary=summary,
        selected_insight_ids_json=json.dumps(selected),
    )
    db.add(draft)
    db.commit()
    db.refresh(draft)

    return _draft_response(draft, db)
