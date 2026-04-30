import logging
import os

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import get_db
from app.exceptions import AppError, AIChatDisabledError
from app.limiter import limiter
from app.middleware.auth import get_current_user
from app.middleware.plans import require_feature
from app.models import User
from app.services.access_guards import get_project_for_user
from app.services.ai_chat.constants import AI_CHAT_UNAVAILABLE_USER_MESSAGE
from app.services.ai_chat_service import chat_with_data
from app.services.ai_chat.suggestions import suggest_chat_questions
from app.services.dataset_loader import load_prepared
from app.services.serializers import to_jsonable
from app.state import PROJECT_FILES

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["chat"])


def _load_owned(db: Session, user: User, project_id: int):
    """Verify ownership, then load + clean the dataset."""
    get_project_for_user(db, project_id, user)
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
    db: Session = Depends(get_db),
    _plan: None = Depends(require_feature("ai_chat")),
):
    if not req.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty.")

    df = _load_owned(db, current_user, req.project_id)

    # get cached insights if available
    insights = (PROJECT_FILES.get(req.project_id) or {}).get("last_insights", [])

    if os.environ.get("AI_CHAT_DISABLED", "").lower() in ("1", "true", "yes"):
        raise AIChatDisabledError(
            AI_CHAT_UNAVAILABLE_USER_MESSAGE,
            dev_detail="AI_CHAT_DISABLED environment flag is set",
            extra={"suggested_questions": suggest_chat_questions(df, insights)},
        )

    history = [{"role": m.role, "content": m.content} for m in req.history]

    try:
        result = chat_with_data(df, req.message, history, insights)
        return to_jsonable(result)
    except AppError:
        raise
    except Exception as e:
        logger.exception("Chat query failed: %s", e)
        raise HTTPException(status_code=500, detail=f"Chat failed: {e}")
