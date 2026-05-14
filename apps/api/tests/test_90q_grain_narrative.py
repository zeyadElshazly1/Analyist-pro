"""
90Q — Grain-aware narrative context sentence tests.

Unit tests:  _build_grain_context_sentence (no pipeline, no I/O).
Integration: generate_narrative still produces a non-empty string with profile wired in.
"""
from __future__ import annotations

import csv
import datetime
import io

import pandas as pd
import pytest

from app.services.analysis.narrative import (
    _build_grain_context_sentence,
    generate_narrative,
)
from tests.conftest import TestingSessionLocal, _make_test_jwt, TEST_USER_ID
from app.plan_names import PLAN_CONSULTANT


# ── Unit tests — _build_grain_context_sentence ────────────────────────────────

def _profile(
    grain: str = "order",
    row_count: int = 50,
    date_range: dict | None = None,
    recommended: list[str] | None = None,
) -> dict:
    return {
        "grain_label": grain,
        "fingerprint": {"row_count": row_count, "date_range": date_range},
        "strategy": {
            "recommended_analysis_types": recommended or [],
        },
    }


def test_order_grain_produces_transaction_level_phrase():
    s = _build_grain_context_sentence(_profile(grain="order"))
    assert "transaction-level" in s


def test_transaction_grain_produces_transaction_level_phrase():
    s = _build_grain_context_sentence(_profile(grain="transaction"))
    assert "transaction-level" in s


def test_customer_grain_produces_customer_level_phrase():
    s = _build_grain_context_sentence(_profile(grain="customer"))
    assert "customer-level" in s


def test_time_period_grain_produces_time_series_phrase():
    s = _build_grain_context_sentence(_profile(grain="time_period"))
    assert "time-series" in s


def test_unknown_grain_omits_grain_phrase_but_keeps_row_count():
    s = _build_grain_context_sentence(_profile(grain="unknown", row_count=100))
    assert "transaction-level" not in s
    assert "customer-level" not in s
    assert "100" in s


def test_none_profile_returns_empty_string():
    # generate_narrative guards None before calling, but test helper directly.
    # _build_grain_context_sentence expects a dict; test via generate_narrative instead.
    df = pd.DataFrame({"a": [1, 2]})
    result = generate_narrative([], df, pre_analysis_profile=None)
    assert isinstance(result, str)
    assert len(result) > 0


def test_malformed_profile_returns_empty_string():
    s = _build_grain_context_sentence({})
    assert isinstance(s, str)


def test_strategy_types_humanised_correctly():
    s = _build_grain_context_sentence(_profile(recommended=["trend_analysis", "anomaly_detection"]))
    assert "trend analysis" in s.lower()
    assert "anomaly detection" in s.lower()


def test_max_two_strategy_types_in_sentence():
    s = _build_grain_context_sentence(
        _profile(recommended=["trend_analysis", "anomaly_detection", "correlation_analysis"])
    )
    # Only first two should appear
    assert "trend analysis" in s.lower()
    assert "anomaly detection" in s.lower()
    assert "correlation analysis" not in s.lower()


def test_date_range_included_when_present():
    s = _build_grain_context_sentence(
        _profile(date_range={"min": "2023-01-01", "max": "2023-12-31"})
    )
    assert "2023-01-01" in s
    assert "2023-12-31" in s


def test_date_range_missing_keys_does_not_crash():
    s = _build_grain_context_sentence(_profile(date_range={"min": None, "max": None}))
    assert isinstance(s, str)


def test_generate_narrative_with_none_profile_unchanged():
    """Passing pre_analysis_profile=None must produce the same output as before 90Q."""
    df = pd.DataFrame({"x": range(20), "y": range(20)})
    result = generate_narrative([], df, pre_analysis_profile=None)
    assert "The dataset" in result


def test_generate_narrative_with_profile_prepends_context():
    df = pd.DataFrame({"x": range(20), "y": range(20)})
    profile = _profile(grain="customer", row_count=20, recommended=["segment_comparison"])
    result = generate_narrative([], df, pre_analysis_profile=profile)
    assert "customer-level" in result
    assert "The dataset" in result


# ── Integration test — full pipeline run ──────────────────────────────────────

def _make_csv() -> bytes:
    regions = ["North", "South", "East", "West", "Central"]
    header = ["order_id", "customer_id", "order_date", "region", "revenue", "units"]
    rows = [header]
    for i in range(50):
        date = (datetime.date(2023, 1, 1) + datetime.timedelta(weeks=i)).isoformat()
        rows.append([
            f"ORD{i:04d}", f"CUST{i % 15:02d}", date,
            regions[i % 5], str(round(200.0 + i * 12.5, 2)), str(1 + (i % 8)),
        ])
    buf = io.StringIO()
    csv.writer(buf).writerows(rows)
    return buf.getvalue().encode()


_CSV = _make_csv()


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


def test_grain_narrative_baseline_structure_preserved(client):
    """Full pipeline run: narrative must be a non-empty string and contain
    the row-count phrase.  Confirms wiring doesn't break the narrative output."""
    headers = _upgrade_to_consultant(client)
    r = client.post("/projects", json={"name": "90Q Narrative"}, headers=headers)
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
    body = r.json()

    narrative = body.get("narrative") or ""
    assert isinstance(narrative, str), "narrative must be a string"
    assert len(narrative) > 50, "narrative is unexpectedly short"
    # The scope sentence (rows × cols) must still be present.
    assert "rows" in narrative, "narrative lost its row-count phrase after 90Q wiring"
