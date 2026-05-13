"""
89B — Flow alignment tests.

Verifies that the sync route and inline stream produce results with the
same canonical top-level key set, and that cache-hit paths in both
routes backfill insight_selection_meta.

Note on stream route DB patching: analysis_stream.py imports SessionLocal
at module load time (not via FastAPI's Depends), so the setup_db autouse
fixture's app.db.SessionLocal patch does not reach it.  Stream tests that
exercise the HTTP layer must additionally patch
`app.routes.analysis_stream.SessionLocal` to the test session.
"""
from __future__ import annotations

import io
import json

import pytest

from tests.conftest import TestingSessionLocal, _make_test_jwt, TEST_USER_ID
from app.plan_names import PLAN_CONSULTANT

# ── Canonical shape ───────────────────────────────────────────────────────────

# Every fresh analysis result — regardless of which entry point produced it —
# must contain at least these top-level keys.
CANONICAL_RESULT_KEYS = frozenset({
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
    "profile_hygiene_shadow_meta",
})


# ── Shared helpers ────────────────────────────────────────────────────────────

CSV = (
    b"name,age,salary\n"
    b"Alice,30,70000\n"
    b"Bob,25,55000\n"
    b"Carol,35,90000\n"
)

LEGACY_CACHED_PAYLOAD = {
    "project_id": None,         # filled in per-test
    "cleaning_summary": {"steps": 0},
    "cleaning_result": {},
    "profile_result": [],
    "health_result": {"score": 0.8},
    "insight_results": [
        {"title": "Revenue trend", "confidence": 0.75, "suppressed_by_plan": False},
        {"title": "Unit anomaly", "confidence": 0.3, "suppressed_by_plan": False},
    ],
    "narrative": "Legacy narrative — predates 88M.",
    "executive_panel": {},
    "analysis_plan": {"dataset_kind": "generic", "confidence": 0.5},
    # insight_selection_meta intentionally absent
}


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


def _create_project(client, headers, name="Alignment Test") -> int:
    r = client.post("/projects", json={"name": name}, headers=headers)
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


def _run_sync(client, pid: int, headers):
    return client.post("/analysis/run", json={"project_id": pid}, headers=headers)


def _parse_sse_result(sse_text: str) -> dict | None:
    """Extract the final 'result' payload from an SSE response body."""
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
    """Patch the stream route's module-level SessionLocal to the test session.

    analysis_stream.py imports SessionLocal at module load time rather than
    using FastAPI's Depends, so the setup_db fixture's db_mod patch does not
    reach it.  This helper applies the same override for stream tests.
    """
    import app.routes.analysis_stream as stream_mod
    monkeypatch.setattr(stream_mod, "SessionLocal", TestingSessionLocal)


# ── Canonical shape: sync route ───────────────────────────────────────────────

class TestSyncRouteCanonicalShape:
    def test_fresh_result_contains_all_canonical_keys(self, client):
        headers = _consultant_headers(client)
        pid = _create_project(client, headers)
        _upload(client, pid, headers)

        r = _run_sync(client, pid, headers)
        assert r.status_code == 200, r.text
        body = r.json()

        missing = CANONICAL_RESULT_KEYS - set(body.keys())
        assert not missing, f"Sync fresh result missing keys: {missing}"

    def test_cache_hit_result_contains_all_canonical_keys(self, client, monkeypatch):
        import app.routes.analysis as analysis_mod
        from app.state import PROJECT_FILES

        headers = _consultant_headers(client)
        pid = _create_project(client, headers, name="Sync Cache Shape")
        _upload(client, pid, headers)

        # First run to populate PROJECT_FILES with a real file hash.
        r = _run_sync(client, pid, headers)
        assert r.status_code == 200

        fh = (PROJECT_FILES.get(pid) or {}).get("file_hash")
        assert fh

        _cache: dict[str, dict] = {}
        payload = {**LEGACY_CACHED_PAYLOAD, "project_id": pid}
        _cache[f"{pid}:{fh}"] = payload

        monkeypatch.setattr(analysis_mod, "get_cached_analysis", lambda p, h: _cache.get(f"{p}:{h}"))
        monkeypatch.setattr(analysis_mod, "set_cached_analysis", lambda p, h, v: _cache.__setitem__(f"{p}:{h}", v))

        r = _run_sync(client, pid, headers)
        assert r.status_code == 200, r.text
        body = r.json()

        assert body.get("insight_selection_meta") is not None
        assert body["insight_selection_meta"]["backfilled_from_cache"] is True


# ── Canonical shape: inline stream ────────────────────────────────────────────

class TestStreamInlineCanonicalShape:
    def test_fresh_result_contains_all_canonical_keys(self, client, monkeypatch):
        _patch_stream_db(monkeypatch)

        headers = _consultant_headers(client)
        pid = _create_project(client, headers, name="Stream Fresh Shape")
        _upload(client, pid, headers)

        token = _make_test_jwt()
        r = client.get(f"/analysis/stream/{pid}?token={token}")
        assert r.status_code == 200

        result = _parse_sse_result(r.text)
        assert result is not None, "No result event found in SSE stream"

        missing = CANONICAL_RESULT_KEYS - set(result.keys())
        assert not missing, f"Stream fresh result missing keys: {missing}"

    def test_cache_hit_backfills_insight_selection_meta(self, client, monkeypatch):
        import app.routes.analysis_stream as stream_mod
        from app.state import PROJECT_FILES

        _patch_stream_db(monkeypatch)

        headers = _consultant_headers(client)
        pid = _create_project(client, headers, name="Stream Cache Backfill")
        _upload(client, pid, headers)

        # First run — real pipeline — to ensure PROJECT_FILES has a file_hash.
        token = _make_test_jwt()
        r = client.get(f"/analysis/stream/{pid}?token={token}")
        assert r.status_code == 200

        fh = (PROJECT_FILES.get(pid) or {}).get("file_hash")
        assert fh, "Upload must have populated PROJECT_FILES with a file hash"

        # Seed a legacy cache payload (no insight_selection_meta).
        _cache: dict[str, dict] = {}
        _cache[f"{pid}:{fh}"] = {**LEGACY_CACHED_PAYLOAD, "project_id": pid}

        monkeypatch.setattr(stream_mod, "get_cached_analysis", lambda p, h: _cache.get(f"{p}:{h}"))
        monkeypatch.setattr(stream_mod, "set_cached_analysis", lambda p, h, v: _cache.__setitem__(f"{p}:{h}", v))

        r = client.get(f"/analysis/stream/{pid}?token={token}")
        assert r.status_code == 200

        result = _parse_sse_result(r.text)
        assert result is not None, "No result event in SSE stream"
        assert result.get("insight_selection_meta") is not None
        assert result["insight_selection_meta"]["backfilled_from_cache"] is True

    def test_cache_hit_result_contains_insight_selection_meta_key(self, client, monkeypatch):
        import app.routes.analysis_stream as stream_mod
        from app.state import PROJECT_FILES

        _patch_stream_db(monkeypatch)

        headers = _consultant_headers(client)
        pid = _create_project(client, headers, name="Stream Cache Keys")
        _upload(client, pid, headers)

        token = _make_test_jwt()
        client.get(f"/analysis/stream/{pid}?token={token}")

        fh = (PROJECT_FILES.get(pid) or {}).get("file_hash")
        assert fh

        _cache: dict[str, dict] = {}
        _cache[f"{pid}:{fh}"] = {**LEGACY_CACHED_PAYLOAD, "project_id": pid}

        monkeypatch.setattr(stream_mod, "get_cached_analysis", lambda p, h: _cache.get(f"{p}:{h}"))
        monkeypatch.setattr(stream_mod, "set_cached_analysis", lambda p, h, v: _cache.__setitem__(f"{p}:{h}", v))

        r = client.get(f"/analysis/stream/{pid}?token={token}")
        assert r.status_code == 200

        result = _parse_sse_result(r.text)
        assert result is not None
        assert "insight_selection_meta" in result


# ── Canonical shape: key-set parity between sync and stream ──────────────────

class TestSyncStreamKeyParity:
    """Sync fresh result and stream fresh result must share the same canonical keys."""

    def test_sync_and_stream_fresh_results_have_same_top_level_keys(
        self, client, monkeypatch
    ):
        _patch_stream_db(monkeypatch)
        headers = _consultant_headers(client)

        # Sync run
        pid_sync = _create_project(client, headers, name="Parity Sync")
        _upload(client, pid_sync, headers)
        r_sync = _run_sync(client, pid_sync, headers)
        assert r_sync.status_code == 200
        sync_keys = set(r_sync.json().keys())

        # Stream run (separate project — no cache cross-contamination)
        pid_stream = _create_project(client, headers, name="Parity Stream")
        _upload(client, pid_stream, headers)
        token = _make_test_jwt()
        r_stream = client.get(f"/analysis/stream/{pid_stream}?token={token}")
        assert r_stream.status_code == 200
        result = _parse_sse_result(r_stream.text)
        assert result is not None
        stream_keys = set(result.keys())

        only_in_sync = sync_keys - stream_keys
        only_in_stream = stream_keys - sync_keys

        assert not only_in_sync, f"Keys only in sync result: {only_in_sync}"
        assert not only_in_stream, f"Keys only in stream result: {only_in_stream}"
