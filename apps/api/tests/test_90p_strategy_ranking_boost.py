"""
90P — Strategy-aligned ranking boost tests.

Verifies:
  1. Unit tests for _strategy_alignment_boost (no pipeline, no I/O).
  2. Integration baseline: top-5 ordering unchanged after 90P wiring.
"""
from __future__ import annotations

import csv
import datetime
import io

import pytest

from app.services.analysis.ranking import (
    _strategy_alignment_boost,
    _BOOST_STRATEGY_ALIGNED,
    _BOOST_STRATEGY_DEPRIORITY,
    rerank_after_plan_hygiene,
)
from tests.conftest import TestingSessionLocal, _make_test_jwt, TEST_USER_ID
from app.plan_names import PLAN_CONSULTANT


# ── Unit tests ────────────────────────────────────────────────────────────────

class TestStrategyAlignmentBoost:

    def test_aligned_category_returns_positive(self):
        b = _strategy_alignment_boost("trend", ["trend_analysis"], [])
        assert b == _BOOST_STRATEGY_ALIGNED

    def test_deprioritised_category_returns_negative(self):
        b = _strategy_alignment_boost("anomaly", [], ["anomaly_detection"])
        assert b == _BOOST_STRATEGY_DEPRIORITY

    def test_unmapped_category_returns_zero(self):
        b = _strategy_alignment_boost("data_quality", ["trend_analysis"], [])
        assert b == 0.0

    def test_empty_lists_returns_zero(self):
        b = _strategy_alignment_boost("trend", [], [])
        assert b == 0.0

    def test_none_category_returns_zero(self):
        b = _strategy_alignment_boost(None, ["trend_analysis"], [])
        assert b == 0.0

    def test_empty_string_category_returns_zero(self):
        b = _strategy_alignment_boost("", ["trend_analysis"], [])
        assert b == 0.0

    def test_recommended_takes_priority_over_deprioritised(self):
        # Same type in both lists → recommended wins
        b = _strategy_alignment_boost("trend", ["trend_analysis"], ["trend_analysis"])
        assert b == _BOOST_STRATEGY_ALIGNED

    def test_correlation_analysis_maps_to_multiple_categories(self):
        for cat in ("correlation", "multicollinearity", "interaction"):
            b = _strategy_alignment_boost(cat, ["correlation_analysis"], [])
            assert b == _BOOST_STRATEGY_ALIGNED, f"Expected boost for {cat}"

    def test_target_analysis_maps_to_trend_and_correlation(self):
        for cat in ("trend", "correlation", "leading_indicator"):
            b = _strategy_alignment_boost(cat, ["target_analysis"], [])
            assert b == _BOOST_STRATEGY_ALIGNED, f"Expected boost for {cat}"

    def test_distribution_analysis_maps_to_distribution_concentration_simpsons(self):
        for cat in ("distribution", "concentration", "simpsons_paradox"):
            b = _strategy_alignment_boost(cat, ["distribution_analysis"], [])
            assert b == _BOOST_STRATEGY_ALIGNED, f"Expected boost for {cat}"

    def test_unknown_strategy_type_returns_zero(self):
        b = _strategy_alignment_boost("trend", ["nonexistent_analysis_type"], [])
        assert b == 0.0

    def test_rerank_passes_strategy_through(self):
        insights = [
            {"type": "trend", "category": "trend", "severity": "medium", "confidence": 50.0},
            {"type": "data_quality", "category": "data_quality", "severity": "medium", "confidence": 50.0},
        ]
        result = rerank_after_plan_hygiene(
            insights,
            recommended_types=["trend_analysis"],
            deprioritised_types=[],
        )
        assert result[0]["category"] == "trend", (
            "Trend insight should rank above data_quality when trend_analysis is recommended"
        )

    def test_rerank_no_strategy_is_backwards_compatible(self):
        insights = [
            {"type": "trend", "severity": "high", "confidence": 90.0},
            {"type": "anomaly", "severity": "high", "confidence": 90.0},
        ]
        result = rerank_after_plan_hygiene(insights)
        assert len(result) == 2


# ── Fixed dataset (same as 90I/90O baseline) ─────────────────────────────────

def _make_csv() -> bytes:
    regions = ["North", "South", "East", "West", "Central"]
    header = ["order_id", "customer_id", "order_date", "region", "revenue", "units"]
    rows = [header]
    for i in range(50):
        date = (datetime.date(2023, 1, 1) + datetime.timedelta(weeks=i)).isoformat()
        rows.append([
            f"ORD{i:04d}",
            f"CUST{i % 15:02d}",
            date,
            regions[i % 5],
            str(round(200.0 + i * 12.5, 2)),
            str(1 + (i % 8)),
        ])
    buf = io.StringIO()
    csv.writer(buf).writerows(rows)
    return buf.getvalue().encode()


_CSV = _make_csv()

# Re-locked at 90O; 90P boost is uniform across all top-5 categories so
# relative ordering is unchanged.
_BASELINE_TOP5 = [
    ("trend",       "high"),
    ("anomaly",     "high"),
    ("trend",       "high"),
    ("trend",       "medium"),
    ("correlation", "high"),
]


def _upgrade_to_consultant(client) -> dict:
    token = _make_test_jwt()
    headers = {"Authorization": f"Bearer {token}"}
    client.get("/auth/me", headers=headers)
    db = TestingSessionLocal()
    try:
        from app.models import User as _User
        u = db.query(_User).filter(_User.id == TEST_USER_ID).first()
        if u:
            u.plan = PLAN_CONSULTANT
            db.commit()
    finally:
        db.close()
    return headers


def _run_analysis(client) -> dict:
    headers = _upgrade_to_consultant(client)
    r = client.post("/projects", json={"name": "90P Baseline"}, headers=headers)
    assert r.status_code == 200
    pid = r.json()["id"]
    client.post(
        "/upload",
        files={"file": ("orders.csv", io.BytesIO(_CSV), "text/csv")},
        data={"project_id": str(pid)},
        headers=headers,
    )
    r = client.post("/analysis/run", json={"project_id": pid}, headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


# ── Integration test ──────────────────────────────────────────────────────────

def test_strategy_boost_baseline_top5_unchanged(client):
    """After 90P wiring, top-5 ordering must match the 90O-locked baseline.

    All five top insights (trend, anomaly, correlation) map to recommended
    types for the orders dataset — the boost applies uniformly, so relative
    ordering is preserved.  If this fails, update _BASELINE_TOP5 with a
    comment explaining the intentional delta.
    """
    body = _run_analysis(client)
    insight_results = body.get("insight_results") or []
    assert len(insight_results) >= 5, (
        f"Expected ≥5 insights, got {len(insight_results)}"
    )
    actual_top5 = [
        (i.get("category"), i.get("severity"))
        for i in insight_results[:5]
    ]
    assert actual_top5 == _BASELINE_TOP5, (
        f"Top-5 ordering changed after 90P strategy boost wiring.\n"
        f"  Expected: {_BASELINE_TOP5}\n"
        f"  Actual:   {actual_top5}\n"
        f"If intentional, update _BASELINE_TOP5 in this file and the other baseline files."
    )
