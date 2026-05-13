"""
90L — Unit tests for the shadow-mode profile hygiene impact evaluator.
"""
from __future__ import annotations

import pytest

from app.services.analysis.profile_hygiene_shadow import evaluate_profile_hygiene_shadow


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _insight(
    confidence: float = 80.0,
    category: str = "trend",
    title: str = "Test insight",
    col_a: str | None = None,
    **extra,
) -> dict:
    ins: dict = {"confidence": confidence, "category": category, "title": title}
    if col_a is not None:
        ins["col_a"] = col_a
    ins.update(extra)
    return ins


def _profile(risks: list[dict], column_names: list[str] | None = None) -> dict:
    roles = [{"column_name": c} for c in (column_names or [])]
    return {"risks": risks, "column_roles": roles}


def _risk(name: str, affected: list[str], severity: str = "medium") -> dict:
    return {"risk_name": name, "severity": severity, "affected_columns": affected}


# ── Guard conditions ──────────────────────────────────────────────────────────

def test_missing_profile_returns_evaluated_false():
    result = evaluate_profile_hygiene_shadow([_insight()], None)
    assert result["evaluated"] is False
    assert result["reason"] == "missing_pre_analysis_profile"
    assert result["input_count"] == 1


def test_empty_dict_profile_returns_evaluated_false():
    result = evaluate_profile_hygiene_shadow([_insight()], {})
    assert result["evaluated"] is False
    assert result["reason"] == "missing_pre_analysis_profile"


def test_empty_insights_returns_evaluated_false():
    profile = _profile([], [])
    result = evaluate_profile_hygiene_shadow([], profile)
    assert result["evaluated"] is False
    assert result["reason"] == "no_insights"
    assert result["input_count"] == 0


# ── No-penalty baseline ───────────────────────────────────────────────────────

def test_no_penalties_returns_evaluated_true_zero_counts():
    ins = _insight(col_a="revenue", confidence=80.0)
    profile = _profile([], ["revenue"])

    result = evaluate_profile_hygiene_shadow([ins], profile)

    assert result["evaluated"] is True
    assert result["input_count"] == 1
    assert result["profile_penalized_count"] == 0
    assert result["confidence_deltas"] == []
    assert all(v == 0 for v in result["profile_penalty_reasons"].values())


# ── Individual reason counting ────────────────────────────────────────────────

def test_date_part_artifact_is_counted():
    ins = _insight(col_a="order_date_month", confidence=80.0, category="trend")
    profile = _profile(
        [_risk("date_part_artifacts", ["order_date_month"])],
        ["order_date_month"],
    )

    result = evaluate_profile_hygiene_shadow([ins], profile)

    assert result["evaluated"] is True
    assert result["profile_penalized_count"] == 1
    assert result["profile_penalty_reasons"]["profile_date_part_artifact"] == 1
    assert result["confidence_deltas"][0]["reason"] == "profile_date_part_artifact"


def test_high_cardinality_dimension_is_counted():
    ins = _insight(col_a="city", confidence=70.0, category="segment")
    profile = _profile(
        [_risk("high_cardinality_dimensions", ["city"])],
        ["city"],
    )

    result = evaluate_profile_hygiene_shadow([ins], profile)

    assert result["profile_penalized_count"] == 1
    assert result["profile_penalty_reasons"]["profile_high_cardinality_dimension"] == 1


def test_leakage_candidate_is_counted():
    ins = _insight(col_a="closed_date", confidence=90.0)
    profile = _profile(
        [_risk("possible_leakage", ["closed_date"])],
        ["closed_date"],
    )

    result = evaluate_profile_hygiene_shadow([ins], profile)

    assert result["profile_penalized_count"] == 1
    assert result["profile_penalty_reasons"]["profile_leakage_candidate"] == 1


def test_target_leakage_risk_counted_as_leakage_candidate():
    ins = _insight(col_a="model_score", confidence=85.0)
    profile = _profile(
        [_risk("target_leakage_risk", ["model_score"], severity="high")],
        ["model_score"],
    )

    result = evaluate_profile_hygiene_shadow([ins], profile)

    assert result["profile_penalized_count"] == 1
    assert result["profile_penalty_reasons"]["profile_leakage_candidate"] == 1


def test_constant_column_is_counted():
    ins = _insight(col_a="data_source", confidence=70.0)
    profile = _profile(
        [_risk("constant_columns", ["data_source"])],
        ["data_source"],
    )

    result = evaluate_profile_hygiene_shadow([ins], profile)

    assert result["profile_penalized_count"] == 1
    assert result["profile_penalty_reasons"]["profile_constant_column"] == 1


# ── Multiple reasons ──────────────────────────────────────────────────────────

def test_multiple_reasons_counted_separately():
    ins_artifact = _insight(col_a="order_date_month", confidence=80.0, title="Artifact insight")
    ins_segment  = _insight(col_a="city", confidence=70.0, category="segment", title="Segment insight")
    ins_clean    = _insight(col_a="revenue", confidence=90.0, title="Clean insight")

    profile = _profile(
        [
            _risk("date_part_artifacts",      ["order_date_month"]),
            _risk("high_cardinality_dimensions", ["city"]),
        ],
        ["order_date_month", "city", "revenue"],
    )

    result = evaluate_profile_hygiene_shadow(
        [ins_artifact, ins_segment, ins_clean], profile
    )

    assert result["input_count"] == 3
    assert result["profile_penalized_count"] == 2
    assert result["profile_penalty_reasons"]["profile_date_part_artifact"] == 1
    assert result["profile_penalty_reasons"]["profile_high_cardinality_dimension"] == 1
    assert result["profile_penalty_reasons"]["profile_leakage_candidate"] == 0
    assert result["profile_penalty_reasons"]["profile_constant_column"] == 0
    assert len(result["confidence_deltas"]) == 2


# ── confidence_deltas shape ───────────────────────────────────────────────────

def test_confidence_deltas_include_required_fields():
    ins = _insight(col_a="order_date_month", confidence=80.0, title="Trend in month", category="trend")
    profile = _profile(
        [_risk("date_part_artifacts", ["order_date_month"])],
        ["order_date_month"],
    )

    result = evaluate_profile_hygiene_shadow([ins], profile)
    delta = result["confidence_deltas"][0]

    assert delta["index"] == 0
    assert delta["before_confidence"] == pytest.approx(80.0)
    assert delta["after_confidence"] == pytest.approx(80.0 * 0.35)
    assert delta["reason"] == "profile_date_part_artifact"
    assert delta["title"] == "Trend in month"
    assert delta["category"] == "trend"


def test_confidence_deltas_index_matches_position_in_input():
    ins0 = _insight(col_a="revenue",           confidence=90.0)
    ins1 = _insight(col_a="order_date_month",  confidence=80.0)
    ins2 = _insight(col_a="region",            confidence=70.0)

    profile = _profile(
        [_risk("date_part_artifacts", ["order_date_month"])],
        ["revenue", "order_date_month", "region"],
    )

    result = evaluate_profile_hygiene_shadow([ins0, ins1, ins2], profile)

    assert len(result["confidence_deltas"]) == 1
    assert result["confidence_deltas"][0]["index"] == 1   # ins1 is at position 1


# ── Non-mutation ──────────────────────────────────────────────────────────────

def test_does_not_mutate_input_insights():
    ins = _insight(col_a="order_date_month", confidence=80.0)
    original = dict(ins)
    profile = _profile(
        [_risk("date_part_artifacts", ["order_date_month"])],
        ["order_date_month"],
    )

    evaluate_profile_hygiene_shadow([ins], profile)

    assert ins == original, "Input insight dict was mutated"


def test_does_not_mutate_input_list():
    ins = _insight(col_a="order_date_month", confidence=80.0)
    insights = [ins]
    profile = _profile(
        [_risk("date_part_artifacts", ["order_date_month"])],
        ["order_date_month"],
    )

    evaluate_profile_hygiene_shadow(insights, profile)

    assert len(insights) == 1
    assert insights[0] is ins


# ── No rerank / no count change ───────────────────────────────────────────────

def test_does_not_change_insight_count():
    insights = [
        _insight(col_a="order_date_month", confidence=80.0),
        _insight(col_a="revenue",          confidence=90.0),
        _insight(col_a="region",           confidence=70.0),
    ]
    profile = _profile(
        [_risk("date_part_artifacts", ["order_date_month"])],
        ["order_date_month", "revenue", "region"],
    )

    result = evaluate_profile_hygiene_shadow(insights, profile)

    # input_count always equals len of original list — no capping
    assert result["input_count"] == 3


def test_all_penalty_reason_keys_present_even_when_zero():
    ins = _insight(col_a="revenue", confidence=80.0)
    profile = _profile([], ["revenue"])

    result = evaluate_profile_hygiene_shadow([ins], profile)

    expected_keys = {
        "profile_date_part_artifact",
        "profile_high_cardinality_dimension",
        "profile_leakage_candidate",
        "profile_constant_column",
    }
    assert set(result["profile_penalty_reasons"].keys()) == expected_keys
