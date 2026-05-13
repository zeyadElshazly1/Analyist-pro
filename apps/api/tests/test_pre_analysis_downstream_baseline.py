"""
90I — Pre-analysis regression baseline.

Captures current output shape BEFORE pre_analysis_profile influences
any downstream behavior (ranking, hygiene, charts, narrative).

The fixed 50-row orders dataset is deterministic: no random noise,
fixed seed columns, weekly dates from 2023-01-01.

NOTE on column count: the cleaning pipeline expands order_date into
date-part columns (year, month, day, day_of_week, quarter, is_weekend),
so df_clean has 12 columns even though the input CSV has 6.  The profile
is built from df_clean, so fingerprint.column_count == 12.
"""
from __future__ import annotations

import csv
import datetime
import io
import json
from typing import Any

import pytest

from tests.conftest import TestingSessionLocal, _make_test_jwt, TEST_USER_ID
from app.plan_names import PLAN_CONSULTANT


# ── Fixed dataset ─────────────────────────────────────────────────────────────

def _make_csv() -> bytes:
    """50-row orders CSV — fully deterministic, no random values."""
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

# ── Baseline constants ────────────────────────────────────────────────────────
# Captured from a live run of the pipeline on _CSV (2026-05-13).
# Update these ONLY when a deliberate behavior change is made AND
# the PR author explicitly acknowledges the change.

# Cleaning expands order_date → 6 date-part cols; total cleaned cols = 12.
_EXPECTED_CLEANED_COLUMN_COUNT = 12

# Grain detector sees order_id (transaction_id role) → "order".
_VALID_GRAIN_LABELS = {"order", "transaction", "time_period", "unknown"}

# Top-5 insight (category, severity) tuples from the current ranking.
# type is None for all current insights (InsightResult.type is not populated
# by the adapter).  We anchor on category+severity which are stable.
_BASELINE_TOP5: list[tuple[str | None, str | None]] = [
    ("trend",       "high"),
    ("trend",       "high"),
    ("anomaly",     "high"),
    ("trend",       "medium"),
    ("correlation", "high"),
]

# All canonical top-level keys every result must carry.
_CANONICAL_KEYS = frozenset({
    "project_id",
    "run_id",
    "intake_result",
    "cleaning_summary",
    "cleaning_result",
    "profile_result",
    "health_result",
    "insight_results",
    "narrative",
    "executive_panel",
    "dataset_summary",
    "analysis_plan",
    "insight_selection_meta",
    "pre_analysis_profile",
})


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


def _create_and_run(client) -> dict:
    """Create a project, upload the fixed CSV, run analysis, return result dict."""
    headers = _upgrade_to_consultant(client)

    r = client.post("/projects", json={"name": "90I Baseline"}, headers=headers)
    assert r.status_code == 200
    pid = r.json()["id"]

    r = client.post(
        "/upload",
        files={"file": ("orders.csv", io.BytesIO(_CSV), "text/csv")},
        data={"project_id": str(pid)},
        headers=headers,
    )
    assert r.status_code == 200

    r = client.post("/analysis/run", json={"project_id": pid}, headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


# ── Function-scoped fixture — runs pipeline once per test via cache ───────────
# client is function-scoped so we cannot use class or module scope for the
# fixture directly.  We cache on the client object itself so each test-session
# still only runs the pipeline once per conftest DB transaction.

_RESULT_CACHE: dict[int, dict] = {}


@pytest.fixture()
def baseline_result(client):
    key = id(client)
    if key not in _RESULT_CACHE:
        _RESULT_CACHE[key] = _create_and_run(client)
    return _RESULT_CACHE[key]


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestPreAnalysisDownstreamBaseline:
    """
    All five tests share one pipeline run via baseline_result.
    Do NOT change these assertions without a deliberate, reviewed decision.
    """

    # ── Test 1: result carries both old and new planning layers ───────────────

    def test_result_contains_both_planning_layers(self, baseline_result):
        """Both the V1 analysis_plan and the V2 pre_analysis_profile must be present."""
        body = baseline_result

        assert "analysis_plan" in body, "V1 analysis_plan missing from result"
        assert body["analysis_plan"] is not None

        assert "pre_analysis_profile" in body, "V2 pre_analysis_profile missing from result"
        assert body["pre_analysis_profile"] is not None

        assert "insight_results" in body
        assert "insight_selection_meta" in body

    # ── Test 2: pre_analysis_profile is observational only ───────────────────

    def test_pre_analysis_profile_is_observational_only(self, baseline_result):
        """
        None of the downstream output blocks (insight_results, executive_panel,
        narrative, analysis_plan) must contain a 'pre_analysis_profile' key or
        reference the V2 grain/strategy fields by name.

        This proves the profile is stored but NOT yet driving output.
        """
        body = baseline_result
        profile = body["pre_analysis_profile"]

        # Downstream blocks that must remain profile-unaware.
        downstream_blobs = [
            json.dumps(body.get("insight_results") or []),
            json.dumps(body.get("executive_panel") or {}),
            str(body.get("narrative") or ""),
            json.dumps(body.get("analysis_plan") or {}),
        ]

        for blob in downstream_blobs:
            assert "pre_analysis_profile" not in blob, (
                "Downstream block references 'pre_analysis_profile' — "
                "the V2 profile must remain observational until 90I+ integration."
            )
            # The grain_label and strategy fields are internal to the profile;
            # their values (e.g. "order") appearing in narrative is fine —
            # what we guard against is the profile object itself leaking in.
            assert '"grain_label"' not in blob or blob == json.dumps(body.get("analysis_plan") or {}), (
                # analysis_plan may carry a grain-like field from V1 planner — that's OK.
                # Insight / exec-panel / narrative must not embed raw V2 profile keys.
                True
            )

        # The profile block itself must not nest inside insight_results items.
        for item in (body.get("insight_results") or []):
            if isinstance(item, dict):
                assert "pre_analysis_profile" not in item
                assert "grain_label" not in item
                assert "column_roles" not in item

    # ── Test 3: insight ordering baseline ────────────────────────────────────

    def test_insight_ordering_baseline(self, baseline_result):
        """
        Capture the (category, severity) ordering of the top-5 insights.

        This is the regression guard: if pre_analysis_profile-aware hygiene
        accidentally changes ranking, this test will fail before it ships.

        To intentionally update: change _BASELINE_TOP5 in a dedicated PR
        that also updates the 90H checkpoint and records the expected delta.
        """
        insight_results = baseline_result.get("insight_results") or []
        assert len(insight_results) >= 5, (
            f"Expected at least 5 insights, got {len(insight_results)}. "
            "The fixed dataset should reliably produce trend+anomaly+correlation findings."
        )

        actual_top5 = [
            (i.get("category"), i.get("severity"))
            for i in insight_results[:5]
        ]

        assert actual_top5 == _BASELINE_TOP5, (
            f"Insight ordering changed — this means ranking or hygiene behaviour "
            f"was modified.\n"
            f"  Expected: {_BASELINE_TOP5}\n"
            f"  Actual:   {actual_top5}\n"
            f"If this is intentional, update _BASELINE_TOP5 in this file and "
            f"document the change in PRE_ANALYSIS_V2_CHECKPOINT_90H.md."
        )

    # ── Test 4: profile sanity baseline ──────────────────────────────────────

    def test_profile_sanity_baseline(self, baseline_result):
        """
        Assert invariant properties of the V2 profile for the fixed dataset.
        Tolerant on exact grain because heuristics may legitimately classify
        this dataset as 'order' or 'time_period' depending on column weighting.
        """
        profile = baseline_result["pre_analysis_profile"]

        assert profile["planner_version"] == "v2.0-deterministic"

        fp = profile["fingerprint"]
        assert fp["row_count"] == 50, (
            f"fingerprint.row_count should be 50 (the fixed CSV has 50 rows), got {fp['row_count']}"
        )
        # After cleaning, order_date expands into 6 date-part columns → 12 total.
        assert fp["column_count"] == _EXPECTED_CLEANED_COLUMN_COUNT, (
            f"fingerprint.column_count should be {_EXPECTED_CLEANED_COLUMN_COUNT} "
            f"(6 original + 6 date-parts after cleaning), got {fp['column_count']}"
        )

        assert profile["grain_label"] in _VALID_GRAIN_LABELS, (
            f"grain_label {profile['grain_label']!r} not in {_VALID_GRAIN_LABELS}"
        )
        assert 0.0 <= profile["grain_confidence"] <= 1.0

        roles = profile["column_roles"]
        assert len(roles) == _EXPECTED_CLEANED_COLUMN_COUNT, (
            f"Expected {_EXPECTED_CLEANED_COLUMN_COUNT} column_roles (one per cleaned column), "
            f"got {len(roles)}"
        )

        # The 6 original input columns must each appear in column_roles.
        role_names = {r["column_name"] for r in roles}
        for col in ("order_id", "customer_id", "order_date", "region", "revenue", "units"):
            assert col in role_names, f"Original column {col!r} missing from column_roles"

        # Strategy must recommend at least one analysis type for this rich dataset.
        assert len(profile["strategy"]["recommended_analysis_types"]) >= 1

    # ── Test 5: canonical result keys preserved ───────────────────────────────

    def test_canonical_result_keys_preserved(self, baseline_result):
        """
        All canonical top-level keys must still be present.
        This is the shape-stability guard for the full result dict.
        """
        body = baseline_result
        missing = _CANONICAL_KEYS - set(body.keys())
        assert not missing, (
            f"Canonical result keys missing: {missing}\n"
            f"Keys present: {sorted(body.keys())}"
        )
