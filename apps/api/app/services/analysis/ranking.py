"""
Insight deduplication and ranking.

BUG FIX: The original analyzer.py deduplicated by insight["title"][:40].lower()
— a fragile prefix match that could:
  (a) discard distinct insights whose titles happen to share a prefix
  (b) miss duplicate insights expressed with different titles

This module uses a semantic key: (insight_type, frozenset_of_involved_columns).
For insights without explicit column references, it falls back to a normalised
title prefix so the behaviour degrades gracefully rather than failing.

rank_insights: composite sort — severity 65%, confidence 35%.
"""
from __future__ import annotations

from app.config import MAX_INSIGHTS


_SEV_WEIGHT = {"high": 1.0, "medium": 0.6, "low": 0.2}


def _insight_key(ins: dict) -> tuple:
    """
    Return a hashable semantic deduplication key.

    Prefers (type, frozenset_of_columns) when column references are present;
    falls back to (type, normalised_title_prefix) otherwise.
    """
    itype = ins.get("type", "")

    # Collect all column references present in this insight dict
    col_refs: list[str] = []
    for field in ("col_a", "col_b"):
        v = ins.get(field)
        if v:
            col_refs.append(v)

    # Some insight types embed columns in a known pattern in 'title'
    # e.g. "Segment gap: region → revenue" — extract both sides
    if not col_refs and itype in {"segment", "concentration", "trend", "distribution", "anomaly"}:
        title = ins.get("title", "")
        # "Segment gap: cat → num" / "Rate gap: cat → target"
        if "→" in title:
            parts = title.split("→")
            left = parts[0].split(":")[-1].strip()
            right = parts[1].strip()
            col_refs = [left, right]
        # "Trend detected: col (direction)"
        elif "Trend detected:" in title:
            col_part = title.split(":")[-1].strip().split(" (")[0]
            col_refs = [col_part]
        # "Anomalies in col" / "Skewed distribution: col" / "Constant column: col"
        elif ":" in title:
            col_part = title.split(":")[-1].strip()
            col_refs = [col_part]

    if col_refs:
        return (itype, frozenset(col_refs))

    # Fallback: normalised title prefix (original behaviour)
    return (itype, ins.get("title", "")[:40].lower())


def deduplicate_insights(insights: list[dict]) -> list[dict]:
    """Remove duplicate insights using semantic (type + columns) keys."""
    seen: set = set()
    deduped: list[dict] = []
    for ins in insights:
        key = _insight_key(ins)
        if key not in seen:
            seen.add(key)
            deduped.append(ins)
    return deduped


def rank_insights(insights: list[dict]) -> list[dict]:
    """
    Sort insights by composite score (severity 65%, confidence 35%),
    deduplicate, then cap at MAX_INSIGHTS.

    Returns (ranked_deduped_list, total_before_cap).
    """
    insights.sort(
        key=lambda x: -(
            _SEV_WEIGHT.get(x.get("severity", "low"), 0.2) * 0.65
            + (x.get("confidence", 50) / 100.0) * 0.35
        )
    )
    deduped = deduplicate_insights(insights)
    total_found = len(deduped)
    return deduped[:MAX_INSIGHTS], total_found
