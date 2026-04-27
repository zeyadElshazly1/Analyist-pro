"""
Tests for intake_result persistence and reopen behaviour.

Covers TASK 3 acceptance criteria:
  • Upload returns an intake_result block.
  • Sync analysis stores intake_result inside result_json.
  • The /analysis/run/{run_id}/results endpoint exposes intake_result.
  • Old result_json without intake_result still works (clean None).
  • Cache hit backfills intake_result on subsequent runs.
"""
import io
import json


# ── Helpers ───────────────────────────────────────────────────────────────────

def _upload(client, project_id: int, headers, csv_bytes: bytes):
    return client.post(
        "/upload",
        files={"file": ("data.csv", io.BytesIO(csv_bytes), "text/csv")},
        data={"project_id": str(project_id)},
        headers=headers,
    )


def _run(client, project_id: int, headers):
    return client.post(
        "/analysis/run", json={"project_id": project_id}, headers=headers
    )


def _latest_run_id(client, project_id: int, headers) -> int:
    r = client.get(
        f"/analysis/runs/{project_id}/latest", headers=headers
    )
    assert r.status_code == 200, r.text
    return r.json()["run_id"]


# ── Upload returns intake_result ──────────────────────────────────────────────

def test_upload_returns_intake_result(client, project, csv_bytes, auth_headers):
    pid = project["id"]
    r = _upload(client, pid, auth_headers, csv_bytes)
    assert r.status_code == 200, r.text
    body = r.json()
    assert "intake_result" in body
    intake = body["intake_result"]
    assert isinstance(intake, dict) and len(intake) > 0
    assert intake["file_name"] == "data.csv"
    assert intake["parse_status"] in ("ok", "parsed_with_warnings", "fallback")
    assert 0.0 <= intake["confidence"] <= 1.0
    assert isinstance(intake["preview_sample"], list)
    assert intake["n_columns"] == 3


# ── Sync analysis stores intake_result ────────────────────────────────────────

def test_run_response_includes_intake_result(client, uploaded_project, auth_headers):
    pid = uploaded_project["id"]
    r = _run(client, pid, auth_headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert "intake_result" in body
    intake = body["intake_result"]
    assert intake is not None
    assert intake["file_name"] == "data.csv"
    # Canonical-first: not buried inside other blocks.
    assert "intake_result" not in (body.get("health_result") or {})
    assert "intake_result" not in (body.get("cleaning_result") or {})


def test_intake_result_persisted_in_result_json(
    client, uploaded_project, auth_headers
):
    """Stored result_json must carry intake_result so reopens see it."""
    pid = uploaded_project["id"]
    _run(client, pid, auth_headers)

    hist = client.get(f"/analysis/history/{pid}", headers=auth_headers).json()
    aid = hist[0]["id"]
    full = client.get(
        f"/analysis/result/{aid}", headers=auth_headers
    ).json()
    stored = full["result"]
    assert "intake_result" in stored
    assert stored["intake_result"] is not None
    assert stored["intake_result"]["file_name"] == "data.csv"


# ── Run results endpoint surfaces intake_result ──────────────────────────────

def test_run_results_endpoint_returns_intake_result(
    client, uploaded_project, auth_headers
):
    pid = uploaded_project["id"]
    _run(client, pid, auth_headers)
    rid = _latest_run_id(client, pid, auth_headers)

    r = client.get(f"/analysis/run/{rid}/results", headers=auth_headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert "intake_result" in body
    assert body["intake_result"] is not None
    assert body["intake_result"]["file_name"] == "data.csv"
    assert body["intake_result"]["parse_status"] in (
        "ok", "parsed_with_warnings", "fallback"
    )


# ── Backwards compat: old runs without intake_result still work ──────────────

def test_legacy_result_json_returns_none_intake_result(
    client, uploaded_project, auth_headers
):
    """Run results endpoint must surface intake_result=None for legacy runs."""
    from app.db import SessionLocal
    from app.models import AnalysisResult

    pid = uploaded_project["id"]
    _run(client, pid, auth_headers)
    rid = _latest_run_id(client, pid, auth_headers)

    db = SessionLocal()
    try:
        row = db.query(AnalysisResult).filter(AnalysisResult.id == rid).first()
        stored = json.loads(row.result_json)
        stored.pop("intake_result", None)
        row.result_json = json.dumps(stored, default=str)
        db.commit()
    finally:
        db.close()

    r = client.get(f"/analysis/run/{rid}/results", headers=auth_headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["intake_result"] is None
    # Other canonical blocks must still be intact.
    assert body["health_result"] is not None
    assert body["cleaning_result"] is not None
    assert body["insight_results"] is not None


# ── Cache hit backfills intake_result ─────────────────────────────────────────

def test_cache_hit_backfills_missing_intake_result(
    client, uploaded_project, auth_headers, monkeypatch
):
    """Second run hits the cache; if cached payload had no intake_result we
    backfill it before returning so the UI is consistent."""
    import app.routes.analysis as analysis_mod

    pid = uploaded_project["id"]

    # Stub the cache helpers so we can simulate a pre-fix legacy payload.
    legacy_cache: dict[str, dict] = {}

    def fake_get(project_id: int, file_hash: str | None):
        if not file_hash:
            return None
        return legacy_cache.get(f"{project_id}:{file_hash}")

    def fake_set(project_id: int, file_hash: str | None, result: dict):
        if not file_hash:
            return
        legacy_cache[f"{project_id}:{file_hash}"] = result

    monkeypatch.setattr(analysis_mod, "get_cached_analysis", fake_get)
    monkeypatch.setattr(analysis_mod, "set_cached_analysis", fake_set)

    # Pre-seed the cache with a payload that has NO intake_result (legacy shape).
    from app.state import PROJECT_FILES
    fh = (PROJECT_FILES.get(pid) or {}).get("file_hash")
    assert fh, "Upload should have populated PROJECT_FILES with a file hash"
    legacy_cache[f"{pid}:{fh}"] = {
        "project_id": pid,
        "cleaning_summary": {"steps": 0},
        "cleaning_result": {},
        "profile_result": [],
        "health_result": {"some": "value"},
        "insight_results": [],
        "narrative": "legacy",
        "executive_panel": {},
    }

    # Re-run — should hit the (legacy) cache and backfill intake_result.
    r = _run(client, pid, auth_headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("intake_result"), (
        "Cache-hit response must backfill intake_result for legacy payloads"
    )
    assert body["intake_result"]["file_name"] == "data.csv"
    # The cache itself should now also be updated.
    assert legacy_cache[f"{pid}:{fh}"]["intake_result"] is not None


# ── Canonical block isolation ─────────────────────────────────────────────────

def test_intake_result_is_top_level_canonical_block(
    client, uploaded_project, auth_headers
):
    """intake_result must live as its own block, not inside health/cleaning."""
    pid = uploaded_project["id"]
    r = _run(client, pid, auth_headers)
    body = r.json()

    assert "intake_result" in body
    intake = body["intake_result"]
    assert intake is not None

    # Canonical fields exposed only at the top level.
    expected_keys = {
        "file_id", "file_name", "parse_status", "confidence", "file_kind",
        "detected_header_row", "preamble_rows", "footer_rows", "delimiter",
        "encoding", "n_columns", "warnings", "parsing_decisions",
        "file_metadata", "preview_sample",
    }
    assert expected_keys.issubset(set(intake.keys()))


# ── Cross-user isolation: ownership guard still applies ──────────────────────

def test_intake_result_not_visible_to_other_users(
    client, uploaded_project, auth_headers
):
    """A second user must not be able to fetch intake_result for someone
    else's run via the run-results endpoint."""
    import base64
    import hashlib
    import hmac
    import json as _json
    import time

    from tests.conftest import TEST_JWT_SECRET

    pid = uploaded_project["id"]
    _run(client, pid, auth_headers)
    rid = _latest_run_id(client, pid, auth_headers)

    # Build a JWT for a different user id.
    secret = TEST_JWT_SECRET.encode()

    def b64url(data: bytes) -> str:
        return base64.urlsafe_b64encode(data).rstrip(b"=").decode()

    other_id = "00000000-0000-0000-0000-0000000000ff"
    header = b64url(_json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
    payload = b64url(_json.dumps({
        "sub": other_id,
        "email": "other@example.com",
        "role": "authenticated",
        "aud": "authenticated",
        "exp": int(time.time()) + 3600,
    }).encode())
    signing_input = f"{header}.{payload}".encode()
    sig = b64url(hmac.new(secret, signing_input, hashlib.sha256).digest())
    other_headers = {"Authorization": f"Bearer {header}.{payload}.{sig}"}

    r = client.get(f"/analysis/run/{rid}/results", headers=other_headers)
    assert r.status_code == 404
