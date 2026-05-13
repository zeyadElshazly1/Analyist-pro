"""
90M — profile_hygiene_shadow_meta exposed in saved run results.

Covers:
  • Completed run with profile_hygiene_shadow_meta in result_json returns the block.
  • Legacy completed run without the block returns None.
  • Incomplete / non-report_ready run returns None.
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


_SHADOW_STUB = {
    "evaluated": True,
    "input_count": 5,
    "profile_penalized_count": 1,
    "profile_penalty_reasons": {
        "profile_date_part_artifact": 1,
        "profile_high_cardinality_dimension": 0,
        "profile_leakage_candidate": 0,
        "profile_constant_column": 0,
    },
    "confidence_deltas": [
        {"index": 2, "before_confidence": 80.0, "after_confidence": 28.0,
         "reason": "profile_date_part_artifact", "title": "Trend in month", "category": "trend"},
    ],
}


def test_run_results_includes_shadow_meta_for_completed_run(
    client, uploaded_project, auth_headers
):
    """Completed runs with profile_hygiene_shadow_meta should expose it on reopen."""
    from app.db import SessionLocal
    from app.models import AnalysisResult

    pid = uploaded_project["id"]
    _run(client, pid, auth_headers)
    rid = _latest_run_id(client, pid, auth_headers)

    db = SessionLocal()
    try:
        row = db.query(AnalysisResult).filter(AnalysisResult.id == rid).first()
        stored = json.loads(row.result_json)
        stored["profile_hygiene_shadow_meta"] = _SHADOW_STUB
        row.result_json = json.dumps(stored, default=str)
        db.commit()
    finally:
        db.close()

    payload = _run_results(client, rid, auth_headers)

    assert payload["profile_hygiene_shadow_meta"] is not None
    assert payload["profile_hygiene_shadow_meta"]["evaluated"] is True
    assert payload["profile_hygiene_shadow_meta"]["profile_penalized_count"] == 1


def test_run_results_legacy_run_without_shadow_meta_returns_none(
    client, uploaded_project, auth_headers
):
    """Legacy result_json without profile_hygiene_shadow_meta must return None."""
    from app.db import SessionLocal
    from app.models import AnalysisResult

    pid = uploaded_project["id"]
    _run(client, pid, auth_headers)
    rid = _latest_run_id(client, pid, auth_headers)

    db = SessionLocal()
    try:
        row = db.query(AnalysisResult).filter(AnalysisResult.id == rid).first()
        stored = json.loads(row.result_json)
        stored.pop("profile_hygiene_shadow_meta", None)
        row.result_json = json.dumps(stored, default=str)
        db.commit()
    finally:
        db.close()

    payload = _run_results(client, rid, auth_headers)

    assert payload["profile_hygiene_shadow_meta"] is None
    assert payload["insight_results"] is not None


def test_run_results_incomplete_run_has_no_shadow_meta(
    client, uploaded_project, auth_headers
):
    """Runs that have not reached report_ready must return profile_hygiene_shadow_meta=None."""
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

    assert payload["profile_hygiene_shadow_meta"] is None
