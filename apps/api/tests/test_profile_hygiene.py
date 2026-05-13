"""
90J — Unit tests for profile-aware hygiene helper.

All tests use enabled=True unless testing the disabled-by-default path.
No pipeline path calls apply_pre_analysis_profile_hygiene yet (90J gate).
"""
from __future__ import annotations

import pytest

from app.services.analysis.profile_hygiene import apply_pre_analysis_profile_hygiene


# ── Fixture helpers ───────────────────────────────────────────────────────────

def _insight(
    confidence: float = 80.0,
    category: str = "trend",
    title: str = "Test insight",
    col_a: str | None = None,
    columns: list[str] | None = None,
    **extra,
) -> dict:
    ins: dict = {"confidence": confidence, "category": category, "title": title}
    if col_a is not None:
        ins["col_a"] = col_a
    if columns is not None:
        ins["columns"] = columns
    ins.update(extra)
    return ins


def _profile(risks: list[dict], column_names: list[str] | None = None) -> dict:
    """Minimal pre_analysis_profile dict with the given risks and column_roles."""
    roles = [{"column_name": c} for c in (column_names or [])]
    return {"risks": risks, "column_roles": roles}


def _risk(name: str, affected: list[str], severity: str = "medium") -> dict:
    return {"risk_name": name, "severity": severity, "affected_columns": affected}


# ── Disabled-by-default ───────────────────────────────────────────────────────

def test_disabled_by_default_returns_original_list():
    insights = [_insight(col_a="order_date_month")]
    profile = _profile([_risk("date_part_artifacts", ["order_date_month"])], ["order_date_month"])
    result = apply_pre_analysis_profile_hygiene(insights, profile)  # enabled=False default
    assert result is insights


def test_disabled_explicitly_returns_original_list():
    insights = [_insight(col_a="leaked")]
    profile = _profile([_risk("possible_leakage", ["leaked"])], ["leaked"])
    result = apply_pre_analysis_profile_hygiene(insights, profile, enabled=False)
    assert result is insights


# ── None / empty profile ──────────────────────────────────────────────────────

def test_none_profile_returns_original_list():
    insights = [_insight()]
    result = apply_pre_analysis_profile_hygiene(insights, None, enabled=True)
    assert result is insights


def test_empty_dict_profile_returns_original_list():
    insights = [_insight()]
    result = apply_pre_analysis_profile_hygiene(insights, {}, enabled=True)
    assert result is insights


# ── Non-mutation ──────────────────────────────────────────────────────────────

def test_does_not_mutate_input_list():
    ins = _insight(col_a="order_date_month")
    original_ins = dict(ins)
    insights = [ins]
    profile = _profile([_risk("date_part_artifacts", ["order_date_month"])], ["order_date_month"])

    result = apply_pre_analysis_profile_hygiene(insights, profile, enabled=True)

    # Input list object unchanged
    assert insights[0] is ins
    # Input dict unchanged
    assert ins == original_ins
    # Penalised insight is a new object
    assert result[0] is not ins


def test_does_not_mutate_input_dicts():
    ins1 = _insight(col_a="order_date_month", confidence=80.0)
    ins2 = _insight(col_a="revenue", confidence=90.0)
    profile = _profile([_risk("date_part_artifacts", ["order_date_month"])], ["order_date_month", "revenue"])

    result = apply_pre_analysis_profile_hygiene([ins1, ins2], profile, enabled=True)

    assert ins1["confidence"] == 80.0    # untouched original
    assert ins2["confidence"] == 90.0    # not penalised — revenue isn't an artifact
    assert result[0]["confidence"] == pytest.approx(80.0 * 0.35)
    assert result[1]["confidence"] == 90.0


# ── Rule 1: date_part_artifacts ───────────────────────────────────────────────

def test_date_part_artifacts_penalizes_col_a_match():
    ins = _insight(col_a="order_date_month", confidence=80.0)
    profile = _profile([_risk("date_part_artifacts", ["order_date_month"])], ["order_date_month"])

    result = apply_pre_analysis_profile_hygiene([ins], profile, enabled=True)

    assert result[0]["confidence"] == pytest.approx(80.0 * 0.35)
    assert result[0]["suppressed_by_profile"] is True
    assert result[0]["profile_penalty_reason"] == "profile_date_part_artifact"


def test_date_part_artifacts_penalizes_text_match():
    ins = _insight(
        title="Trend detected: order_date_month (upward)",
        confidence=70.0,
    )
    profile = _profile([_risk("date_part_artifacts", ["order_date_month"])], ["order_date_month"])

    result = apply_pre_analysis_profile_hygiene([ins], profile, enabled=True)

    assert result[0]["confidence"] == pytest.approx(70.0 * 0.35)
    assert result[0]["profile_penalty_reason"] == "profile_date_part_artifact"


def test_date_part_artifacts_does_not_penalize_unaffected_column():
    ins = _insight(col_a="revenue", confidence=80.0)
    profile = _profile([_risk("date_part_artifacts", ["order_date_month"])], ["revenue", "order_date_month"])

    result = apply_pre_analysis_profile_hygiene([ins], profile, enabled=True)

    assert result[0]["confidence"] == 80.0
    assert "suppressed_by_profile" not in result[0]


# ── Rule 2: high_cardinality_dimensions ──────────────────────────────────────

def test_high_cardinality_penalizes_segment_insight():
    ins = _insight(col_a="region", confidence=75.0, category="segment")
    profile = _profile([_risk("high_cardinality_dimensions", ["region"])], ["region"])

    result = apply_pre_analysis_profile_hygiene([ins], profile, enabled=True)

    assert result[0]["confidence"] == pytest.approx(75.0 * 0.50)
    assert result[0]["profile_penalty_reason"] == "profile_high_cardinality_dimension"


def test_high_cardinality_penalizes_distribution_insight():
    ins = _insight(col_a="city", confidence=60.0, category="distribution")
    profile = _profile([_risk("high_cardinality_dimensions", ["city"])], ["city"])

    result = apply_pre_analysis_profile_hygiene([ins], profile, enabled=True)

    assert result[0]["confidence"] == pytest.approx(60.0 * 0.50)


def test_high_cardinality_does_not_penalize_trend_insight():
    ins = _insight(col_a="region", confidence=75.0, category="trend")
    profile = _profile([_risk("high_cardinality_dimensions", ["region"])], ["region"])

    result = apply_pre_analysis_profile_hygiene([ins], profile, enabled=True)

    assert result[0]["confidence"] == 75.0
    assert "suppressed_by_profile" not in result[0]


def test_high_cardinality_does_not_penalize_correlation_insight():
    ins = _insight(col_a="region", confidence=65.0, category="correlation")
    profile = _profile([_risk("high_cardinality_dimensions", ["region"])], ["region"])

    result = apply_pre_analysis_profile_hygiene([ins], profile, enabled=True)

    assert result[0]["confidence"] == 65.0


# ── Rule 3: leakage candidates ────────────────────────────────────────────────

def test_possible_leakage_penalizes_insight():
    ins = _insight(col_a="closed_date", confidence=90.0, category="trend")
    profile = _profile(
        [_risk("possible_leakage", ["closed_date", "outcome"])],
        ["closed_date", "outcome"],
    )

    result = apply_pre_analysis_profile_hygiene([ins], profile, enabled=True)

    assert result[0]["confidence"] == pytest.approx(90.0 * 0.25)
    assert result[0]["profile_penalty_reason"] == "profile_leakage_candidate"


def test_target_leakage_risk_penalizes_insight():
    ins = _insight(col_a="model_score", confidence=85.0, category="correlation")
    profile = _profile(
        [_risk("target_leakage_risk", ["model_score"], severity="high")],
        ["model_score"],
    )

    result = apply_pre_analysis_profile_hygiene([ins], profile, enabled=True)

    assert result[0]["confidence"] == pytest.approx(85.0 * 0.25)
    assert result[0]["profile_penalty_reason"] == "profile_leakage_candidate"


# ── Rule 4: constant_columns ──────────────────────────────────────────────────

def test_constant_columns_penalizes_insight():
    ins = _insight(col_a="data_source", confidence=70.0)
    profile = _profile([_risk("constant_columns", ["data_source"])], ["data_source"])

    result = apply_pre_analysis_profile_hygiene([ins], profile, enabled=True)

    assert result[0]["confidence"] == pytest.approx(70.0 * 0.30)
    assert result[0]["profile_penalty_reason"] == "profile_constant_column"


# ── Text-only matching ────────────────────────────────────────────────────────

def test_text_only_insight_matched_against_known_profile_columns():
    ins = _insight(
        title="Distribution of order_date_year shows no variance",
        confidence=65.0,
    )
    profile = _profile(
        [_risk("date_part_artifacts", ["order_date_year"])],
        ["order_date_year"],
    )

    result = apply_pre_analysis_profile_hygiene([ins], profile, enabled=True)

    assert result[0]["confidence"] == pytest.approx(65.0 * 0.35)


def test_fake_column_mention_in_text_is_ignored():
    """Column not in profile column_roles must not trigger a penalty."""
    ins = _insight(
        title="Revenue trend looks like order_date_century (fictional column)",
        confidence=80.0,
    )
    # profile knows only real columns, not order_date_century
    profile = _profile(
        [_risk("date_part_artifacts", ["order_date_month"])],
        ["order_date_month"],
    )

    result = apply_pre_analysis_profile_hygiene([ins], profile, enabled=True)

    assert result[0]["confidence"] == 80.0
    assert "suppressed_by_profile" not in result[0]


# ── Existing plan metadata preserved ─────────────────────────────────────────

def test_preserves_existing_suppressed_by_plan_metadata():
    ins = _insight(
        col_a="order_date_month",
        confidence=40.0,
        suppressed_by_plan=True,
        plan_penalty_reason="plan_ignore_column",
    )
    profile = _profile([_risk("date_part_artifacts", ["order_date_month"])], ["order_date_month"])

    result = apply_pre_analysis_profile_hygiene([ins], profile, enabled=True)

    assert result[0]["suppressed_by_plan"] is True
    assert result[0]["plan_penalty_reason"] == "plan_ignore_column"
    assert result[0]["suppressed_by_profile"] is True
    assert result[0]["profile_penalty_reason"] == "profile_date_part_artifact"
    assert result[0]["confidence"] == pytest.approx(40.0 * 0.35)


# ── Empty inputs ──────────────────────────────────────────────────────────────

def test_empty_insight_list_returns_empty():
    profile = _profile([_risk("date_part_artifacts", ["col_x"])], ["col_x"])
    result = apply_pre_analysis_profile_hygiene([], profile, enabled=True)
    assert result == []


def test_no_risks_returns_unchanged_insights():
    ins = _insight(col_a="revenue", confidence=80.0)
    profile = _profile([], ["revenue"])

    result = apply_pre_analysis_profile_hygiene([ins], profile, enabled=True)

    assert result[0]["confidence"] == 80.0
    assert "suppressed_by_profile" not in result[0]
