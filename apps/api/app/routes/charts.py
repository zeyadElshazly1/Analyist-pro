from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.file_loader import load_dataset
from app.services.cleaner import clean_dataset
from app.services.chart_builder import build_chart_data
from app.services.persistence import get_project_file_info

router = APIRouter(prefix="/charts", tags=["charts"])


class ChartRequest(BaseModel):
    project_id: int


@router.post("/suggest")
def suggest_chart(payload: ChartRequest):
    project_id = payload.project_id

    file_info = get_project_file_info(project_id)
    if not file_info:
        raise HTTPException(status_code=404, detail="No uploaded file found for this project.")
    file_path = file_info["path"]

    try:
        df = load_dataset(file_path)
        df_clean, _, _ = clean_dataset(df)
        charts = build_chart_data(df_clean)
        return {"charts": charts}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to build chart: {str(e)}")
