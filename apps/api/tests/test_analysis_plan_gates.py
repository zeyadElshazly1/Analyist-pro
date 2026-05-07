"""
79A — Plan gate tests for /analysis/diff and /analysis/download-cleaned.

Verifies that:
- Free users receive 402 with the correct feature name.
- Consultant users are not blocked by the plan gate (may still get non-402
  errors for other reasons such as missing files or invalid run IDs).
"""
from __future__ import annotations

import pytest

from app.plan_names import PLAN_CONSULTANT
from tests.conftest import (
    TEST_USER_ID,
    TestingSessionLocal,
    _make_test_jwt,
)


# ── helpers ───────────────────────────────────────────────────────────────────

def _free_headers(client) -> dict:
    """Auth headers for a free-plan user (default plan on creation)."""
    token = _make_test_jwt()
    headers = {"Authorization": f"Bearer {token}"}
    client.get("/auth/me", headers=headers)
    return headers


def _consultant_headers(client) -> dict:
    """Auth headers for a consultant-plan user."""
    token = _make_test_jwt()
    headers = {"Authorization": f"Bearer {token}"}
    client.get("/auth/me", headers=headers)

    from app.models import User as UserModel

    db = TestingSessionLocal()
    try:
        user = db.query(UserModel).filter(UserModel.id == TEST_USER_ID).first()
        if user:
            user.plan = PLAN_CONSULTANT
            db.commit()
    finally:
        db.close()
    return headers


# ── GET /analysis/diff ────────────────────────────────────────────────────────


class TestDiffPlanGate:
    def test_free_user_gets_402(self, client):
        headers = _free_headers(client)
        r = client.get("/analysis/diff?run_a=1&run_b=2", headers=headers)
        assert r.status_code == 402
        detail = r.json().get("detail", {})
        assert detail.get("feature") == "file_compare"

    def test_free_user_402_has_message(self, client):
        headers = _free_headers(client)
        r = client.get("/analysis/diff?run_a=1&run_b=2", headers=headers)
        assert r.status_code == 402
        detail = r.json().get("detail", {})
        assert "message" in detail
        assert len(detail["message"]) > 0

    def test_consultant_user_not_blocked_by_plan_gate(self, client):
        headers = _consultant_headers(client)
        r = client.get("/analysis/diff?run_a=999999&run_b=999998", headers=headers)
        # Plan gate passes — may get 404 (run not found) or 400 (bad IDs),
        # but must NOT return 402.
        assert r.status_code != 402


# ── GET /analysis/download-cleaned/{project_id} ───────────────────────────────


class TestDownloadCleanedPlanGate:
    def test_free_user_gets_402(self, client):
        headers = _free_headers(client)
        r = client.get("/analysis/download-cleaned/999999", headers=headers)
        assert r.status_code == 402
        detail = r.json().get("detail", {})
        assert detail.get("feature") == "report_export"

    def test_free_user_402_has_message(self, client):
        headers = _free_headers(client)
        r = client.get("/analysis/download-cleaned/999999", headers=headers)
        assert r.status_code == 402
        detail = r.json().get("detail", {})
        assert "message" in detail
        assert len(detail["message"]) > 0

    def test_consultant_user_not_blocked_by_plan_gate(self, client):
        headers = _consultant_headers(client)
        r = client.get("/analysis/download-cleaned/999999", headers=headers)
        # Plan gate passes — may get 404 (project not found), but must NOT 402.
        assert r.status_code != 402
