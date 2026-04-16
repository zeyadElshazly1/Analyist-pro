"""
Chart ranking and output cap.

rank_and_cap — sort by score descending, return top MAX_CHARTS.
"""
from .budget import MAX_CHARTS


def rank_and_cap(charts: list[dict]) -> list[dict]:
    """Sort charts by score descending and cap output at MAX_CHARTS."""
    charts.sort(key=lambda c: c.get("score", 0), reverse=True)
    return charts[:MAX_CHARTS]
