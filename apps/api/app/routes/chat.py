from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.middleware.auth import get_current_user
from app.models import User
from app.services.ai_chat_service import chat_with_data
from app.services.cleaner import clean_dataset
from app.services.file_loader import load_dataset
from app.services.serializers import to_jsonable
from app.state import PROJECT_FILES

router = APIRouter(prefix="/chat", tags=["chat"])


def _load(project_id: int):
    if project_id not in PROJECT_FILES:
        raise HTTPException(status_code=404, detail="No uploaded file for this project.")
    path = PROJECT_FILES[project_id]["path"]
    try:
        df = load_dataset(path)
        df_clean, _, _ = clean_dataset(df)
        return df_clean
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Uploaded file not found on disk.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load dataset: {e}")


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    project_id: int
    message: str
    history: list[ChatMessage] = []


@router.post("/query")
def chat_query(req: ChatRequest, current_user: User = Depends(get_current_user)):
    if not req.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty.")

    df = _load(req.project_id)

    # get cached insights if available
    insights = PROJECT_FILES[req.project_id].get("last_insights", [])

    history = [{"role": m.role, "content": m.content} for m in req.history]

    try:
        result = chat_with_data(df, req.message, history, insights)
        return to_jsonable(result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Chat failed: {e}")
