from app.config import MAX_INSIGHTS


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
    return {
        "post_hygiene_candidate_count": len(post_hygiene_candidates),
        "visible_insight_count": len(capped_insights),
        "suppressed_candidate_count": suppressed_candidate_count,
        "suppressed_visible_count": suppressed_visible_count,
        "final_cap": final_cap,
    }
