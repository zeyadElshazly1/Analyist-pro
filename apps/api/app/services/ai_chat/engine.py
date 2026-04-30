"""
AI chat engine orchestrator.

chat_with_data(df, user_message, conversation_history, insights) → dict

Pipeline:
  1. detect_intent — classify the query type
  2. build_context — rich structured schema + insights (intent-aware)
  3. call_llm     — Anthropic → OpenAI; on failure raises AppError with codes
  4. extract code — parse ```python block from LLM response
  5. execute_query — AST-whitelisted safe exec
  6. serialise     — convert result to JSON-safe types
  7. chart_hint    — suggest chart type from result shape

Return dict keys (backward-compatible):
    answer, code_used, result_type, table_data, number_result,
    model_used, exec_error, chart_hint, intent (new — additive only)
"""
from __future__ import annotations

import logging
import re

import pandas as pd

from app.exceptions import (
    AIChatKeyMissingError,
    AIChatProviderUnavailableError,
    AIChatTimeoutError,
)

from .constants import AI_CHAT_UNAVAILABLE_USER_MESSAGE
from .context import build_context
from .intent import detect_intent
from .llm_client import call_llm
from .result_serializer import _result_to_serializable, _suggest_chart
from .safe_executor import execute_query
from .suggestions import suggest_chat_questions

logger = logging.getLogger(__name__)

_CODE_RE = re.compile(r"```python\n(.*?)\n```", re.DOTALL)


def _build_system_prompt(context: str) -> str:
    return (
        "You are a data analyst assistant. The user has uploaded a dataset and wants to analyse it.\n\n"
        f"{context}\n\n"
        "Instructions:\n"
        "- Answer data questions concisely and accurately based on the dataset context above.\n"
        "- If the user asks for calculations, aggregations, filtering, or data manipulation, "
        "write Python pandas code to compute the answer.\n"
        "- Wrap any code in a ```python code block. The dataframe is available as `df`. "
        "Store the final result in a variable called `result`.\n"
        "- Only use `pd` (pandas) and `np` (numpy) — no other imports.\n"
        "- Keep explanations brief. Show max 10 rows for tables.\n"
        "- If you don't have enough information to answer, say so clearly."
    )


def chat_with_data(
    df: pd.DataFrame,
    user_message: str,
    conversation_history: list,
    insights: list | None = None,
) -> dict:
    """
    Process a natural-language data question and return a structured response.

    Parameters
    ----------
    df : pd.DataFrame
        The cleaned dataset the user is analysing.
    user_message : str
        The user's current message.
    conversation_history : list[dict]
        Prior turns as {role, content} dicts (Anthropic format).
    insights : list | None
        Pre-computed analysis insights to include in context.

    Returns
    -------
    dict with keys: answer, code_used, result_type, table_data,
                    number_result, model_used, exec_error, chart_hint, intent
    """
    intent  = detect_intent(user_message)
    context = build_context(df, insights=insights, intent=intent)
    system  = _build_system_prompt(context)

    # Build message list for LLM (append current turn)
    messages = list(conversation_history) + [{"role": "user", "content": user_message}]

    suggested = suggest_chat_questions(df, insights)
    extra = {"suggested_questions": suggested}
    llm = call_llm(system, messages, intent=intent)

    if llm.error_code == "AI_KEY_MISSING":
        raise AIChatKeyMissingError(
            AI_CHAT_UNAVAILABLE_USER_MESSAGE,
            dev_detail="No ANTHROPIC_API_KEY or OPENAI_API_KEY configured",
            extra=extra,
        )
    if llm.error_code == "AI_TIMEOUT":
        raise AIChatTimeoutError(
            AI_CHAT_UNAVAILABLE_USER_MESSAGE,
            dev_detail="LLM request timed out",
            extra=extra,
        )
    if llm.error_code == "AI_PROVIDER_UNAVAILABLE":
        raise AIChatProviderUnavailableError(
            AI_CHAT_UNAVAILABLE_USER_MESSAGE,
            dev_detail="LLM provider error or empty response",
            extra=extra,
        )

    answer_text = llm.text
    model_used = llm.model
    if not answer_text:
        raise AIChatProviderUnavailableError(
            AI_CHAT_UNAVAILABLE_USER_MESSAGE,
            dev_detail="LLM returned empty answer",
            extra=extra,
        )

    # ── Extract and run pandas code from LLM response ─────────────────────────
    code_match = _CODE_RE.search(answer_text)
    code       = code_match.group(1) if code_match else None

    table_data    = None
    number_result = None
    result_type   = "text"
    exec_error    = None

    if code:
        exec_result, exec_error = execute_query(df, code)
        if exec_error is None and exec_result is not None:
            result_type, table_data, number_result = _result_to_serializable(exec_result)
        elif exec_error:
            answer_text += f"\n\n_(Code execution note: {exec_error})_"

    chart_hint = _suggest_chart(result_type, table_data)

    return {
        "answer":        answer_text,
        "code_used":     code,
        "result_type":   result_type,
        "table_data":    table_data,
        "number_result": number_result,
        "model_used":    model_used,
        "exec_error":    exec_error,
        "chart_hint":    chart_hint,
        "intent":        intent,          # new field — additive, backward-compat
    }
