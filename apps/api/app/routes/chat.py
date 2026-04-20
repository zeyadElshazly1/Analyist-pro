from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from app.limiter import limiter
from app.middleware.auth import get_current_user
from app.middleware.plans import require_feature
from app.models import User
from app.services.ai_chat_service import chat_with_data
from app.services.dataset_loader import load_prepared
from app.services.serializers import to_jsonable
from app.state import PROJECT_FILES

router = APIRouter(prefix="/chat", tags=["chat"])


def _load(project_id: int):
    return load_prepared(project_id)


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    project_id: int
    message: str
    history: list[ChatMessage] = []


@router.post("/query")
@limiter.limit("30/minute")
def chat_query(
    request: Request,
    req: ChatRequest,
    current_user: User = Depends(get_current_user),
    _plan: None = Depends(require_feature("ai_chat")),
):
    if not req.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty.")

    df = _load(req.project_id)

    # get cached insights if available
    insights = (PROJECT_FILES.get(req.project_id) or {}).get("last_insights", [])

    history = [{"role": m.role, "content": m.content} for m in req.history]

    try:
        result = chat_with_data(df, req.message, history, insights)
        return to_jsonable(result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Chat failed: {e}")
