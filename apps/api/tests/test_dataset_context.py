"""
Tests for the dataset_context schema, signal definitions, and detector.

Coverage:
  - DatasetContext dataclass construction and immutability
  - CONFIDENCE_THRESHOLD and dataset type constants
  - generic_tabular_context convenience constructor
  - _normalise_col handles mixed casing, underscores, hyphens, spaces
  - role_for_column maps canonical Yahoo snapshot column names correctly
  - role_for_column returns "unknown" for unrecognised columns
  - frozensets are non-empty and contain only strings
  - detect_dataset_context classification (snapshot / timeseries / generic)
  - resolve_semantic_roles covers every column
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from pathlib import Path

from app.services.dataset_context import (
    DatasetContext,
    CONFIDENCE_THRESHOLD,
    FINANCIAL_MARKETS_SNAPSHOT,
    FINANCIAL_MARKETS_TIMESERIES,
    GENERIC_TABULAR,
    generic_tabular_context,
    _normalise_col,
    role_for_column,
    detect_dataset_context,
    resolve_semantic_roles,
    RETURN_NAMES,
    VOLATILITY_NAMES,
    SHARPE_NAMES,
    ASSET_CLASS_NAMES,
    SECTOR_NAMES,
    ANALYST_UPSIDE_NAMES,
    POSITION_52W_NAMES,
    COMPOSITE_SCORE_NAMES,
    OHLC_NAMES,
    ASSET_ID_NAMES,
    ASSET_LABEL_NAMES,
    SIZE_METRIC_NAMES,
)


# ── DatasetContext schema ─────────────────────────────────────────────────────

class TestDatasetContextSchema:
    def test_default_construction(self):
        ctx = DatasetContext()
        assert ctx.dataset_type == GENERIC_TABULAR
        assert ctx.confidence == 1.0
        assert ctx.matched_signals == ()
        assert ctx.semantic_roles == {}
        assert ctx.warnings == ()

    def test_explicit_construction(self):
        ctx = DatasetContext(
            dataset_type=FINANCIAL_MARKETS_SNAPSHOT,
            confidence=0.87,
            matched_signals=("return column detected", "volatility column detected"),
            semantic_roles={"ytd_return": "return_period", "volatility": "volatility"},
            warnings=("Mixed asset classes detected.",),
        )
        assert ctx.dataset_type == FINANCIAL_MARKETS_SNAPSHOT
        assert ctx.confidence == 0.87
        assert "return column detected" in ctx.matched_signals
        assert ctx.semantic_roles["ytd_return"] == "return_period"
        assert len(ctx.warnings) == 1

    def test_frozen_immutable(self):
        ctx = DatasetContext()
        with pytest.raises((AttributeError, TypeError)):
            ctx.dataset_type = FINANCIAL_MARKETS_SNAPSHOT  # type: ignore[misc]

    def test_confidence_boundary_zero(self):
        ctx = DatasetContext(confidence=0.0)
        assert ctx.confidence == 0.0

    def test_confidence_boundary_one(self):
        ctx = DatasetContext(confidence=1.0)
        assert ctx.confidence == 1.0

    def test_confidence_below_zero_raises(self):
        with pytest.raises(ValueError):
            DatasetContext(confidence=-0.01)

    def test_confidence_above_one_raises(self):
        with pytest.raises(ValueError):
            DatasetContext(confidence=1.001)

    def test_dataset_type_constants_distinct(self):
        assert FINANCIAL_MARKETS_SNAPSHOT != FINANCIAL_MARKETS_TIMESERIES
        assert FINANCIAL_MARKETS_SNAPSHOT != GENERIC_TABULAR
        assert FINANCIAL_MARKETS_TIMESERIES != GENERIC_TABULAR

    def test_confidence_threshold_value(self):
        assert CONFIDENCE_THRESHOLD == 0.65

    def test_generic_tabular_context_helper(self):
        ctx = generic_tabular_context()
        assert ctx.dataset_type == GENERIC_TABULAR
        assert ctx.confidence == 1.0
        assert ctx.matched_signals == ()
        assert ctx.warnings == ()

    def test_generic_tabular_context_with_roles(self):
        roles = {"ticker": "asset_id", "ytd_return": "return_period"}
        ctx = generic_tabular_context(semantic_roles=roles)
        assert ctx.semantic_roles == roles

    def test_two_identical_contexts_are_equal(self):
        ctx_a = DatasetContext(dataset_type=GENERIC_TABULAR, confidence=1.0)
        ctx_b = DatasetContext(dataset_type=GENERIC_TABULAR, confidence=1.0)
        assert ctx_a == ctx_b

    def test_hashable(self):
        ctx = DatasetContext()
        # Frozen dataclasses are hashable
        assert isinstance(hash(ctx), int)


# ── _normalise_col ────────────────────────────────────────────────────────────

class TestNormaliseCol:
    def test_camel_case(self):
        assert _normalise_col("currentPrice") == "currentprice"

    def test_underscore_separated(self):
        assert _normalise_col("current_price") == "currentprice"

    def test_space_separated_title_case(self):
        assert _normalise_col("Current Price") == "currentprice"

    def test_mixed_underscores_and_suffix(self):
        # "return_1y_pct" → "return1ypct"
        result = _normalise_col("return_1y_pct")
        assert result == "return1ypct"

    def test_all_lowercase_unchanged_except_stripping(self):
        assert _normalise_col("volatility") == "volatility"

    def test_hyphen_removed(self):
        assert _normalise_col("ytd-return") == "ytdreturn"

    def test_dot_removed(self):
        assert _normalise_col("sharpe.ratio") == "sharperatio"

    def test_percent_sign_removed(self):
        assert _normalise_col("return_pct%") == "returnpct"

    def test_mixed_case_with_numbers(self):
        assert _normalise_col("Sharpe_1Y") == "sharpe1y"

    def test_empty_string(self):
        assert _normalise_col("") == ""

    def test_only_special_chars(self):
        assert _normalise_col("___---") == ""


# ── role_for_column ───────────────────────────────────────────────────────────

class TestRoleForColumn:
    # ── return_period ─────────────────────────────────────────────────────────
    def test_return_1y_pct(self):
        assert role_for_column("return_1y_pct") == "return_period"

    def test_ytd_return(self):
        assert role_for_column("ytd_return") == "return_period"

    def test_ytdreturn_no_separator(self):
        assert role_for_column("ytdreturn") == "return_period"

    def test_one_year_return(self):
        assert role_for_column("one_year_return") == "return_period"

    def test_three_year_return(self):
        assert role_for_column("three_year_return") == "return_period"

    def test_return_5y(self):
        assert role_for_column("return_5y") == "return_period"

    def test_perf_ytd(self):
        assert role_for_column("perf_ytd") == "return_period"

    # ── volatility ────────────────────────────────────────────────────────────
    def test_volatility(self):
        assert role_for_column("volatility") == "volatility"

    def test_volatility_1y_ann(self):
        assert role_for_column("volatility_1y_ann") == "volatility"

    def test_vol_1y(self):
        assert role_for_column("vol_1y") == "volatility"

    def test_annualised_vol(self):
        assert role_for_column("annualised_vol") == "volatility"

    def test_std_dev(self):
        assert role_for_column("std_dev") == "volatility"

    # ── sharpe_ratio ──────────────────────────────────────────────────────────
    def test_sharpe_1y(self):
        assert role_for_column("sharpe_1y") == "sharpe_ratio"

    def test_sharpe_ratio(self):
        assert role_for_column("sharpe_ratio") == "sharpe_ratio"

    def test_sortino(self):
        assert role_for_column("sortino") == "sharpe_ratio"

    def test_risk_adjusted_return(self):
        assert role_for_column("risk_adjusted_return") == "sharpe_ratio"

    # ── asset_class ───────────────────────────────────────────────────────────
    def test_asset_class(self):
        assert role_for_column("asset_class") == "asset_class"

    def test_instrument_type(self):
        assert role_for_column("instrument_type") == "asset_class"

    def test_fund_type(self):
        assert role_for_column("fund_type") == "asset_class"

    # ── sector ────────────────────────────────────────────────────────────────
    def test_sector(self):
        assert role_for_column("sector") == "sector"

    def test_gics_sector(self):
        assert role_for_column("gics_sector") == "sector"

    def test_industry(self):
        assert role_for_column("industry") == "sector"

    # ── analyst_upside ────────────────────────────────────────────────────────
    def test_analyst_upside_pct(self):
        assert role_for_column("analyst_upside_pct") == "analyst_upside"

    def test_consensus_upside(self):
        assert role_for_column("consensus_upside") == "analyst_upside"

    def test_price_target_upside(self):
        assert role_for_column("price_target_upside") == "analyst_upside"

    def test_implied_upside(self):
        assert role_for_column("implied_upside") == "analyst_upside"

    # ── position_52w ─────────────────────────────────────────────────────────
    def test_pct_of_52w_high(self):
        assert role_for_column("pct_of_52w_high") == "position_52w"

    def test_week52_position_pct(self):
        assert role_for_column("week52_position_pct") == "position_52w"

    def test_week_52_position(self):
        assert role_for_column("week_52_position") == "position_52w"

    def test_52w_range(self):
        assert role_for_column("52w_range") == "position_52w"

    # ── asset_id ──────────────────────────────────────────────────────────────
    def test_ticker(self):
        assert role_for_column("ticker") == "asset_id"

    def test_symbol(self):
        assert role_for_column("symbol") == "asset_id"

    def test_isin(self):
        assert role_for_column("isin") == "asset_id"

    # ── asset_label ───────────────────────────────────────────────────────────
    def test_short_name(self):
        assert role_for_column("shortName") == "asset_label"

    def test_long_name(self):
        assert role_for_column("longName") == "asset_label"

    def test_company_name(self):
        assert role_for_column("company_name") == "asset_label"

    # ── size_metric ───────────────────────────────────────────────────────────
    def test_market_cap(self):
        assert role_for_column("marketCap") == "size_metric"

    def test_mkt_cap(self):
        assert role_for_column("mkt_cap") == "size_metric"

    def test_aum(self):
        assert role_for_column("aum") == "size_metric"

    # ── ohlc_price ────────────────────────────────────────────────────────────
    def test_open(self):
        assert role_for_column("open") == "ohlc_price"

    def test_adj_close(self):
        assert role_for_column("adj_close") == "ohlc_price"

    # ── unknown ───────────────────────────────────────────────────────────────
    def test_random_unknown_col(self):
        assert role_for_column("random_unknown_col") == "unknown"

    def test_widget_count(self):
        assert role_for_column("widget_count") == "unknown"

    def test_empty_string(self):
        assert role_for_column("") == "unknown"

    def test_numeric_only_name(self):
        assert role_for_column("12345") == "unknown"


# ── Signal frozensets sanity ──────────────────────────────────────────────────

class TestSignalFrozensets:
    ALL_SETS = [
        ("RETURN_NAMES",        RETURN_NAMES),
        ("VOLATILITY_NAMES",    VOLATILITY_NAMES),
        ("SHARPE_NAMES",        SHARPE_NAMES),
        ("ASSET_CLASS_NAMES",   ASSET_CLASS_NAMES),
        ("SECTOR_NAMES",        SECTOR_NAMES),
        ("ANALYST_UPSIDE_NAMES",ANALYST_UPSIDE_NAMES),
        ("POSITION_52W_NAMES",  POSITION_52W_NAMES),
        ("COMPOSITE_SCORE_NAMES", COMPOSITE_SCORE_NAMES),
        ("OHLC_NAMES",          OHLC_NAMES),
        ("ASSET_ID_NAMES",      ASSET_ID_NAMES),
        ("ASSET_LABEL_NAMES",   ASSET_LABEL_NAMES),
        ("SIZE_METRIC_NAMES",   SIZE_METRIC_NAMES),
    ]

    @pytest.mark.parametrize("name,fset", ALL_SETS)
    def test_non_empty(self, name, fset):
        assert len(fset) > 0, f"{name} must not be empty"

    @pytest.mark.parametrize("name,fset", ALL_SETS)
    def test_all_strings(self, name, fset):
        for entry in fset:
            assert isinstance(entry, str), f"{name} entry {entry!r} is not a str"

    @pytest.mark.parametrize("name,fset", ALL_SETS)
    def test_all_normalised(self, name, fset):
        for entry in fset:
            assert entry == _normalise_col(entry), (
                f"{name} entry {entry!r} is not normalised — "
                f"expected {_normalise_col(entry)!r}"
            )

    def test_no_overlap_asset_id_and_label(self):
        overlap = ASSET_ID_NAMES & ASSET_LABEL_NAMES
        assert not overlap, f"Unexpected overlap between ASSET_ID and ASSET_LABEL: {overlap}"

    def test_no_overlap_return_and_volatility(self):
        overlap = RETURN_NAMES & VOLATILITY_NAMES
        assert not overlap, f"Unexpected overlap between RETURN and VOLATILITY: {overlap}"

    def test_ohlc_not_in_return_names(self):
        # "close", "open" etc. must not be misclassified as returns
        assert "close" not in RETURN_NAMES
        assert "open" not in RETURN_NAMES


# ── Detector fixtures ─────────────────────────────────────────────────────────

def _yahoo_snapshot_df(n: int = 50) -> pd.DataFrame:
    """
    Canonical Yahoo Finance global markets snapshot shape.

    Columns: ticker, shortName, asset_class, sector, ytd_return,
    one_year_return, volatility, sharpe_ratio, analyst_upside_pct,
    week_52_position, composite_score, marketCap.
    """
    rng = np.random.default_rng(42)
    classes = ["Equity", "ETF", "Bond", "Crypto"]
    sectors = ["Technology", "Financials", "Healthcare", "Energy", "Consumer"]
    return pd.DataFrame({
        "ticker":              [f"TK{i:03d}" for i in range(n)],
        "shortName":           [f"Asset {i}" for i in range(n)],
        "asset_class":         rng.choice(classes, n),
        "sector":              rng.choice(sectors, n),
        "ytd_return":          rng.uniform(-0.3, 0.5, n),
        "one_year_return":     rng.uniform(-0.4, 0.8, n),
        "volatility":          rng.uniform(0.05, 0.6, n),
        "sharpe_ratio":        rng.uniform(-1.0, 3.0, n),
        "analyst_upside_pct":  rng.uniform(-0.1, 0.4, n),
        "week_52_position":    rng.uniform(0.0, 1.0, n),
        "composite_score":     rng.uniform(0.0, 100.0, n),
        "marketCap":           rng.integers(1_000_000, 1_000_000_000_000, n).astype(float),
    })


def _minimum_snapshot_df(n: int = 30) -> pd.DataFrame:
    """Minimal snapshot: return + volatility + sharpe only."""
    rng = np.random.default_rng(7)
    return pd.DataFrame({
        "ytd_return":   rng.uniform(-0.3, 0.5, n),
        "volatility":   rng.uniform(0.05, 0.6, n),
        "sharpe_ratio": rng.uniform(-1.0, 3.0, n),
    })


def _return_only_df(n: int = 30) -> pd.DataFrame:
    """Only a single return column — should fall back to generic."""
    rng = np.random.default_rng(9)
    return pd.DataFrame({
        "ytd_return": rng.uniform(-0.3, 0.5, n),
        "random_col": rng.normal(0, 1, n),
    })


def _telco_churn_df(n: int = 100) -> pd.DataFrame:
    """Telco churn dataset — should not classify as financial."""
    rng = np.random.default_rng(3)
    return pd.DataFrame({
        "customer_id":      [f"CUS{i}" for i in range(n)],
        "tenure_months":    rng.integers(1, 72, n),
        "monthly_charges":  rng.uniform(20, 120, n),
        "total_charges":    rng.uniform(100, 8000, n),
        "contract":         rng.choice(["Month-to-month", "One year", "Two year"], n),
        "churned":          rng.integers(0, 2, n),
    })


def _ohlc_timeseries_df(n: int = 252) -> pd.DataFrame:
    """Daily OHLC timeseries — should classify as financial_markets_timeseries."""
    rng = np.random.default_rng(1)
    dates = pd.date_range("2024-01-02", periods=n, freq="B")
    price = 100.0 + rng.normal(0, 1, n).cumsum()
    return pd.DataFrame({
        "date":   dates,
        "open":   price + rng.uniform(-0.5, 0.5, n),
        "high":   price + rng.uniform(0.0, 1.0, n),
        "low":    price - rng.uniform(0.0, 1.0, n),
        "close":  price,
        "volume": rng.integers(1_000_000, 50_000_000, n).astype(float),
    })


# ── detect_dataset_context ────────────────────────────────────────────────────

class TestDetectDatasetContext:

    # ── Snapshot classification ───────────────────────────────────────────────

    def test_yahoo_snapshot_is_snapshot(self):
        ctx = detect_dataset_context(_yahoo_snapshot_df())
        assert ctx.dataset_type == FINANCIAL_MARKETS_SNAPSHOT

    def test_yahoo_snapshot_confidence_high(self):
        ctx = detect_dataset_context(_yahoo_snapshot_df())
        assert ctx.confidence >= 0.85

    def test_minimum_snapshot_is_snapshot(self):
        ctx = detect_dataset_context(_minimum_snapshot_df())
        assert ctx.dataset_type == FINANCIAL_MARKETS_SNAPSHOT

    def test_minimum_snapshot_confidence_at_threshold(self):
        ctx = detect_dataset_context(_minimum_snapshot_df())
        assert ctx.confidence >= CONFIDENCE_THRESHOLD

    def test_minimum_snapshot_confidence_below_yahoo(self):
        min_ctx   = detect_dataset_context(_minimum_snapshot_df())
        yahoo_ctx = detect_dataset_context(_yahoo_snapshot_df())
        assert min_ctx.confidence < yahoo_ctx.confidence

    def test_snapshot_matched_signals_non_empty(self):
        ctx = detect_dataset_context(_yahoo_snapshot_df())
        assert len(ctx.matched_signals) >= 3

    def test_snapshot_matched_signals_mention_return(self):
        ctx = detect_dataset_context(_yahoo_snapshot_df())
        assert any("return_period" in s for s in ctx.matched_signals)

    def test_snapshot_matched_signals_mention_volatility(self):
        ctx = detect_dataset_context(_yahoo_snapshot_df())
        assert any("volatility" in s for s in ctx.matched_signals)

    # ── Fallback: return-only ─────────────────────────────────────────────────

    def test_return_only_is_generic(self):
        ctx = detect_dataset_context(_return_only_df())
        assert ctx.dataset_type == GENERIC_TABULAR

    def test_return_only_matched_signals_mentions_fallback(self):
        ctx = detect_dataset_context(_return_only_df())
        assert any("No supported" in s for s in ctx.matched_signals)

    # ── Fallback: telco churn ─────────────────────────────────────────────────

    def test_churn_dataset_is_generic(self):
        ctx = detect_dataset_context(_telco_churn_df())
        assert ctx.dataset_type == GENERIC_TABULAR

    def test_churn_dataset_not_snapshot(self):
        ctx = detect_dataset_context(_telco_churn_df())
        assert ctx.dataset_type != FINANCIAL_MARKETS_SNAPSHOT

    def test_churn_dataset_not_timeseries(self):
        ctx = detect_dataset_context(_telco_churn_df())
        assert ctx.dataset_type != FINANCIAL_MARKETS_TIMESERIES

    # ── Edge cases ────────────────────────────────────────────────────────────

    def test_empty_dataframe_is_generic(self):
        ctx = detect_dataset_context(pd.DataFrame())
        assert ctx.dataset_type == GENERIC_TABULAR

    def test_empty_dataframe_no_raise(self):
        ctx = detect_dataset_context(pd.DataFrame())
        assert isinstance(ctx, DatasetContext)

    def test_single_column_is_generic(self):
        ctx = detect_dataset_context(pd.DataFrame({"a": [1, 2, 3]}))
        assert ctx.dataset_type == GENERIC_TABULAR

    def test_single_column_no_raise(self):
        ctx = detect_dataset_context(pd.DataFrame({"a": [1, 2, 3]}))
        assert isinstance(ctx, DatasetContext)

    # ── Timeseries classification ─────────────────────────────────────────────

    def test_ohlc_timeseries_is_timeseries(self):
        ctx = detect_dataset_context(_ohlc_timeseries_df())
        assert ctx.dataset_type == FINANCIAL_MARKETS_TIMESERIES

    def test_timeseries_confidence_high(self):
        ctx = detect_dataset_context(_ohlc_timeseries_df())
        assert ctx.confidence >= 0.65

    def test_timeseries_matched_signals_mention_datetime(self):
        ctx = detect_dataset_context(_ohlc_timeseries_df())
        assert any(
            "time axis" in s.lower() or "datetime" in s.lower()
            for s in ctx.matched_signals
        )

    def test_timeseries_matched_signals_mention_ohlc(self):
        ctx = detect_dataset_context(_ohlc_timeseries_df())
        assert any("OHLC" in s or "ohlc" in s for s in ctx.matched_signals)

    def test_timeseries_warnings_describe_finance_panel(self):
        ctx = detect_dataset_context(_ohlc_timeseries_df())
        assert any("financial markets time-series" in w.lower() for w in ctx.warnings)

    def test_etf_fixture_classifies_as_financial_timeseries(self):
        path = Path(__file__).resolve().parent / "fixtures" / "etf_prices_sample.csv"
        df = pd.read_csv(path, parse_dates=["price_date"])
        ctx = detect_dataset_context(df)
        assert ctx.dataset_type == FINANCIAL_MARKETS_TIMESERIES

    def test_snapshot_without_datetime_not_timeseries(self):
        ctx = detect_dataset_context(_yahoo_snapshot_df())
        assert ctx.dataset_type != FINANCIAL_MARKETS_TIMESERIES

    # ── Determinism ───────────────────────────────────────────────────────────

    def test_detector_is_deterministic(self):
        df = _yahoo_snapshot_df()
        ctx_a = detect_dataset_context(df)
        ctx_b = detect_dataset_context(df)
        assert ctx_a == ctx_b

    def test_detector_deterministic_generic(self):
        df = _telco_churn_df()
        assert detect_dataset_context(df) == detect_dataset_context(df)

    # ── Warnings ──────────────────────────────────────────────────────────────

    def test_mixed_asset_class_produces_warning(self):
        ctx = detect_dataset_context(_yahoo_snapshot_df())
        # yahoo df has 4 asset classes → warning must be present
        assert any("mixed asset class" in w.lower() for w in ctx.warnings)

    def test_single_asset_class_no_mixed_warning(self):
        df = _minimum_snapshot_df()  # no asset_class column at all
        ctx = detect_dataset_context(df)
        assert not any("mixed asset class" in w.lower() for w in ctx.warnings)

    def test_single_asset_class_value_no_mixed_warning(self):
        rng = np.random.default_rng(5)
        n = 20
        df = pd.DataFrame({
            "ytd_return":   rng.uniform(-0.2, 0.3, n),
            "volatility":   rng.uniform(0.1, 0.4, n),
            "sharpe_ratio": rng.uniform(0.0, 2.0, n),
            "asset_class":  ["Equity"] * n,  # only one class
        })
        ctx = detect_dataset_context(df)
        assert not any("mixed asset class" in w.lower() for w in ctx.warnings)


# ── resolve_semantic_roles ────────────────────────────────────────────────────

class TestResolveSemanticRoles:

    def test_covers_all_columns(self):
        df = _yahoo_snapshot_df()
        roles = resolve_semantic_roles(df, FINANCIAL_MARKETS_SNAPSHOT)
        assert set(roles.keys()) == set(df.columns)

    def test_no_none_values(self):
        df = _yahoo_snapshot_df()
        roles = resolve_semantic_roles(df, FINANCIAL_MARKETS_SNAPSHOT)
        assert all(v is not None for v in roles.values())

    def test_no_empty_string_values(self):
        df = _yahoo_snapshot_df()
        roles = resolve_semantic_roles(df, FINANCIAL_MARKETS_SNAPSHOT)
        assert all(v != "" for v in roles.values())

    def test_known_roles_assigned(self):
        df = _yahoo_snapshot_df()
        roles = resolve_semantic_roles(df, FINANCIAL_MARKETS_SNAPSHOT)
        assert roles["ytd_return"]    == "return_period"
        assert roles["volatility"]    == "volatility"
        assert roles["sharpe_ratio"]  == "sharpe_ratio"
        assert roles["asset_class"]   == "asset_class"
        assert roles["sector"]        == "sector"
        assert roles["ticker"]        == "asset_id"
        assert roles["shortName"]     == "asset_label"
        assert roles["marketCap"]     == "size_metric"

    def test_unknown_columns_get_unknown(self):
        df = pd.DataFrame({
            "ytd_return":    [0.1, 0.2],
            "volatility":    [0.2, 0.3],
            "sharpe_ratio":  [1.0, 1.5],
            "widget_count":  [5, 10],   # unknown
            "random_field":  ["a", "b"],  # unknown
        })
        roles = resolve_semantic_roles(df, FINANCIAL_MARKETS_SNAPSHOT)
        assert roles["widget_count"]  == "unknown"
        assert roles["random_field"]  == "unknown"

    def test_empty_dataframe_returns_empty_dict(self):
        roles = resolve_semantic_roles(pd.DataFrame(), GENERIC_TABULAR)
        assert roles == {}

    def test_generic_tabular_context_still_maps_roles(self):
        df = _telco_churn_df()
        roles = resolve_semantic_roles(df, GENERIC_TABULAR)
        assert set(roles.keys()) == set(df.columns)
        # churn columns are unknown
        assert roles["customer_id"]   == "unknown"
        assert roles["churned"]       == "unknown"

    def test_roles_via_detector_match_direct_call(self):
        """Roles embedded in DatasetContext equal a direct resolve_semantic_roles call."""
        df = _yahoo_snapshot_df()
        ctx = detect_dataset_context(df)
        direct = resolve_semantic_roles(df, ctx.dataset_type)
        assert ctx.semantic_roles == direct


# ── get_dataset_summary — dataset_context field ───────────────────────────────

class TestGetDatasetSummaryContext:
    """
    Verify that get_dataset_summary() includes a well-formed dataset_context
    field and that all pre-existing summary keys are still present.
    """

    def setup_method(self):
        from app.services.analysis.orchestrator import get_dataset_summary
        self._get = get_dataset_summary

    # ── Backward-compatibility: existing keys survive ─────────────────────────

    def test_existing_key_rows(self):
        s = self._get(_yahoo_snapshot_df())
        assert "rows" in s

    def test_existing_key_columns(self):
        s = self._get(_yahoo_snapshot_df())
        assert "columns" in s

    def test_existing_key_numeric_cols(self):
        s = self._get(_yahoo_snapshot_df())
        assert "numeric_cols" in s

    def test_existing_key_categorical_cols(self):
        s = self._get(_yahoo_snapshot_df())
        assert "categorical_cols" in s

    def test_existing_key_datetime_cols(self):
        s = self._get(_yahoo_snapshot_df())
        assert "datetime_cols" in s

    def test_existing_key_missing_pct(self):
        s = self._get(_yahoo_snapshot_df())
        assert "missing_pct" in s

    def test_existing_key_domain(self):
        s = self._get(_yahoo_snapshot_df())
        assert "domain" in s

    # ── New key present ───────────────────────────────────────────────────────

    def test_dataset_context_key_present(self):
        s = self._get(_yahoo_snapshot_df())
        assert "dataset_context" in s

    def test_dataset_context_is_dict(self):
        s = self._get(_yahoo_snapshot_df())
        assert isinstance(s["dataset_context"], dict)

    # ── dataset_context sub-fields ────────────────────────────────────────────

    def test_dataset_type_field_present(self):
        s = self._get(_yahoo_snapshot_df())
        assert "dataset_type" in s["dataset_context"]

    def test_confidence_field_present(self):
        s = self._get(_yahoo_snapshot_df())
        assert "confidence" in s["dataset_context"]

    def test_matched_signals_field_present(self):
        s = self._get(_yahoo_snapshot_df())
        assert "matched_signals" in s["dataset_context"]

    def test_semantic_roles_field_present(self):
        s = self._get(_yahoo_snapshot_df())
        assert "semantic_roles" in s["dataset_context"]

    def test_warnings_field_present(self):
        s = self._get(_yahoo_snapshot_df())
        assert "warnings" in s["dataset_context"]

    # ── Yahoo snapshot classification ─────────────────────────────────────────

    def test_snapshot_dataset_type(self):
        s = self._get(_yahoo_snapshot_df())
        assert s["dataset_context"]["dataset_type"] == FINANCIAL_MARKETS_SNAPSHOT

    def test_snapshot_confidence_above_threshold(self):
        s = self._get(_yahoo_snapshot_df())
        assert s["dataset_context"]["confidence"] >= CONFIDENCE_THRESHOLD

    def test_snapshot_semantic_roles_covers_all_columns(self):
        df = _yahoo_snapshot_df()
        s = self._get(df)
        assert set(s["dataset_context"]["semantic_roles"].keys()) == set(df.columns)

    # ── Generic tabular classification ────────────────────────────────────────

    def test_generic_dataset_type(self):
        df = pd.DataFrame({"age": [25, 30], "income": [50000, 70000]})
        s = self._get(df)
        assert s["dataset_context"]["dataset_type"] == GENERIC_TABULAR

    def test_generic_semantic_roles_covers_all_columns(self):
        df = pd.DataFrame({"age": [25, 30], "income": [50000, 70000]})
        s = self._get(df)
        assert set(s["dataset_context"]["semantic_roles"].keys()) == set(df.columns)

    # ── JSON-friendliness (no tuples) ─────────────────────────────────────────

    def test_matched_signals_is_list(self):
        s = self._get(_yahoo_snapshot_df())
        assert isinstance(s["dataset_context"]["matched_signals"], list)

    def test_warnings_is_list(self):
        s = self._get(_yahoo_snapshot_df())
        assert isinstance(s["dataset_context"]["warnings"], list)

    def test_semantic_roles_is_dict(self):
        s = self._get(_yahoo_snapshot_df())
        assert isinstance(s["dataset_context"]["semantic_roles"], dict)

    def test_confidence_is_float(self):
        s = self._get(_yahoo_snapshot_df())
        assert isinstance(s["dataset_context"]["confidence"], float)

    def test_dataset_type_is_str(self):
        s = self._get(_yahoo_snapshot_df())
        assert isinstance(s["dataset_context"]["dataset_type"], str)

    # ── Edge cases ────────────────────────────────────────────────────────────

    def test_empty_dataframe_no_raise(self):
        s = self._get(pd.DataFrame())
        assert s["dataset_context"]["dataset_type"] == GENERIC_TABULAR

    def test_single_column_no_raise(self):
        s = self._get(pd.DataFrame({"x": [1, 2, 3]}))
        assert "dataset_context" in s
