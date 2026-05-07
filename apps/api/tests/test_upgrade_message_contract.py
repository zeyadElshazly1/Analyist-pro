"""
81E — UPGRADE_MESSAGES / plan-gate HTTP 402 contract tests.

Verifies that:
- Every feature in PLAN_FEATURES exists in PLAN_LIMITS for every plan.
- Every feature in PLAN_FEATURES has an UPGRADE_MESSAGES entry.
- require_feature() raises HTTP 402 with the correct payload shape for
  free users.
- detail.feature exactly matches the requested feature key.
- detail.message and detail.current_plan are present.
- Consultant users pass all Consultant-enabled features without 402.
- check_project_limit() raises HTTP 402 with feature="projects".
"""
from __future__ import annotations

import pytest

from app.middleware.plans import (
    PLAN_FEATURES,
    PLAN_LIMITS,
    UPGRADE_MESSAGES,
)
from app.plan_names import PLAN_CONSULTANT, PLAN_FREE, PLAN_STUDIO
from tests.conftest import TestingSessionLocal, _make_test_jwt, TEST_USER_ID


# ── Static contract checks (no HTTP) ──────────────────────────────────────────

class TestPlanFeatureContract:
    def test_every_plan_feature_in_plan_limits_for_all_plans(self):
        for plan, limits in PLAN_LIMITS.items():
            for feature in PLAN_FEATURES:
                assert feature in limits, (
                    f"Feature '{feature}' missing from PLAN_LIMITS['{plan}']"
                )

    def test_every_plan_feature_has_upgrade_message(self):
        for feature in PLAN_FEATURES:
            assert feature in UPGRADE_MESSAGES, (
                f"Feature '{feature}' has no entry in UPGRADE_MESSAGES"
            )
            assert len(UPGRADE_MESSAGES[feature]) > 0

    def test_upgrade_messages_ancillary_keys_present(self):
        assert "projects" in UPGRADE_MESSAGES
        assert "file_size" in UPGRADE_MESSAGES
        assert "team" in UPGRADE_MESSAGES

    def test_free_plan_blocks_all_plan_features(self):
        free_limits = PLAN_LIMITS[PLAN_FREE]
        for feature in PLAN_FEATURES:
            assert free_limits[feature] is False, (
                f"Free plan should block '{feature}'"
            )

    def test_consultant_plan_allows_non_team_features(self):
        # "team" is Studio-only; all other PLAN_FEATURES are enabled for Consultant.
        consultant_limits = PLAN_LIMITS[PLAN_CONSULTANT]
        for feature in PLAN_FEATURES - {"team"}:
            assert consultant_limits[feature] is True, (
                f"Consultant plan should allow '{feature}'"
            )
        assert consultant_limits["team"] is False

    def test_studio_plan_allows_all_plan_features(self):
        studio_limits = PLAN_LIMITS[PLAN_STUDIO]
        for feature in PLAN_FEATURES:
            assert studio_limits[feature] is True, (
                f"Studio plan should allow '{feature}'"
            )


# ── HTTP 402 payload contract (integration via TestClient) ─────────────────────

def _free_headers(client) -> dict:
    token = _make_test_jwt()
    headers = {"Authorization": f"Bearer {token}"}
    client.get("/auth/me", headers=headers)
    return headers


def _consultant_headers(client) -> dict:
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


# Map each gated feature to a representative route we can hit cheaply
_FEATURE_PROBE_ROUTES: dict[str, tuple[str, str]] = {
    "file_compare":  ("GET", "/analysis/diff?run_a=1&run_b=2"),
    "report_export": ("GET", "/analysis/download-cleaned/999999"),
}


class TestRequireFeature402Payload:
    @pytest.mark.parametrize("feature,method,path", [
        (f, m, p) for f, (m, p) in _FEATURE_PROBE_ROUTES.items()
    ])
    def test_free_user_gets_402(self, client, feature, method, path):
        headers = _free_headers(client)
        r = client.request(method, path, headers=headers)
        assert r.status_code == 402

    @pytest.mark.parametrize("feature,method,path", [
        (f, m, p) for f, (m, p) in _FEATURE_PROBE_ROUTES.items()
    ])
    def test_402_detail_has_message(self, client, feature, method, path):
        headers = _free_headers(client)
        r = client.request(method, path, headers=headers)
        detail = r.json().get("detail", {})
        assert "message" in detail
        assert len(detail["message"]) > 0

    @pytest.mark.parametrize("feature,method,path", [
        (f, m, p) for f, (m, p) in _FEATURE_PROBE_ROUTES.items()
    ])
    def test_402_detail_feature_matches_feature_key(self, client, feature, method, path):
        headers = _free_headers(client)
        r = client.request(method, path, headers=headers)
        detail = r.json().get("detail", {})
        assert detail.get("feature") == feature

    @pytest.mark.parametrize("feature,method,path", [
        (f, m, p) for f, (m, p) in _FEATURE_PROBE_ROUTES.items()
    ])
    def test_402_detail_has_current_plan(self, client, feature, method, path):
        headers = _free_headers(client)
        r = client.request(method, path, headers=headers)
        detail = r.json().get("detail", {})
        assert "current_plan" in detail
        assert detail["current_plan"] == PLAN_FREE

    @pytest.mark.parametrize("feature,method,path", [
        (f, m, p) for f, (m, p) in _FEATURE_PROBE_ROUTES.items()
    ])
    def test_consultant_user_not_blocked(self, client, feature, method, path):
        headers = _consultant_headers(client)
        r = client.request(method, path, headers=headers)
        assert r.status_code != 402


# ── check_project_limit contract ──────────────────────────────────────────────

class TestProjectLimitContract:
    def test_project_limit_402_has_feature_projects(self, client):
        """Free user hitting the project cap gets feature='projects'."""
        from app.plan_names import PLAN_FREE
        token = _make_test_jwt()
        headers = {"Authorization": f"Bearer {token}"}
        client.get("/auth/me", headers=headers)

        # Create 3 projects (free plan limit)
        for i in range(3):
            client.post("/projects", json={"name": f"proj {i}"}, headers=headers)

        # Fourth project should be blocked
        r = client.post("/projects", json={"name": "proj 4"}, headers=headers)
        assert r.status_code == 402
        detail = r.json().get("detail", {})
        assert detail.get("feature") == "projects"
        assert "message" in detail
        assert "current_plan" in detail
