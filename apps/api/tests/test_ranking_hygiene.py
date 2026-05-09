"""
88D — Post-hygiene re-ranking tests.

Verifies that rerank_after_plan_hygiene() moves suppressed findings below
clean findings while preserving all insights and not mutating inputs.
"""
from __future__ import annotations

from app.services.analysis.ranking import rerank_after_plan_hygiene


def test_suppressed_insight_moves_below_clean_insight():
    noisy = {
        "type": "data_quality",
        "severity": "high",
        "confidence": 90,
        "title": "order_date_month concentration",
        "suppressed_by_plan": True,
        "plan_penalty_reason": "date_part_feature",
    }
    clean = {
        "type": "trend",
        "severity": "medium",
        "confidence": 75,
        "title": "Revenue trend over order_date",
    }

    result = rerank_after_plan_hygiene([noisy, clean])

    assert result == [clean, noisy]


def test_clean_insights_sort_by_composite_score():
    low = {
        "type": "trend",
        "severity": "low",
        "confidence": 95,
        "title": "Weak trend",
    }
    high = {
        "type": "anomaly",
        "severity": "high",
        "confidence": 60,
        "title": "Major anomaly",
    }

    result = rerank_after_plan_hygiene([low, high])

    assert result == [high, low]


def test_suppressed_insights_sort_by_composite_score_after_clean_items():
    weak_suppressed = {
        "type": "data_quality",
        "severity": "low",
        "confidence": 20,
        "title": "Weak noisy finding",
        "suppressed_by_plan": True,
    }
    strong_suppressed = {
        "type": "data_quality",
        "severity": "high",
        "confidence": 45,
        "title": "Stronger noisy finding",
        "suppressed_by_plan": True,
    }
    clean = {
        "type": "segment",
        "severity": "medium",
        "confidence": 60,
        "title": "Clean segment",
    }

    result = rerank_after_plan_hygiene([weak_suppressed, strong_suppressed, clean])

    assert result == [clean, strong_suppressed, weak_suppressed]


def test_rerank_after_plan_hygiene_does_not_mutate_inputs():
    first = {
        "type": "data_quality",
        "severity": "high",
        "confidence": 90,
        "title": "Noisy",
        "suppressed_by_plan": True,
    }
    second = {
        "type": "trend",
        "severity": "medium",
        "confidence": 75,
        "title": "Clean",
    }
    original = [first, second]
    before_list = list(original)
    before_first = dict(first)
    before_second = dict(second)

    rerank_after_plan_hygiene(original)

    assert original == before_list
    assert first == before_first
    assert second == before_second


def test_rerank_after_plan_hygiene_stable_for_equal_scores():
    a = {
        "type": "trend",
        "severity": "medium",
        "confidence": 70,
        "title": "A",
    }
    b = {
        "type": "trend",
        "severity": "medium",
        "confidence": 70,
        "title": "B",
    }

    result = rerank_after_plan_hygiene([a, b])

    assert result == [a, b]


def test_empty_list_returns_empty():
    assert rerank_after_plan_hygiene([]) == []


def test_all_suppressed_still_sorted_by_score():
    low = {
        "type": "data_quality",
        "severity": "low",
        "confidence": 30,
        "title": "Low suppressed",
        "suppressed_by_plan": True,
    }
    high = {
        "type": "data_quality",
        "severity": "high",
        "confidence": 50,
        "title": "High suppressed",
        "suppressed_by_plan": True,
    }

    result = rerank_after_plan_hygiene([low, high])

    assert result == [high, low]


def test_no_suppressed_preserves_composite_order():
    a = {"type": "anomaly", "severity": "high", "confidence": 80, "title": "A"}
    b = {"type": "segment", "severity": "medium", "confidence": 60, "title": "B"}
    c = {"type": "trend", "severity": "low", "confidence": 90, "title": "C"}

    result = rerank_after_plan_hygiene([a, b, c])

    # All clean; should come out sorted by composite descending
    scores = [
        (ins["severity"], ins["confidence"]) for ins in result
    ]
    # a: high+80 → best composite; b: medium+60; c: low+90 (low weight on sev)
    assert result[0] == a


def test_suppressed_false_treated_as_not_suppressed():
    """suppressed_by_plan=False must not push the insight below clean ones."""
    explicitly_not_suppressed = {
        "type": "data_quality",
        "severity": "high",
        "confidence": 90,
        "title": "Not suppressed",
        "suppressed_by_plan": False,
    }
    clean = {
        "type": "trend",
        "severity": "low",
        "confidence": 50,
        "title": "Clean low",
    }

    result = rerank_after_plan_hygiene([clean, explicitly_not_suppressed])

    # explicitly_not_suppressed has higher composite; should be first
    assert result[0] == explicitly_not_suppressed


# ── 88G — rank_insights limit parameter ──────────────────────────────────────

from app.config import MAX_INSIGHTS
from app.services.analysis.ranking import rank_insights


def test_rank_insights_default_limit_uses_max_insights():
    insights = [
        {
            "type": "trend",
            "severity": "medium",
            "confidence": 50 + i,
            "title": f"Trend {i}",
        }
        for i in range(MAX_INSIGHTS + 5)
    ]

    ranked, total = rank_insights(insights)

    assert len(ranked) == MAX_INSIGHTS
    assert total == MAX_INSIGHTS + 5


def test_rank_insights_custom_limit_returns_candidate_pool():
    insights = [
        {
            "type": "trend",
            "severity": "medium",
            "confidence": 50 + i,
            "title": f"Trend {i}",
        }
        for i in range(MAX_INSIGHTS + 5)
    ]

    ranked, total = rank_insights(insights, limit=MAX_INSIGHTS + 3)

    assert len(ranked) == MAX_INSIGHTS + 3
    assert total == MAX_INSIGHTS + 5


def test_rank_insights_custom_limit_does_not_change_input_count():
    insights = [
        {
            "type": "trend",
            "severity": "medium",
            "confidence": 70,
            "title": f"Trend {i}",
        }
        for i in range(MAX_INSIGHTS + 5)
    ]

    before_len = len(insights)
    rank_insights(insights, limit=MAX_INSIGHTS + 2)

    assert len(insights) == before_len


def test_rank_insights_limit_none_equals_default():
    insights = [
        {
            "type": "anomaly",
            "severity": "high",
            "confidence": 80,
            "title": f"Anomaly {i}",
        }
        for i in range(MAX_INSIGHTS + 10)
    ]

    ranked_default, _ = rank_insights(list(insights))
    ranked_explicit, _ = rank_insights(list(insights), limit=None)

    assert len(ranked_default) == len(ranked_explicit) == MAX_INSIGHTS


def test_rank_insights_limit_smaller_than_input():
    insights = [
        {"type": "trend", "severity": "low", "confidence": 60, "title": f"T{i}"}
        for i in range(5)
    ]
    ranked, total = rank_insights(insights, limit=3)
    assert len(ranked) == 3
    assert total == 5


def test_rank_insights_limit_larger_than_available():
    insights = [
        {"type": "trend", "severity": "medium", "confidence": 70, "title": f"T{i}"}
        for i in range(3)
    ]
    ranked, total = rank_insights(insights, limit=MAX_INSIGHTS + 10)
    assert len(ranked) == 3
    assert total == 3
