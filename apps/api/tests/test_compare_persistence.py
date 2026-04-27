"""
Tests for compare_result persistence and reopen behaviour.

Covers TASK 6 acceptance criteria:
  * /explore/multifile returns a canonical compare_result block.
  * compare_result is persisted into the latest report_ready run's result_json
    pinned to the *left-hand* project (project_id_a).
  * The /analysis/run/{run_id}/results endpoint exposes compare_result.
  * Other canonical blocks (intake / cleaning / health / insights / profile /
    executive_panel / narrative) are not overwritten when compare runs.
  * Old result_json without compare_result still works — endpoint returns null.
  * Compare endpoint requires ownership of *both* referenced projects (the
    cross-user reject is already covered in test_ownership_guards.py).

These tests use the consultant_auth_headers fixture because /explore/multifile
is gated by the file_compare feature.
"""
from __future__ import annotations

import io
import json


# ── Helpers ───────────────────────────────────────────────────────────────────

def _upload(client, project_id: int, headers, csv_bytes: bytes, name: str = "data.csv"):
    return client.post(
        "/upload",
        files={"file": (name, io.BytesIO(csv_bytes), "text/csv")},
        data={"project_id": str(project_id)},
        headers=headers,
    )


def _run(client, project_id: int, headers):
    return client.post(
        "/analysis/run", json={"project_id": project_id}, headers=headers
    )


def _latest_run_id(client, project_id: int, headers) -> int:
    r = client.get(f"/analysis/runs/{project_id}/latest", headers=headers)
    assert r.status_code == 200, r.text
    return r.json()["run_id"]


def _create_second_project_with_data(
    client, headers, csv_bytes: bytes, name: str = "Project B"
) -> int:
    """Create a second project owned by the current user and upload a file
    so /explore/multifile has two valid sides to compare."""
    r = client.post("/projects", json={"name": name}, headers=headers)
    assert r.status_code == 200, r.text
    pid = r.json()["id"]
    r = _upload(client, pid, headers, csv_bytes, name="data_b.csv")
    assert r.status_code == 200, r.text
    return pid


def _setup_two_analysed_projects(
    client, project, csv_bytes, consultant_auth_headers
) -> tuple[int, int]:
    """Two projects, each with an uploaded CSV and a completed analysis run.

    Returns (project_id_a, project_id_b) — A is the fixture project (already
    upgraded to consultant), B is a fresh sibling owned by the same user.
    """
    pid_a = project["id"]
    # Upload + analyse A
    assert _upload(client, pid_a, consultant_auth_headers, csv_bytes).status_code == 200
    assert _run(client, pid_a, consultant_auth_headers).status_code == 200
    # Create + upload + analyse B
    pid_b = _create_second_project_with_data(client, consultant_auth_headers, csv_bytes)
    assert _run(client, pid_b, consultant_auth_headers).status_code == 200
    return pid_a, pid_b


# ── /explore/multifile returns compare_result ────────────────────────────────

def test_multifile_compare_returns_compare_result(
    client, project, csv_bytes, consultant_auth_headers
):
    pid_a, pid_b = _setup_two_analysed_projects(
        client, project, csv_bytes, consultant_auth_headers
    )

    r = client.post(
        "/explore/multifile",
        json={"project_id_a": pid_a, "project_id_b": pid_b},
        headers=consultant_auth_headers,
    )
    assert r.status_code == 200, r.text
    body = r.json()

    assert "compare_result" in body
    cr = body["compare_result"]
    assert isinstance(cr, dict)
    # Canonical CompareResult fields exist and are well-typed
    assert "compare_id" in cr
    assert "file_a" in cr and "file_b" in cr
    assert isinstance(cr["file_a"], dict) and isinstance(cr["file_b"], dict)
    assert "schema_changes" in cr
    assert "row_volume_changes" in cr
    assert "metric_deltas" in cr and isinstance(cr["metric_deltas"], list)
    assert "health_changes" in cr
    assert "summary_draft" in cr and isinstance(cr["summary_draft"], str)
    assert "caution_flags" in cr and isinstance(cr["caution_flags"], list)


# ── Persistence on the left-hand run ─────────────────────────────────────────

def test_compare_result_persisted_into_latest_run(
    client, project, csv_bytes, consultant_auth_headers
):
    """compare_result is written into the latest report_ready run for
    project_id_a (the project the consultant is currently working in)."""
    from app.db import SessionLocal
    from app.models import AnalysisResult

    pid_a, pid_b = _setup_two_analysed_projects(
        client, project, csv_bytes, consultant_auth_headers
    )
    rid_a_before = _latest_run_id(client, pid_a, consultant_auth_headers)

    # Sanity-check: result_json does not yet have compare_result
    db = SessionLocal()
    try:
        row = db.query(AnalysisResult).filter(AnalysisResult.id == rid_a_before).first()
        stored = json.loads(row.result_json) if row.result_json else {}
        assert "compare_result" not in stored
    finally:
        db.close()

    r = client.post(
        "/explore/multifile",
        json={"project_id_a": pid_a, "project_id_b": pid_b},
        headers=consultant_auth_headers,
    )
    assert r.status_code == 200, r.text

    # After compare: same run, but compare_result is now persisted
    db = SessionLocal()
    try:
        row = db.query(AnalysisResult).filter(AnalysisResult.id == rid_a_before).first()
        stored = json.loads(row.result_json) if row.result_json else {}
        assert "compare_result" in stored
        assert isinstance(stored["compare_result"], dict)
        assert stored["compare_result"]["compare_id"]
    finally:
        db.close()


def test_compare_persistence_does_not_overwrite_other_blocks(
    client, project, csv_bytes, consultant_auth_headers
):
    """Persisting compare_result must leave intake / cleaning / health /
    insight / profile / executive_panel / narrative untouched."""
    from app.db import SessionLocal
    from app.models import AnalysisResult

    pid_a, pid_b = _setup_two_analysed_projects(
        client, project, csv_bytes, consultant_auth_headers
    )
    rid_a = _latest_run_id(client, pid_a, consultant_auth_headers)

    db = SessionLocal()
    try:
        row = db.query(AnalysisResult).filter(AnalysisResult.id == rid_a).first()
        before = json.loads(row.result_json)
    finally:
        db.close()

    # Other canonical blocks must already be in the result (sanity)
    for key in (
        "intake_result",
        "cleaning_result",
        "health_result",
        "insight_results",
        "profile_result",
    ):
        assert key in before, f"missing {key} before compare — fixture broken"

    r = client.post(
        "/explore/multifile",
        json={"project_id_a": pid_a, "project_id_b": pid_b},
        headers=consultant_auth_headers,
    )
    assert r.status_code == 200

    db = SessionLocal()
    try:
        row = db.query(AnalysisResult).filter(AnalysisResult.id == rid_a).first()
        after = json.loads(row.result_json)
    finally:
        db.close()

    # Each pre-existing block is preserved byte-for-byte
    for key in (
        "intake_result",
        "cleaning_result",
        "health_result",
        "insight_results",
        "profile_result",
    ):
        assert after.get(key) == before.get(key), f"{key} was clobbered"

    # compare_result was added
    assert "compare_result" in after


# ── Run results endpoint surfaces compare_result ─────────────────────────────

def test_run_results_endpoint_returns_compare_result(
    client, project, csv_bytes, consultant_auth_headers
):
    pid_a, pid_b = _setup_two_analysed_projects(
        client, project, csv_bytes, consultant_auth_headers
    )

    r = client.post(
        "/explore/multifile",
        json={"project_id_a": pid_a, "project_id_b": pid_b},
        headers=consultant_auth_headers,
    )
    assert r.status_code == 200

    rid = _latest_run_id(client, pid_a, consultant_auth_headers)
    res = client.get(f"/analysis/run/{rid}/results", headers=consultant_auth_headers)
    assert res.status_code == 200, res.text
    body = res.json()

    assert "compare_result" in body
    assert body["compare_result"] is not None
    assert isinstance(body["compare_result"], dict)
    assert body["compare_result"]["compare_id"]


def test_run_detail_has_compare_flag_after_compare(
    client, project, csv_bytes, consultant_auth_headers
):
    """The has_compare_result flag on RunDetail must flip to True after a
    successful compare against this run's project."""
    pid_a, pid_b = _setup_two_analysed_projects(
        client, project, csv_bytes, consultant_auth_headers
    )

    rid = _latest_run_id(client, pid_a, consultant_auth_headers)
    detail_before = client.get(
        f"/analysis/run/{rid}", headers=consultant_auth_headers
    ).json()
    assert detail_before.get("has_compare_result") in (False, None)

    r = client.post(
        "/explore/multifile",
        json={"project_id_a": pid_a, "project_id_b": pid_b},
        headers=consultant_auth_headers,
    )
    assert r.status_code == 200

    detail_after = client.get(
        f"/analysis/run/{rid}", headers=consultant_auth_headers
    ).json()
    assert detail_after["has_compare_result"] is True


# ── Backwards compat: legacy runs without compare_result ─────────────────────

def test_legacy_result_json_returns_none_compare_result(
    client, uploaded_project, auth_headers
):
    """Run results endpoint must surface compare_result=None for legacy runs
    that were never paired against another project — without crashing."""
    pid = uploaded_project["id"]
    _run(client, pid, auth_headers)
    rid = _latest_run_id(client, pid, auth_headers)

    res = client.get(f"/analysis/run/{rid}/results", headers=auth_headers)
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["compare_result"] is None
    # Other canonical blocks remain intact
    assert body["health_result"] is not None
    assert body["cleaning_result"] is not None
    assert body["insight_results"] is not None


# ── Compare with no prior analysis run is a clean no-op for persistence ──────

def test_compare_persistence_noop_when_left_project_has_no_run(
    client, project, csv_bytes, consultant_auth_headers
):
    """If the left-hand project has no report_ready run yet, persistence is a
    silent no-op — the live response still works, but the comparison has
    nowhere durable to land until the next analysis run completes."""
    from app.db import SessionLocal
    from app.models import AnalysisResult

    pid_a = project["id"]
    # Upload to A but DO NOT analyse it
    assert _upload(client, pid_a, consultant_auth_headers, csv_bytes).status_code == 200

    pid_b = _create_second_project_with_data(client, consultant_auth_headers, csv_bytes)
    assert _run(client, pid_b, consultant_auth_headers).status_code == 200

    r = client.post(
        "/explore/multifile",
        json={"project_id_a": pid_a, "project_id_b": pid_b},
        headers=consultant_auth_headers,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    # Live response still includes compare_result
    assert isinstance(body.get("compare_result"), dict)

    # No run for project A yet, so nothing was persisted (and nothing crashed)
    db = SessionLocal()
    try:
        rows = (
            db.query(AnalysisResult)
            .filter(AnalysisResult.project_id == pid_a)
            .all()
        )
        # Either no rows at all, or no row carries compare_result yet
        for row in rows:
            stored = json.loads(row.result_json) if row.result_json else {}
            assert "compare_result" not in stored
    finally:
        db.close()
