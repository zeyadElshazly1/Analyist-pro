import json

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import Optional

from app.db import get_db
from app.middleware.auth import get_current_user
from app.middleware.plans import require_feature
from app.models import AnalysisResult, Project, ReportDraft, User
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
    }


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
    }
