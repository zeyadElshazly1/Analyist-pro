"""
Template context builder.

build_context(df, analysis_result, project_name, mode) → dict

Collects all variables the Jinja2 template needs and pre-processes them
into safe, display-ready values (no formatting logic in the template).
"""
from __future__ import annotations

from datetime import datetime

import pandas as pd

from .charts import build_chart_configs

_SEVERITY_BADGE = {
    "high":   "badge-red",
    "medium": "badge-yellow",
    "low":    "badge-blue",
}


def _grade(score: float) -> str:
    if score >= 80:
        return "A"
    if score >= 60:
        return "B"
    if score >= 40:
        return "C"
    return "D"


def build_context(
    df: pd.DataFrame,
    analysis_result: dict,
    project_name: str,
    mode: str = "analyst",
) -> dict:
    n_rows, n_cols = df.shape
    missing_pct = round(df.isnull().mean().mean() * 100, 1)

    health_score = analysis_result.get("health_score", 0)
    if isinstance(health_score, dict):
        health_score = health_score.get("total", health_score.get("overall", 0))
    health_score = float(health_score or 0)
    grade = _grade(health_score)

    # Narrative
    narrative = analysis_result.get("narrative", "")
    narrative_paras = [p.strip() for p in str(narrative).split("\n\n") if p.strip()] if narrative else []

    # Quality rows (fallback if no breakdown)
    breakdown = analysis_result.get("health_breakdown", {})
    if not breakdown:
        breakdown = {"Overall": health_score}
    quality_rows = []
    for dim, score in breakdown.items():
        sc = float(score) if isinstance(score, (int, float)) else 0.0
        badge_cls = "badge-green" if sc >= 80 else "badge-yellow" if sc >= 60 else "badge-red"
        label = "Good" if sc >= 80 else "Fair" if sc >= 60 else "Poor"
        quality_rows.append((dim, f"{sc:.0f}", badge_cls, label))

    # Insights (analyst: up to 10; executive: up to 3)
    max_insights = 3 if mode == "executive" else 10
    raw_insights = analysis_result.get("insights", [])
    insights = []
    for ins in raw_insights[:max_insights]:
        severity = str(ins.get("severity", "medium")).lower()
        insights.append({
            "finding":   ins.get("finding", ins.get("title", "")),
            "evidence":  ins.get("evidence", ""),
            "action":    ins.get("recommendation", ins.get("action", "")),
            "severity":  severity,
            "badge_cls": _SEVERITY_BADGE.get(severity, "badge-purple"),
        })

    # Column rows (analyst only)
    profile = analysis_result.get("profile", {})
    columns_data = profile.get("columns", []) if isinstance(profile, dict) else []
    column_rows = []
    for col in columns_data[:50]:
        miss_f = float(col.get("missing_pct", 0) or 0)
        if miss_f > 30:
            status_cls, status_label = "badge-red", "High missing"
        elif miss_f > 5:
            status_cls, status_label = "badge-yellow", "Some missing"
        else:
            status_cls, status_label = "badge-green", "Good"
        mean = col.get("mean", "")
        std  = col.get("std", "")
        column_rows.append({
            "name":         col.get("name", ""),
            "dtype":        col.get("dtype", ""),
            "missing_pct":  f"{miss_f:.1f}%",
            "unique":       col.get("unique_count", col.get("n_unique", "—")),
            "mean":         f"{mean:.2f}" if isinstance(mean, float) else (str(mean) if mean else "—"),
            "std":          f"{std:.2f}"  if isinstance(std, float)  else (str(std)  if std  else "—"),
            "status_cls":   status_cls,
            "status_label": status_label,
        })

    # Cleaning rows (analyst only)
    cleaning_raw = analysis_result.get("cleaning_report", analysis_result.get("cleaning", []))
    cleaning_rows = []
    if cleaning_raw and isinstance(cleaning_raw, list):
        for step in cleaning_raw[:20]:
            cleaning_rows.append({
                "step":   step.get("step", step.get("action", "")) if isinstance(step, dict) else str(step),
                "detail": step.get("detail", step.get("description", "")) if isinstance(step, dict) else "",
                "impact": step.get("impact", "") if isinstance(step, dict) else "",
            })

    # Chart configs
    chart_configs = build_chart_configs(analysis_result)

    return {
        "title":          project_name,
        "date":           datetime.now().strftime("%Y-%m-%d %H:%M"),
        "mode":           mode,
        "n_rows":         f"{n_rows:,}",
        "n_cols":         n_cols,
        "missing_pct":    missing_pct,
        "grade":          grade,
        "narrative":      narrative,
        "narrative_paras": narrative_paras,
        "quality_rows":   quality_rows,
        "insights":       insights,
        "column_rows":    column_rows,
        "cleaning_rows":  cleaning_rows,
        "health_chart":   chart_configs.get("health_chart"),
        "missing_chart":  chart_configs.get("missing_chart"),
    }
