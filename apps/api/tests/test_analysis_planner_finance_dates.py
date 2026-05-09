"""
86G — Finance date false-positive regression tests.

Verifies that financial metric column names containing calendar words
(day, week, month, year, quarter) as bare substrings are NOT classified
as time_columns, while real date/timestamp columns in any domain still
are detected correctly.

Also verifies that ticker and symbol land in columns_to_ignore instead
of target_metrics.
"""
import pytest

from app.services.analysis.analysis_planner import build_analysis_plan


# ── Finance metric columns — must NOT be time_columns ────────────────────────

class TestFinanceMetricColumnsNotTimeColumns:
    """Finance price/volume metric names that contain day/week/month substrings
    must not be misclassified as time columns."""

    _FINANCE_METRIC_COLS = [
        "ticker", "price_date",
        "daylow", "dayhigh",
        "fiftydayaverage", "twohundreddayaverage",
        "averagevolume10days",
        "fiftytwoweeklow", "fiftytwoweekhigh",
        "pricetosalestrailing12months",
        "earningsquarterlygrowth",
        "open", "high", "low", "close", "volume",
    ]

    def _plan(self):
        return build_analysis_plan(self._FINANCE_METRIC_COLS)

    def test_daylow_not_time_column(self):
        assert "daylow" not in self._plan().time_columns

    def test_dayhigh_not_time_column(self):
        assert "dayhigh" not in self._plan().time_columns

    def test_fiftydayaverage_not_time_column(self):
        assert "fiftydayaverage" not in self._plan().time_columns

    def test_twohundreddayaverage_not_time_column(self):
        assert "twohundreddayaverage" not in self._plan().time_columns

    def test_averagevolume10days_not_time_column(self):
        assert "averagevolume10days" not in self._plan().time_columns

    def test_fiftytwoweeklow_not_time_column(self):
        assert "fiftytwoweeklow" not in self._plan().time_columns

    def test_fiftytwoweekhigh_not_time_column(self):
        assert "fiftytwoweekhigh" not in self._plan().time_columns

    def test_pricetosalestrailing12months_not_time_column(self):
        assert "pricetosalestrailing12months" not in self._plan().time_columns

    def test_earningsquarterlygrowth_not_time_column(self):
        assert "earningsquarterlygrowth" not in self._plan().time_columns

    def test_price_date_is_still_time_column(self):
        """Real date column in the same dataset must still be detected."""
        assert "price_date" in self._plan().time_columns


# ── Real date columns across domains — must remain in time_columns ────────────

class TestRealDateColumnsDetected:
    """Columns that genuinely represent dates must continue to be classified
    as time_columns regardless of tightened calendar-unit patterns."""

    def test_price_date(self):
        plan = build_analysis_plan(["price_date", "close", "volume"])
        assert "price_date" in plan.time_columns

    def test_trade_date(self):
        plan = build_analysis_plan(["trade_date", "close", "volume"])
        assert "trade_date" in plan.time_columns

    def test_build_timestamp(self):
        plan = build_analysis_plan(["build_timestamp", "close", "volume"])
        assert "build_timestamp" in plan.time_columns

    def test_created_at(self):
        plan = build_analysis_plan(["created_at", "revenue", "region"])
        assert "created_at" in plan.time_columns

    def test_updated_on(self):
        plan = build_analysis_plan(["updated_on", "revenue", "region"])
        assert "updated_on" in plan.time_columns

    def test_effective_date_insurance(self):
        plan = build_analysis_plan(["policy_id", "effective_date", "premium", "claim_amount"])
        assert "effective_date" in plan.time_columns

    def test_policy_end_date_insurance(self):
        plan = build_analysis_plan(["policy_id", "policy_end_date", "premium"])
        assert "policy_end_date" in plan.time_columns

    def test_order_date_sales(self):
        plan = build_analysis_plan(["order_id", "order_date", "revenue", "region"])
        assert "order_date" in plan.time_columns

    def test_hire_date_hr(self):
        plan = build_analysis_plan(["employee_id", "hire_date", "salary", "department"])
        assert "hire_date" in plan.time_columns

    def test_standalone_date_column(self):
        """A column named literally 'date' must be a time column."""
        plan = build_analysis_plan(["date", "ticker", "close", "volume"])
        assert "date" in plan.time_columns

    def test_fiscal_year_column(self):
        """fiscal_year has underscores around 'year' — should be detected."""
        plan = build_analysis_plan(["fiscal_year", "revenue", "region"])
        assert "fiscal_year" in plan.time_columns

    def test_fiscal_quarter_column(self):
        """fiscal_quarter has underscore before 'quarter' — should be detected."""
        plan = build_analysis_plan(["fiscal_quarter", "revenue", "region"])
        assert "fiscal_quarter" in plan.time_columns


# ── ticker and symbol — must be in columns_to_ignore, not target_metrics ──────

class TestTickerSymbolIgnored:
    def test_ticker_in_columns_to_ignore(self):
        plan = build_analysis_plan(["ticker", "close", "volume", "return_pct", "price_date"])
        assert "ticker" in plan.columns_to_ignore

    def test_symbol_in_columns_to_ignore(self):
        plan = build_analysis_plan(["symbol", "close", "volume", "return_pct", "price_date"])
        assert "symbol" in plan.columns_to_ignore

    def test_ticker_not_in_target_metrics(self):
        plan = build_analysis_plan(["ticker", "close", "volume", "return_pct", "price_date"])
        assert "ticker" not in plan.target_metrics

    def test_symbol_not_in_target_metrics(self):
        plan = build_analysis_plan(["symbol", "close", "volume", "return_pct", "price_date"])
        assert "symbol" not in plan.target_metrics

    def test_other_targets_unaffected_when_ticker_ignored(self):
        """Ignoring ticker must not prevent close/volume from being targets."""
        plan = build_analysis_plan(["ticker", "close", "volume", "return_pct", "price_date"])
        assert "close" in plan.target_metrics or "volume" in plan.target_metrics

    def test_stock_ticker_column_also_ignored(self):
        """Compound column name stock_ticker must also be caught."""
        plan = build_analysis_plan(["stock_ticker", "close", "volume"])
        assert "stock_ticker" in plan.columns_to_ignore


# ── Finance dataset domain still classified correctly ─────────────────────────

class TestFinanceDomainUnchanged:
    """Tightening date detection must not break finance domain classification."""

    _COLS = [
        "ticker", "price_date",
        "daylow", "dayhigh", "fiftydayaverage",
        "open", "high", "low", "close", "volume", "return_pct",
    ]

    def test_domain_still_finance(self):
        plan = build_analysis_plan(self._COLS)
        assert plan.dataset_kind == "finance"

    def test_confidence_still_high(self):
        plan = build_analysis_plan(self._COLS)
        assert plan.confidence >= 0.6

    def test_no_invented_columns(self):
        valid = set(self._COLS)
        plan = build_analysis_plan(self._COLS)
        all_cols: list[str] = (
            plan.target_metrics
            + plan.important_dimensions
            + plan.time_columns
            + plan.columns_to_ignore
            + [h.x_column for h in plan.recommended_charts]
            + [h.y_column for h in plan.recommended_charts if h.y_column]
        )
        for col in all_cols:
            assert col in valid, f"Invented column reference: {col!r}"
