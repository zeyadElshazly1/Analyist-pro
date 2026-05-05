"""End-to-end checks using the Yahoo-style global markets CSV fixture (Task 76A)."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from app.services.analysis.orchestrator import analyze_dataset
from app.services.analysis.ranking import _FINANCE_SNAPSHOT_TITLE_ORDER
from app.services.dataset_context import FINANCIAL_MARKETS_SNAPSHOT, detect_dataset_context
from app.services.insight_adapter import build_insight_results
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

    titles_seen = [str(i.get("title", "")) for i in insights]
    premium_set = set(_FINANCE_SNAPSHOT_TITLE_ORDER)
    present_premium = [t for t in _FINANCE_SNAPSHOT_TITLE_ORDER if t in titles_seen]

    domain_finance = [i for i in insights if i.get("domain") == FINANCIAL_MARKETS_SNAPSHOT]
    assert len(domain_finance) >= 5

    n_pre = len(present_premium)
    assert titles_seen[:n_pre] == present_premium, (
        f"Expected opening block {present_premium}, got {titles_seen[:n_pre]}"
    )

    first_generic_corr_idx = next(
        (j for j, i in enumerate(insights) if i.get("type") == "correlation"),
        None,
    )
    last_premium_idx = max(j for j, t in enumerate(titles_seen) if t in premium_set)

    if first_generic_corr_idx is not None:
        assert first_generic_corr_idx > last_premium_idx

    assert titles_seen[0] == "Top return leaders"

    bad_seg_markers = (
        "→ previousclose",
        "→ open",
        "→ daylow",
        "→ currentprice",
        "→ fiftydayaverage",
        "→ twohundreddayaverage",
    )
    for idx, ins in enumerate(insights):
        tl = str(ins.get("title", "")).lower()
        if ins.get("type") == "segment" and "segment gap:" in tl:
            if any(m in tl for m in bad_seg_markers):
                assert idx >= n_pre, f"price segment {ins.get('title')} before premium block"
        if "anomalies in currentprice" in tl:
            assert idx >= n_pre


def test_yahoo_finance_insight_adapter_stringifies_structured_evidence() -> None:
    """Regression: finance insights use dict evidence — InsightResult must stay schema-valid."""
    df = pd.read_csv(_FIXTURE)
    insights, _ = analyze_dataset(df)
    results = build_insight_results(insights)
    assert len(results) >= 1
    assert all(isinstance(r.evidence, str) for r in results)
