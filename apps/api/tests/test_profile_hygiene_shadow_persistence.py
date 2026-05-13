"""
90M — Tests that profile_hygiene_shadow_meta is persisted in fresh analysis
results across the sync route and inline stream.
"""
from __future__ import annotations

import io
import json

import pytest

from tests.conftest import TestingSessionLocal, _make_test_jwt, TEST_USER_ID
from app.plan_names import PLAN_CONSULTANT


CSV = (
    b"name,age,salary\n"
    b"Alice,30,70000\n"
    b"Bob,25,55000\n"
    b"Carol,35,90000\n"
)


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


def _create_project(client, headers) -> int:
    r = client.post("/projects", json={"name": "Shadow Persistence Test"}, headers=headers)
    assert r.status_code == 200
    return r.json()["id"]


def _upload(client, pid: int, headers) -> None:
    r = client.post(
        "/upload",
        files={"file": ("data.csv", io.BytesIO(CSV), "text/csv")},
        data={"project_id": str(pid)},
        headers=headers,
    )
    assert r.status_code == 200


def _parse_sse_result(sse_text: str) -> dict | None:
    for line in sse_text.split("\n"):
        if not line.startswith("data: "):
            continue
        try:
            event = json.loads(line[6:])
        except Exception:
            continue
        if event.get("result"):
            return event["result"]
    return None


def _patch_stream_db(monkeypatch) -> None:
    import app.routes.analysis_stream as stream_mod
    monkeypatch.setattr(stream_mod, "SessionLocal", TestingSessionLocal)


# ── Sync route ────────────────────────────────────────────────────────────────

class TestSyncShadowMeta:
    @pytest.fixture(autouse=True)
    def _run(self, client, monkeypatch):
        headers = _consultant_headers(client)
        pid = _create_project(client, headers)
        _upload(client, pid, headers)
        r = client.post("/analysis/run", json={"project_id": pid}, headers=headers)
        assert r.status_code == 200
        self.body = r.json()

    def test_key_present_in_result(self):
        assert "profile_hygiene_shadow_meta" in self.body

    def test_value_is_dict(self):
        meta = self.body["profile_hygiene_shadow_meta"]
        assert isinstance(meta, dict)

    def test_evaluated_field_present(self):
        meta = self.body["profile_hygiene_shadow_meta"]
        assert "evaluated" in meta

    def test_input_count_is_non_negative(self):
        meta = self.body["profile_hygiene_shadow_meta"]
        if meta.get("evaluated") is True:
            assert meta["input_count"] >= 0

    def test_profile_penalized_count_present_when_evaluated(self):
        meta = self.body["profile_hygiene_shadow_meta"]
        if meta.get("evaluated") is True:
            assert "profile_penalized_count" in meta

    def test_confidence_deltas_is_list_when_evaluated(self):
        meta = self.body["profile_hygiene_shadow_meta"]
        if meta.get("evaluated") is True:
            assert isinstance(meta["confidence_deltas"], list)


# ── Inline stream ─────────────────────────────────────────────────────────────

class TestStreamShadowMeta:
    @pytest.fixture(autouse=True)
    def _run(self, client, monkeypatch):
        _patch_stream_db(monkeypatch)
        headers = _consultant_headers(client)
        pid = _create_project(client, headers)
        _upload(client, pid, headers)
        token = _make_test_jwt()
        r = client.get(f"/analysis/stream/{pid}?token={token}")
        assert r.status_code == 200
        self.result = _parse_sse_result(r.text)
        assert self.result is not None, "SSE stream produced no result payload"

    def test_key_present_in_stream_result(self):
        assert "profile_hygiene_shadow_meta" in self.result

    def test_value_is_dict_in_stream(self):
        meta = self.result["profile_hygiene_shadow_meta"]
        assert isinstance(meta, dict)

    def test_evaluated_field_present_in_stream(self):
        meta = self.result["profile_hygiene_shadow_meta"]
        assert "evaluated" in meta
