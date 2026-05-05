"""Tests for insight ranking composite scores and snapshot domain boosts (Task 73C)."""
from __future__ import annotations

import numpy as np
import pandas as pd

from app.services.analysis.orchestrator import analyze_dataset
from app.services.analysis.ranking import (
    _SNAPSHOT_FINANCE_PREMIUM_TITLES,
    _composite_score,
    rank_insights,
)
from app.services.dataset_context.schema import FINANCIAL_MARKETS_SNAPSHOT, DatasetContext


def _base_composite_legacy(ins: dict) -> float:
    """Pre-73C base (severity + confidence + target-driver terms only)."""
    sev_weights = {"high": 1.0, "medium": 0.6, "low": 0.2}
    sev = sev_weights.get(ins.get("severity", "low"), 0.2)
    conf = float(ins.get("confidence", 50)) / 100.0
    td_bonus = 0.30 if ins.get("is_target_driver") else 0.0
    return min(1.0, sev * 0.50 + conf * 0.25 + td_bonus * 0.25)


def test_no_domain_tag_scores_match_legacy_formula() -> None:
    corr = {
        "type": "correlation",
        "severity": "medium",
        "confidence": 78.0,
        "title": "Relationship detected: a & b",
        "col_a": "feat_a",
        "col_b": "feat_b",
    }
    assert _composite_score(corr) == _base_composite_legacy(corr)


def test_finance_snapshot_premium_boost_beats_med_correlations() -> None:
    correlations = []
    rng = ord("x")
    for _ in range(6):
        a, b = f"c{rng}", f"c{rng+1}"
        correlations.append(
            {
                "type": "correlation",
                "severity": "medium",
                "confidence": 76.0,
                "title": f"Relationship detected: {a} & {b}",
                "col_a": a,
                "col_b": b,
            }
        )
        rng += 2
    leaders = {
        "type": "segment",
        "severity": "medium",
        "confidence": 85.0,
        "domain": FINANCIAL_MARKETS_SNAPSHOT,
        "title": "Top return leaders",
        "finding": "f",
        "action": "a",
    }
    pool = correlations + [leaders]
    ranked, _ = rank_insights(pool)
    assert ranked[0]["title"] == "Top return leaders"


def test_price_caveat_does_not_outrank_main_finance_insights() -> None:
    caveat = {
        "type": "multicollinearity",
        "severity": "medium",
        "confidence": 85.0,
        "domain": FINANCIAL_MARKETS_SNAPSHOT,
        "title": "Price fields are highly overlapping",
        "finding": "f",
        "action": "a",
        "why_it_matters": "w",
        "columns_used": ["open", "currentPrice"],
    }
    volatility = {
        "type": "concentration",
        "severity": "medium",
        "confidence": 82.0,
        "domain": FINANCIAL_MARKETS_SNAPSHOT,
        "title": "Highest volatility assets",
        "finding": "f",
        "action": "a",
    }
    ranked, _ = rank_insights([caveat, volatility])
    assert ranked[0]["title"] == "Highest volatility assets"
    assert _composite_score(volatility) > _composite_score(caveat)


def test_weak_finance_domain_does_not_beat_high_severity_generic() -> None:
    generic = {
        "type": "anomaly",
        "severity": "high",
        "confidence": 96.0,
        "title": "Anomalies in revenue",
        "finding": "f",
        "action": "a",
    }
    weak_finance = {
        "type": "segment",
        "severity": "medium",
        "confidence": 40.0,
        "domain": FINANCIAL_MARKETS_SNAPSHOT,
        "title": "Top return leaders",
        "finding": "f",
        "action": "a",
    }
    assert _composite_score(generic) > _composite_score(weak_finance)
    ranked, _ = rank_insights([weak_finance, generic])
    assert ranked[0]["title"] == "Anomalies in revenue"


def _dense_snapshot_for_ranking(n: int = 88) -> pd.DataFrame:
    rng = np.random.default_rng(606)
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


def test_analyze_finance_snapshot_surfaces_multiple_premium_finance_titles() -> None:
    df = _dense_snapshot_for_ranking()
    insights, _ = analyze_dataset(df)
    titles = [i.get("title") for i in insights]
    premiers_present = sum(1 for t in titles if t in _SNAPSHOT_FINANCE_PREMIUM_TITLES)
    assert premiers_present >= 2


def test_snapshot_ctx_orders_finance_before_high_correlations() -> None:
    ctx = DatasetContext(
        dataset_type=FINANCIAL_MARKETS_SNAPSHOT,
        confidence=0.9,
        semantic_roles={},
    )
    corr = {
        "type": "correlation",
        "severity": "high",
        "confidence": 95.0,
        "title": "Relationship detected: fee_a & fee_b",
        "col_a": "fee_a",
        "col_b": "fee_b",
    }
    fin = {
        "type": "segment",
        "severity": "medium",
        "confidence": 85.0,
        "domain": FINANCIAL_MARKETS_SNAPSHOT,
        "title": "Top return leaders",
        "finding": "f",
        "action": "a",
    }
    ranked, _ = rank_insights([corr, fin], ctx)
    assert ranked[0]["title"] == "Top return leaders"
