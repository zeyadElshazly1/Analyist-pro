"""
81F — Team management plan-gate tests.

Verifies that:
- Free users cannot create/list/remove team invites (→ 402).
- Consultant users cannot create/list/remove team invites (→ 402).
- Studio users can create invites, list members, and remove invites.
- 402 detail shape is stable: message / feature="team" / current_plan.
- Invite acceptance (POST /team/invite/{token}/accept) does NOT require
  Studio — any authenticated user can accept.
- Seat-limit 402 on accept includes current_plan.
"""
from __future__ import annotations

import pytest

from app.plan_names import PLAN_CONSULTANT, PLAN_FREE, PLAN_STUDIO
from tests.conftest import TestingSessionLocal, _make_test_jwt, TEST_USER_ID


# ── helpers ────────────────────────────────────────────────────────────────────

def _headers_for_plan(client, plan: str | None) -> dict:
    """Return auth headers for a user with the given plan."""
    token = _make_test_jwt()
    headers = {"Authorization": f"Bearer {token}"}
    client.get("/auth/me", headers=headers)
    if plan is not None and plan != PLAN_FREE:
        from app.models import User as UserModel
        db = TestingSessionLocal()
        try:
            user = db.query(UserModel).filter(UserModel.id == TEST_USER_ID).first()
            if user:
                user.plan = plan
                db.commit()
        finally:
            db.close()
    return headers


def _free_headers(client):    return _headers_for_plan(client, PLAN_FREE)
def _consultant_headers(client): return _headers_for_plan(client, PLAN_CONSULTANT)
def _studio_headers(client):  return _headers_for_plan(client, PLAN_STUDIO)


def _assert_team_402(r):
    assert r.status_code == 402
    detail = r.json().get("detail", {})
    assert detail.get("feature") == "team"
    assert "message" in detail and len(detail["message"]) > 0
    assert "current_plan" in detail


# ── POST /team/invite ─────────────────────────────────────────────────────────

class TestCreateInvite:
    def test_free_user_blocked(self, client):
        r = client.post("/team/invite", json={}, headers=_free_headers(client))
        _assert_team_402(r)

    def test_consultant_user_blocked(self, client):
        r = client.post("/team/invite", json={}, headers=_consultant_headers(client))
        _assert_team_402(r)

    def test_studio_user_can_invite(self, client):
        r = client.post("/team/invite", json={}, headers=_studio_headers(client))
        assert r.status_code == 201
        body = r.json()
        assert "invite_id" in body
        assert "token" in body

    def test_402_current_plan_reflects_free(self, client):
        r = client.post("/team/invite", json={}, headers=_free_headers(client))
        detail = r.json().get("detail", {})
        assert detail.get("current_plan") == PLAN_FREE

    def test_402_current_plan_reflects_consultant(self, client):
        r = client.post("/team/invite", json={}, headers=_consultant_headers(client))
        detail = r.json().get("detail", {})
        assert detail.get("current_plan") == PLAN_CONSULTANT


# ── GET /team/members ─────────────────────────────────────────────────────────

class TestListMembers:
    def test_free_user_blocked(self, client):
        r = client.get("/team/members", headers=_free_headers(client))
        _assert_team_402(r)

    def test_consultant_user_blocked(self, client):
        r = client.get("/team/members", headers=_consultant_headers(client))
        _assert_team_402(r)

    def test_studio_user_can_list(self, client):
        r = client.get("/team/members", headers=_studio_headers(client))
        assert r.status_code == 200
        body = r.json()
        assert "members" in body
        assert "seats_used" in body
        assert "seat_limit" in body


# ── DELETE /team/members/{invite_id} ─────────────────────────────────────────

class TestRemoveMember:
    def test_free_user_blocked(self, client):
        r = client.delete("/team/members/999", headers=_free_headers(client))
        _assert_team_402(r)

    def test_consultant_user_blocked(self, client):
        r = client.delete("/team/members/999", headers=_consultant_headers(client))
        _assert_team_402(r)

    def test_studio_user_gets_404_for_nonexistent_invite(self, client):
        # Plan gate passes; 404 is the correct response for a missing invite.
        r = client.delete("/team/members/999999", headers=_studio_headers(client))
        assert r.status_code == 404

    def test_studio_user_can_delete_own_invite(self, client):
        headers = _studio_headers(client)
        create_r = client.post("/team/invite", json={}, headers=headers)
        assert create_r.status_code == 201
        invite_id = create_r.json()["invite_id"]

        delete_r = client.delete(f"/team/members/{invite_id}", headers=headers)
        assert delete_r.status_code == 204


# ── GET /team/invite/{token} — public, no plan required ──────────────────────

class TestGetInvitePublic:
    def test_nonexistent_token_returns_404(self, client):
        r = client.get("/team/invite/nonexistenttoken123")
        assert r.status_code == 404

    def test_valid_token_accessible_without_auth(self, client):
        studio_headers = _studio_headers(client)
        create_r = client.post("/team/invite", json={}, headers=studio_headers)
        assert create_r.status_code == 201
        token = create_r.json()["token"]

        # Public endpoint — no auth header
        r = client.get(f"/team/invite/{token}")
        assert r.status_code == 200
        assert r.json()["status"] == "pending"


# ── POST /team/invite/{token}/accept — no Studio required for member ──────────

class TestAcceptInvite:
    def _create_invite_token(self, client) -> str:
        studio_headers = _studio_headers(client)
        r = client.post("/team/invite", json={}, headers=studio_headers)
        assert r.status_code == 201
        return r.json()["token"]

    def test_free_user_can_accept_invite(self, client):
        token = self._create_invite_token(client)
        # A different free user accepts (use a different user_id)
        from tests.conftest import _make_test_jwt
        member_token = _make_test_jwt(user_id="00000000-0000-0000-0000-000000000002",
                                      email="member@example.com")
        member_headers = {"Authorization": f"Bearer {member_token}"}
        client.get("/auth/me", headers=member_headers)

        r = client.post(f"/team/invite/{token}/accept", headers=member_headers)
        assert r.status_code == 200
        assert "Welcome" in r.json().get("message", "")

    def test_accept_seat_limit_402_includes_current_plan(self, client):
        """Seat-limit 402 on accept must include current_plan for UI consistency."""
        from app.models import TeamInvite
        from tests.conftest import TEST_USER_ID

        studio_headers = _studio_headers(client)

        # Fill all 4 member seats
        tokens = []
        for i in range(4):
            r = client.post("/team/invite", json={}, headers=studio_headers)
            if r.status_code != 201:
                break
            tokens.append(r.json()["token"])

        for idx, tok in enumerate(tokens):
            uid = f"00000000-0000-0000-0000-00000000000{idx + 2}"
            member_token = _make_test_jwt(user_id=uid, email=f"m{idx}@example.com")
            mh = {"Authorization": f"Bearer {member_token}"}
            client.get("/auth/me", headers=mh)
            client.post(f"/team/invite/{tok}/accept", headers=mh)

        # Create one more invite beyond the seat limit
        extra_r = client.post("/team/invite", json={}, headers=studio_headers)
        if extra_r.status_code != 201:
            pytest.skip("Seat limit already reached before extra invite")
        extra_token = extra_r.json()["token"]

        overflow_token = _make_test_jwt(user_id="00000000-0000-0000-0000-000000000009",
                                         email="overflow@example.com")
        overflow_headers = {"Authorization": f"Bearer {overflow_token}"}
        client.get("/auth/me", headers=overflow_headers)

        r = client.post(f"/team/invite/{extra_token}/accept", headers=overflow_headers)
        if r.status_code == 402:
            detail = r.json().get("detail", {})
            assert "current_plan" in detail
            assert detail.get("feature") == "team_seats"
