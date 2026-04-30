"""
Chart ranking and output cap.

rank_and_cap — sort by score descending, return top MAX_CHARTS.
"""
from .budget import MAX_CHARTS


def rank_and_cap(charts: list[dict]) -> list[dict]:
    """Sort charts by score descending, dedupe by signature, cap at MAX_CHARTS."""
    charts.sort(key=lambda c: c.get("score", 0), reverse=True)
    seen: set[tuple] = set()
    deduped: list[dict] = []
    for c in charts:
        sig = (
            str(c.get("type", "")),
            str(c.get("title", "")).strip().lower(),
            str(c.get("x_key", "")),
            str(c.get("y_key", "")),
        )
        if sig in seen:
            continue
        seen.add(sig)
        deduped.append(c)
        if len(deduped) >= MAX_CHARTS:
            break
    return deduped
