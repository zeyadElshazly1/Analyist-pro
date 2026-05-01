"""Integration tests: domain packs wired into analyze_dataset."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from app.services.analysis.orchestrator import analyze_dataset
from app.services.dataset_context import (
    CONFIDENCE_THRESHOLD,
    FINANCIAL_MARKETS_SNAPSHOT,
    GENERIC_TABULAR,
    detect_dataset_context,
)


def _integration_financial_snapshot_df(n: int = 45) -> pd.DataFrame:
    """Enough Yahoo-style snapshot columns for confident financial_markets_snapshot classification."""
    rng = np.random.default_rng(101)
    return pd.DataFrame(
        {
            "ticker": [f"TK{i:03d}" for i in range(n)],
            "ytd_return": rng.uniform(-0.25, 0.35, n),
            "volatility": rng.uniform(0.08, 0.55, n),
            "sharpe_ratio": rng.uniform(-0.5, 2.5, n),
        }
    )


def _below_snapshot_threshold_df(n: int = 40) -> pd.DataFrame:
    """Strong return signal only — snapshot score stays below CONFIDENCE_THRESHOLD."""
    rng = np.random.default_rng(202)
    return pd.DataFrame(
        {
            "ytd_return": rng.uniform(-0.25, 0.35, n),
            "noise_feature": rng.normal(0.0, 1.0, n),
        }
    )


# Distinct SnapshotFinanceInsightPack titles — avoid collisions with generic pipeline titles.
_DOMAIN_PACK_MARKERS = frozenset(
    {
        "Top return leaders",
        "Highest volatility assets",
        "Best risk-adjusted performers",
    }
)


def test_financial_snapshot_triggers_detected_above_threshold():
    df = _integration_financial_snapshot_df()
    ctx = detect_dataset_context(df)
    assert ctx.dataset_type == FINANCIAL_MARKETS_SNAPSHOT
    assert ctx.confidence >= CONFIDENCE_THRESHOLD


def test_financial_snapshot_analyze_includes_domain_insights():
    df = _integration_financial_snapshot_df()
    insights, narrative = analyze_dataset(df)

    assert isinstance(insights, list)
    assert isinstance(narrative, str)
    titles = {ins.get("title") for ins in insights}
    assert titles & _DOMAIN_PACK_MARKERS


def test_generic_tabular_no_domain_pack_marker_titles():
    df = pd.DataFrame(
        {"feature_x": np.arange(40), "feature_y": np.random.default_rng(1).normal(0, 1, 40)}
    )
    ctx = detect_dataset_context(df)
    assert ctx.dataset_type == GENERIC_TABULAR

    insights, _ = analyze_dataset(df)
    titles = {ins.get("title") for ins in insights}
    assert not (titles & _DOMAIN_PACK_MARKERS)


def test_below_snapshot_threshold_skips_domain_insights():
    df = _below_snapshot_threshold_df()
    ctx = detect_dataset_context(df)
    assert ctx.dataset_type == GENERIC_TABULAR

    insights, narrative = analyze_dataset(df)
    assert isinstance(insights, list)
    assert isinstance(narrative, str)
    titles = {ins.get("title") for ins in insights}
    assert not (titles & _DOMAIN_PACK_MARKERS)


def test_analyze_dataset_return_type_stable():
    df = _integration_financial_snapshot_df()
    out = analyze_dataset(df)
    assert isinstance(out, tuple)
    assert len(out) == 2
    insights, narrative = out
    assert isinstance(insights, list)
    assert isinstance(narrative, str)


def test_snapshot_two_rows_analyze_dataset_completes():
    """Tiny snapshot-shaped frame yields empty or sparse domain insights without errors."""
    rng = np.random.default_rng(303)
    df = pd.DataFrame(
        {
            "symbol": ["A", "B"],
            "ytd_return": rng.uniform(-0.1, 0.1, 2),
            "volatility": rng.uniform(0.1, 0.3, 2),
            "sharpe_ratio": rng.uniform(0.8, 1.4, 2),
        }
    )
    ctx = detect_dataset_context(df)
    assert ctx.dataset_type == FINANCIAL_MARKETS_SNAPSHOT

    insights, narrative = analyze_dataset(df)
    assert isinstance(insights, list)
    assert isinstance(narrative, str)


def test_domain_pack_empty_list_does_not_break_analyze(monkeypatch: pytest.MonkeyPatch):
    df = _integration_financial_snapshot_df()

    def _empty(_df: pd.DataFrame, _ctx):  # type: ignore[no-untyped-def]
        return []

    monkeypatch.setattr("app.services.analysis.orchestrator.run_domain_pack", _empty)

    insights, narrative = analyze_dataset(df)
    assert isinstance(insights, list)
    assert isinstance(narrative, str)
