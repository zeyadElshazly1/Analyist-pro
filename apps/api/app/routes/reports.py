from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response

from app.services.analysis_jobs import ANALYSIS_VERSION, build_analysis_result
from app.services.file_loader import load_dataset
from app.services.report_service import generate_html_report, generate_pdf_report
from app.services.persistence import (
    get_cached_artifact,
    get_latest_dataset,
    get_project,
    record_usage_event,
    save_artifact,
)

router = APIRouter(prefix="/reports", tags=["reports"])


def _load_and_analyze(project_id: int) -> tuple:
    dataset = get_latest_dataset(project_id)
    if dataset is None:
        raise HTTPException(status_code=404, detail="No uploaded file for this project.")

    try:
        df = load_dataset(dataset["storage_path"])
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Uploaded file not found.")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to load dataset: {exc}")

    artifact = get_cached_artifact(dataset["id"], "analysis_result", ANALYSIS_VERSION)
    if artifact is not None:
        return df, dataset, artifact["payload"]

    try:
        analysis_result, _ = build_analysis_result(dataset["storage_path"])
        save_artifact(project_id, dataset["id"], None, "analysis_result", analysis_result, ANALYSIS_VERSION)
        return df, dataset, analysis_result
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {exc}")


@router.get("/export/{project_id}")
def export_report(project_id: int, format: str = Query("html", pattern="^(html|pdf)$")):
    df, dataset, analysis_result = _load_and_analyze(project_id)
    project = get_project(project_id)
    project_name = project["name"] if project else f"Project {project_id}"

    if format == "html":
        html = generate_html_report(df, analysis_result, project_name)
        record_usage_event(
            "report_exported",
            project_id=project_id,
            dataset_id=dataset["id"],
            metadata={"format": "html"},
        )
        return Response(
            content=html,
            media_type="text/html",
            headers={"Content-Disposition": f'attachment; filename="analysis_report_{project_id}.html"'},
        )

    pdf_bytes = generate_pdf_report(df, analysis_result, project_name)
    record_usage_event(
        "report_exported",
        project_id=project_id,
        dataset_id=dataset["id"],
        metadata={"format": "pdf"},
    )
    media_type = "application/pdf" if pdf_bytes[:4] == b"%PDF" else "text/html"
    ext = "pdf" if media_type == "application/pdf" else "html"
    return Response(
        content=pdf_bytes,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="analysis_report_{project_id}.{ext}"'},
    )


@router.get("/preview/{project_id}")
def preview_report(project_id: int):
    _, _, analysis_result = _load_and_analyze(project_id)
    return analysis_result
