"""Local (non-LLM) suggested questions for AI chat when the provider is unavailable."""

from __future__ import annotations

from typing import Any

import pandas as pd


def suggest_chat_questions(
    df: pd.DataFrame,
    insights: list[dict[str, Any]] | None = None,
    *,
    limit: int = 6,
) -> list[str]:
    """Build short question prompts from columns and optional insight titles."""
    insights = insights or []
    out: list[str] = []
    if df is None or df.empty:
        for ins in insights[:limit]:
            title = (ins.get("title") or ins.get("finding") or "").strip()
            if title:
                out.append(_cap_sentence(f"Explain this finding: {title}"))
        return out[:limit]

    cols = list(df.columns)
    numeric = {str(c) for c in df.select_dtypes(include=["number"]).columns}
    text_like = {
        str(c) for c in df.select_dtypes(include=["object", "string", "category"]).columns
    }

    for c in cols[:10]:
        s = str(c)
        if s in numeric:
            out.append(_cap_sentence(f"What are typical values and outliers for `{s}`?"))
        elif s in text_like:
            out.append(_cap_sentence(f"What are the most frequent values in `{s}`?"))
        else:
            out.append(_cap_sentence(f"Summarize the distribution of `{s}`."))

    for ins in insights[:5]:
        title = (ins.get("title") or ins.get("finding") or "").strip()
        if title:
            out.append(_cap_sentence(f"Dig deeper on: {title[:120]}"))

    seen: set[str] = set()
    uniq: list[str] = []
    for q in out:
        if q and q not in seen:
            seen.add(q)
            uniq.append(q)
        if len(uniq) >= limit:
            break
    return uniq[:limit]


def _cap_sentence(s: str) -> str:
    s = " ".join(s.split())
    if not s:
        return ""
    return s[0].upper() + s[1:] if len(s) > 1 else s.upper()
