from app.config import MAX_INSIGHTS
from app.services.analysis.trust_filters import is_summary_eligible


def final_cap_with_candidate_count(insights: list[dict]) -> tuple[list[dict], int]:
    """Return (capped_insights, pre_cap_count) without mutating the input list."""
    candidate_count = len(insights)
    return insights[:MAX_INSIGHTS], candidate_count


def build_insight_selection_meta(
    post_hygiene_candidates: list[dict],
    capped_insights: list[dict],
    *,
    final_cap: int = MAX_INSIGHTS,
) -> dict:
    suppressed_candidate_count = sum(
        1 for ins in post_hygiene_candidates
        if isinstance(ins, dict) and ins.get("suppressed_by_plan") is True
    )
    suppressed_visible_count = sum(
        1 for ins in capped_insights
        if isinstance(ins, dict) and ins.get("suppressed_by_plan") is True
    )
    summary_eligible_visible_count = sum(
        1 for ins in capped_insights
        if is_summary_eligible(ins)
    )
    summary_ineligible_visible_count = len(capped_insights) - summary_eligible_visible_count
    return {
        "post_hygiene_candidate_count": len(post_hygiene_candidates),
        "visible_insight_count": len(capped_insights),
        "summary_eligible_visible_count": summary_eligible_visible_count,
        "summary_ineligible_visible_count": summary_ineligible_visible_count,
        "suppressed_candidate_count": suppressed_candidate_count,
        "suppressed_visible_count": suppressed_visible_count,
        "final_cap": final_cap,
    }
