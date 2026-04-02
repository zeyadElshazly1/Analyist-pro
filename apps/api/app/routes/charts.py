from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.state import PROJECT_FILES
from app.services.file_loader import load_dataset
from app.services.cleaner import clean_dataset
from app.services.chart_builder import build_chart_data

router = APIRouter(prefix="/charts", tags=["charts"])


class ChartRequest(BaseModel):
    project_id: int


@router.post("/suggest")
def suggest_chart(payload: ChartRequest):
    project_id = payload.project_id

    if project_id not in PROJECT_FILES:
        raise HTTPException(status_code=404, detail="No uploaded file found for this project.")

    file_info = PROJECT_FILES[project_id]
    file_path = file_info["path"]

    try:
        df = load_dataset(file_path)
        df_clean, _, _ = clean_dataset(df)
        charts = build_chart_data(df_clean)
        return {"charts": charts}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to build chart: {str(e)}")