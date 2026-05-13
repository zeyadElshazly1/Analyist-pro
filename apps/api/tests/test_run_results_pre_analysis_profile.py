"""
90G — pre_analysis_profile exposed in saved run results.

Covers:
  • Completed run with pre_analysis_profile in result_json returns the block.
  • Legacy completed run without the block returns None.
  • Incomplete / non-report_ready run returns None.
  • Cache-hit backfill builds the profile from the *cleaned* dataset, not raw.
"""
import json


def _run(client, project_id: int, headers):
    return client.post("/analysis/run", json={"project_id": project_id}, headers=headers)


def _latest_run_id(client, project_id: int, headers) -> int:
    r = client.get(f"/analysis/runs/{project_id}/latest", headers=headers)
    assert r.status_code == 200, r.text
    return r.json()["run_id"]


def _run_results(client, run_id: int, headers) -> dict:
    r = client.get(f"/analysis/run/{run_id}/results", headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


_PROFILE_STUB = {
    "fingerprint": {"row_count": 50, "column_count": 4, "dataset_shape": "snapshot"},
    "grain_label": "order",
    "grain_confidence": 0.9,
    "planner_version": "v2.0-deterministic",
}


def test_run_results_includes_pre_analysis_profile_for_completed_run(
    client, uploaded_project, auth_headers
):
    """Runs that produced pre_analysis_profile should expose it on reopen."""
    from app.db import SessionLocal
    from app.models import AnalysisResult

    pid = uploaded_project["id"]
    _run(client, pid, auth_headers)
    rid = _latest_run_id(client, pid, auth_headers)

    db = SessionLocal()
    try:
        row = db.query(AnalysisResult).filter(AnalysisResult.id == rid).first()
        stored = json.loads(row.result_json)
        stored["pre_analysis_profile"] = _PROFILE_STUB
        row.result_json = json.dumps(stored, default=str)
        db.commit()
    finally:
        db.close()

    payload = _run_results(client, rid, auth_headers)

    assert payload["pre_analysis_profile"] is not None
    assert payload["pre_analysis_profile"]["grain_label"] == "order"
    assert payload["pre_analysis_profile"]["grain_confidence"] == 0.9


def test_run_results_legacy_run_without_pre_analysis_profile_returns_none(
    client, uploaded_project, auth_headers
):
    """Legacy result_json without pre_analysis_profile must return None."""
    from app.db import SessionLocal
    from app.models import AnalysisResult

    pid = uploaded_project["id"]
    _run(client, pid, auth_headers)
    rid = _latest_run_id(client, pid, auth_headers)

    db = SessionLocal()
    try:
        row = db.query(AnalysisResult).filter(AnalysisResult.id == rid).first()
        stored = json.loads(row.result_json)
        stored.pop("pre_analysis_profile", None)
        row.result_json = json.dumps(stored, default=str)
        db.commit()
    finally:
        db.close()

    payload = _run_results(client, rid, auth_headers)

    assert payload["pre_analysis_profile"] is None
    # Other canonical blocks must remain intact.
    assert payload["insight_results"] is not None


def test_run_results_incomplete_run_has_no_pre_analysis_profile(
    client, uploaded_project, auth_headers
):
    """Runs that have not reached report_ready must return pre_analysis_profile=None."""
    from app.db import SessionLocal
    from app.models import AnalysisResult

    pid = uploaded_project["id"]
    _run(client, pid, auth_headers)
    rid = _latest_run_id(client, pid, auth_headers)

    db = SessionLocal()
    try:
        row = db.query(AnalysisResult).filter(AnalysisResult.id == rid).first()
        row.status = "created"
        db.commit()
    finally:
        db.close()

    payload = _run_results(client, rid, auth_headers)

    assert payload["pre_analysis_profile"] is None


def test_cache_hit_backfill_uses_cleaned_dataset(client, uploaded_project, auth_headers, monkeypatch):
    """Backfill must pass the cleaned frame to build_pre_analysis_profile, not the raw one.

    Strategy: monkeypatch build_pre_analysis_profile in the sync-route module to
    capture the DataFrame it receives, then trigger a cache-hit backfill and
    assert the captured frame has the same columns as what clean_dataset produces
    from the project file.
    """
    import app.routes.analysis as analysis_mod
    from app.state import PROJECT_FILES
    from app.services.cleaner import clean_dataset as _clean
    from app.services.file_loader import load_dataset as _load
    from app.services.analysis.pre_analysis import build_pre_analysis_profile as _real_build

    pid = uploaded_project["id"]

    # First real run to populate PROJECT_FILES with a file_hash and file_path.
    _run(client, pid, auth_headers)

    fh = (PROJECT_FILES.get(pid) or {}).get("file_hash")
    assert fh, "file_hash must be set after a real run"
    file_path = (PROJECT_FILES.get(pid) or {}).get("path")
    assert file_path

    # Determine what columns clean_dataset produces for this file.
    _raw = _load(file_path)
    _cleaned, _, _ = _clean(_raw)
    expected_cols = set(_cleaned.columns.tolist())

    # Capture the DataFrame columns passed to build_pre_analysis_profile during backfill.
    captured: list = []

    def _spy(df):
        captured.append(df.columns.tolist())
        return _real_build(df)

    monkeypatch.setattr(analysis_mod, "build_pre_analysis_profile", _spy)

    # Seed a legacy cache entry (no pre_analysis_profile).
    _cache: dict = {}
    legacy = {
        "project_id": pid,
        "cleaning_summary": {"steps": 0},
        "cleaning_result": {},
        "profile_result": [],
        "health_result": {},
        "insight_results": [],
        "narrative": "",
        "executive_panel": {},
        "analysis_plan": {"dataset_kind": "generic", "confidence": 0.5},
        "insight_selection_meta": {"backfilled_from_cache": True},
        # pre_analysis_profile intentionally absent
    }
    _cache[f"{pid}:{fh}"] = legacy

    monkeypatch.setattr(analysis_mod, "get_cached_analysis", lambda p, h: _cache.get(f"{p}:{h}"))
    monkeypatch.setattr(analysis_mod, "set_cached_analysis", lambda p, h, v: _cache.__setitem__(f"{p}:{h}", v))

    _run(client, pid, auth_headers)

    assert captured, "build_pre_analysis_profile was not called during backfill"
    assert set(captured[0]) == expected_cols, (
        f"Backfill used wrong columns.\n"
        f"  Got:      {sorted(captured[0])}\n"
        f"  Expected: {sorted(expected_cols)}"
    )
