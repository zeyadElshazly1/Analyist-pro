from __future__ import annotations

import os
import re

import numpy as np
import pandas as pd

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
    except Exception:
        pass

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

    if anthropic_key:
        try:
            import anthropic

            client = anthropic.Anthropic(api_key=anthropic_key)
            messages = list(conversation_history) + [{"role": "user", "content": user_message}]
            response = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=1024,
                system=system_prompt,
                messages=messages,
            )
            answer_text = response.content[0].text
            model_used = "claude-haiku-4-5-20251001"
        except ImportError:
            pass
        except Exception as e:
            answer_text = f"AI service error: {e}. Falling back to basic analysis."

    elif openai_key:
        try:
            import openai

            client = openai.OpenAI(api_key=openai_key)
            messages = [{"role": "system", "content": system_prompt}]
            messages += [{"role": m["role"], "content": m["content"]} for m in conversation_history]
            messages.append({"role": "user", "content": user_message})
            response = client.chat.completions.create(
                model=os.environ.get("OPENAI_MODEL", "gpt-4o-mini"),
                max_tokens=1024,
                messages=messages,
            )
            answer_text = response.choices[0].message.content
            model_used = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
        except ImportError:
            answer_text = "openai package not installed. Run: pip install openai"
        except Exception as e:
            answer_text = f"OpenAI error: {e}. Falling back to basic analysis."

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

    return {
        "answer": answer_text,
        "code_used": code,
        "result_type": result_type,
        "table_data": table_data,
        "number_result": number_result,
        "model_used": model_used,
        "exec_error": exec_error,
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
