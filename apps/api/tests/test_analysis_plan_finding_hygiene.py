"""
86E — Analysis plan finding hygiene tests.

Verifies that apply_analysis_plan_hygiene():
- Penalises findings using ignored (ID/artifact) columns
- Penalises date-part derived feature findings
- Preserves genuine time-series trend findings
- Preserves findings on target_metrics and important_dimensions
- Is safe when analysis_plan is None
"""
import pytest

from app.services.analysis.analysis_plan_hygiene import apply_analysis_plan_hygiene
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
        columns_to_ignore=["policy_id", "customer_id", "avg_S", "Unnamed: 14"],
        recommended_charts=[],
        insight_priorities=["correlation", "segment_comparison"],
        analysis_warnings=[],
        report_template_hint="detailed_audit",
    )
    base.update(overrides)
    return AnalysisPlan(**base)


def _insight(**overrides) -> dict:
    base = dict(
        type="correlation",
        severity="medium",
        confidence=70.0,
        col_a="premium",
        col_b="claim_amount",
        title="Premium vs Claim",
        finding="Premium correlates with claim amount",
        is_target_driver=False,
    )
    base.update(overrides)
    return base


def _confidence(insights: list[dict], title: str) -> float:
    for ins in insights:
        if ins.get("title") == title:
            return float(ins.get("confidence", 0))
    raise KeyError(f"insight not found: {title!r}")


def _is_penalised(ins: dict) -> bool:
    return ins.get("suppressed_by_plan", False) is True


# ── No plan — safe fallback ───────────────────────────────────────────────────

class TestNoPlan:
    def test_none_plan_returns_unchanged(self):
        insights = [_insight(), _insight(title="Other")]
        result = apply_analysis_plan_hygiene(insights, None)
        assert result == insights

    def test_none_plan_does_not_mutate_input(self):
        original = [_insight()]
        apply_analysis_plan_hygiene(original, None)
        assert "suppressed_by_plan" not in original[0]


# ── Ignored-column penalty ────────────────────────────────────────────────────

class TestIgnoredColumnPenalty:
    def test_all_ignored_cols_penalised(self):
        plan = _plan()
        ins = _insight(col_a="policy_id", col_b="customer_id", title="ID pair")
        result = apply_analysis_plan_hygiene([ins], plan)
        assert _is_penalised(result[0])
        assert result[0]["confidence"] < ins["confidence"]

    def test_penalty_reason_is_ignored_column(self):
        plan = _plan()
        ins = _insight(col_a="policy_id", col_b="customer_id", title="ID pair")
        result = apply_analysis_plan_hygiene([ins], plan)
        assert result[0]["plan_penalty_reason"] == "ignored_column"

    def test_mixed_cols_not_penalised(self):
        """If one col is ignored but the other is real, do not penalise."""
        plan = _plan()
        ins = _insight(col_a="policy_id", col_b="premium", title="ID + real")
        result = apply_analysis_plan_hygiene([ins], plan)
        assert not _is_penalised(result[0])
        assert result[0]["confidence"] == ins["confidence"]

    def test_all_real_cols_not_penalised(self):
        plan = _plan()
        ins = _insight(col_a="premium", col_b="claim_amount", title="Real pair")
        result = apply_analysis_plan_hygiene([ins], plan)
        assert not _is_penalised(result[0])


# ── Date-part feature penalty ─────────────────────────────────────────────────

class TestDatePartPenalty:
    def test_date_month_derived_from_time_column_penalised(self):
        plan = _plan(time_columns=["effective_date"])
        ins = _insight(col_a="effective_date_month", col_b="premium",
                       title="Month vs premium")
        result = apply_analysis_plan_hygiene([ins], plan)
        assert _is_penalised(result[0])
        assert result[0]["plan_penalty_reason"] == "date_part_feature"

    def test_date_quarter_derived_penalised(self):
        plan = _plan(time_columns=["effective_date"])
        ins = _insight(col_a="effective_date_quarter", col_b="claim_amount",
                       title="Quarter vs claim")
        result = apply_analysis_plan_hygiene([ins], plan)
        assert _is_penalised(result[0])

    def test_date_year_derived_penalised(self):
        plan = _plan(time_columns=["effective_date"])
        ins = _insight(col_a="premium", col_b="effective_date_year",
                       title="Premium vs year")
        result = apply_analysis_plan_hygiene([ins], plan)
        assert _is_penalised(result[0])

    def test_date_weekend_flag_penalised(self):
        plan = _plan(time_columns=["order_date"])
        ins = _insight(col_a="order_date_weekend", col_b="revenue",
                       title="Weekend flag vs revenue")
        result = apply_analysis_plan_hygiene([ins], plan)
        assert _is_penalised(result[0])

    def test_real_date_column_not_penalised(self):
        """Finding directly on effective_date (not a derived part) should survive."""
        plan = _plan(time_columns=["effective_date"])
        ins = _insight(col_a="effective_date", col_b="premium",
                       title="Effective date vs premium")
        result = apply_analysis_plan_hygiene([ins], plan)
        assert not _is_penalised(result[0])

    def test_derived_col_not_from_time_col_not_penalised(self):
        """column_month where 'column' is NOT a time_column — no penalty."""
        plan = _plan(time_columns=["effective_date"])
        ins = _insight(col_a="premium_month", col_b="claim_amount",
                       title="Premium month vs claim")
        result = apply_analysis_plan_hygiene([ins], plan)
        assert not _is_penalised(result[0])

    def test_confidence_reduced_by_penalty(self):
        plan = _plan(time_columns=["effective_date"])
        ins = _insight(col_a="effective_date_month", col_b="premium",
                       confidence=70.0, title="Month penalty check")
        result = apply_analysis_plan_hygiene([ins], plan)
        assert result[0]["confidence"] < 70.0
        assert result[0]["confidence"] > 0.0


# ── Genuine trend findings preserved ─────────────────────────────────────────

class TestGenuineTrendPreserved:
    def test_trend_on_real_date_not_penalised(self):
        plan = _plan(time_columns=["order_date"])
        ins = _insight(
            type="trend",
            col_a="order_date",
            col_b="revenue",
            title="Revenue trend over order_date",
        )
        result = apply_analysis_plan_hygiene([ins], plan)
        assert not _is_penalised(result[0])

    def test_trend_on_date_part_still_penalised(self):
        """Trend on order_date_month (not a real date col) still penalised."""
        plan = _plan(time_columns=["order_date"])
        ins = _insight(
            type="trend",
            col_a="order_date_month",
            col_b="revenue",
            title="Revenue trend over month (derived)",
        )
        result = apply_analysis_plan_hygiene([ins], plan)
        assert _is_penalised(result[0])


# ── Target metric and dimension preservation ──────────────────────────────────

class TestTargetAndDimensionPreserved:
    def test_target_metric_finding_not_penalised(self):
        plan = _plan()
        ins = _insight(col_a="premium", col_b="claim_amount",
                       title="Premium vs claim — target pair")
        result = apply_analysis_plan_hygiene([ins], plan)
        assert not _is_penalised(result[0])
        assert result[0]["confidence"] == ins["confidence"]

    def test_dimension_finding_not_penalised(self):
        plan = _plan()
        ins = _insight(col_a="coverage_type", col_b="premium",
                       title="Coverage type vs premium")
        result = apply_analysis_plan_hygiene([ins], plan)
        assert not _is_penalised(result[0])

    def test_does_not_mutate_original_insight(self):
        plan = _plan(time_columns=["effective_date"])
        original = _insight(col_a="effective_date_month", col_b="premium",
                            title="Mutation test")
        apply_analysis_plan_hygiene([original], plan)
        assert "suppressed_by_plan" not in original
        assert original["confidence"] == 70.0
