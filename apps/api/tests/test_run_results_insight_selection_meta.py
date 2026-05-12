"""
88O — insight_selection_meta exposed in saved run results.

Covers:
  • Completed run with insight_selection_meta in result_json returns the block.
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


_META = {
    "post_hygiene_candidate_count": 20,
    "visible_insight_count": 15,
    "suppressed_candidate_count": 3,
    "suppressed_visible_count": 1,
    "final_cap": 15,
}


def test_run_results_includes_insight_selection_meta_for_completed_run(
    client, uploaded_project, auth_headers
):
    """Runs that produced insight_selection_meta should expose it on reopen."""
    from app.db import SessionLocal
    from app.models import AnalysisResult

    pid = uploaded_project["id"]
    _run(client, pid, auth_headers)
    rid = _latest_run_id(client, pid, auth_headers)

    db = SessionLocal()
    try:
        row = db.query(AnalysisResult).filter(AnalysisResult.id == rid).first()
        stored = json.loads(row.result_json)
        stored["insight_selection_meta"] = _META
        row.result_json = json.dumps(stored, default=str)
        db.commit()
    finally:
        db.close()

    payload = _run_results(client, rid, auth_headers)

    assert payload["insight_selection_meta"] is not None
    assert payload["insight_selection_meta"]["post_hygiene_candidate_count"] == 20
    assert payload["insight_selection_meta"]["final_cap"] == 15
    assert payload["insight_selection_meta"]["suppressed_candidate_count"] == 3
    assert payload["insight_selection_meta"]["suppressed_visible_count"] == 1
    assert payload["insight_selection_meta"]["visible_insight_count"] == 15


def test_run_results_legacy_run_without_insight_selection_meta_returns_none(
    client, uploaded_project, auth_headers
):
    """Legacy result_json without insight_selection_meta must return None."""
    from app.db import SessionLocal
    from app.models import AnalysisResult

    pid = uploaded_project["id"]
    _run(client, pid, auth_headers)
    rid = _latest_run_id(client, pid, auth_headers)

    db = SessionLocal()
    try:
        row = db.query(AnalysisResult).filter(AnalysisResult.id == rid).first()
        stored = json.loads(row.result_json)
        stored.pop("insight_selection_meta", None)
        row.result_json = json.dumps(stored, default=str)
        db.commit()
    finally:
        db.close()

    payload = _run_results(client, rid, auth_headers)

    assert payload["insight_selection_meta"] is None
    # Other canonical blocks must remain intact.
    assert payload["insight_results"] is not None


def test_run_results_incomplete_run_has_no_insight_selection_meta(
    client, uploaded_project, auth_headers
):
    """Runs that have not reached report_ready must return insight_selection_meta=None."""
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

    assert payload["insight_selection_meta"] is None
