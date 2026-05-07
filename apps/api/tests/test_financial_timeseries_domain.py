"""
Regression tests for financial_markets_timeseries domain (Task 77A).
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from app.services.analysis.domain.timeseries_finance import FINANCE_TS_PREMIUM_TITLE_ORDER
from app.services.analysis.orchestrator import analyze_dataset
from app.services.charting.orchestrator import build_chart_data
from app.services.dataset_context import FINANCIAL_MARKETS_TIMESERIES, detect_dataset_context


def _etf_fixture_df() -> pd.DataFrame:
    path = Path(__file__).resolve().parent / "fixtures" / "etf_prices_sample.csv"
    return pd.read_csv(path, parse_dates=["price_date"])


def test_fixture_detection_and_health_dataset_type():
    df = _etf_fixture_df()
    ctx = detect_dataset_context(df)
    assert ctx.dataset_type == FINANCIAL_MARKETS_TIMESERIES
    from app.services.profiling.health_scorer import calculate_health_score

    health = calculate_health_score(df)
    assert health["dataset_type"] == "financial_markets_timeseries"


def test_ranked_insights_premium_order_matches_contract():
    df = _etf_fixture_df()
    insights, _ = analyze_dataset(df)
    titles = [str(ins.get("title", "")) for ins in insights]

    for tile in FINANCE_TS_PREMIUM_TITLE_ORDER:
        assert tile in titles

    # Premium finance narrative block precedes generic correlations / overlaps caveat sequencing contract.
    for i, t in enumerate(FINANCE_TS_PREMIUM_TITLE_ORDER):
        assert titles[i] == t

    corr_idxs = [i for i, ins in enumerate(insights) if ins.get("type") == "correlation"]
    if corr_idxs:
        assert min(corr_idxs) > len(FINANCE_TS_PREMIUM_TITLE_ORDER)


def test_chart_bundle_contains_timeseries_finance_titles():
    df = _etf_fixture_df()
    charts = build_chart_data(df)
    titles = {c.get("title") for c in charts}
    assert "Price trend by symbol" in titles
    assert "Total return leaderboard" in titles
    assert "Volatility leaderboard" in titles
    assert "Drawdown chart" in titles
    assert "Volume leaderboard" in titles
    assert "Return distribution" in titles


def test_multi_series_price_chart_payload_shape():
    df = _etf_fixture_df()
    charts = build_chart_data(df)
    price_chart = next(c for c in charts if c.get("title") == "Price trend by symbol")
    assert price_chart.get("type") == "line"
    assert isinstance(price_chart.get("line_series"), list)
    assert len(price_chart["line_series"]) >= 2
