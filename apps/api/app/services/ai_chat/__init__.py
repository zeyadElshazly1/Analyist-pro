"""
Analyst Pro AI chat package.

Re-exports the public API used by app.services.ai_chat_service,
app.routes.chat, and app.routes.analysis.
"""
from .engine import chat_with_data        # noqa: F401
from .story import generate_data_story    # noqa: F401

__all__ = ["chat_with_data", "generate_data_story"]
