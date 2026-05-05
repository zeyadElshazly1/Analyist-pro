"""Tests for finance-aware insight suppression (Task 73B)."""
from __future__ import annotations

import numpy as np
import pandas as pd

from app.services.analysis.insight_suppression import (
    _PRICE_OVERLAP_FINDING_TITLE,
    suppress_for_dataset_context,
)
from app.services.analysis.orchestrator import analyze_dataset
from app.services.dataset_context import FINANCIAL_MARKETS_SNAPSHOT, GENERIC_TABULAR, detect_dataset_context
from app.services.dataset_context.schema import DatasetContext


def _snapshot_ctx() -> DatasetContext:
    return DatasetContext(dataset_type=FINANCIAL_MARKETS_SNAPSHOT, confidence=0.9, semantic_roles={})


def test_generic_tabular_returns_same_object() -> None:
    ctx = DatasetContext(dataset_type=GENERIC_TABULAR, confidence=1.0, semantic_roles={})
    insights: list[dict] = [
        {"type": "correlation", "col_a": "open", "col_b": "dayLow", "title": "x"},
    ]
    out = suppress_for_dataset_context(insights, ctx)
    assert out is insights


def test_snapshot_suppresses_price_only_correlations() -> None:
    ctx = _snapshot_ctx()
    insights = [
        {"type": "correlation", "col_a": "open", "col_b": "dayLow", "title": "R1"},
        {"type": "correlation", "col_a": "open", "col_b": "dayHigh", "title": "R2"},
        {"type": "correlation", "col_a": "ytd_return", "col_b": "open", "title": "Keep"},
        {
            "type": "segment",
            "title": "Top return leaders",
            "domain": FINANCIAL_MARKETS_SNAPSHOT,
            "finding": "x",
        },
    ]
    out = suppress_for_dataset_context(insights, ctx)
    titles = [i.get("title") for i in out]
    assert "R1" not in titles and "R2" not in titles
    assert "Keep" in titles
    assert "Top return leaders" in titles


def test_snapshot_suppresses_multicollinearity_mostly_price() -> None:
    ctx = _snapshot_ctx()
    ins = {
        "type": "multicollinearity",
        "title": "Multicollinearity detected (3 columns)",
        "evidence": "VIF scores: open (VIF=12.0), dayLow (VIF=11.0), dayHigh (VIF=10.0)",
        "finding": "f",
        "action": "a",
    }
    out = suppress_for_dataset_context([ins], ctx)
    assert out == []


def test_snapshot_keeps_multicollinearity_when_mixed_columns() -> None:
    ctx = _snapshot_ctx()
    ins = {
        "type": "multicollinearity",
        "title": "Multicollinearity detected (3 columns)",
        "evidence": "VIF scores: open (VIF=12.0), ytd_return (VIF=11.0), volatility (VIF=10.0)",
        "finding": "f",
        "action": "a",
    }
    out = suppress_for_dataset_context([ins], ctx)
    assert len(out) == 1


def test_snapshot_suppresses_moving_average_and_price_derived_correlations() -> None:
    ctx = _snapshot_ctx()
    insights = [
        {"type": "correlation", "col_a": "sma_50", "col_b": "currentPrice", "title": "M1"},
        {"type": "correlation", "col_a": "fiftyDayAverage", "col_b": "price_vs_sma200_pct", "title": "M2"},
        {"type": "correlation", "col_a": "ytd_return", "col_b": "volatility", "title": "Keep"},
    ]
    out = suppress_for_dataset_context(insights, ctx)
    titles = [i.get("title") for i in out]
    assert "Keep" in titles
    assert _PRICE_OVERLAP_FINDING_TITLE in titles
def test_caveat_added_when_two_or_more_price_noise_removed() -> None:
    ctx = _snapshot_ctx()
    insights = [
        {"type": "correlation", "col_a": "open", "col_b": "dayLow", "title": "A"},
        {"type": "correlation", "col_a": "dayHigh", "col_b": "currentPrice", "title": "B"},
    ]
    out = suppress_for_dataset_context(insights, ctx)
    caveat = next((i for i in out if i.get("title") == _PRICE_OVERLAP_FINDING_TITLE), None)
    assert caveat is not None
    assert caveat.get("type") == "multicollinearity"
    assert caveat.get("severity") == "medium"
    assert caveat.get("confidence") == 85
    assert caveat.get("domain") == FINANCIAL_MARKETS_SNAPSHOT
    assert isinstance(caveat.get("columns_used"), list)


def test_caveat_not_added_when_only_one_removal() -> None:
    ctx = _snapshot_ctx()
    insights = [
        {"type": "correlation", "col_a": "open", "col_b": "dayLow", "title": "A"},
        {"type": "correlation", "col_a": "ytd_return", "col_b": "volatility", "title": "K"},
    ]
    out = suppress_for_dataset_context(insights, ctx)
    assert _PRICE_OVERLAP_FINDING_TITLE not in {i.get("title") for i in out}


def test_snapshot_drops_trends() -> None:
    ctx = _snapshot_ctx()
    insights = [
        {"type": "trend", "title": "Trend detected: x (upward)", "finding": "f"},
    ]
    assert suppress_for_dataset_context(insights, ctx) == []


def test_snapshot_drops_asset_id_high_cardinality() -> None:
    ctx = _snapshot_ctx()
    insights = [
        {
            "type": "data_quality",
            "title": "High-cardinality column: ticker",
            "finding": "f",
            "action": "a",
        },
        {
            "type": "data_quality",
            "title": "High-cardinality column: region_bucket",
            "finding": "f",
            "action": "a",
        },
    ]
    out = suppress_for_dataset_context(insights, ctx)
    assert len(out) == 1
    assert "region_bucket" in out[0].get("title", "")


def _snapshot_with_price_overlap_df(n: int = 80) -> pd.DataFrame:
    """Snapshot-classified frame with tightly linked price columns to surface generic correlations."""
    rng = np.random.default_rng(707)
    base = rng.lognormal(mean=4.0, sigma=0.15, size=n).astype(np.float64)
    return pd.DataFrame(
        {
            "ticker": [f"TK{i:04d}" for i in range(n)],
            "ytd_return": rng.uniform(-0.2, 0.35, n),
            "volatility": rng.uniform(0.08, 0.55, n),
            "sharpe_ratio": rng.uniform(-0.2, 2.2, n),
            "open": base * (1.0 + rng.normal(0.0, 0.002, n)),
            "dayLow": base * (0.985 + rng.normal(0.0, 0.002, n)),
            "dayHigh": base * (1.015 + rng.normal(0.0, 0.002, n)),
            "currentPrice": base * (1.0 + rng.normal(0.0, 0.002, n)),
        }
    )


def test_analyze_snapshot_price_rich_suppresses_price_correlations_and_adds_caveat() -> None:
    df = _snapshot_with_price_overlap_df()
    ctx = detect_dataset_context(df)
    assert ctx.dataset_type == FINANCIAL_MARKETS_SNAPSHOT

    insights, _ = analyze_dataset(df)
    titles = " ".join(str(i.get("title", "")) for i in insights)
    assert "Relationship detected: open &" not in titles
    assert "Relationship detected: dayLow &" not in titles
    assert any(i.get("title") == _PRICE_OVERLAP_FINDING_TITLE for i in insights)


def test_analyze_finance_snapshot_still_surfaces_return_leaders() -> None:
    df = _snapshot_with_price_overlap_df()
    insights, _ = analyze_dataset(df)
    assert any(i.get("title") == "Top return leaders" for i in insights)


def test_analyze_generic_keeps_correlation_insights() -> None:
    rng = np.random.default_rng(808)
    n = 60
    xs = rng.normal(0.0, 1.0, n)
    df = pd.DataFrame(
        {
            "predictor_alpha": xs,
            "response_beta": xs * 2.5 + rng.normal(0.0, 0.05, n),
            "noise_gamma": rng.normal(0.0, 2.0, n),
        }
    )
    assert detect_dataset_context(df).dataset_type == GENERIC_TABULAR
    insights, _ = analyze_dataset(df)
    rel = [i for i in insights if i.get("type") == "correlation"]
    titles = [i.get("title", "") for i in rel]
    assert any(
        ("predictor_alpha" in t and "response_beta" in t) or ("response_beta" in t and "predictor_alpha" in t)
        for t in titles
    )
