from fastapi import APIRouter, BackgroundTasks, HTTPException

from app.schemas.analysis import AnalysisRequest
from app.services.analysis_jobs import ANALYSIS_VERSION, build_analysis_result, run_analysis_job
from app.services.persistence import (
    create_analysis_job,
    get_cached_artifact,
    get_latest_dataset,
    record_usage_event,
)

router = APIRouter(prefix="/analysis", tags=["analysis"])


@router.post("/run")
def run_analysis(payload: AnalysisRequest, background_tasks: BackgroundTasks):
    dataset = get_latest_dataset(payload.project_id)
    if dataset is None:
        raise HTTPException(status_code=404, detail="No uploaded dataset found for this project.")

    job = create_analysis_job(payload.project_id, dataset["id"], ANALYSIS_VERSION)
    record_usage_event(
        "analysis_started",
        project_id=payload.project_id,
        dataset_id=dataset["id"],
        job_id=job["id"],
        metadata={"source": "legacy_run_endpoint", "analysis_version": ANALYSIS_VERSION},
    )
    background_tasks.add_task(run_analysis_job, job["id"])
    return job


@router.get("/latest/{project_id}")
def latest_analysis(project_id: int):
    dataset = get_latest_dataset(project_id)
    if dataset is None:
        raise HTTPException(status_code=404, detail="No uploaded dataset found for this project.")

    artifact = get_cached_artifact(dataset["id"], "analysis_result", ANALYSIS_VERSION)
    if artifact is None:
        raise HTTPException(status_code=404, detail="No completed analysis found for this project.")
    return artifact["payload"]


@router.post("/run-sync")
def run_analysis_sync(payload: AnalysisRequest):
    dataset = get_latest_dataset(payload.project_id)
    if dataset is None:
        raise HTTPException(status_code=404, detail="No uploaded dataset found for this project.")

    try:
        result, _ = build_analysis_result(dataset["storage_path"])
        return result
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {exc}")
