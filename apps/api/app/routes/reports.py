from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import HTMLResponse, Response

from app.services.analyzer import analyze_dataset
from app.services.cleaner import clean_dataset
from app.services.file_loader import load_dataset
from app.services.profiler import calculate_health_score, profile_dataset
from app.services.report_service import generate_html_report, generate_pdf_report
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
def export_report(project_id: int, format: str = Query("html", regex="^(html|pdf)$")):
    df, analysis_result = _load_and_analyze(project_id)
    project_name = PROJECT_FILES[project_id].get("name", f"Project {project_id}")

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
def preview_report(project_id: int):
    _, analysis_result = _load_and_analyze(project_id)
    return analysis_result
