from app.config import MAX_INSIGHTS


def final_cap_with_candidate_count(insights: list[dict]) -> tuple[list[dict], int]:
    """Return (capped_insights, pre_cap_count) without mutating the input list."""
    candidate_count = len(insights)
    return insights[:MAX_INSIGHTS], candidate_count
