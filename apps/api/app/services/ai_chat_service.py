from __future__ import annotations

import logging
import os
import re

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

_FORBIDDEN_CODE = re.compile(
    r"\b(import\s|open\s*\(|os\.|sys\.|subprocess|__import__|eval\s*\(|exec\s*\()\b",
    re.IGNORECASE,
)

_SAFE_BUILTINS = {
    "print": print, "len": len, "range": range, "list": list, "dict": dict,
    "str": str, "int": int, "float": float, "bool": bool, "round": round,
    "abs": abs, "min": min, "max": max, "sum": sum, "sorted": sorted,
    "enumerate": enumerate, "zip": zip, "isinstance": isinstance,
    "type": type, "hasattr": hasattr, "getattr": getattr,
}


def _build_context(df: pd.DataFrame, insights: list | None = None) -> str:
    n_rows, n_cols = df.shape
    lines = [f"Dataset: {n_rows:,} rows × {n_cols} columns", "Columns:"]

    for col in df.columns[:30]:  # cap at 30 cols
        dtype = str(df[col].dtype)
        n_unique = int(df[col].nunique())
        missing_pct = round(df[col].isnull().mean() * 100, 1)
        lines.append(f"  - {col} ({dtype}, {n_unique} unique, {missing_pct}% missing)")

    if n_cols > 30:
        lines.append(f"  ... and {n_cols - 30} more columns")

    # sample rows
    lines.append("\nSample data (first 3 rows):")
    try:
        sample = df.head(3).to_string(max_cols=10, max_colwidth=30)
        lines.append(sample)
    except Exception as e:
        logger.debug(f"Could not render sample rows: {e}")

    if insights:
        lines.append("\nTop insights:")
        for ins in insights[:3]:
            finding = ins.get("finding", ins.get("title", ""))
            if finding:
                lines.append(f"  - {finding}")

    return "\n".join(lines)


def _execute_code(df: pd.DataFrame, code: str) -> tuple[object, str | None]:
    """Execute pandas code safely. Returns (result, error)."""
    if _FORBIDDEN_CODE.search(code):
        return None, "Code contains unsafe patterns."

    namespace = {
        "df": df.copy(),
        "pd": pd,
        "np": np,
        "result": None,
    }
    try:
        exec(code, {"__builtins__": _SAFE_BUILTINS}, namespace)  # noqa: S102
        result = namespace.get("result")
        return result, None
    except Exception as e:
        return None, str(e)


def _suggest_chart(
    result_type: str,
    table_data: list | None,
) -> dict | None:
    """
    Heuristically suggest a chart type from the query result shape.
    Returns a hint dict or None if no chart makes sense.
    """
    if result_type == "number":
        return {"type": "kpi"}

    if result_type != "table" or not table_data or len(table_data) < 2:
        return None

    cols = list(table_data[0].keys())
    if len(cols) < 2:
        return None

    def _is_numeric(col: str) -> bool:
        for row in table_data[:10]:
            v = row.get(col)
            if v is None or v == "":
                continue
            try:
                float(v)
            except (TypeError, ValueError):
                return False
        return True

    numeric_cols = [c for c in cols if _is_numeric(c)]
    cat_cols = [c for c in cols if c not in numeric_cols]

    # categorical + numeric → bar
    if len(cat_cols) >= 1 and len(numeric_cols) >= 1:
        return {"type": "bar", "x_col": cat_cols[0], "y_col": numeric_cols[0]}

    # 2+ numeric — scatter for large result sets, bar for small
    if len(numeric_cols) >= 2:
        if len(table_data) > 20:
            return {"type": "scatter", "x_col": numeric_cols[0], "y_col": numeric_cols[1]}
        return {"type": "bar", "x_col": numeric_cols[0], "y_col": numeric_cols[1]}

    return None


def _result_to_serializable(result: object) -> tuple[str, list | None, float | str | None]:
    """Returns (result_type, table_data, number_result)."""
    if result is None:
        return "text", None, None
    if isinstance(result, pd.DataFrame):
        return "table", result.head(20).to_dict(orient="records"), None
    if isinstance(result, pd.Series):
        df_res = result.reset_index().head(20)
        return "table", df_res.to_dict(orient="records"), None
    if isinstance(result, (int, float, np.integer, np.floating)):
        return "number", None, round(float(result), 6)
    if isinstance(result, str):
        return "text", None, None
    # try to convert
    try:
        df_res = pd.DataFrame(result)
        return "table", df_res.head(20).to_dict(orient="records"), None
    except Exception:
        return "text", None, str(result)


def chat_with_data(
    df: pd.DataFrame,
    user_message: str,
    conversation_history: list,
    insights: list | None = None,
) -> dict:
    context = _build_context(df, insights)

    system_prompt = f"""You are a data analyst assistant. The user has uploaded a dataset and wants to analyze it.

{context}

Instructions:
- Answer data questions concisely and accurately based on the dataset context above.
- If the user asks for calculations, aggregations, filtering, or data manipulation, write Python pandas code to compute the answer.
- Wrap any code in a ```python code block. The dataframe is available as `df`. Store the final result in a variable called `result`.
- Only use `pd` (pandas) and `np` (numpy) — no other imports.
- Keep explanations brief. Show max 10 rows for tables.
- If you don't have enough information to answer, say so clearly."""

    answer_text = None
    model_used = "fallback"

    anthropic_key = os.environ.get("ANTHROPIC_API_KEY", "")
    openai_key = os.environ.get("OPENAI_API_KEY", "")

    # Model names are configurable via env so they can be updated without code deploys
    claude_model = os.environ.get("CLAUDE_CHAT_MODEL", "claude-haiku-4-5-20251001")
    openai_model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")

    if anthropic_key:
        try:
            import anthropic  # noqa: PLC0415
            client = anthropic.Anthropic(api_key=anthropic_key)
            messages = list(conversation_history) + [{"role": "user", "content": user_message}]
            response = client.messages.create(
                model=claude_model,
                max_tokens=1024,
                system=system_prompt,
                messages=messages,
            )
            answer_text = response.content[0].text
            model_used = claude_model
        except ImportError:
            logger.warning(
                "anthropic package not installed — AI chat unavailable. "
                "Run: pip install anthropic"
            )
        except Exception as e:
            logger.error(f"Anthropic API call failed: {type(e).__name__}: {e}", exc_info=True)
            answer_text = (
                "The AI assistant is temporarily unavailable. "
                "Your question has been received but cannot be answered right now. "
                "Please try again in a moment."
            )

    elif openai_key:
        try:
            import openai  # noqa: PLC0415
            client = openai.OpenAI(api_key=openai_key)
            messages = [{"role": "system", "content": system_prompt}]
            messages += [{"role": m["role"], "content": m["content"]} for m in conversation_history]
            messages.append({"role": "user", "content": user_message})
            response = client.chat.completions.create(
                model=openai_model,
                max_tokens=1024,
                messages=messages,
            )
            answer_text = response.choices[0].message.content
            model_used = openai_model
        except ImportError:
            logger.warning(
                "openai package not installed — AI chat unavailable. "
                "Run: pip install openai"
            )
            answer_text = (
                "The AI assistant is not configured. "
                "Please set ANTHROPIC_API_KEY or OPENAI_API_KEY to enable AI-powered responses."
            )
        except Exception as e:
            logger.error(f"OpenAI API call failed: {type(e).__name__}: {e}", exc_info=True)
            answer_text = (
                "The AI assistant is temporarily unavailable. Please try again in a moment."
            )

    if answer_text is None:
        answer_text = _fallback_answer(df, user_message)

    # extract code block
    code_match = re.search(r"```python\n(.*?)\n```", answer_text, re.DOTALL)
    code = code_match.group(1) if code_match else None

    # execute code if found
    table_data = None
    number_result = None
    result_type = "text"
    exec_error = None

    if code:
        exec_result, exec_error = _execute_code(df, code)
        if exec_error is None and exec_result is not None:
            result_type, table_data, number_result = _result_to_serializable(exec_result)
        elif exec_error:
            answer_text += f"\n\n_(Code execution note: {exec_error})_"

    chart_hint = _suggest_chart(result_type, table_data)

    return {
        "answer": answer_text,
        "code_used": code,
        "result_type": result_type,
        "table_data": table_data,
        "number_result": number_result,
        "model_used": model_used,
        "exec_error": exec_error,
        "chart_hint": chart_hint,
    }


def _fallback_answer(df: pd.DataFrame, message: str) -> str:
    """Rule-based fallback when Anthropic API is unavailable."""
    msg_lower = message.lower()
    n_rows, n_cols = df.shape
    numeric = df.select_dtypes(include="number")

    if any(w in msg_lower for w in ("how many rows", "row count", "size", "shape")):
        return f"The dataset has **{n_rows:,} rows** and **{n_cols} columns**."

    if any(w in msg_lower for w in ("column", "field", "variable")):
        cols = ", ".join(f"`{c}`" for c in df.columns[:15])
        return f"The dataset has {n_cols} columns: {cols}{'...' if n_cols > 15 else ''}."

    if any(w in msg_lower for w in ("missing", "null", "nan")):
        missing = df.isnull().sum()
        top_missing = missing[missing > 0].sort_values(ascending=False).head(5)
        if top_missing.empty:
            return "There are no missing values in the dataset."
        lines = [f"- **{col}**: {int(cnt)} missing ({cnt/n_rows*100:.1f}%)" for col, cnt in top_missing.items()]
        return "Columns with missing values:\n" + "\n".join(lines)

    if any(w in msg_lower for w in ("average", "mean", "median")) and not numeric.empty:
        col_name = next((c for c in numeric.columns if c.lower() in msg_lower), numeric.columns[0])
        mean = numeric[col_name].mean()
        median = numeric[col_name].median()
        return f"**{col_name}**: mean = {mean:.4f}, median = {median:.4f}"

    if any(w in msg_lower for w in ("summary", "describe", "overview", "statistics")):
        if not numeric.empty:
            desc = numeric.describe().round(2)
            return f"Summary statistics:\n```\n{desc.to_string()}\n```"

    return (
        f"This dataset has {n_rows:,} rows and {n_cols} columns. "
        f"Set the ANTHROPIC_API_KEY environment variable to enable AI-powered analysis. "
        f"Available columns: {', '.join(df.columns[:10].tolist())}."
    )


def generate_data_story(analysis_result: dict) -> dict:
    """
    Use Claude to generate a structured 5-slide data story from an analysis result.
    Returns: { title, slides: [{slide_num, title, narrative, key_points}] }
    Falls back to a rule-based story if no API key is configured.
    """
    import json as _json
    import os

    anthropic_key = os.environ.get("ANTHROPIC_API_KEY", "")

    summary = analysis_result.get("dataset_summary", {})
    health = analysis_result.get("health_score", {})
    insights = analysis_result.get("insights", [])[:8]
    narrative = analysis_result.get("narrative", "")

    # Build context for the prompt
    context_lines = [
        f"Dataset: {summary.get('rows', '?')} rows × {summary.get('columns', '?')} columns",
        f"Health score: {health.get('total', health.get('overall', '?'))}/100",
        f"Missing data: {summary.get('missing_pct', 0):.1f}%",
        "",
        "Top insights:",
    ]
    for ins in insights:
        context_lines.append(f"- [{ins.get('severity','').upper()}] {ins.get('finding', ins.get('title', ''))}")
    if narrative:
        context_lines.append(f"\nNarrative summary:\n{narrative[:600]}")

    context = "\n".join(context_lines)

    prompt = f"""You are a senior data analyst. Based on this dataset analysis, generate a concise 5-slide data story in JSON format.

Analysis context:
{context}

Return ONLY valid JSON with this exact structure (no markdown, no explanation):
{{
  "title": "A compelling title for this data story (max 10 words)",
  "slides": [
    {{
      "slide_num": 1,
      "title": "Executive Summary",
      "narrative": "2-3 sentence overview of the dataset and headline finding",
      "key_points": ["point 1", "point 2", "point 3"]
    }},
    {{
      "slide_num": 2,
      "title": "Key Findings",
      "narrative": "2-3 sentences describing the top statistical findings",
      "key_points": ["finding 1", "finding 2", "finding 3"]
    }},
    {{
      "slide_num": 3,
      "title": "Deep Dive",
      "narrative": "2-3 sentences on the most interesting or unexpected pattern",
      "key_points": ["detail 1", "detail 2", "detail 3"]
    }},
    {{
      "slide_num": 4,
      "title": "Recommendations",
      "narrative": "2-3 sentences on concrete actions based on the data",
      "key_points": ["action 1", "action 2", "action 3"]
    }},
    {{
      "slide_num": 5,
      "title": "Next Steps",
      "narrative": "2-3 sentences on what to analyze next or what data to collect",
      "key_points": ["next step 1", "next step 2", "next step 3"]
    }}
  ]
}}"""

    story_model = os.environ.get("CLAUDE_STORY_MODEL", "claude-sonnet-4-6")

    if anthropic_key:
        try:
            import anthropic  # noqa: PLC0415
            client = anthropic.Anthropic(api_key=anthropic_key)
            response = client.messages.create(
                model=story_model,
                max_tokens=2048,
                messages=[{"role": "user", "content": prompt}],
            )
            text = response.content[0].text.strip()
            # Strip any accidental markdown fences
            if text.startswith("```"):
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
            return _json.loads(text)
        except ImportError:
            logger.warning("anthropic package not installed — falling back to rule-based story")
        except _json.JSONDecodeError as e:
            logger.warning(f"Story generation returned invalid JSON: {e} — falling back to rule-based")
        except Exception as e:
            logger.error(f"Story generation failed ({type(e).__name__}: {e}) — using rule-based fallback", exc_info=True)

    # ── Rule-based fallback ───────────────────────────────────────────────────
    top_insights = insights[:3]
    finding_texts = [i.get("finding", i.get("title", "")) for i in top_insights]
    action_texts = [i.get("action", "") for i in top_insights if i.get("action")]

    return {
        "title": f"Data Story: {summary.get('columns', '?')}-Column Dataset Analysis",
        "slides": [
            {
                "slide_num": 1,
                "title": "Executive Summary",
                "narrative": narrative[:300] if narrative else f"This dataset contains {summary.get('rows', '?')} rows and {summary.get('columns', '?')} columns with a health score of {health.get('total', health.get('overall', '?'))}/100.",
                "key_points": [
                    f"{summary.get('rows', '?')} total records",
                    f"{summary.get('numeric_cols', '?')} numeric columns",
                    f"Health score: {health.get('total', health.get('overall', '?'))}/100",
                ],
            },
            {
                "slide_num": 2,
                "title": "Key Findings",
                "narrative": "The analysis identified several statistically significant patterns in the dataset.",
                "key_points": finding_texts[:3] or ["No high-severity insights detected."],
            },
            {
                "slide_num": 3,
                "title": "Deep Dive",
                "narrative": "The most interesting pattern involves the relationship between key variables in the dataset.",
                "key_points": [i.get("evidence", "") for i in top_insights[:3] if i.get("evidence")] or ["Run the full analysis for detailed statistical evidence."],
            },
            {
                "slide_num": 4,
                "title": "Recommendations",
                "narrative": "Based on the findings, the following actions are recommended.",
                "key_points": action_texts[:3] or ["Set ANTHROPIC_API_KEY for AI-powered recommendations."],
            },
            {
                "slide_num": 5,
                "title": "Next Steps",
                "narrative": "To deepen the analysis, consider exploring additional dimensions of the data.",
                "key_points": [
                    "Run correlation analysis to identify variable relationships",
                    "Apply ML predictions to forecast key metrics",
                    "Segment data by category columns to find group differences",
                ],
            },
        ],
    }
