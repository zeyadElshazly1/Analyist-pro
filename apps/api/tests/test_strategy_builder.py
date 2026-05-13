"""
90F — Unit tests for the analysis strategy builder, risk detector,
      and hypothesis planner.
"""
from __future__ import annotations

import pytest

from app.schemas.pre_analysis import ColumnSemanticRole, DatasetFingerprint
from app.services.analysis.strategy_builder import (
    build_analysis_strategy,
    build_hypothesis_plan,
    detect_analysis_risks,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _fp(**kwargs) -> DatasetFingerprint:
    defaults = {"row_count": 200, "column_count": 6, "dataset_shape": "snapshot"}
    defaults.update(kwargs)
    return DatasetFingerprint(**defaults)


def _role(
    name: str,
    primary: str = "dimension",
    confidence: float = 0.7,
    cardinality: int = 5,
    missing_rate: float = 0.0,
    notes: str | None = None,
) -> ColumnSemanticRole:
    return ColumnSemanticRole(
        column_name=name,
        primary_role=primary,
        role_confidence=confidence,
        cardinality=cardinality,
        missing_rate=missing_rate,
        notes=notes,
    )


def _metric(name: str, card: int = 200) -> ColumnSemanticRole:
    return _role(name, primary="metric", cardinality=card)


def _currency(name: str) -> ColumnSemanticRole:
    return _role(name, primary="currency_amount")


def _rate(name: str) -> ColumnSemanticRole:
    return _role(name, primary="rate_percentage")


def _dim(name: str, card: int = 5) -> ColumnSemanticRole:
    return _role(name, primary="dimension", cardinality=card)


def _time(name: str = "date") -> ColumnSemanticRole:
    return _role(name, primary="time")


def _target(name: str) -> ColumnSemanticRole:
    return _role(name, primary="target")


def _text(name: str) -> ColumnSemanticRole:
    return _role(name, primary="free_text")


def _entity(name: str, card: int = 200) -> ColumnSemanticRole:
    return _role(name, primary="entity_id", cardinality=card)


def _tx(name: str, card: int = 200) -> ColumnSemanticRole:
    return _role(name, primary="transaction_id", cardinality=card)


def _helper(name: str, notes: str = "Possible date-part extraction artefact.") -> ColumnSemanticRole:
    return _role(name, primary="helper_artifact", notes=notes)


def _leakage(name: str, conf: float = 0.7) -> ColumnSemanticRole:
    return _role(name, primary="leakage_candidate", confidence=conf)


def _geo(name: str, card: int = 5) -> ColumnSemanticRole:
    return _role(name, primary="geographic", cardinality=card)


def _bool_flag(name: str) -> ColumnSemanticRole:
    return _role(name, primary="boolean_flag")


# ── build_analysis_strategy ───────────────────────────────────────────────────

class TestBuildAnalysisStrategy:
    def test_includes_trend_when_time_and_metric_exist(self):
        fp = _fp()
        roles = [_time(), _metric("revenue")]
        s = build_analysis_strategy(fp, roles, "order")
        assert "trend_analysis" in s.recommended_analysis_types

    def test_includes_segment_comparison_when_dimension_and_metric(self):
        fp = _fp()
        roles = [_dim("region"), _metric("revenue")]
        s = build_analysis_strategy(fp, roles, "order")
        assert "segment_comparison" in s.recommended_analysis_types

    def test_includes_correlation_when_two_or_more_metrics(self):
        fp = _fp()
        roles = [_metric("revenue"), _metric("units"), _dim("region")]
        s = build_analysis_strategy(fp, roles, "order")
        assert "correlation_analysis" in s.recommended_analysis_types

    def test_includes_anomaly_when_metric_and_rows_gte_20(self):
        fp = _fp(row_count=50)
        roles = [_metric("score")]
        s = build_analysis_strategy(fp, roles, "unknown")
        assert "anomaly_detection" in s.recommended_analysis_types

    def test_does_not_include_anomaly_when_row_count_below_20(self):
        fp = _fp(row_count=10)
        roles = [_metric("score")]
        s = build_analysis_strategy(fp, roles, "unknown")
        assert "anomaly_detection" not in s.recommended_analysis_types

    def test_includes_missingness_when_missing_rate_nonzero(self):
        fp = _fp(overall_missing_rate=0.1)
        roles = [_metric("revenue")]
        s = build_analysis_strategy(fp, roles, "order")
        assert "missingness_analysis" in s.recommended_analysis_types

    def test_no_missingness_when_rate_is_zero(self):
        fp = _fp(overall_missing_rate=0.0)
        roles = [_metric("revenue")]
        s = build_analysis_strategy(fp, roles, "order")
        assert "missingness_analysis" not in s.recommended_analysis_types

    def test_includes_target_analysis_when_target_exists(self):
        fp = _fp()
        roles = [_target("churn"), _metric("revenue")]
        s = build_analysis_strategy(fp, roles, "customer")
        assert "target_analysis" in s.recommended_analysis_types

    def test_includes_text_review_when_free_text_exists(self):
        fp = _fp()
        roles = [_text("notes"), _metric("score")]
        s = build_analysis_strategy(fp, roles, "customer")
        assert "text_review" in s.recommended_analysis_types

    def test_deprioritises_trend_when_no_time(self):
        fp = _fp()
        roles = [_metric("revenue"), _dim("region")]
        s = build_analysis_strategy(fp, roles, "order")
        assert "trend_analysis" in s.deprioritised_analysis_types

    def test_deprioritises_segment_when_no_dimension(self):
        fp = _fp()
        roles = [_metric("revenue"), _metric("units")]
        s = build_analysis_strategy(fp, roles, "order")
        assert "segment_comparison" in s.deprioritised_analysis_types

    def test_deprioritises_correlation_when_fewer_than_two_metrics(self):
        fp = _fp()
        roles = [_metric("revenue"), _dim("region")]
        s = build_analysis_strategy(fp, roles, "order")
        assert "correlation_analysis" in s.deprioritised_analysis_types

    def test_deprioritises_anomaly_when_row_count_below_20(self):
        fp = _fp(row_count=10)
        roles = [_metric("score")]
        s = build_analysis_strategy(fp, roles, "unknown")
        assert "anomaly_detection" in s.deprioritised_analysis_types

    def test_deprioritises_target_when_no_target_col(self):
        fp = _fp()
        roles = [_metric("revenue"), _dim("region")]
        s = build_analysis_strategy(fp, roles, "order")
        assert "target_analysis" in s.deprioritised_analysis_types

    def test_deprioritises_text_review_when_no_free_text(self):
        fp = _fp()
        roles = [_metric("revenue")]
        s = build_analysis_strategy(fp, roles, "order")
        assert "text_review" in s.deprioritised_analysis_types

    def test_chart_families_include_line_for_trend(self):
        fp = _fp()
        roles = [_time(), _metric("revenue")]
        s = build_analysis_strategy(fp, roles, "order")
        assert "line" in s.recommended_chart_families

    def test_chart_families_include_bar_for_segment(self):
        fp = _fp()
        roles = [_dim("region"), _metric("revenue")]
        s = build_analysis_strategy(fp, roles, "order")
        assert "bar" in s.recommended_chart_families

    def test_chart_families_include_scatter_for_correlation(self):
        fp = _fp()
        roles = [_metric("revenue"), _metric("units"), _dim("region")]
        s = build_analysis_strategy(fp, roles, "order")
        assert "scatter" in s.recommended_chart_families

    def test_chart_families_include_histogram_for_distribution(self):
        fp = _fp()
        roles = [_metric("score")]
        s = build_analysis_strategy(fp, roles, "unknown")
        assert "histogram" in s.recommended_chart_families

    def test_chart_families_include_table_for_text_review(self):
        fp = _fp()
        roles = [_text("notes"), _metric("score")]
        s = build_analysis_strategy(fp, roles, "customer")
        assert "table" in s.recommended_chart_families

    def test_recommended_metric_columns_capped_at_8(self):
        fp = _fp(column_count=15)
        roles = [_metric(f"m{i}") for i in range(12)]
        s = build_analysis_strategy(fp, roles, "unknown")
        assert len(s.recommended_metric_columns) <= 8

    def test_recommended_dimension_columns_capped_at_8(self):
        fp = _fp(column_count=15)
        roles = [_dim(f"d{i}") for i in range(12)]
        s = build_analysis_strategy(fp, roles, "unknown")
        assert len(s.recommended_dimension_columns) <= 8

    def test_recommended_time_columns_capped_at_3(self):
        fp = _fp(column_count=10)
        roles = [_time(f"ts_{i}") for i in range(5)]
        s = build_analysis_strategy(fp, roles, "time_period")
        assert len(s.recommended_time_columns) <= 3

    def test_recommended_columns_preserve_original_order(self):
        fp = _fp()
        roles = [_metric("revenue"), _dim("region"), _metric("units"), _dim("tier")]
        s = build_analysis_strategy(fp, roles, "order")
        assert s.recommended_metric_columns == ["revenue", "units"]
        assert s.recommended_dimension_columns == ["region", "tier"]

    def test_empty_roles_returns_empty_strategy(self):
        fp = _fp(row_count=0, column_count=0)
        s = build_analysis_strategy(fp, [], "unknown")
        assert s.recommended_analysis_types == []
        assert s.recommended_metric_columns == []

    def test_target_analysis_is_first_when_target_exists(self):
        fp = _fp()
        roles = [_target("churn"), _time(), _metric("revenue"), _dim("region")]
        s = build_analysis_strategy(fp, roles, "customer")
        assert s.recommended_analysis_types[0] == "target_analysis"


# ── detect_analysis_risks ─────────────────────────────────────────────────────

class TestDetectAnalysisRisks:
    def test_detects_too_many_id_columns(self):
        # 3 of 4 columns are IDs → 75% > 20%
        fp = _fp(column_count=4)
        roles = [_entity("cust_id"), _tx("order_id"), _entity("prod_id"), _metric("amount")]
        risks = detect_analysis_risks(fp, roles)
        names = [r.risk_name for r in risks]
        assert "too_many_id_columns" in names

    def test_does_not_flag_too_many_ids_when_below_threshold(self):
        # 1 of 5 IDs → 20% — not > 20%
        fp = _fp(column_count=5)
        roles = [_entity("cust_id"), _metric("a"), _metric("b"), _dim("c"), _dim("d")]
        risks = detect_analysis_risks(fp, roles)
        names = [r.risk_name for r in risks]
        assert "too_many_id_columns" not in names

    def test_detects_sparse_columns(self):
        fp = _fp()
        roles = [
            _role("notes", missing_rate=0.8),
            _metric("revenue"),
        ]
        risks = detect_analysis_risks(fp, roles)
        names = [r.risk_name for r in risks]
        assert "sparse_columns" in names
        r = next(r for r in risks if r.risk_name == "sparse_columns")
        assert "notes" in r.affected_columns

    def test_does_not_flag_sparse_when_under_threshold(self):
        fp = _fp()
        roles = [_role("notes", missing_rate=0.59), _metric("revenue")]
        risks = detect_analysis_risks(fp, roles)
        assert "sparse_columns" not in [r.risk_name for r in risks]

    def test_detects_date_part_artifacts(self):
        fp = _fp()
        roles = [
            _helper("signup_month"),
            _metric("revenue"),
        ]
        risks = detect_analysis_risks(fp, roles)
        assert "date_part_artifacts" in [r.risk_name for r in risks]

    def test_does_not_flag_date_part_for_non_helper(self):
        fp = _fp()
        roles = [_metric("revenue"), _dim("region")]
        risks = detect_analysis_risks(fp, roles)
        assert "date_part_artifacts" not in [r.risk_name for r in risks]

    def test_detects_possible_leakage(self):
        fp = _fp()
        roles = [_leakage("post_event"), _target("churn"), _metric("score")]
        risks = detect_analysis_risks(fp, roles)
        names = [r.risk_name for r in risks]
        assert "possible_leakage" in names

    def test_no_possible_leakage_without_target(self):
        fp = _fp()
        roles = [_leakage("post_event"), _metric("revenue")]
        risks = detect_analysis_risks(fp, roles)
        assert "possible_leakage" not in [r.risk_name for r in risks]

    def test_detects_very_small_sample_and_not_small_sample(self):
        fp = _fp(row_count=15)
        roles = [_metric("x")]
        risks = detect_analysis_risks(fp, roles)
        names = [r.risk_name for r in risks]
        assert "very_small_sample" in names
        assert "small_sample" not in names

    def test_detects_small_sample_for_30_to_99_rows(self):
        fp = _fp(row_count=50)
        roles = [_metric("x")]
        risks = detect_analysis_risks(fp, roles)
        names = [r.risk_name for r in risks]
        assert "small_sample" in names
        assert "very_small_sample" not in names

    def test_no_sample_risk_for_large_dataset(self):
        fp = _fp(row_count=500)
        roles = [_metric("x")]
        risks = detect_analysis_risks(fp, roles)
        names = [r.risk_name for r in risks]
        assert "small_sample" not in names
        assert "very_small_sample" not in names

    def test_detects_high_cardinality_dimensions(self):
        # 200 row dataset, threshold = max(50, 200*0.5) = 100
        fp = _fp(row_count=200)
        roles = [_geo("city", card=150), _metric("revenue")]
        risks = detect_analysis_risks(fp, roles)
        names = [r.risk_name for r in risks]
        assert "high_cardinality_dimensions" in names

    def test_no_high_cardinality_for_low_card_dim(self):
        fp = _fp(row_count=200)
        roles = [_dim("region", card=4), _metric("revenue")]
        risks = detect_analysis_risks(fp, roles)
        assert "high_cardinality_dimensions" not in [r.risk_name for r in risks]

    def test_detects_constant_columns(self):
        fp = _fp()
        roles = [_role("source", cardinality=1), _metric("revenue")]
        risks = detect_analysis_risks(fp, roles)
        assert "constant_columns" in [r.risk_name for r in risks]

    def test_no_constant_columns_when_all_have_multiple_values(self):
        fp = _fp()
        roles = [_dim("region", card=4), _metric("revenue")]
        risks = detect_analysis_risks(fp, roles)
        assert "constant_columns" not in [r.risk_name for r in risks]

    def test_detects_mixed_grain(self):
        fp = _fp(dataset_shape="snapshot")
        roles = [_tx("order_id"), _entity("customer_id"), _metric("amount")]
        risks = detect_analysis_risks(fp, roles)
        assert "mixed_grain" in [r.risk_name for r in risks]

    def test_no_mixed_grain_for_non_snapshot_shape(self):
        fp = _fp(dataset_shape="transactional")
        roles = [_tx("order_id"), _entity("customer_id"), _metric("amount")]
        risks = detect_analysis_risks(fp, roles)
        assert "mixed_grain" not in [r.risk_name for r in risks]

    def test_no_mixed_grain_without_both_id_types(self):
        fp = _fp(dataset_shape="snapshot")
        roles = [_tx("order_id"), _metric("amount")]
        risks = detect_analysis_risks(fp, roles)
        assert "mixed_grain" not in [r.risk_name for r in risks]

    def test_risk_objects_are_valid_analysis_risk_models(self):
        from app.schemas.pre_analysis import AnalysisRisk
        fp = _fp(row_count=10)
        roles = [_metric("x"), _role("sparse", missing_rate=0.9)]
        risks = detect_analysis_risks(fp, roles)
        assert all(isinstance(r, AnalysisRisk) for r in risks)

    def test_returns_empty_list_for_clean_dataset(self):
        fp = _fp(row_count=500, column_count=5)
        roles = [_metric("a"), _metric("b"), _dim("c"), _dim("d"), _time()]
        risks = detect_analysis_risks(fp, roles)
        # No sample risks, no ID risks, no leakage, no sparse, no constant → empty
        assert risks == []


# ── build_hypothesis_plan ─────────────────────────────────────────────────────

class TestBuildHypothesisPlan:
    def test_produces_metric_dimension_hypothesis(self):
        fp = _fp()
        roles = [_metric("revenue"), _dim("region")]
        hp = build_hypothesis_plan(fp, roles, "order")
        assert any("metrics vary" in h for h in hp.hypotheses)

    def test_produces_trend_hypothesis(self):
        fp = _fp()
        roles = [_metric("revenue"), _time()]
        hp = build_hypothesis_plan(fp, roles, "time_period")
        assert any("trend" in h.lower() for h in hp.hypotheses)

    def test_produces_missingness_hypothesis(self):
        fp = _fp(overall_missing_rate=0.15)
        roles = [_metric("revenue")]
        hp = build_hypothesis_plan(fp, roles, "order")
        assert any("missingness" in h.lower() for h in hp.hypotheses)

    def test_no_missingness_hypothesis_when_rate_zero(self):
        fp = _fp(overall_missing_rate=0.0)
        roles = [_metric("revenue")]
        hp = build_hypothesis_plan(fp, roles, "order")
        assert not any("missingness" in h.lower() for h in hp.hypotheses)

    def test_produces_id_helper_warning_hypothesis(self):
        fp = _fp()
        roles = [_entity("customer_id"), _metric("revenue")]
        hp = build_hypothesis_plan(fp, roles, "customer")
        assert any("id" in h.lower() or "helper" in h.lower() for h in hp.hypotheses)

    def test_produces_correlation_hypothesis_for_two_metrics(self):
        fp = _fp()
        roles = [_metric("revenue"), _metric("units"), _dim("region")]
        hp = build_hypothesis_plan(fp, roles, "order")
        assert any("correlation" in h.lower() for h in hp.hypotheses)

    def test_no_correlation_hypothesis_for_one_metric(self):
        fp = _fp()
        roles = [_metric("revenue"), _dim("region")]
        hp = build_hypothesis_plan(fp, roles, "order")
        assert not any("correlation" in h.lower() for h in hp.hypotheses)

    def test_produces_anomaly_hypothesis_for_large_dataset(self):
        fp = _fp(row_count=100)
        roles = [_metric("revenue")]
        hp = build_hypothesis_plan(fp, roles, "order")
        assert any("anomal" in h.lower() for h in hp.hypotheses)

    def test_no_anomaly_hypothesis_for_tiny_dataset(self):
        fp = _fp(row_count=5)
        roles = [_metric("revenue")]
        hp = build_hypothesis_plan(fp, roles, "order")
        assert not any("anomal" in h.lower() for h in hp.hypotheses)

    def test_produces_target_hypothesis(self):
        fp = _fp()
        roles = [_target("churn"), _metric("spend")]
        hp = build_hypothesis_plan(fp, roles, "customer")
        assert any("target" in h.lower() for h in hp.hypotheses)

    def test_produces_free_text_hypothesis(self):
        fp = _fp()
        roles = [_text("notes"), _metric("score")]
        hp = build_hypothesis_plan(fp, roles, "customer")
        assert any("text" in h.lower() or "free" in h.lower() for h in hp.hypotheses)

    def test_fallback_hypothesis_always_present(self):
        fp = _fp(row_count=500, column_count=5)
        roles = [_metric("a"), _metric("b")]
        hp = build_hypothesis_plan(fp, roles, "unknown")
        assert any("distributions" in h.lower() for h in hp.hypotheses)

    def test_max_8_hypotheses(self):
        fp = _fp(overall_missing_rate=0.1, row_count=100)
        roles = [
            _target("churn"),
            _metric("rev"),
            _metric("units"),
            _metric("margin"),
            _dim("region"),
            _time(),
            _entity("cust_id"),
            _text("notes"),
        ]
        hp = build_hypothesis_plan(fp, roles, "customer")
        assert len(hp.hypotheses) <= 8

    def test_does_not_mutate_column_roles(self):
        fp = _fp()
        roles = [_metric("revenue"), _dim("region")]
        original = [ColumnSemanticRole(**r.model_dump()) for r in roles]
        build_hypothesis_plan(fp, roles, "order")
        for before, after in zip(original, roles):
            assert before.model_dump() == after.model_dump()

    def test_returns_hypothesis_plan_instance(self):
        from app.schemas.pre_analysis import HypothesisPlan
        fp = _fp()
        roles = [_metric("x")]
        hp = build_hypothesis_plan(fp, roles, "unknown")
        assert isinstance(hp, HypothesisPlan)
