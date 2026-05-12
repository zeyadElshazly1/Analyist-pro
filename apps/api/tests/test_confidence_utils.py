"""
88P — shared confidence utility tests.
"""
from __future__ import annotations

from app.services.analysis.confidence import (
    safe_confidence_0_100,
    safe_confidence_from_insight,
)


def test_safe_confidence_defaults_for_none():
    assert safe_confidence_0_100(None) == 50.0


def test_safe_confidence_defaults_for_invalid_string():
    assert safe_confidence_0_100("unknown") == 50.0


def test_safe_confidence_clamps_negative_to_zero():
    assert safe_confidence_0_100(-10) == 0.0


def test_safe_confidence_clamps_above_100():
    assert safe_confidence_0_100(999) == 100.0


def test_safe_confidence_preserves_valid_number():
    assert safe_confidence_0_100(82.5) == 82.5


def test_safe_confidence_from_insight_reads_confidence_key():
    assert safe_confidence_from_insight({"confidence": 75}) == 75.0


def test_safe_confidence_from_insight_defaults_for_missing_key():
    assert safe_confidence_from_insight({}) == 50.0


def test_safe_confidence_from_insight_defaults_for_non_dict():
    assert safe_confidence_from_insight(None) == 50.0


# ── 88R — NaN and infinity handling ──────────────────────────────────────────

import math


def test_safe_confidence_nan_defaults_to_50():
    assert safe_confidence_0_100(float("nan")) == 50.0


def test_safe_confidence_string_nan_defaults_to_50():
    assert safe_confidence_0_100("nan") == 50.0


def test_safe_confidence_positive_infinity_clamps_to_100():
    assert safe_confidence_0_100(float("inf")) == 100.0


def test_safe_confidence_negative_infinity_clamps_to_zero():
    assert safe_confidence_0_100(float("-inf")) == 0.0


def test_safe_confidence_from_insight_nan_defaults_to_50():
    assert safe_confidence_from_insight({"confidence": float("nan")}) == 50.0
