"""
90G — Unit tests for the pre_analysis profile composer.

Verifies that build_pre_analysis_profile wires all V2 sub-steps
correctly and returns a valid PreAnalysisProfile.
"""
from __future__ import annotations

import pandas as pd
import pytest

from app.schemas.pre_analysis import PreAnalysisProfile
from app.services.analysis.pre_analysis import build_pre_analysis_profile


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _sales_df() -> pd.DataFrame:
    return pd.DataFrame({
        "order_id":   [f"ORD{i:03d}" for i in range(50)],
        "customer_id": [f"CUST{i % 10:02d}" for i in range(50)],
        "revenue":    [100.0 + i * 5 for i in range(50)],
        "units":      [1 + i % 10 for i in range(50)],
        "region":     ["North", "South"] * 25,
        "order_date": pd.date_range("2024-01-01", periods=50, freq="D"),
    })


def _tiny_df() -> pd.DataFrame:
    return pd.DataFrame({"x": [1, 2], "y": [3, 4]})


def _all_missing_df() -> pd.DataFrame:
    return pd.DataFrame({
        "a": [None] * 20,
        "b": [None] * 20,
        "c": range(20),
    })


# ── Return type ───────────────────────────────────────────────────────────────

def test_returns_pre_analysis_profile_instance():
    df = _sales_df()
    result = build_pre_analysis_profile(df)
    assert isinstance(result, PreAnalysisProfile)


def test_profile_is_json_serialisable():
    import json
    df = _sales_df()
    profile = build_pre_analysis_profile(df)
    dumped = profile.model_dump()
    # model_dump → json.dumps should not raise
    json.dumps(dumped)


# ── Fingerprint wiring ────────────────────────────────────────────────────────

def test_fingerprint_row_count_matches_df():
    df = _sales_df()
    profile = build_pre_analysis_profile(df)
    assert profile.fingerprint.row_count == len(df)


def test_fingerprint_column_count_matches_df():
    df = _sales_df()
    profile = build_pre_analysis_profile(df)
    assert profile.fingerprint.column_count == len(df.columns)


# ── Column roles wiring ───────────────────────────────────────────────────────

def test_column_roles_count_matches_df_columns():
    df = _sales_df()
    profile = build_pre_analysis_profile(df)
    assert len(profile.column_roles) == len(df.columns)


def test_column_roles_names_match_df_columns():
    df = _sales_df()
    profile = build_pre_analysis_profile(df)
    role_names = {r.column_name for r in profile.column_roles}
    assert role_names == set(df.columns)


# ── Grain wiring ──────────────────────────────────────────────────────────────

def test_grain_label_is_valid():
    from app.schemas.pre_analysis import PreAnalysisProfile
    df = _sales_df()
    profile = build_pre_analysis_profile(df)
    valid_labels = {
        "customer", "order", "policy", "transaction", "event",
        "product", "employee", "time_period", "session", "survey_response", "unknown",
    }
    assert profile.grain_label in valid_labels


def test_grain_confidence_in_range():
    df = _sales_df()
    profile = build_pre_analysis_profile(df)
    assert 0.0 <= profile.grain_confidence <= 1.0


# ── Strategy wiring ───────────────────────────────────────────────────────────

def test_strategy_is_populated_for_rich_dataset():
    df = _sales_df()
    profile = build_pre_analysis_profile(df)
    assert len(profile.strategy.recommended_analysis_types) > 0


# ── Hypothesis plan wiring ────────────────────────────────────────────────────

def test_hypothesis_plan_always_has_fallback():
    df = _tiny_df()
    profile = build_pre_analysis_profile(df)
    # The fallback hypothesis is always appended
    assert any("distribution" in h.lower() for h in profile.hypothesis_plan.hypotheses)


# ── Metadata ─────────────────────────────────────────────────────────────────

def test_generated_at_is_present():
    df = _sales_df()
    profile = build_pre_analysis_profile(df)
    assert profile.generated_at
    assert "T" in profile.generated_at  # ISO-8601 format contains 'T'


def test_planner_version_is_v2():
    df = _sales_df()
    profile = build_pre_analysis_profile(df)
    assert profile.planner_version == "v2.0-deterministic"


# ── Edge cases ────────────────────────────────────────────────────────────────

def test_tiny_dataset_does_not_raise():
    profile = build_pre_analysis_profile(_tiny_df())
    assert isinstance(profile, PreAnalysisProfile)


def test_high_missing_dataset_does_not_raise():
    profile = build_pre_analysis_profile(_all_missing_df())
    assert isinstance(profile, PreAnalysisProfile)


def test_does_not_mutate_input_df():
    df = _sales_df()
    cols_before = df.columns.tolist()
    rows_before = len(df)
    build_pre_analysis_profile(df)
    assert df.columns.tolist() == cols_before
    assert len(df) == rows_before
