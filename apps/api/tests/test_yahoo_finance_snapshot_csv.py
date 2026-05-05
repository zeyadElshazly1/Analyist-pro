"""End-to-end checks using the Yahoo-style global markets CSV fixture (Task 76A)."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from app.services.analysis.orchestrator import analyze_dataset
from app.services.dataset_context import FINANCIAL_MARKETS_SNAPSHOT, detect_dataset_context
from app.services.profiler import calculate_health_score


_FIXTURE = Path(__file__).resolve().parent / "fixtures" / "yahoo_finance_global_markets_2026.csv"


def test_yahoo_finance_fixture_detects_snapshot_and_health_label() -> None:
    df = pd.read_csv(_FIXTURE)
    ctx = detect_dataset_context(df)
    assert ctx.dataset_type == FINANCIAL_MARKETS_SNAPSHOT
    assert ctx.confidence >= 0.65

    health = calculate_health_score(df)
    assert health["dataset_type"] == FINANCIAL_MARKETS_SNAPSHOT


def test_yahoo_finance_fixture_top_findings_are_finance_first() -> None:
    df = pd.read_csv(_FIXTURE)
    insights, _ = analyze_dataset(df)
    assert insights, "expected capped insight list"

    premium = {
        "Top return leaders",
        "Largest return laggards",
        "Highest volatility assets",
        "Best risk-adjusted performers",
        "Asset classes show different return profiles",
        "Sectors show different return profiles",
        "Highest analyst-implied upside",
        "Assets cluster at different 52-week positions",
    }
    titles = [str(i.get("title", "")) for i in insights]
    domain_finance = [i for i in insights if i.get("domain") == FINANCIAL_MARKETS_SNAPSHOT]
    assert len(domain_finance) >= 5

    first_generic_corr_idx = next(
        (j for j, i in enumerate(insights) if i.get("type") == "correlation"),
        None,
    )
    last_premium_idx = max(j for j, t in enumerate(titles) if t in premium)

    if first_generic_corr_idx is not None:
        assert first_generic_corr_idx > last_premium_idx

    assert titles[0] == "Top return leaders"
