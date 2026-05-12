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


def _canonical_to_raw_summary_view(ins: dict) -> dict:
    """Return a copy of a canonical insight with confidence scaled back to 0–100.

    Canonical InsightResult confidence is stored as 0.0–1.0; is_summary_eligible
    expects raw 0–100, so we rescale before the check.
    """
    out = dict(ins)
    conf = out.get("confidence")
    if isinstance(conf, (int, float)) and 0 <= conf <= 1:
        out["confidence"] = conf * 100
    return out


def build_cached_insight_selection_meta(result: dict) -> dict | None:
    """Build a best-effort insight_selection_meta block from a cached result.

    Returns None when the cached payload has no usable insight_results list.
    The returned dict includes backfilled_from_cache=True so callers can
    distinguish it from a freshly computed block.
    """
    if not isinstance(result, dict):
        return None

    insights = result.get("insight_results")
    if not isinstance(insights, list):
        return None

    visible = [i for i in insights if isinstance(i, dict)]
    suppressed_visible = sum(
        1 for ins in visible
        if ins.get("suppressed_by_plan") is True
    )
    summary_eligible_visible = sum(
        1 for ins in visible
        if is_summary_eligible(_canonical_to_raw_summary_view(ins))
    )

    return {
        "post_hygiene_candidate_count": len(visible),
        "visible_insight_count": len(visible),
        "summary_eligible_visible_count": summary_eligible_visible,
        "summary_ineligible_visible_count": len(visible) - summary_eligible_visible,
        "suppressed_candidate_count": suppressed_visible,
        "suppressed_visible_count": suppressed_visible,
        "final_cap": MAX_INSIGHTS,
        "backfilled_from_cache": True,
    }
