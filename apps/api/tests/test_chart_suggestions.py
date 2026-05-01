"""
Tests for finance-aware chart suggestions on financial_markets_snapshot (Task 74A).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from app.services.charting.orchestrator import build_chart_data
from app.services.dataset_context import FINANCIAL_MARKETS_SNAPSHOT, detect_dataset_context


_FINANCE_HEADLINE_TITLES = frozenset(
    {
        "Top assets by return",
        "Largest return laggards",
        "Highest volatility assets",
        "Risk vs return",
        "Average return by asset class",
        "Average return by sector",
        "Highest analyst-implied upside",
        "Assets by 52-week position",
    },
)


def _yahoo_snapshot_df(n: int = 55) -> pd.DataFrame:
    rng = np.random.default_rng(42)
    classes = ["Equity", "ETF", "Bond", "Crypto"]
    sectors = ["Technology", "Financials", "Healthcare", "Energy", "Consumer"]
    return pd.DataFrame(
        {
            "ticker": [f"TK{i:03d}" for i in range(n)],
            "shortName": [f"Asset {i}" for i in range(n)],
            "asset_class": rng.choice(classes, n),
            "sector": rng.choice(sectors, n),
            "ytd_return": rng.uniform(-0.3, 0.5, n),
            "one_year_return": rng.uniform(-0.4, 0.8, n),
            "volatility": rng.uniform(0.05, 0.6, n),
            "sharpe_ratio": rng.uniform(-1.0, 3.0, n),
            "analyst_upside_pct": rng.uniform(-0.1, 0.4, n),
            "week_52_position": rng.uniform(0.0, 1.0, n),
            "composite_score": rng.uniform(0.0, 100.0, n),
            "marketCap": rng.integers(1_000_000, 1_000_000_000_000, n).astype(float),
        }
    )


def _telco_generic_df(n: int = 100) -> pd.DataFrame:
    rng = np.random.default_rng(9)
    return pd.DataFrame(
        {
            "customer_id": [f"CUS{i}" for i in range(n)],
            "tenure_months": rng.integers(1, 72, n),
            "monthly_charges": rng.uniform(20, 120, n),
            "contract": rng.choice(["Month-to-month", "One year", "Two year"], n),
            "churned": rng.integers(0, 2, n),
        }
    )


def _snapshot_without_analyst(n: int = 50) -> pd.DataFrame:
    df = _yahoo_snapshot_df(n)
    return df.drop(columns=["analyst_upside_pct"], errors="ignore")


class TestFinanceSnapshotCharts:
    def test_yahoo_like_snapshot_returns_finance_titles(self) -> None:
        df = _yahoo_snapshot_df()
        assert detect_dataset_context(df).dataset_type == FINANCIAL_MARKETS_SNAPSHOT
        charts = build_chart_data(df)
        titles = {c.get("title") for c in charts}
        assert "Top assets by return" in titles
        assert "Largest return laggards" in titles
        assert "Highest volatility assets" in titles
        assert titles & _FINANCE_HEADLINE_TITLES

    def test_no_over_time_or_line_charts_for_snapshot(self) -> None:
        df = _yahoo_snapshot_df()
        charts = build_chart_data(df)
        for c in charts:
            title = str(c.get("title", "")).lower()
            desc = str(c.get("description", "")).lower()
            assert "over time" not in title
            assert "over time" not in desc
            assert c.get("type") != "line"

    def test_risk_vs_return_when_return_and_volatility_exist(self) -> None:
        df = _yahoo_snapshot_df()
        charts = build_chart_data(df)
        sc = next((c for c in charts if c.get("title") == "Risk vs return"), None)
        assert sc is not None
        assert sc["type"] == "scatter"
        ctx = detect_dataset_context(df)
        from app.services.analysis.domain.snapshot_finance import (
            _select_return_column,
            _select_volatility_column,
        )

        assert sc.get("x_label") == _select_volatility_column(df, ctx)
        assert sc.get("y_label") == _select_return_column(df, ctx)
        pts = sc.get("data") or []
        assert len(pts) >= 5


class TestGroupedAndOptionalFinanceCharts:
    def test_average_return_by_asset_class_when_role_present(self) -> None:
        df = _yahoo_snapshot_df()
        charts = build_chart_data(df)
        titles = {c.get("title") for c in charts}
        assert "Average return by asset class" in titles

    def test_skips_analyst_upside_chart_when_column_missing(self) -> None:
        df = _snapshot_without_analyst()
        assert detect_dataset_context(df).dataset_type == FINANCIAL_MARKETS_SNAPSHOT
        charts = build_chart_data(df)
        titles = {c.get("title") for c in charts}
        assert "Highest analyst-implied upside" not in titles

    def test_generic_dataset_chart_suggestions_exclude_finance_headlines(self) -> None:
        df = _telco_generic_df()
        assert detect_dataset_context(df).dataset_type != FINANCIAL_MARKETS_SNAPSHOT
        charts = build_chart_data(df)
        titles = {c.get("title") for c in charts}
        assert titles.isdisjoint(_FINANCE_HEADLINE_TITLES)
