from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse, Response
from sqlalchemy.orm import Session

from app.db import get_db
from app.middleware.auth import get_current_user
from app.models import AnalysisResult, Project, User
from app.services.analyzer import analyze_dataset
from app.services.cleaner import clean_dataset
from app.services.file_loader import load_dataset
from app.services.profiler import calculate_health_score, profile_dataset
from app.services.report_service import generate_excel_report, generate_html_report, generate_pdf_report
from app.services.serializers import to_jsonable
from app.state import PROJECT_FILES

router = APIRouter(prefix="/reports", tags=["reports"])


def _load_and_analyze(project_id: int) -> tuple:
    if project_id not in PROJECT_FILES:
        raise HTTPException(status_code=404, detail="No uploaded file for this project.")
    path = PROJECT_FILES[project_id]["path"]
    try:
        df = load_dataset(path)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Uploaded file not found.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load dataset: {e}")

    try:
        df_clean, cleaning_report, _ = clean_dataset(df)
        profile = profile_dataset(df_clean)
        health_score = calculate_health_score(df_clean)
        insights, narrative = analyze_dataset(df_clean)
        analysis_result = {
            "health_score": to_jsonable(health_score),
            "profile": to_jsonable(profile),
            "insights": to_jsonable(insights),
            "narrative": narrative,
            "cleaning_report": to_jsonable(cleaning_report),
        }
        return df_clean, analysis_result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {e}")


@router.get("/export/{project_id}")
def export_report(
    project_id: int,
    format: str = Query("html", regex="^(html|pdf|xlsx)$"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # Prefer using stored analysis result over re-running for xlsx/html
    if format == "xlsx":
        analysis = (
            db.query(AnalysisResult)
            .join(Project)
            .filter(
                AnalysisResult.project_id == project_id,
                Project.user_id == current_user.id,
            )
            .order_by(AnalysisResult.created_at.desc())
            .first()
        )
        if not analysis:
            raise HTTPException(status_code=404, detail="No analysis found. Run analysis first.")

        import json
        import pandas as pd
        result = json.loads(analysis.result_json)
        project = db.query(Project).filter(Project.id == project_id).first()
        project_name = project.name if project else f"Project {project_id}"

        # Load raw df for Data Preview sheet
        try:
            from app.state import get_project_file_info
            info = get_project_file_info(project_id)
            if info:
                df = load_dataset(info["path"])
            else:
                df = pd.DataFrame()
        except Exception:
            df = pd.DataFrame()

        xlsx_bytes = generate_excel_report(df, result, project_name)
        return Response(
            content=xlsx_bytes,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f'attachment; filename="analysis_report_{project_id}.xlsx"'},
        )

    df, analysis_result = _load_and_analyze(project_id)
    project_name = PROJECT_FILES.get(project_id, {}).get("name", f"Project {project_id}")

    if format == "html":
        html = generate_html_report(df, analysis_result, project_name)
        return Response(
            content=html,
            media_type="text/html",
            headers={"Content-Disposition": f'attachment; filename="analysis_report_{project_id}.html"'},
        )
    else:
        pdf_bytes = generate_pdf_report(df, analysis_result, project_name)
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
):
    _, analysis_result = _load_and_analyze(project_id)
    return analysis_result
