"""
90L — Shadow-mode profile hygiene impact evaluator.

Compares plan-only hygiene vs plan+profile hygiene without changing live output.
Call this after apply_analysis_plan_hygiene, before rerank/cap.
Does not mutate inputs, does not persist anything, does not rerank.
"""
from __future__ import annotations

from app.services.analysis.confidence import safe_confidence_from_insight
from app.services.analysis.profile_hygiene import apply_pre_analysis_profile_hygiene

_ALL_REASONS = (
    "profile_date_part_artifact",
    "profile_high_cardinality_dimension",
    "profile_leakage_candidate",
    "profile_constant_column",
)


def evaluate_profile_hygiene_shadow(
    insights_after_plan_hygiene: list[dict],
    pre_analysis_profile: dict | None,
) -> dict:
    """Return an impact report for profile-aware hygiene without mutating inputs.

    Parameters
    ----------
    insights_after_plan_hygiene:
        Insight list as it exists after ``apply_analysis_plan_hygiene`` has run.
    pre_analysis_profile:
        Serialised ``PreAnalysisProfile`` dict (or None for legacy runs).

    Returns
    -------
    dict
        Impact metadata.  See module docstring for exact shape.
        Never raises; returns ``evaluated=False`` on any guard condition.
    """
    if not insights_after_plan_hygiene:
        return {
            "evaluated": False,
            "reason": "no_insights",
            "input_count": 0,
        }

    if not pre_analysis_profile or not isinstance(pre_analysis_profile, dict):
        return {
            "evaluated": False,
            "reason": "missing_pre_analysis_profile",
            "input_count": len(insights_after_plan_hygiene),
        }

    # Run profile hygiene on a logical copy — the helper is non-mutating so
    # individual dicts are only shallow-copied when penalised.
    after = apply_pre_analysis_profile_hygiene(
        list(insights_after_plan_hygiene),   # new list, same dict objects inside
        pre_analysis_profile,
        enabled=True,
    )

    reason_counts: dict[str, int] = {r: 0 for r in _ALL_REASONS}
    penalized_count = 0
    confidence_deltas: list[dict] = []

    for i, (before, aft) in enumerate(zip(insights_after_plan_hygiene, after)):
        if aft.get("suppressed_by_profile") is True:
            penalized_count += 1
            reason = aft.get("profile_penalty_reason", "")
            if reason in reason_counts:
                reason_counts[reason] += 1

            confidence_deltas.append({
                "index": i,
                "before_confidence": safe_confidence_from_insight(before),
                "after_confidence": safe_confidence_from_insight(aft),
                "reason": reason,
                "title": before.get("title"),
                "category": before.get("category"),
            })

    return {
        "evaluated": True,
        "input_count": len(insights_after_plan_hygiene),
        "profile_penalized_count": penalized_count,
        "profile_penalty_reasons": reason_counts,
        "confidence_deltas": confidence_deltas,
    }
