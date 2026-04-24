import json

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import Optional

from app.db import get_db
from app.middleware.auth import get_current_user
from app.middleware.plans import require_feature
from app.models import AnalysisResult, AuditLog, Project, ReportDraft, User
from app.services.file_loader import load_dataset
from app.services.report_service import generate_excel_report, generate_html_report, generate_pdf_report
from app.state import get_project_file_info

router = APIRouter(prefix="/reports", tags=["reports"])


def _get_stored_analysis(project_id: int, user_id: str, db: Session) -> tuple:
    """Fetch the latest stored analysis for a project, scoped to the current user."""
    analysis = (
        db.query(AnalysisResult)
        .join(Project)
        .filter(
            AnalysisResult.project_id == project_id,
            Project.user_id == user_id,
        )
        .order_by(AnalysisResult.created_at.desc())
        .first()
    )
    if not analysis:
        raise HTTPException(status_code=404, detail="No analysis found. Run analysis first.")

    project = db.query(Project).filter(Project.id == project_id).first()
    project_name = project.name if project else f"Project {project_id}"
    result = json.loads(analysis.result_json)
    return result, project_name


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
    result, project_name = _get_stored_analysis(project_id, current_user.id, db)

    def _log_export(fmt: str):
        try:
            from app.services.audit import log_event
            log_event(
                db,
                action="export_completed",
                user_id=current_user.id,
                resource_type="project",
                resource_id=str(project_id),
                detail={"format": fmt},
                category="activation",
            )
        except Exception:
            pass

    if format == "xlsx":
        df = _load_df(project_id)
        xlsx_bytes = generate_excel_report(df, result, project_name)
        _log_export("xlsx")
        return Response(
            content=xlsx_bytes,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f'attachment; filename="analysis_report_{project_id}.xlsx"'},
        )

    if format == "html":
        html = generate_html_report(_load_df(project_id), result, project_name)
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
        raise HTTPException(status_code=501, detail=str(e))
    except Exception as e:
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
    result, _ = _get_stored_analysis(project_id, current_user.id, db)
    return result


# ── Report Result builder ─────────────────────────────────────────────────────

def _build_report_result(draft: ReportDraft, db: Session) -> dict:
    """
    Assemble a canonical ReportResult from a draft, linked analysis, and audit log.

    All data already exists in the DB — this is a pure assembly step.
    Fields without V1 persistence (user_edits, export_artifact_refs) are empty lists.
    """
    from app.schemas.report import (
        ExportRecord,
        IncludedInsight,
        ReportResult,
        ReportSection,
    )

    # Resolve selected insights from the linked analysis result
    included_insights: list[IncludedInsight] = []
    if draft.analysis_result_id:
        analysis = (
            db.query(AnalysisResult)
            .filter(AnalysisResult.id == draft.analysis_result_id)
            .first()
        )
        if analysis:
            try:
                result_data = json.loads(analysis.result_json)
                raw = result_data.get("insight_results") or result_data.get("insights") or []
                for idx in draft.selected_insights:
                    if isinstance(idx, int) and 0 <= idx < len(raw):
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

    # Export history from audit log (most recent 10)
    export_logs = (
        db.query(AuditLog)
        .filter(
            AuditLog.action == "export_completed",
            AuditLog.resource_type == "project",
            AuditLog.resource_id == str(draft.project_id),
        )
        .order_by(AuditLog.created_at.desc())
        .limit(10)
        .all()
    )
    export_statuses: list[ExportRecord] = []
    for log in export_logs:
        try:
            detail = json.loads(log.detail) if log.detail else {}
        except Exception:
            detail = {}
        fmt = detail.get("format")
        if fmt in ("html", "pdf", "xlsx"):
            export_statuses.append(ExportRecord(
                format=fmt,          # type: ignore[arg-type]
                status="completed",
                exported_at=log.created_at,
            ))

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
    project = db.query(Project).filter(
        Project.id == project_id, Project.user_id == current_user.id
    ).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found.")

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
    """Fetch the current report draft for a project."""
    project = db.query(Project).filter(
        Project.id == project_id, Project.user_id == current_user.id
    ).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found.")

    draft = (
        db.query(ReportDraft)
        .filter(ReportDraft.project_id == project_id)
        .order_by(ReportDraft.created_at.desc())
        .first()
    )
    if not draft:
        return None

    return _draft_response(draft, db)
