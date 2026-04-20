"""
Report templates — opinionated defaults for common consultant use cases.

Each template provides:
  - title_prefix: prepended to the project name
  - insight_sort_keys: ordered list of insight types to prefer
  - focus_sections: which analysis sections to surface first
  - executive_summary_hint: prompt hint for AI summary generation
"""
from __future__ import annotations

TEMPLATES: dict[str, dict] = {
    "monthly_performance": {
        "label": "Monthly Performance Report",
        "title_prefix": "Monthly Performance",
        "insight_sort_keys": ["trend", "anomaly", "correlation", "segment", "distribution"],
        "focus_sections": ["health_score", "insights", "timeseries", "comparison"],
        "executive_summary_hint": (
            "Summarise the key metric trends for the month. Highlight any significant "
            "changes vs the previous period, anomalies, and top 3 actionable findings."
        ),
    },
    "ops_kpi_review": {
        "label": "Ops / KPI Review",
        "title_prefix": "KPI Review",
        "insight_sort_keys": ["data_quality", "anomaly", "distribution", "correlation", "trend"],
        "focus_sections": ["health_score", "cleaning", "insights", "profile"],
        "executive_summary_hint": (
            "Review the operational KPI dataset. Lead with data health and completeness. "
            "Flag missing values, outliers, and variance vs target. Provide 3 recommendations."
        ),
    },
    "finance_summary": {
        "label": "Finance Summary",
        "title_prefix": "Finance Summary",
        "insight_sort_keys": ["anomaly", "distribution", "correlation", "trend", "segment"],
        "focus_sections": ["insights", "charts", "profile", "comparison"],
        "executive_summary_hint": (
            "Summarise the financial dataset. Focus on totals, category breakdowns, "
            "period-over-period deltas, and any outlier transactions. Keep language client-safe."
        ),
    },
}


def get_template(template_id: str) -> dict | None:
    return TEMPLATES.get(template_id)


def sort_insights_by_template(insights: list[dict], template_id: str) -> list[dict]:
    """Re-order insights to match the template's preferred insight types."""
    template = TEMPLATES.get(template_id)
    if not template:
        return insights

    order = template["insight_sort_keys"]

    def _rank(ins: dict) -> int:
        t = ins.get("type", "")
        try:
            return order.index(t)
        except ValueError:
            return len(order)

    return sorted(insights, key=_rank)


def apply_template_to_draft(draft_data: dict, template_id: str, analysis_result: dict) -> dict:
    """
    Pre-fill a report draft payload based on a template and the available
    analysis result.  Returns a dict of suggested draft field values.
    """
    template = TEMPLATES.get(template_id)
    if not template:
        return draft_data

    insights = analysis_result.get("insights", [])
    sorted_insights = sort_insights_by_template(insights, template_id)

    # Select top 5 by template priority
    selected_ids = [
        i for i, ins in enumerate(insights)
        if ins in sorted_insights[:5]
    ]

    return {
        **draft_data,
        "template": template_id,
        "selected_insight_ids": selected_ids[:5],
        "executive_summary_hint": template["executive_summary_hint"],
    }
