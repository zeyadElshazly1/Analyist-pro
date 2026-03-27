from fastapi import APIRouter, HTTPException

from app.schemas.analysis import AnalysisRequest
from app.routes.upload import PROJECT_FILES
from app.services.file_loader import load_dataset
from app.services.cleaner import clean_dataset
from app.services.profiler import profile_dataset, calculate_health_score
from app.services.analyzer import analyze_dataset, get_dataset_summary
from app.services.serializers import to_jsonable

router = APIRouter(prefix="/analysis", tags=["analysis"])


@router.post("/run")
def run_analysis(payload: AnalysisRequest):
    project_id = payload.project_id

    if project_id not in PROJECT_FILES:
        raise HTTPException(
            status_code=404,
            detail="No uploaded file found for this project.",
        )

    file_info = PROJECT_FILES[project_id]
    file_path = file_info["path"]

    try:
        df = load_dataset(file_path)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Uploaded file path is missing.")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load dataset: {str(e)}")

    try:
        if df.empty:
            raise HTTPException(status_code=400, detail="Uploaded dataset is empty.")

        df_clean, cleaning_report, cleaning_summary = clean_dataset(df)

        if df_clean.empty or len(df_clean.columns) == 0:
            raise HTTPException(
                status_code=400,
                detail="Dataset became empty after cleaning.",
            )

        profile = profile_dataset(df_clean)
        health_score = calculate_health_score(df_clean)
        insights = analyze_dataset(df_clean)
        dataset_summary = get_dataset_summary(df_clean)

        return {
            "project_id": project_id,
            "dataset_summary": to_jsonable(dataset_summary),
            "cleaning_summary": to_jsonable(cleaning_summary),
            "cleaning_report": to_jsonable(cleaning_report),
            "health_score": to_jsonable(health_score),
            "profile": to_jsonable(profile),
            "insights": to_jsonable(insights),
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")