"""
90B — Schema tests for Pre-Analysis Intelligence Layer V2 models.
"""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas.pre_analysis import (
    AnalysisRisk,
    AnalysisStrategy,
    ColumnSemanticRole,
    DatasetFingerprint,
    HypothesisPlan,
    PreAnalysisProfile,
)

# ── DatasetFingerprint ────────────────────────────────────────────────────────


def _fp(**kwargs) -> DatasetFingerprint:
    defaults = {"row_count": 100, "column_count": 5, "dataset_shape": "snapshot"}
    defaults.update(kwargs)
    return DatasetFingerprint(**defaults)


def test_dataset_fingerprint_clamps_missing_rate_above_1():
    fp = _fp(overall_missing_rate=1.5)
    assert fp.overall_missing_rate == 1.0


def test_dataset_fingerprint_clamps_missing_rate_below_0():
    fp = _fp(overall_missing_rate=-0.3)
    assert fp.overall_missing_rate == 0.0


def test_dataset_fingerprint_clamps_data_density_above_1():
    fp = _fp(overall_data_density=2.0)
    assert fp.overall_data_density == 1.0


def test_dataset_fingerprint_clamps_data_density_below_0():
    fp = _fp(overall_data_density=-1.0)
    assert fp.overall_data_density == 0.0


def test_dataset_fingerprint_accepts_valid_shape():
    for shape in [
        "transactional", "snapshot", "time_series", "event_log",
        "survey", "entity_table", "panel_data", "unknown",
    ]:
        fp = _fp(dataset_shape=shape)
        assert fp.dataset_shape == shape


def test_dataset_fingerprint_rejects_invalid_dataset_shape():
    with pytest.raises(ValidationError, match="dataset_shape"):
        _fp(dataset_shape="churn_model")


def test_dataset_fingerprint_rejects_negative_row_count():
    with pytest.raises(ValidationError):
        _fp(row_count=-1)


def test_dataset_fingerprint_rejects_negative_column_count():
    with pytest.raises(ValidationError):
        _fp(column_count=-1)


def test_dataset_fingerprint_rejects_negative_sub_counts():
    with pytest.raises(ValidationError):
        _fp(numeric_column_count=-5)


def test_dataset_fingerprint_defaults_are_safe():
    fp = DatasetFingerprint(row_count=0, column_count=0)
    assert fp.dataset_shape == "unknown"
    assert fp.overall_missing_rate == 0.0
    assert fp.overall_data_density == 1.0
    assert fp.duplicate_row_count == 0


# ── ColumnSemanticRole ────────────────────────────────────────────────────────


def _role(**kwargs) -> ColumnSemanticRole:
    defaults = {"column_name": "revenue", "primary_role": "metric"}
    defaults.update(kwargs)
    return ColumnSemanticRole(**defaults)


def test_column_semantic_role_clamps_role_confidence_above_1():
    r = _role(role_confidence=1.8)
    assert r.role_confidence == 1.0


def test_column_semantic_role_clamps_role_confidence_below_0():
    r = _role(role_confidence=-0.5)
    assert r.role_confidence == 0.0


def test_column_semantic_role_clamps_missing_rate_above_1():
    r = _role(missing_rate=2.0)
    assert r.missing_rate == 1.0


def test_column_semantic_role_clamps_missing_rate_below_0():
    r = _role(missing_rate=-0.1)
    assert r.missing_rate == 0.0


def test_column_semantic_role_rejects_empty_column_name():
    with pytest.raises(ValidationError, match="column_name"):
        _role(column_name="")


def test_column_semantic_role_rejects_whitespace_column_name():
    with pytest.raises(ValidationError, match="column_name"):
        _role(column_name="   ")


def test_column_semantic_role_rejects_invalid_primary_role():
    with pytest.raises(ValidationError, match="primary_role"):
        _role(primary_role="churn_flag")


def test_column_semantic_role_accepts_all_valid_primary_roles():
    for role in [
        "metric", "dimension", "time", "entity_id", "transaction_id",
        "target", "leakage_candidate", "helper_artifact", "free_text",
        "geographic", "currency_amount", "rate_percentage", "boolean_flag", "unknown",
    ]:
        r = _role(primary_role=role)
        assert r.primary_role == role


def test_column_semantic_role_rejects_negative_cardinality():
    with pytest.raises(ValidationError, match="cardinality"):
        _role(cardinality=-1)


def test_column_semantic_role_secondary_roles_default_empty():
    r = _role()
    assert r.secondary_roles == []


# ── AnalysisRisk ──────────────────────────────────────────────────────────────


def _risk(**kwargs) -> AnalysisRisk:
    defaults = {
        "risk_name": "sparse_columns",
        "severity": "medium",
        "description": "One or more columns exceed 60% missing rate.",
    }
    defaults.update(kwargs)
    return AnalysisRisk(**defaults)


def test_analysis_risk_accepts_valid_severities():
    for sev in ["low", "medium", "high"]:
        r = _risk(severity=sev)
        assert r.severity == sev


def test_analysis_risk_rejects_invalid_severity():
    with pytest.raises(ValidationError, match="severity"):
        _risk(severity="critical")


def test_analysis_risk_rejects_empty_risk_name():
    with pytest.raises(ValidationError, match="risk_name"):
        _risk(risk_name="")


def test_analysis_risk_rejects_whitespace_risk_name():
    with pytest.raises(ValidationError, match="risk_name"):
        _risk(risk_name="  ")


def test_analysis_risk_rejects_empty_description():
    with pytest.raises(ValidationError, match="description"):
        _risk(description="")


def test_analysis_risk_affected_columns_default_empty():
    r = _risk()
    assert r.affected_columns == []


# ── HypothesisPlan ────────────────────────────────────────────────────────────


def test_hypothesis_plan_strips_empty_strings():
    hp = HypothesisPlan(hypotheses=["", "Do metrics vary?", "  ", "Check trends."])
    assert hp.hypotheses == ["Do metrics vary?", "Check trends."]


def test_hypothesis_plan_default_empty():
    hp = HypothesisPlan()
    assert hp.hypotheses == []


# ── PreAnalysisProfile ────────────────────────────────────────────────────────


def _profile(**kwargs) -> PreAnalysisProfile:
    fp = DatasetFingerprint(row_count=100, column_count=5, dataset_shape="snapshot")
    defaults = {"fingerprint": fp, "generated_at": "2026-05-13T00:00:00Z"}
    defaults.update(kwargs)
    return PreAnalysisProfile(**defaults)


def test_pre_analysis_profile_clamps_grain_confidence_above_1():
    p = _profile(grain_confidence=1.5)
    assert p.grain_confidence == 1.0


def test_pre_analysis_profile_clamps_grain_confidence_below_0():
    p = _profile(grain_confidence=-0.2)
    assert p.grain_confidence == 0.0


def test_pre_analysis_profile_rejects_invalid_grain_label():
    with pytest.raises(ValidationError, match="grain_label"):
        _profile(grain_label="insurance_policy")


def test_pre_analysis_profile_accepts_all_valid_grain_labels():
    for label in [
        "customer", "order", "policy", "transaction", "event",
        "product", "employee", "time_period", "session", "survey_response", "unknown",
    ]:
        p = _profile(grain_label=label)
        assert p.grain_label == label


def test_pre_analysis_profile_rejects_empty_generated_at():
    with pytest.raises(ValidationError, match="generated_at"):
        _profile(generated_at="")


def test_pre_analysis_profile_rejects_whitespace_generated_at():
    with pytest.raises(ValidationError, match="generated_at"):
        _profile(generated_at="   ")


def test_pre_analysis_profile_rejects_empty_planner_version():
    with pytest.raises(ValidationError, match="planner_version"):
        _profile(planner_version="")


def test_pre_analysis_profile_model_dump_includes_all_blocks():
    p = _profile()
    d = p.model_dump()
    assert "fingerprint" in d
    assert "column_roles" in d
    assert "grain_label" in d
    assert "grain_confidence" in d
    assert "strategy" in d
    assert "risks" in d
    assert "hypothesis_plan" in d
    assert "generated_at" in d
    assert "planner_version" in d


def test_pre_analysis_profile_defaults_are_independent():
    fp = DatasetFingerprint(row_count=10, column_count=2, dataset_shape="snapshot")

    a = PreAnalysisProfile(fingerprint=fp, generated_at="2026-05-13T00:00:00Z")
    b = PreAnalysisProfile(fingerprint=fp, generated_at="2026-05-13T00:00:00Z")

    a.column_roles.append(
        ColumnSemanticRole(
            column_name="revenue",
            primary_role="metric",
            role_confidence=0.9,
        )
    )

    assert b.column_roles == []


def test_pre_analysis_profile_strategy_defaults_are_independent():
    fp = DatasetFingerprint(row_count=10, column_count=2, dataset_shape="snapshot")

    a = PreAnalysisProfile(fingerprint=fp, generated_at="2026-05-13T00:00:00Z")
    b = PreAnalysisProfile(fingerprint=fp, generated_at="2026-05-13T00:00:00Z")

    a.strategy.recommended_metric_columns.append("revenue")

    assert b.strategy.recommended_metric_columns == []


def test_pre_analysis_profile_risks_defaults_are_independent():
    fp = DatasetFingerprint(row_count=10, column_count=2, dataset_shape="snapshot")

    a = PreAnalysisProfile(fingerprint=fp, generated_at="2026-05-13T00:00:00Z")
    b = PreAnalysisProfile(fingerprint=fp, generated_at="2026-05-13T00:00:00Z")

    a.risks.append(
        AnalysisRisk(risk_name="sparse_columns", severity="low", description="x")
    )

    assert b.risks == []


def test_pre_analysis_profile_default_grain_label_is_unknown():
    p = _profile()
    assert p.grain_label == "unknown"


def test_pre_analysis_profile_default_planner_version():
    p = _profile()
    assert p.planner_version == "v2.0-deterministic"


# ── AnalysisStrategy ──────────────────────────────────────────────────────────


def test_analysis_strategy_all_fields_default_empty():
    s = AnalysisStrategy()
    assert s.recommended_analysis_types == []
    assert s.deprioritised_analysis_types == []
    assert s.recommended_metric_columns == []
    assert s.recommended_dimension_columns == []
    assert s.recommended_time_columns == []
    assert s.recommended_chart_families == []
