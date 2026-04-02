from __future__ import annotations

import re

import numpy as np
import pandas as pd

_FORBIDDEN = re.compile(
    r"\b(import|open|os\.|sys\.|eval\(|exec\(|subprocess|__)\b", re.IGNORECASE
)

_SAFE_BUILTINS = {
    "__builtins__": {
        "print": print, "len": len, "range": range, "list": list, "dict": dict,
        "str": str, "int": int, "float": float, "bool": bool, "round": round,
        "abs": abs, "min": min, "max": max, "sum": sum, "sorted": sorted,
        "enumerate": enumerate, "zip": zip, "isinstance": isinstance,
    }
}


def _build_namespace(df: pd.DataFrame) -> dict:
    ns = {col: df[col] for col in df.columns}
    ns.update({
        "pd": pd,
        "np": np,
        "log": np.log,
        "log1p": np.log1p,
        "log2": np.log2,
        "sqrt": np.sqrt,
        "abs": np.abs,
        "exp": np.exp,
        "sin": np.sin,
        "cos": np.cos,
        "floor": np.floor,
        "ceil": np.ceil,
        "round": np.round,
    })
    return ns


def create_feature(df: pd.DataFrame, name: str, formula: str) -> dict:
    # Safety check
    if _FORBIDDEN.search(formula):
        raise ValueError("Formula contains unsafe patterns (import/open/os/sys/eval/exec/__)")

    if not name.strip():
        raise ValueError("Feature name cannot be empty.")

    ns = _build_namespace(df)
    safe_globals = {"__builtins__": {}}
    safe_globals.update(_SAFE_BUILTINS["__builtins__"])

    try:
        result = eval(formula, safe_globals, ns)  # noqa: S307
    except Exception as e:
        raise ValueError(f"Formula evaluation error: {e}")

    if isinstance(result, pd.Series):
        series = result.reset_index(drop=True)
    elif isinstance(result, (int, float, bool, np.integer, np.floating)):
        series = pd.Series([result] * len(df))
    elif isinstance(result, np.ndarray):
        if result.ndim == 1:
            series = pd.Series(result)
        else:
            raise ValueError("Formula must return a 1-dimensional result.")
    else:
        raise ValueError(f"Formula returned unsupported type: {type(result)}")

    preview = [v if not (isinstance(v, float) and np.isnan(v)) else None for v in series.head(5).tolist()]
    null_count = int(series.isnull().sum())
    dtype = str(series.dtype)

    stats: dict = {"null_count": null_count, "dtype": dtype}
    if pd.api.types.is_numeric_dtype(series):
        stats.update({
            "mean": round(float(series.mean()), 4) if null_count < len(series) else None,
            "std": round(float(series.std()), 4) if null_count < len(series) else None,
            "min": round(float(series.min()), 4) if null_count < len(series) else None,
            "max": round(float(series.max()), 4) if null_count < len(series) else None,
        })

    return {
        "name": name,
        "formula": formula,
        "preview": preview,
        "dtype": dtype,
        "stats": stats,
        "series_values": series.tolist(),  # stored for route to persist
    }


def suggest_features(df: pd.DataFrame) -> list[dict]:
    suggestions: list[dict] = []
    numeric_cols = df.select_dtypes(include="number").columns.tolist()

    # Log transforms for skewed columns
    for col in numeric_cols:
        try:
            col_vals = pd.to_numeric(df[col], errors="coerce").dropna()
            if len(col_vals) == 0:
                continue
            skew = float(col_vals.skew())
            if abs(skew) > 1.5 and (col_vals >= 0).all():
                suggestions.append({
                    "name": f"log_{col}",
                    "formula": f"log1p({col})",
                    "rationale": f"'{col}' is highly skewed (skew={skew:.2f}). Log transform can normalize the distribution.",
                    "category": "transform",
                })
        except Exception:
            pass

    # Ratios for numeric pairs
    if len(numeric_cols) >= 2:
        for i, col_a in enumerate(numeric_cols[:8]):
            for col_b in numeric_cols[i + 1: 8]:
                # only suggest if denominator rarely zero
                if df[col_b].eq(0).mean() < 0.1 and df[col_b].mean() != 0:
                    suggestions.append({
                        "name": f"{col_a}_per_{col_b}",
                        "formula": f"{col_a} / ({col_b} + 1e-9)",
                        "rationale": f"Ratio of '{col_a}' to '{col_b}' may capture a meaningful rate or efficiency metric.",
                        "category": "ratio",
                    })
                if len(suggestions) >= 15:
                    break
            if len(suggestions) >= 15:
                break

    # Interaction terms for highly correlated pairs
    if len(numeric_cols) >= 2:
        try:
            corr = df[numeric_cols[:10]].corr().abs()
            for i in range(len(corr.columns)):
                for j in range(i + 1, len(corr.columns)):
                    if corr.iloc[i, j] > 0.6:
                        a, b = corr.columns[i], corr.columns[j]
                        suggestions.append({
                            "name": f"{a}_x_{b}",
                            "formula": f"{a} * {b}",
                            "rationale": f"'{a}' and '{b}' are correlated (r={corr.iloc[i, j]:.2f}). Their interaction may capture non-linear effects.",
                            "category": "interaction",
                        })
                    if len(suggestions) >= 20:
                        break
                if len(suggestions) >= 20:
                    break
        except Exception:
            pass

    # Datetime features
    for col in df.select_dtypes(include=["datetime64"]).columns:
        suggestions.append({
            "name": f"{col}_month",
            "formula": f"{col}.dt.month",
            "rationale": f"Extract month from '{col}' to capture seasonal patterns.",
            "category": "datetime",
        })
        suggestions.append({
            "name": f"{col}_dayofweek",
            "formula": f"{col}.dt.dayofweek",
            "rationale": f"Extract day of week from '{col}' (0=Monday) to capture weekly patterns.",
            "category": "datetime",
        })

    return suggestions[:20]
