"""
Dataset context builder.

build_context(df, insights, intent) → str

Produces a richer structured context string for the LLM system prompt:
  - Full schema with dtype, cardinality, missing %, and:
      * categorical columns (≤20 unique): top-5 sample values
      * numeric columns: [min, max], mean
  - Intent-appropriate sample rows (first 3)
  - Top insights with severity tags and statistical evidence
"""
from __future__ import annotations

import logging

import pandas as pd

logger = logging.getLogger(__name__)

_MAX_SCHEMA_COLS = 50   # caps context length for very wide datasets


def build_context(
    df: pd.DataFrame,
    insights: list | None = None,
    intent: str = "general",
) -> str:
    n_rows, n_cols = df.shape
    lines: list[str] = [f"Dataset: {n_rows:,} rows × {n_cols} columns"]

    # ── Schema ────────────────────────────────────────────────────────────────
    lines.append("\nSchema:")
    for col in df.columns[:_MAX_SCHEMA_COLS]:
        series      = df[col]
        dtype       = str(series.dtype)
        n_unique    = int(series.nunique())
        missing_pct = round(series.isnull().mean() * 100, 1)

        if series.dtype == object and n_unique <= 20:
            # Categorical: show top values so LLM writes correct filter literals
            sample_vals = series.dropna().value_counts().head(5).index.tolist()
            extra = f", values: {sample_vals}"
        elif pd.api.types.is_numeric_dtype(series):
            clean = series.dropna()
            if len(clean) > 0:
                extra = (
                    f", range: [{clean.min():.4g}, {clean.max():.4g}]"
                    f", mean: {clean.mean():.4g}"
                )
            else:
                extra = ""
        elif pd.api.types.is_datetime64_any_dtype(series):
            clean = series.dropna()
            if len(clean) > 0:
                extra = f", from {clean.min()} to {clean.max()}"
            else:
                extra = ""
        else:
            extra = ""

        lines.append(
            f"  {col} ({dtype}, {n_unique} unique, {missing_pct}% missing{extra})"
        )

    if n_cols > _MAX_SCHEMA_COLS:
        lines.append(f"  … and {n_cols - _MAX_SCHEMA_COLS} more columns")

    # ── Sample rows (intent-filtered) ────────────────────────────────────────
    if intent in ("summary", "mean", "general", "schema"):
        lines.append("\nSample rows (first 3):")
        try:
            lines.append(df.head(3).to_string(max_cols=10, max_colwidth=25))
        except Exception as exc:
            logger.debug("Could not render sample rows: %s", exc)

    # ── Insights ──────────────────────────────────────────────────────────────
    if insights:
        lines.append("\nTop insights from automated analysis:")
        for ins in insights[:5]:
            finding  = ins.get("finding", ins.get("title", ""))
            evidence = ins.get("evidence", "")
            severity = ins.get("severity", "")
            if not finding:
                continue
            tag = f"[{severity.upper()}] " if severity else ""
            lines.append(f"  - {tag}{finding}")
            if evidence:
                lines.append(f"    Evidence: {evidence}")

    return "\n".join(lines)
