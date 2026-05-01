"""
Tests for the domain pack registry infrastructure.

Coverage:
  - All public symbols import cleanly from app.services.analysis.domain
  - get_domain_pack returns correct pack or None for every dataset_type
  - run_domain_pack returns [] for all V1 types
  - get_suppression_keys returns empty set for all V1 types
  - No function raises on unknown types, generic_tabular, or empty DataFrames
  - DomainInsightPack base class defaults are correct
  - SnapshotFinancePlaceholderPack has the right dataset_type attribute
"""
from __future__ import annotations

import pandas as pd
import numpy as np
import pytest

from app.services.analysis.domain import (
    DomainInsightPack,
    DOMAIN_PACKS,
    SnapshotFinancePlaceholderPack,
    get_domain_pack,
    get_suppression_keys,
    run_domain_pack,
)
from app.services.dataset_context import (
    DatasetContext,
    FINANCIAL_MARKETS_SNAPSHOT,
    FINANCIAL_MARKETS_TIMESERIES,
    GENERIC_TABULAR,
    detect_dataset_context,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _snapshot_context(roles: dict | None = None) -> DatasetContext:
    return DatasetContext(
        dataset_type=FINANCIAL_MARKETS_SNAPSHOT,
        confidence=0.90,
        matched_signals=("return_period column detected (ytd_return)",),
        semantic_roles=roles or {"ytd_return": "return_period"},
        warnings=(),
    )


def _timeseries_context() -> DatasetContext:
    return DatasetContext(
        dataset_type=FINANCIAL_MARKETS_TIMESERIES,
        confidence=0.90,
        matched_signals=("Datetime column detected",),
        semantic_roles={"date": "unknown", "close": "ohlc_price"},
        warnings=(),
    )


def _generic_context() -> DatasetContext:
    return DatasetContext(
        dataset_type=GENERIC_TABULAR,
        confidence=1.0,
        matched_signals=(),
        semantic_roles={"customer_id": "unknown"},
        warnings=(),
    )


def _snapshot_df(n: int = 20) -> pd.DataFrame:
    rng = np.random.default_rng(0)
    return pd.DataFrame({
        "ticker":       [f"TK{i}" for i in range(n)],
        "ytd_return":   rng.uniform(-0.3, 0.5, n),
        "volatility":   rng.uniform(0.05, 0.6, n),
        "sharpe_ratio": rng.uniform(-1.0, 3.0, n),
    })


# ── Import sanity ─────────────────────────────────────────────────────────────

class TestImports:
    def test_domain_insight_pack_importable(self):
        assert DomainInsightPack is not None

    def test_domain_packs_dict_importable(self):
        assert isinstance(DOMAIN_PACKS, dict)

    def test_placeholder_pack_importable(self):
        assert SnapshotFinancePlaceholderPack is not None

    def test_get_domain_pack_importable(self):
        assert callable(get_domain_pack)

    def test_run_domain_pack_importable(self):
        assert callable(run_domain_pack)

    def test_get_suppression_keys_importable(self):
        assert callable(get_suppression_keys)


# ── DomainInsightPack base class ──────────────────────────────────────────────

class TestDomainInsightPackBase:
    def test_base_run_returns_empty_list(self):
        pack = DomainInsightPack()
        result = pack.run(pd.DataFrame(), _generic_context())
        assert result == []

    def test_base_suppression_keys_returns_empty_set(self):
        pack = DomainInsightPack()
        result = pack.suppression_keys(_generic_context())
        assert result == set()

    def test_base_dataset_type_is_empty_string(self):
        assert DomainInsightPack.dataset_type == ""

    def test_base_run_returns_list_type(self):
        pack = DomainInsightPack()
        assert isinstance(pack.run(pd.DataFrame(), _generic_context()), list)

    def test_base_suppression_keys_returns_set_type(self):
        pack = DomainInsightPack()
        assert isinstance(pack.suppression_keys(_generic_context()), set)


# ── SnapshotFinancePlaceholderPack ────────────────────────────────────────────

class TestSnapshotPlaceholderPack:
    def test_dataset_type_attribute(self):
        assert SnapshotFinancePlaceholderPack.dataset_type == FINANCIAL_MARKETS_SNAPSHOT

    def test_run_returns_empty_list(self):
        pack = SnapshotFinancePlaceholderPack()
        result = pack.run(_snapshot_df(), _snapshot_context())
        assert result == []

    def test_suppression_keys_returns_empty_set(self):
        pack = SnapshotFinancePlaceholderPack()
        assert pack.suppression_keys(_snapshot_context()) == set()

    def test_run_empty_dataframe(self):
        pack = SnapshotFinancePlaceholderPack()
        assert pack.run(pd.DataFrame(), _snapshot_context()) == []

    def test_is_subclass_of_base(self):
        assert issubclass(SnapshotFinancePlaceholderPack, DomainInsightPack)


# ── DOMAIN_PACKS registry dict ────────────────────────────────────────────────

class TestDomainPacksDict:
    def test_snapshot_is_registered(self):
        assert FINANCIAL_MARKETS_SNAPSHOT in DOMAIN_PACKS

    def test_timeseries_not_registered(self):
        assert FINANCIAL_MARKETS_TIMESERIES not in DOMAIN_PACKS

    def test_generic_not_registered(self):
        assert GENERIC_TABULAR not in DOMAIN_PACKS

    def test_registered_pack_is_domain_insight_pack(self):
        pack = DOMAIN_PACKS[FINANCIAL_MARKETS_SNAPSHOT]
        assert isinstance(pack, DomainInsightPack)

    def test_registered_pack_is_placeholder(self):
        pack = DOMAIN_PACKS[FINANCIAL_MARKETS_SNAPSHOT]
        assert isinstance(pack, SnapshotFinancePlaceholderPack)


# ── get_domain_pack ───────────────────────────────────────────────────────────

class TestGetDomainPack:
    def test_snapshot_returns_pack(self):
        pack = get_domain_pack(FINANCIAL_MARKETS_SNAPSHOT)
        assert pack is not None

    def test_snapshot_returns_placeholder(self):
        pack = get_domain_pack(FINANCIAL_MARKETS_SNAPSHOT)
        assert isinstance(pack, SnapshotFinancePlaceholderPack)

    def test_timeseries_returns_none(self):
        assert get_domain_pack(FINANCIAL_MARKETS_TIMESERIES) is None

    def test_generic_returns_none(self):
        assert get_domain_pack(GENERIC_TABULAR) is None

    def test_unknown_type_returns_none(self):
        assert get_domain_pack("completely_unknown_type") is None

    def test_empty_string_returns_none(self):
        assert get_domain_pack("") is None


# ── run_domain_pack ───────────────────────────────────────────────────────────

class TestRunDomainPack:
    def test_snapshot_returns_list(self):
        result = run_domain_pack(_snapshot_df(), _snapshot_context())
        assert isinstance(result, list)

    def test_snapshot_placeholder_returns_empty(self):
        result = run_domain_pack(_snapshot_df(), _snapshot_context())
        assert result == []

    def test_timeseries_returns_empty(self):
        df = pd.DataFrame({"close": [100.0, 101.0]})
        result = run_domain_pack(df, _timeseries_context())
        assert result == []

    def test_generic_returns_empty(self):
        df = pd.DataFrame({"a": [1, 2, 3]})
        result = run_domain_pack(df, _generic_context())
        assert result == []

    def test_unknown_type_returns_empty(self):
        ctx = DatasetContext(dataset_type="no_such_domain", confidence=1.0)
        result = run_domain_pack(pd.DataFrame(), ctx)
        assert result == []

    def test_empty_dataframe_snapshot_no_raise(self):
        result = run_domain_pack(pd.DataFrame(), _snapshot_context())
        assert result == []

    def test_empty_dataframe_generic_no_raise(self):
        result = run_domain_pack(pd.DataFrame(), _generic_context())
        assert result == []


# ── get_suppression_keys ──────────────────────────────────────────────────────

class TestGetSuppressionKeys:
    def test_snapshot_returns_set(self):
        result = get_suppression_keys(_snapshot_context())
        assert isinstance(result, set)

    def test_snapshot_placeholder_returns_empty_set(self):
        assert get_suppression_keys(_snapshot_context()) == set()

    def test_timeseries_returns_empty_set(self):
        assert get_suppression_keys(_timeseries_context()) == set()

    def test_generic_returns_empty_set(self):
        assert get_suppression_keys(_generic_context()) == set()

    def test_unknown_type_returns_empty_set(self):
        ctx = DatasetContext(dataset_type="no_such_domain", confidence=1.0)
        assert get_suppression_keys(ctx) == set()


# ── Integration: detector → registry ─────────────────────────────────────────

class TestDetectorToRegistry:
    """Verify that a real detect_dataset_context() result flows into the registry."""

    def _yahoo_df(self, n: int = 30) -> pd.DataFrame:
        rng = np.random.default_rng(1)
        return pd.DataFrame({
            "ticker":       [f"TK{i}" for i in range(n)],
            "ytd_return":   rng.uniform(-0.3, 0.5, n),
            "volatility":   rng.uniform(0.05, 0.6, n),
            "sharpe_ratio": rng.uniform(-1.0, 3.0, n),
        })

    def test_detected_snapshot_has_registered_pack(self):
        ctx = detect_dataset_context(self._yahoo_df())
        assert ctx.dataset_type == FINANCIAL_MARKETS_SNAPSHOT
        assert get_domain_pack(ctx.dataset_type) is not None

    def test_detected_snapshot_run_returns_list(self):
        df = self._yahoo_df()
        ctx = detect_dataset_context(df)
        assert isinstance(run_domain_pack(df, ctx), list)

    def test_detected_snapshot_suppression_keys_is_set(self):
        ctx = detect_dataset_context(self._yahoo_df())
        assert isinstance(get_suppression_keys(ctx), set)

    def test_generic_detected_has_no_pack(self):
        df = pd.DataFrame({"age": [25, 30], "income": [50000, 70000]})
        ctx = detect_dataset_context(df)
        assert ctx.dataset_type == GENERIC_TABULAR
        assert get_domain_pack(ctx.dataset_type) is None
