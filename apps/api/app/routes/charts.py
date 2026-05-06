from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

import logging

from app.db import get_db
from app.middleware.auth import get_current_user
from app.models import User
from app.services.access_guards import get_project_for_user
from app.state import get_project_file_info
from app.services.file_loader import load_dataset
from app.services.cleaner import clean_dataset
from app.services.chart_builder import build_chart_data
from app.services.analysis.large_dataset_mode import prepare_analysis_frame

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/charts", tags=["charts"])


class ChartRequest(BaseModel):
    project_id: int


@router.post("/suggest")
def suggest_chart(
    payload: ChartRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    project_id = payload.project_id
    get_project_for_user(db, project_id, current_user)

    info = get_project_file_info(project_id)
    if not info:
        raise HTTPException(
            status_code=404,
            detail="No uploaded file found for this project. Please upload a dataset first.",
        )

    try:
        df = load_dataset(info["path"])
        df_clean, _, _ = clean_dataset(df)
        df_plot, _ = prepare_analysis_frame(df_clean)
        charts = build_chart_data(df_plot)
        return {"charts": charts}
    except MemoryError:
        logger.error(f"Out of memory building charts for project {project_id}", exc_info=True)
        raise HTTPException(
            status_code=503,
            detail="The dataset is too large to generate charts with current server resources.",
        )
    except Exception as e:
        logger.error(f"Chart generation failed for project {project_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to generate charts. Please try again.")
