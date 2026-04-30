"""
LLM API client.

call_llm(...) → LLMCallResult

Tries Anthropic first, then OpenAI on failure. Structured error codes for HTTP layer.
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass

logger = logging.getLogger(__name__)

_CLAUDE_MODEL = os.environ.get("CLAUDE_CHAT_MODEL", "claude-haiku-4-5-20251001")
_OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")

_INTENT_HINTS: dict[str, str] = {
    "group": "Focus on groupby and pivot aggregations in your pandas code.",
    "trend": "Focus on time-series patterns and date-based aggregations.",
    "corr": "Focus on correlations and relationships between numeric columns.",
    "anomaly": "Focus on outlier detection using IQR or Z-score methods.",
    "top": "Focus on ranking and top/bottom N values.",
    "mean": "Compute means and medians; show the numeric result clearly.",
    "missing": "Analyse missing-value patterns and report column counts.",
    "summary": "Provide a concise statistical summary of the numeric columns.",
}


@dataclass(frozen=True)
class LLMCallResult:
    """LLM outcome: success (text set, error_code None) or failure (error_code set)."""

    text: str | None
    model: str
    error_code: str | None = None


def _is_timeout(exc: BaseException) -> bool:
    name = type(exc).__name__.lower()
    if "timeout" in name:
        return True
    s = str(exc).lower()
    return "timeout" in s


def call_llm(
    system_prompt: str,
    messages: list[dict],
    intent: str = "general",
    max_tokens: int = 1024,
) -> LLMCallResult:
    hint = _INTENT_HINTS.get(intent, "")
    full_system = f"{system_prompt}\n\n{hint}".strip() if hint else system_prompt

    anthropic_key = os.environ.get("ANTHROPIC_API_KEY", "")
    openai_key = os.environ.get("OPENAI_API_KEY", "")

    if not anthropic_key and not openai_key:
        return LLMCallResult(None, "fallback", "AI_KEY_MISSING")

    any_timeout = False
    any_other = False
    last_model = "fallback"

    if anthropic_key:
        try:
            import anthropic  # noqa: PLC0415

            client = anthropic.Anthropic(api_key=anthropic_key)
            response = client.messages.create(
                model=_CLAUDE_MODEL,
                max_tokens=max_tokens,
                system=full_system,
                messages=messages,
            )
            text = response.content[0].text
            if text is None or not str(text).strip():
                any_other = True
                last_model = _CLAUDE_MODEL
            else:
                return LLMCallResult(str(text).strip(), _CLAUDE_MODEL, None)
        except ImportError:
            logger.warning(
                "anthropic package not installed — skipping. Run: pip install anthropic"
            )
        except Exception as exc:  # noqa: BLE001
            logger.error(
                "Anthropic API call failed: %s: %s", type(exc).__name__, exc, exc_info=True
            )
            last_model = _CLAUDE_MODEL
            if _is_timeout(exc):
                any_timeout = True
            else:
                any_other = True

    if openai_key:
        try:
            import openai  # noqa: PLC0415

            client = openai.OpenAI(api_key=openai_key)
            oai_msgs = [{"role": "system", "content": full_system}]
            oai_msgs += [{"role": m["role"], "content": m["content"]} for m in messages]
            response = client.chat.completions.create(
                model=_OPENAI_MODEL,
                max_tokens=max_tokens,
                messages=oai_msgs,
            )
            text = response.choices[0].message.content
            if text is None or not str(text).strip():
                any_other = True
                last_model = _OPENAI_MODEL
            else:
                return LLMCallResult(str(text).strip(), _OPENAI_MODEL, None)
        except ImportError:
            logger.warning("openai package not installed — skipping. Run: pip install openai")
        except Exception as exc:  # noqa: BLE001
            logger.error(
                "OpenAI API call failed: %s: %s", type(exc).__name__, exc, exc_info=True
            )
            last_model = _OPENAI_MODEL
            if _is_timeout(exc):
                any_timeout = True
            else:
                any_other = True

    if any_timeout:
        return LLMCallResult(None, last_model, "AI_TIMEOUT")
    if any_other:
        return LLMCallResult(None, last_model, "AI_PROVIDER_UNAVAILABLE")

    return LLMCallResult(None, "fallback", "AI_PROVIDER_UNAVAILABLE")
