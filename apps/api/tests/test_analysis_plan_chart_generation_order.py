"""
86K — Chart generation column prioritisation tests.

Verifies that build_chart_data() uses analysis_plan to reorder columns
before applying budget caps, so target_metrics and important_dimensions
generate charts even when they appear late in DataFrame column order.

Also covers prioritize_columns_for_charts() unit tests directly.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from app.services.analysis.chart_plan_hygiene import prioritize_columns_for_charts
from app.services.charting.orchestrator import build_chart_data
from app.schemas.analysis_plan import AnalysisPlan


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _plan(**overrides) -> AnalysisPlan:
    base = dict(
        dataset_kind="insurance",
        confidence=0.90,
        business_context="Insurance portfolio",
        primary_entity="policy",
        target_metrics=["annual_premium_usd", "frequency", "severity"],
        important_dimensions=["coverage_type", "territory"],
        time_columns=["effective_date"],
        columns_to_ignore=["policy_id"],
        recommended_charts=[],
        insight_priorities=["correlation"],
        analysis_warnings=[],
        report_template_hint="detailed_audit",
    )
    base.update(overrides)
    return AnalysisPlan(**base)


def _insurance_df(n: int = 120) -> pd.DataFrame:
    """DataFrame where target metrics appear AFTER four generic numeric columns.

    Column order: age, vehicle_year, policy_length_years, number_of_accidents,
    annual_premium_usd, frequency, severity  (targets at positions 5-7)

    Without plan: MAX_HIST_COLS=4 cuts off before any target.
    With plan: targets are reordered to positions 1-3, get histograms.

    Note: numeric columns use integer/discretized values to avoid the
    _is_id_col 90%-unique exclusion that fires on all-distinct floats.
    """
    rng = np.random.default_rng(42)
    return pd.DataFrame({
        "age":                 rng.integers(18, 80, n).astype(float),
        "vehicle_year":        rng.integers(2000, 2023, n).astype(float),
        "policy_length_years": rng.integers(1, 10, n).astype(float),
        "number_of_accidents": rng.integers(0, 5, n).astype(float),
        # Targets: use rounded integers so uniqueness stays well below 90%
        "annual_premium_usd":  (rng.integers(500, 5000, n) // 100 * 100).astype(float),
        "frequency":           rng.integers(0, 10, n).astype(float),
        "severity":            (rng.integers(200, 20000, n) // 500 * 500).astype(float),
        "coverage_type":       rng.choice(["basic", "standard", "premium"], n),
        "territory":           rng.choice(["north", "south", "east", "west"], n),
    })


def _chart_cols(charts: list[dict]) -> set[str]:
    """Collect all column names referenced by chart x_label / y_label.

    Filters placeholder labels that the chart builder inserts (not column names).
    """
    cols: set[str] = set()
    # These are generic chart-builder placeholders, never real column names
    _skip = {"count", "density", "value", "mean", "index", "column"}
    for c in charts:
        for field in ("x_label", "y_label"):
            val = c.get(field)
            if isinstance(val, str) and val.lower() not in _skip:
                cols.add(val)
    return cols


# ── Unit tests for prioritize_columns_for_charts ─────────────────────────────

class TestPrioritizeColumnsForCharts:
    def test_targets_move_to_front(self):
        cols = ["age", "vehicle_year", "annual_premium_usd", "frequency"]
        plan = _plan(target_metrics=["annual_premium_usd", "frequency"])
        result = prioritize_columns_for_charts(cols, plan)
        assert result[0] in {"annual_premium_usd", "frequency"}
        assert result[1] in {"annual_premium_usd", "frequency"}

    def test_dims_follow_targets(self):
        cols = ["age", "coverage_type", "annual_premium_usd", "territory"]
        plan = _plan(
            target_metrics=["annual_premium_usd"],
            important_dimensions=["coverage_type", "territory"],
        )
        result = prioritize_columns_for_charts(cols, plan)
        target_idx = result.index("annual_premium_usd")
        dim_idx_a  = result.index("coverage_type")
        dim_idx_b  = result.index("territory")
        assert target_idx < dim_idx_a
        assert target_idx < dim_idx_b

    def test_ignored_cols_move_to_end(self):
        cols = ["policy_id", "age", "annual_premium_usd"]
        plan = _plan(target_metrics=["annual_premium_usd"], columns_to_ignore=["policy_id"])
        result = prioritize_columns_for_charts(cols, plan)
        assert result[-1] == "policy_id"
        assert result[0] == "annual_premium_usd"

    def test_all_columns_preserved(self):
        cols = ["age", "vehicle_year", "annual_premium_usd", "frequency"]
        plan = _plan(target_metrics=["annual_premium_usd"])
        result = prioritize_columns_for_charts(cols, plan)
        assert set(result) == set(cols)
        assert len(result) == len(cols)

    def test_none_plan_returns_unchanged(self):
        cols = ["age", "vehicle_year", "annual_premium_usd"]
        assert prioritize_columns_for_charts(cols, None) == cols

    def test_low_confidence_plan_returns_unchanged(self):
        plan = _plan(confidence=0.45, dataset_kind="generic")
        cols = ["age", "vehicle_year", "annual_premium_usd"]
        assert prioritize_columns_for_charts(cols, plan) == cols

    def test_unknown_columns_stay_in_others_bucket(self):
        """Columns not in any plan set are kept between dims and ignored."""
        cols = ["mystery_col", "annual_premium_usd", "policy_id"]
        plan = _plan(target_metrics=["annual_premium_usd"], columns_to_ignore=["policy_id"])
        result = prioritize_columns_for_charts(cols, plan)
        assert result[0] == "annual_premium_usd"
        assert result[-1] == "policy_id"
        assert "mystery_col" in result

    def test_order_within_targets_bucket_preserved(self):
        """The relative order among target metrics themselves must not change."""
        cols = ["a_target", "b_target", "generic"]
        plan = _plan(target_metrics=["a_target", "b_target"])
        result = prioritize_columns_for_charts(cols, plan)
        assert result.index("a_target") < result.index("b_target")

    def test_empty_columns_list(self):
        plan = _plan()
        assert prioritize_columns_for_charts([], plan) == []

    def test_target_not_in_columns_ignored_safely(self):
        """Targets that don't exist in the column list are silently ignored."""
        cols = ["age", "vehicle_year"]
        plan = _plan(target_metrics=["nonexistent_col"])
        result = prioritize_columns_for_charts(cols, plan)
        assert result == cols   # unchanged since no targets present


# ── Integration: build_chart_data with analysis_plan ─────────────────────────

class TestBuildChartDataWithPlan:
    def test_target_metrics_appear_in_charts_with_plan(self):
        """Target metrics at column positions 5-7 must generate charts when plan provided."""
        df = _insurance_df()
        plan = _plan()
        charts = build_chart_data(df, analysis_plan=plan)
        cols = _chart_cols(charts)
        # At least one target metric must have a chart
        targets = {"annual_premium_usd", "frequency", "severity"}
        assert cols & targets, (
            f"No target metric chart generated. Chart cols found: {cols}"
        )

    def test_without_plan_targets_may_not_appear_in_histograms(self):
        """Without plan, targets at col positions 5-7 are beyond MAX_HIST_COLS=4.

        They may appear in scatter pairs but not as histogram charts (title
        starting with 'Distribution of').  This confirms the problem 86K fixes.
        """
        df = _insurance_df()
        charts = build_chart_data(df)  # no plan
        hist_titles = {c["title"] for c in charts if c.get("title", "").startswith("Distribution of")}
        target_hists = {t for t in hist_titles if any(
            tgt in t for tgt in ["annual_premium_usd", "frequency", "severity"]
        )}
        # Without plan, these targets should NOT have histogram charts
        assert not target_hists, (
            f"Targets appeared in histograms without plan: {target_hists}"
        )

    def test_dimension_charts_appear_for_categorical_with_plan(self):
        """important_dimensions move to front of categorical_cols list."""
        df = _insurance_df()
        plan = _plan()
        charts = build_chart_data(df, analysis_plan=plan)
        cols = _chart_cols(charts)
        dims = {"coverage_type", "territory"}
        assert cols & dims, f"No dimension chart generated. Chart cols: {cols}"

    def test_no_plan_fallback_still_generates_charts(self):
        """build_chart_data with no plan still produces valid charts."""
        df = _insurance_df()
        charts = build_chart_data(df)
        assert len(charts) > 0

    def test_generic_low_confidence_plan_behaves_like_no_plan(self):
        """Low-confidence plan must not reorder columns."""
        df = _insurance_df()
        generic_plan = _plan(confidence=0.45, dataset_kind="generic")
        charts_no_plan   = build_chart_data(df)
        charts_gen_plan  = build_chart_data(df, analysis_plan=generic_plan)
        # Titles should be identical (same column order → same charts)
        no_plan_titles  = sorted(c.get("title","") for c in charts_no_plan)
        gen_plan_titles = sorted(c.get("title","") for c in charts_gen_plan)
        assert no_plan_titles == gen_plan_titles

    def test_finance_snapshot_unaffected_by_plan(self):
        """Financial snapshot path ignores generic reordering — already semantic."""
        from app.services.dataset_context.schema import FINANCIAL_MARKETS_SNAPSHOT
        from app.services.dataset_context import detect_dataset_context

        rng = np.random.default_rng(7)
        n = 60
        df_fin = pd.DataFrame({
            "ticker":         [f"T{i:03d}" for i in range(n)],
            "asset_class":    rng.choice(["equity", "bond", "etf"], n),
            "return_1y_pct":  rng.normal(0.08, 0.20, n),
            "volatility_1y_ann": np.abs(rng.normal(0.25, 0.10, n)),
            "analyst_upside_pct": rng.uniform(-0.10, 0.30, n),
        })

        ctx = detect_dataset_context(df_fin)
        if ctx.dataset_type != FINANCIAL_MARKETS_SNAPSHOT:
            pytest.skip("DataFrame not classified as snapshot — context detection differs")

        finance_plan = _plan(dataset_kind="finance", confidence=0.92)
        charts = build_chart_data(df_fin, dataset_context=ctx, analysis_plan=finance_plan)
        # Snapshot builder produces semantically relevant charts regardless
        assert len(charts) >= 1


# ── Sales domain — cross-domain check ────────────────────────────────────────

class TestSalesDomainPrioritisation:
    def test_revenue_chart_generated_before_generic_columns(self):
        """Sales plan: revenue must appear in charts even if column order puts it last."""
        rng = np.random.default_rng(99)
        n = 100
        df = pd.DataFrame({
            "order_id_num":     range(n),          # excluded: 100% unique
            "quantity":         rng.integers(1, 50, n).astype(float),
            "discount_tier":    rng.integers(0, 5, n).astype(float),  # integers → not all-unique
            "days_since_order": rng.integers(1, 365, n).astype(float),
            "revenue":          (rng.integers(50, 5000, n) // 50 * 50).astype(float),  # TARGET
        })
        plan = _plan(
            dataset_kind="sales",
            target_metrics=["revenue"],
            important_dimensions=[],
        )
        charts = build_chart_data(df, analysis_plan=plan)
        cols = _chart_cols(charts)
        assert "revenue" in cols, f"revenue not in chart cols: {cols}"
