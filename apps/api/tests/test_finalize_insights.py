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
