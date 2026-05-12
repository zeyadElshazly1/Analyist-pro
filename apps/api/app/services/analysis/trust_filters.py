from app.services.analysis.confidence import safe_confidence_from_insight


def is_summary_eligible(
    ins: dict,
    *,
    min_confidence: float = 50.0,
) -> bool:
    """Return True when an insight is safe for high-level summaries.

    Used by narrative and executive panel.
    Does not mutate the insight.
    """
    if not isinstance(ins, dict):
        return False

    if ins.get("suppressed_by_plan") is True:
        return False

    if safe_confidence_from_insight(ins) < min_confidence:
        return False

    return True
