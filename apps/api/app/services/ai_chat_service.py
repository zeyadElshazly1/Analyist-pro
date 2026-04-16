"""
Backward-compatibility shim for app.services.ai_chat_service.

All production callers do:
    from app.services.ai_chat_service import chat_with_data, generate_data_story

All logic lives in app.services.ai_chat.
Do not add logic to this file.
"""
from app.services.ai_chat import chat_with_data, generate_data_story  # noqa: F401

__all__ = ["chat_with_data", "generate_data_story"]
