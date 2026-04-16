"""
LLM API client.

call_llm(system_prompt, messages, intent, max_tokens) → (answer_text | None, model_used)

Tries Anthropic first, then OpenAI.  Returns (None, "fallback") when both are
unavailable so the caller can invoke the local fallback engine.
"""
from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)

# Model names are configurable via env so they can be updated without code deploys
_CLAUDE_MODEL  = os.environ.get("CLAUDE_CHAT_MODEL",  "claude-haiku-4-5-20251001")
_OPENAI_MODEL  = os.environ.get("OPENAI_MODEL",       "gpt-4o-mini")

# Intent → concise instruction appended to the system prompt
_INTENT_HINTS: dict[str, str] = {
    "group":   "Focus on groupby and pivot aggregations in your pandas code.",
    "trend":   "Focus on time-series patterns and date-based aggregations.",
    "corr":    "Focus on correlations and relationships between numeric columns.",
    "anomaly": "Focus on outlier detection using IQR or Z-score methods.",
    "top":     "Focus on ranking and top/bottom N values.",
    "mean":    "Compute means and medians; show the numeric result clearly.",
    "missing": "Analyse missing-value patterns and report column counts.",
    "summary": "Provide a concise statistical summary of the numeric columns.",
}


def call_llm(
    system_prompt: str,
    messages: list[dict],
    intent: str = "general",
    max_tokens: int = 1024,
) -> tuple[str | None, str]:
    """
    Call the configured LLM with an intent-enriched system prompt.

    Returns (answer_text, model_name) on success.
    Returns (None, "fallback") when no API key is set or both calls fail.
    Returns (error_string, model_name) when the API is temporarily unavailable
    (the engine will show the error message to the user rather than a blank).
    """
    hint = _INTENT_HINTS.get(intent, "")
    full_system = f"{system_prompt}\n\n{hint}".strip() if hint else system_prompt

    anthropic_key = os.environ.get("ANTHROPIC_API_KEY", "")
    openai_key    = os.environ.get("OPENAI_API_KEY", "")

    # ── Anthropic ─────────────────────────────────────────────────────────────
    if anthropic_key:
        try:
            import anthropic  # noqa: PLC0415
            client   = anthropic.Anthropic(api_key=anthropic_key)
            response = client.messages.create(
                model=_CLAUDE_MODEL,
                max_tokens=max_tokens,
                system=full_system,
                messages=messages,
            )
            return response.content[0].text, _CLAUDE_MODEL
        except ImportError:
            logger.warning(
                "anthropic package not installed — AI chat unavailable. "
                "Run: pip install anthropic"
            )
        except Exception as exc:
            logger.error(
                "Anthropic API call failed: %s: %s", type(exc).__name__, exc, exc_info=True
            )
            return (
                "The AI assistant is temporarily unavailable. "
                "Please try again in a moment.",
                _CLAUDE_MODEL,
            )

    # ── OpenAI fallback ───────────────────────────────────────────────────────
    if openai_key:
        try:
            import openai  # noqa: PLC0415
            client   = openai.OpenAI(api_key=openai_key)
            oai_msgs = [{"role": "system", "content": full_system}]
            oai_msgs += [{"role": m["role"], "content": m["content"]} for m in messages]
            response = client.chat.completions.create(
                model=_OPENAI_MODEL,
                max_tokens=max_tokens,
                messages=oai_msgs,
            )
            return response.choices[0].message.content, _OPENAI_MODEL
        except ImportError:
            logger.warning("openai package not installed — Run: pip install openai")
        except Exception as exc:
            logger.error(
                "OpenAI API call failed: %s: %s", type(exc).__name__, exc, exc_info=True
            )
            return (
                "The AI assistant is temporarily unavailable. Please try again in a moment.",
                _OPENAI_MODEL,
            )

    return None, "fallback"
