import json

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.db import get_db
from app.middleware.auth import get_current_user
from app.models import AnalysisResult, Project, User
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
):
    result, project_name = _get_stored_analysis(project_id, current_user.id, db)

    if format == "xlsx":
        df = _load_df(project_id)
        xlsx_bytes = generate_excel_report(df, result, project_name)
        return Response(
            content=xlsx_bytes,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f'attachment; filename="analysis_report_{project_id}.xlsx"'},
        )

    if format == "html":
        html = generate_html_report(_load_df(project_id), result, project_name)
        return Response(
            content=html,
            media_type="text/html",
            headers={"Content-Disposition": f'attachment; filename="analysis_report_{project_id}.html"'},
        )

    # pdf
    pdf_bytes = generate_pdf_report(_load_df(project_id), result, project_name)
    media_type = "application/pdf" if pdf_bytes[:4] == b"%PDF" else "text/html"
    ext = "pdf" if media_type == "application/pdf" else "html"
    return Response(
        content=pdf_bytes,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="analysis_report_{project_id}.{ext}"'},
    )


@router.get("/preview/{project_id}")
def preview_report(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    result, _ = _get_stored_analysis(project_id, current_user.id, db)
    return result
