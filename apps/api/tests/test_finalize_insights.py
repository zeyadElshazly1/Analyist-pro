"""
88L — tests for final_cap_with_candidate_count helper.
"""
from __future__ import annotations

from app.config import MAX_INSIGHTS
from app.services.analysis.finalize_insights import final_cap_with_candidate_count


def test_final_cap_with_candidate_count_preserves_pre_cap_count():
    items = [{"title": str(i)} for i in range(MAX_INSIGHTS + 3)]

    capped, count = final_cap_with_candidate_count(items)

    assert len(capped) == MAX_INSIGHTS
    assert count == MAX_INSIGHTS + 3


def test_final_cap_with_candidate_count_does_not_mutate_input():
    items = [{"title": str(i)} for i in range(MAX_INSIGHTS + 3)]
    before = list(items)

    final_cap_with_candidate_count(items)

    assert items == before


def test_final_cap_with_fewer_than_max_returns_all():
    items = [{"title": str(i)} for i in range(3)]

    capped, count = final_cap_with_candidate_count(items)

    assert len(capped) == 3
    assert count == 3


def test_final_cap_empty_list():
    capped, count = final_cap_with_candidate_count([])

    assert capped == []
    assert count == 0


# ── 88M — build_insight_selection_meta ───────────────────────────────────────

from app.services.analysis.finalize_insights import build_insight_selection_meta


def test_build_insight_selection_meta_counts_candidates_and_visible():
    candidates = [{"title": str(i)} for i in range(MAX_INSIGHTS + 3)]
    capped, _ = final_cap_with_candidate_count(candidates)

    meta = build_insight_selection_meta(candidates, capped)

    assert meta["post_hygiene_candidate_count"] == MAX_INSIGHTS + 3
    assert meta["visible_insight_count"] == MAX_INSIGHTS
    assert meta["final_cap"] == MAX_INSIGHTS


def test_build_insight_selection_meta_counts_suppressed():
    candidates = [
        {"title": "clean 1"},
        {"title": "suppressed 1", "suppressed_by_plan": True},
        {"title": "suppressed 2", "suppressed_by_plan": True},
    ]
    capped = candidates[:2]

    meta = build_insight_selection_meta(candidates, capped)

    assert meta["suppressed_candidate_count"] == 2
    assert meta["suppressed_visible_count"] == 1


def test_build_insight_selection_meta_ignores_false_suppression_flag():
    candidates = [
        {"title": "clean", "suppressed_by_plan": False},
        {"title": "suppressed", "suppressed_by_plan": True},
    ]

    meta = build_insight_selection_meta(candidates, candidates)

    assert meta["suppressed_candidate_count"] == 1
    assert meta["suppressed_visible_count"] == 1


def test_build_insight_selection_meta_does_not_mutate_inputs():
    candidates = [{"title": "x", "suppressed_by_plan": True}]
    capped = list(candidates)
    before_candidates = [dict(x) for x in candidates]
    before_capped = [dict(x) for x in capped]

    build_insight_selection_meta(candidates, capped)

    assert candidates == before_candidates
    assert capped == before_capped
