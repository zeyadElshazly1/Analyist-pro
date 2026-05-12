"""
88S — shared summary eligibility helper tests.
"""
from __future__ import annotations

from app.services.analysis.trust_filters import is_summary_eligible


def test_summary_eligible_clean_confident_insight():
    assert is_summary_eligible({"confidence": 80}) is True


def test_summary_excludes_suppressed_by_plan():
    assert is_summary_eligible({"confidence": 90, "suppressed_by_plan": True}) is False


def test_summary_treats_suppressed_false_as_clean():
    assert is_summary_eligible({"confidence": 80, "suppressed_by_plan": False}) is True


def test_summary_excludes_low_confidence():
    assert is_summary_eligible({"confidence": 49}) is False


def test_summary_allows_exactly_50_confidence():
    assert is_summary_eligible({"confidence": 50}) is True


def test_summary_uses_safe_confidence_default_for_invalid_value():
    assert is_summary_eligible({"confidence": "unknown"}) is True


def test_summary_excludes_negative_confidence():
    assert is_summary_eligible({"confidence": -10}) is False


def test_summary_allows_above_100_confidence_after_clamp():
    assert is_summary_eligible({"confidence": 999}) is True


def test_summary_excludes_non_dict_input():
    assert is_summary_eligible(None) is False
