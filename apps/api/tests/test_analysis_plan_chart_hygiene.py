"""
86I — Analysis plan chart hygiene tests.

Verifies that apply_analysis_plan_chart_hygiene():
- Boosts charts whose columns are target_metrics or important_dimensions
- Penalises charts whose columns are all in columns_to_ignore
- Leaves charts unchanged when analysis_plan is None
- Leaves charts unchanged for generic / low-confidence plans
- Sorts output by score descending
- Does not mutate input charts
- Preserves real date trend charts
- Does not penalise finance metric columns as date-derived artifacts
"""
import pytest

from app.services.analysis.chart_plan_hygiene import apply_analysis_plan_chart_hygiene
from app.schemas.analysis_plan import AnalysisPlan


# ── Helpers ───────────────────────────────────────────────────────────────────

def _plan(**overrides) -> AnalysisPlan:
    base = dict(
        dataset_kind="insurance",
        confidence=0.82,
        business_context="Insurance portfolio",
        primary_entity="policy",
        target_metrics=["premium", "claim_amount"],
        important_dimensions=["coverage_type", "region"],
        time_columns=["effective_date"],
        columns_to_ignore=["policy_id", "customer_id"],
        recommended_charts=[],
        insight_priorities=["correlation"],
        analysis_warnings=[],
        report_template_hint="detailed_audit",
    )
    base.update(overrides)
    return AnalysisPlan(**base)


def _chart(x_label: str, y_label: str, score: float = 8.0, **extra) -> dict:
    return {
        "type": "bar",
        "title": f"{x_label} vs {y_label}",
        "x_key": "label",
        "y_key": "value",
        "x_label": x_label,
        "y_label": y_label,
        "data": [],
        "score": score,
        **extra,
    }


def _score(charts: list[dict], x_label: str) -> float:
    for c in charts:
        if c.get("x_label") == x_label:
            return float(c.get("score", 0))
    raise KeyError(f"chart not found: {x_label!r}")


def _boosted(c: dict) -> bool:
    return "plan_boost_reason" in c


def _penalised(c: dict) -> bool:
    return c.get("plan_penalty_reason") == "ignored_column"


# ── None plan / low-confidence plan — pass-through ───────────────────────────

class TestNoPlanPassthrough:
    def test_none_plan_returns_same_list(self):
        charts = [_chart("premium", "Count"), _chart("region", "Count")]
        result = apply_analysis_plan_chart_hygiene(charts, None)
        assert result == charts

    def test_none_plan_does_not_mutate(self):
        original = _chart("premium", "Count", score=8.0)
        apply_analysis_plan_chart_hygiene([original], None)
        assert "plan_boost_reason" not in original
        assert original["score"] == 8.0

    def test_low_confidence_plan_unchanged(self):
        plan = _plan(confidence=0.55, dataset_kind="generic")
        charts = [_chart("premium", "Count", score=8.0)]
        result = apply_analysis_plan_chart_hygiene(charts, plan)
        assert result[0]["score"] == 8.0
        assert "plan_boost_reason" not in result[0]


# ── Ignored-column penalty ────────────────────────────────────────────────────

class TestIgnoredColumnPenalty:
    def test_all_ignored_cols_penalised(self):
        plan = _plan()
        c = _chart("policy_id", "Count", score=8.0)
        result = apply_analysis_plan_chart_hygiene([c], plan)
        assert _penalised(result[0])
        assert result[0]["score"] < 8.0

    def test_penalty_multiplier_applied(self):
        plan = _plan()
        c = _chart("policy_id", "Count", score=8.0)
        result = apply_analysis_plan_chart_hygiene([c], plan)
        assert abs(result[0]["score"] - 8.0 * 0.40) < 1e-6

    def test_mixed_ignored_and_real_not_penalised(self):
        plan = _plan()
        c = _chart("policy_id", "premium", score=8.0)
        result = apply_analysis_plan_chart_hygiene([c], plan)
        assert not _penalised(result[0])

    def test_real_col_chart_not_penalised(self):
        plan = _plan()
        c = _chart("premium", "Count", score=8.0)
        result = apply_analysis_plan_chart_hygiene([c], plan)
        assert not _penalised(result[0])


# ── Target metric boost ───────────────────────────────────────────────────────

class TestTargetMetricBoost:
    def test_target_metric_chart_boosted(self):
        plan = _plan()
        c = _chart("premium", "Count", score=8.0)
        result = apply_analysis_plan_chart_hygiene([c], plan)
        assert _boosted(result[0])
        assert result[0]["score"] > 8.0

    def test_target_metric_boost_reason(self):
        plan = _plan()
        c = _chart("premium", "Count", score=8.0)
        result = apply_analysis_plan_chart_hygiene([c], plan)
        assert result[0]["plan_boost_reason"] == "target_metric"

    def test_second_target_metric_also_boosted(self):
        plan = _plan()
        c = _chart("claim_amount", "Count", score=8.0)
        result = apply_analysis_plan_chart_hygiene([c], plan)
        assert _boosted(result[0])


# ── Target × dimension boost ─────────────────────────────────────────────────

class TestTargetDimensionBoost:
    def test_target_x_dimension_highest_boost(self):
        plan = _plan()
        target_only = _chart("premium", "Count", score=8.0)
        target_dim  = _chart("coverage_type", "premium", score=8.0)

        result = apply_analysis_plan_chart_hygiene([target_only, target_dim], plan)
        # target × dimension should score higher than target-only
        target_dim_score  = _score(result, "coverage_type")
        target_only_score = _score(result, "premium")
        assert target_dim_score > target_only_score

    def test_target_dim_boost_reason(self):
        plan = _plan()
        c = _chart("region", "claim_amount", score=8.0)
        result = apply_analysis_plan_chart_hygiene([c], plan)
        assert result[0]["plan_boost_reason"] == "target_metric_x_dimension"


# ── Target × time-series boost ────────────────────────────────────────────────

class TestTargetTimeTrendBoost:
    def test_target_trend_chart_boosted(self):
        plan = _plan()
        # timeseries chart: x_label=date_col, y_label=num_col
        c = _chart("effective_date", "premium", score=10.0)
        result = apply_analysis_plan_chart_hygiene([c], plan)
        assert _boosted(result[0])
        assert result[0]["plan_boost_reason"] == "target_metric_trend"
        assert result[0]["score"] > 10.0

    def test_real_date_trend_preserved_not_penalised(self):
        plan = _plan()
        c = _chart("effective_date", "premium", score=10.0)
        result = apply_analysis_plan_chart_hygiene([c], plan)
        assert not _penalised(result[0])


# ── Dimension-only boost ──────────────────────────────────────────────────────

class TestDimensionBoost:
    def test_dimension_chart_gets_dim_boost(self):
        plan = _plan()
        c = _chart("region", "Count", score=6.0)
        result = apply_analysis_plan_chart_hygiene([c], plan)
        assert _boosted(result[0])
        assert result[0]["plan_boost_reason"] == "important_dimension"

    def test_dimension_boost_less_than_target_boost(self):
        plan = _plan()
        dim_chart    = _chart("region",  "Count", score=6.0)
        target_chart = _chart("premium", "Count", score=6.0)
        result = apply_analysis_plan_chart_hygiene([dim_chart, target_chart], plan)
        dim_score    = _score(result, "region")
        target_score = _score(result, "premium")
        assert target_score > dim_score


# ── Finance metric columns — not penalised as date artifacts ──────────────────

class TestFinanceMetricColumnsNotPenalised:
    def test_daylow_not_penalised(self):
        plan = _plan(
            dataset_kind="finance",
            target_metrics=["close", "volume"],
            time_columns=["price_date"],
            columns_to_ignore=["ticker"],
        )
        c = _chart("dayLow", "dayHigh", score=8.0)
        result = apply_analysis_plan_chart_hygiene([c], plan)
        assert not _penalised(result[0])

    def test_finance_metric_not_boosted_as_time(self):
        plan = _plan(
            dataset_kind="finance",
            target_metrics=["close"],
            time_columns=["price_date"],
            columns_to_ignore=["ticker"],
        )
        c = _chart("dayLow", "close", score=8.0)
        result = apply_analysis_plan_chart_hygiene([c], plan)
        # close is target, dayLow is not in time_columns → reason is target_metric not trend
        assert result[0].get("plan_boost_reason") in ("target_metric", None)
        assert result[0].get("plan_boost_reason") != "target_metric_trend"


# ── Output ordering ───────────────────────────────────────────────────────────

class TestOutputOrdering:
    def test_output_sorted_by_score_descending(self):
        plan = _plan()
        charts = [
            _chart("policy_id", "Count", score=8.0),   # will be penalised
            _chart("premium", "Count", score=8.0),      # will be boosted
            _chart("region", "Count", score=6.0),       # dim boost
        ]
        result = apply_analysis_plan_chart_hygiene(charts, plan)
        scores = [c["score"] for c in result]
        assert scores == sorted(scores, reverse=True)

    def test_target_dim_chart_ranks_above_histogram(self):
        plan = _plan()
        histogram  = _chart("vehicle_age", "Count", score=8.0)   # generic numeric
        target_dim = _chart("coverage_type", "premium", score=8.0)  # target × dim
        result = apply_analysis_plan_chart_hygiene([histogram, target_dim], plan)
        assert result[0]["x_label"] == "coverage_type"


# ── No mutation ───────────────────────────────────────────────────────────────

class TestNoMutation:
    def test_input_charts_not_mutated(self):
        plan = _plan()
        original = _chart("premium", "Count", score=8.0)
        apply_analysis_plan_chart_hygiene([original], plan)
        assert "plan_boost_reason" not in original
        assert original["score"] == 8.0

    def test_penalised_input_not_mutated(self):
        plan = _plan()
        original = _chart("policy_id", "Count", score=8.0)
        apply_analysis_plan_chart_hygiene([original], plan)
        assert "plan_penalty_reason" not in original
        assert original["score"] == 8.0
