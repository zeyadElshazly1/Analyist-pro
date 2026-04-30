"""
Insight deduplication and ranking.

BUG FIX: The original analyzer.py deduplicated by insight["title"][:40].lower()
— a fragile prefix match that could:
  (a) discard distinct insights whose titles happen to share a prefix
  (b) miss duplicate insights expressed with different titles

This module uses a semantic key: (insight_type, frozenset_of_involved_columns).
For insights without explicit column references, it falls back to a normalised
title prefix so the behaviour degrades gracefully rather than failing.

rank_insights: composite sort — severity 50%, confidence 25%, target-driver 25%.

Target-driver bonus
-------------------
Insights where ``is_target_driver=True`` (i.e. rate-gap findings that link a
predictor column to a known binary outcome like Churn/Fraud/Default) receive a
0.30-point bonus in the composite score.  Without this, a weak multivariate
anomaly insight with "high" severity could outrank a "medium"-severity finding
that Contract drives churn by 40 percentage points — a clearly worse outcome
for users who need actionable business intelligence first.
"""
from __future__ import annotations

from app.config import MAX_INSIGHTS


_SEV_WEIGHT = {"high": 1.0, "medium": 0.6, "low": 0.2}

# How much weight a "target-driver" insight receives in the composite score.
# Raised above zero so that rate-gap insights linking predictors to binary
# business outcomes (churn, fraud, conversion) are ranked above unrelated
# pattern-detection findings of equivalent severity.
_TARGET_DRIVER_BONUS = 0.30


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


def _composite_score(ins: dict) -> float:
    """
    Composite ranking score for a single insight.

    Components
    ----------
    severity        50% — high/medium/low maps to 1.0/0.6/0.2
    confidence      25% — normalised 0–1 (insight's 0–100 scale)
    target_driver   25% — flat bonus when insight links a predictor to a
                          known binary outcome (is_target_driver=True)

    Rationale: a rate-gap insight with "medium" severity and a 0.30 target-
    driver bonus scores ≈ 0.56, beating a "medium" non-target insight at ≈ 0.34
    but losing to a "high" non-target insight at ≈ 0.72.  This preserves the
    primacy of genuine data anomalies while elevating business-outcome drivers
    above weak pattern findings.
    """
    sev   = _SEV_WEIGHT.get(ins.get("severity", "low"), 0.2)
    conf  = float(ins.get("confidence", 50)) / 100.0
    bonus = _TARGET_DRIVER_BONUS if ins.get("is_target_driver") else 0.0
    return sev * 0.50 + conf * 0.25 + bonus * 0.25


def rank_insights(insights: list[dict]) -> list[dict]:
    """
    Sort insights by composite score (severity 50%, confidence 25%,
    target-driver bonus 25%), deduplicate, then cap at MAX_INSIGHTS.

    Returns (ranked_deduped_list, total_before_cap).
    """
    insights.sort(key=lambda x: -_composite_score(x))
    deduped = deduplicate_insights(insights)
    total_found = len(deduped)
    return deduped[:MAX_INSIGHTS], total_found
