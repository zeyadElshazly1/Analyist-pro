"""
90K — Profile-hygiene wiring tests.

Verifies:
  1. Default flag (True since 90O) → suppressed insights have valid confidence.
  2. Monkeypatched flag (True) + spy → pipeline invokes apply_pre_analysis_profile_hygiene
     with enabled=True and a non-None profile.
  3. 90O re-locked regression baseline (ordering guard re-checked here).
"""
from __future__ import annotations

import csv
import datetime
import io

import pytest

from tests.conftest import TestingSessionLocal, _make_test_jwt, TEST_USER_ID
from app.plan_names import PLAN_CONSULTANT


# ── Fixed dataset (same as 90I baseline) ─────────────────────────────────────

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

_BASELINE_TOP5 = [
    # Re-locked at 90O: hygiene active by default, anomaly moves to rank 2.
    ("trend",       "high"),
    ("anomaly",     "high"),
    ("trend",       "high"),
    ("trend",       "medium"),
    ("correlation", "high"),
]


# ── Shared helpers ────────────────────────────────────────────────────────────

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
    r = client.post("/projects", json={"name": "90K Wiring"}, headers=headers)
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


# ── Test 1: default flag (True since 90O) → suppressed insights are valid ─────

def test_default_flag_true_suppressed_insights_have_valid_confidence(client):
    """With PRE_ANALYSIS_PROFILE_HYGIENE_ENABLED=True (default since 90O),
    any insight carrying suppressed_by_profile=True must still have a valid
    numeric confidence in [0, 100].  The pipeline must not zero out or NaN
    any confidence value during hygiene application."""
    body = _run_analysis(client)
    insight_results = body.get("insight_results") or []
    assert insight_results, "Expected at least one insight from the fixed dataset"

    for ins in insight_results:
        if ins.get("suppressed_by_profile"):
            conf = ins.get("confidence")
            assert conf is not None, (
                f"Suppressed insight has no confidence field: {ins.get('title')}"
            )
            assert isinstance(conf, (int, float)), (
                f"confidence is not numeric on suppressed insight: {conf}"
            )
            assert 0.0 <= conf <= 100.0, (
                f"confidence {conf} out of [0,100] on suppressed insight: {ins.get('title')}"
            )


# ── Test 2: monkeypatch flag True + spy confirms pipeline calls helper ────────

def test_monkeypatch_flag_true_pipeline_invokes_profile_hygiene(client, monkeypatch):
    """When PRE_ANALYSIS_PROFILE_HYGIENE_ENABLED is patched to True, the pipeline
    must call apply_pre_analysis_profile_hygiene with enabled=True and a non-None
    profile dict.  We spy without altering the return value."""
    import app.routes.analysis as analysis_mod
    from app.services.analysis.profile_hygiene import (
        apply_pre_analysis_profile_hygiene as _real,
    )

    calls: list[dict] = []

    def _spy(insights, profile, *, enabled=False):
        calls.append({"enabled": enabled, "profile_is_none": profile is None})
        return _real(insights, profile, enabled=enabled)

    monkeypatch.setattr(analysis_mod, "apply_pre_analysis_profile_hygiene", _spy)
    monkeypatch.setattr(analysis_mod, "PRE_ANALYSIS_PROFILE_HYGIENE_ENABLED", True)

    _run_analysis(client)

    assert calls, "apply_pre_analysis_profile_hygiene was not called during analysis"
    # At least one call must have been made with enabled=True.
    enabled_calls = [c for c in calls if c["enabled"]]
    assert enabled_calls, (
        f"No call with enabled=True found. Calls recorded: {calls}"
    )
    # Profile must be non-None (profile build succeeded for the fixed dataset).
    assert not enabled_calls[0]["profile_is_none"], (
        "Pipeline passed profile=None to hygiene even though build should succeed"
    )


# ── Test 3: 90I baseline unchanged ───────────────────────────────────────────

def test_90i_baseline_insight_ordering_unchanged(client):
    """Re-assert the 90I ordering baseline to confirm wiring did not change behavior."""
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
        f"Insight ordering changed after 90K wiring — default flag must be False.\n"
        f"  Expected: {_BASELINE_TOP5}\n"
        f"  Actual:   {actual_top5}"
    )
