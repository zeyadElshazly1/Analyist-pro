"""
Tests for the dataset_context schema and signal definitions.

Coverage:
  - DatasetContext dataclass construction and immutability
  - CONFIDENCE_THRESHOLD and dataset type constants
  - generic_tabular_context convenience constructor
  - _normalise_col handles mixed casing, underscores, hyphens, spaces
  - role_for_column maps canonical Yahoo snapshot column names correctly
  - role_for_column returns "unknown" for unrecognised columns
  - frozensets are non-empty and contain only strings
"""
from __future__ import annotations

import pytest

from app.services.dataset_context import (
    DatasetContext,
    CONFIDENCE_THRESHOLD,
    FINANCIAL_MARKETS_SNAPSHOT,
    FINANCIAL_MARKETS_TIMESERIES,
    GENERIC_TABULAR,
    generic_tabular_context,
    _normalise_col,
    role_for_column,
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
