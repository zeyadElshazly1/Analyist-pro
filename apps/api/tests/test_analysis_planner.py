"""
Tests for the deterministic Dataset Intelligence Layer (86B).

Covers domain classification, column sorting, confidence banding,
column validation, and the no-invented-columns safety rule.
"""
import pytest

from app.services.analysis.analysis_planner import build_analysis_plan
from app.schemas.analysis_plan import AnalysisPlan


# ── Fixtures ──────────────────────────────────────────────────────────────────

SALES_COLS = [
    "order_id", "order_date", "customer_id", "customer_name",
    "region", "product_category", "product_name",
    "quantity", "unit_price", "discount_pct", "revenue", "sales_rep",
]

INSURANCE_COLS = [
    "policy_id", "effective_date", "customer_id",
    "coverage_type", "premium", "claim_amount",
    "deductible", "region", "vehicle_age",
]

FINANCE_COLS = [
    "date", "ticker", "open", "high", "low", "close",
    "volume", "return_pct", "sector",
]

HR_COLS = [
    "employee_id", "department", "salary", "tenure",
    "attrition", "performance_rating", "hire_date", "gender",
]

GENERIC_COLS = [
    "col_a", "col_b", "col_c", "val_1", "val_2",
]


# ── Domain classification ─────────────────────────────────────────────────────

class TestDomainClassification:
    def test_sales_columns_produce_sales_kind(self):
        plan = build_analysis_plan(SALES_COLS)
        assert plan.dataset_kind == "sales"

    def test_insurance_columns_produce_insurance_kind(self):
        plan = build_analysis_plan(INSURANCE_COLS)
        assert plan.dataset_kind == "insurance"

    def test_finance_columns_produce_finance_kind(self):
        plan = build_analysis_plan(FINANCE_COLS)
        assert plan.dataset_kind == "finance"

    def test_hr_columns_produce_hr_kind(self):
        plan = build_analysis_plan(HR_COLS)
        assert plan.dataset_kind == "hr"

    def test_generic_columns_produce_generic_kind(self):
        plan = build_analysis_plan(GENERIC_COLS)
        assert plan.dataset_kind == "generic"

    def test_empty_columns_produce_generic_kind(self):
        plan = build_analysis_plan([])
        assert plan.dataset_kind == "generic"
        assert plan.confidence == 0.0

    def test_marketing_columns_produce_marketing_kind(self):
        cols = ["campaign_id", "channel", "impressions", "clicks", "ctr", "spend", "conversions"]
        plan = build_analysis_plan(cols)
        assert plan.dataset_kind == "marketing"


# ── Column classification ─────────────────────────────────────────────────────

class TestColumnClassification:
    def test_id_columns_go_to_ignore(self):
        plan = build_analysis_plan(SALES_COLS)
        assert "order_id" in plan.columns_to_ignore
        assert "customer_id" in plan.columns_to_ignore

    def test_unnamed_columns_go_to_ignore(self):
        cols = SALES_COLS + ["Unnamed: 14", "Unnamed: 15"]
        plan = build_analysis_plan(cols)
        assert "Unnamed: 14" in plan.columns_to_ignore
        assert "Unnamed: 15" in plan.columns_to_ignore

    def test_avg_helper_columns_go_to_ignore(self):
        cols = SALES_COLS + ["avg S", "avg P", "total revenue_helper"]
        plan = build_analysis_plan(cols)
        assert "avg S" in plan.columns_to_ignore
        assert "avg P" in plan.columns_to_ignore

    def test_mostly_empty_columns_go_to_ignore(self):
        cols = ["revenue", "region", "sparse_col"]
        profile = {"columns": [
            {"name": "revenue",    "missing_pct": 0.01},
            {"name": "region",     "missing_pct": 0.02},
            {"name": "sparse_col", "missing_pct": 0.92},
        ]}
        plan = build_analysis_plan(cols, profile_summary=profile)
        assert "sparse_col" in plan.columns_to_ignore

    def test_date_columns_go_to_time_columns(self):
        plan = build_analysis_plan(SALES_COLS)
        assert "order_date" in plan.time_columns

    def test_multiple_date_columns_detected(self):
        plan = build_analysis_plan(INSURANCE_COLS)
        assert "effective_date" in plan.time_columns

    def test_hr_hire_date_in_time_columns(self):
        plan = build_analysis_plan(HR_COLS)
        assert "hire_date" in plan.time_columns


# ── Target metrics ────────────────────────────────────────────────────────────

class TestTargetMetrics:
    def test_revenue_is_detected_as_target(self):
        plan = build_analysis_plan(SALES_COLS)
        assert "revenue" in plan.target_metrics

    def test_premium_is_detected_as_target(self):
        plan = build_analysis_plan(INSURANCE_COLS)
        assert "premium" in plan.target_metrics

    def test_close_is_detected_as_target(self):
        plan = build_analysis_plan(FINANCE_COLS)
        assert "close" in plan.target_metrics

    def test_salary_is_detected_as_target(self):
        plan = build_analysis_plan(HR_COLS)
        assert "salary" in plan.target_metrics

    def test_attrition_is_detected_as_target(self):
        plan = build_analysis_plan(HR_COLS)
        assert "attrition" in plan.target_metrics


# ── Confidence ────────────────────────────────────────────────────────────────

class TestConfidence:
    def test_confidence_within_zero_one(self):
        for cols in [SALES_COLS, INSURANCE_COLS, FINANCE_COLS, HR_COLS, GENERIC_COLS]:
            plan = build_analysis_plan(cols)
            assert 0.0 <= plan.confidence <= 1.0

    def test_strong_domain_confidence_above_threshold(self):
        plan = build_analysis_plan(SALES_COLS)
        assert plan.confidence >= 0.6

    def test_generic_confidence_below_threshold(self):
        plan = build_analysis_plan(GENERIC_COLS)
        assert plan.confidence < 0.6

    def test_confidence_clamped_at_one(self):
        # Even a very signal-rich set must not exceed 1.0
        many_tokens = [
            "revenue", "sales", "order", "quantity", "discount",
            "product", "customer", "region", "territory", "deal",
            "pipeline", "conversion", "lead", "quota", "upsell",
        ]
        plan = build_analysis_plan(many_tokens)
        assert plan.confidence <= 1.0


# ── Column validity (no invented columns) ─────────────────────────────────────

class TestColumnValidity:
    def _all_referenced_cols(self, plan: AnalysisPlan) -> list[str]:
        cols: list[str] = []
        cols += plan.target_metrics
        cols += plan.important_dimensions
        cols += plan.time_columns
        cols += plan.columns_to_ignore
        for h in plan.recommended_charts:
            cols.append(h.x_column)
            if h.y_column:
                cols.append(h.y_column)
        return cols

    def test_no_invented_columns_sales(self):
        valid = set(SALES_COLS)
        plan = build_analysis_plan(SALES_COLS)
        for col in self._all_referenced_cols(plan):
            assert col in valid, f"Invented column reference: {col!r}"

    def test_no_invented_columns_insurance(self):
        valid = set(INSURANCE_COLS)
        plan = build_analysis_plan(INSURANCE_COLS)
        for col in self._all_referenced_cols(plan):
            assert col in valid, f"Invented column reference: {col!r}"

    def test_no_invented_columns_finance(self):
        valid = set(FINANCE_COLS)
        plan = build_analysis_plan(FINANCE_COLS)
        for col in self._all_referenced_cols(plan):
            assert col in valid, f"Invented column reference: {col!r}"

    def test_no_invented_columns_hr(self):
        valid = set(HR_COLS)
        plan = build_analysis_plan(HR_COLS)
        for col in self._all_referenced_cols(plan):
            assert col in valid, f"Invented column reference: {col!r}"


# ── Output structure ──────────────────────────────────────────────────────────

class TestOutputStructure:
    def test_returns_analysis_plan_instance(self):
        assert isinstance(build_analysis_plan(SALES_COLS), AnalysisPlan)

    def test_insight_priorities_non_empty(self):
        plan = build_analysis_plan(SALES_COLS)
        assert len(plan.insight_priorities) > 0

    def test_report_template_hint_present(self):
        plan = build_analysis_plan(SALES_COLS)
        assert plan.report_template_hint in {
            "executive_summary", "detailed_audit", "trend_report", "generic"
        }

    def test_generic_fallback_uses_generic_template(self):
        plan = build_analysis_plan(GENERIC_COLS)
        assert plan.report_template_hint == "generic"

    def test_date_warning_present_when_date_cols_detected(self):
        plan = build_analysis_plan(SALES_COLS)
        assert any("Date columns" in w for w in plan.analysis_warnings)

    def test_no_date_warning_when_no_date_cols(self):
        cols = ["revenue", "region", "product", "quantity"]
        plan = build_analysis_plan(cols)
        assert not any("Date columns" in w for w in plan.analysis_warnings)

    def test_chart_hints_have_valid_priorities(self):
        plan = build_analysis_plan(SALES_COLS)
        priorities = [h.priority for h in plan.recommended_charts]
        assert priorities == sorted(priorities)

    def test_business_context_non_empty(self):
        for cols in [SALES_COLS, GENERIC_COLS]:
            plan = build_analysis_plan(cols)
            assert len(plan.business_context) > 0
