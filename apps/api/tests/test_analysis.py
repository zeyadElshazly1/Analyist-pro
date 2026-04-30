"""
Tests for analysis endpoints: run, preview, history, result, share (Phase 0 + Phase 1 + Phase 2).
"""
import io
import json


def test_preview_no_file(client, project, auth_headers):
    pid = project["id"]
    r = client.get(f"/analysis/preview/{pid}", headers=auth_headers)
    assert r.status_code == 404


def test_preview_with_file(client, uploaded_project, auth_headers):
    pid = uploaded_project["id"]
    r = client.get(f"/analysis/preview/{pid}?rows=3", headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    assert "columns" in body
    assert "rows" in body
    assert "total_rows" in body
    assert "total_columns" in body
    assert "missing_pct" in body
    assert isinstance(body["rows"], list)
    if body["rows"]:
        assert isinstance(body["rows"][0], list)
    assert len(body["rows"]) <= 3
    assert body["total_rows"] == 10
    assert body["total_columns"] == 3


def test_run_analysis_no_file(client, project, auth_headers):
    r = client.post("/analysis/run", json={"project_id": project["id"]}, headers=auth_headers)
    assert r.status_code == 404


def test_run_analysis(client, uploaded_project, auth_headers):
    pid = uploaded_project["id"]
    r = client.post("/analysis/run", json={"project_id": pid}, headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    assert body["project_id"] == pid
    assert "health_result" in body
    assert "insight_results" in body
    assert "profile_result" in body
    assert "cleaning_result" in body
    assert "cleaning_summary" in body


def test_run_analysis_persists_to_history(client, uploaded_project, auth_headers):
    pid = uploaded_project["id"]
    client.post("/analysis/run", json={"project_id": pid}, headers=auth_headers)
    r = client.get(f"/analysis/history/{pid}", headers=auth_headers)
    assert r.status_code == 200
    hist = r.json()
    assert len(hist) == 1
    assert hist[0]["project_id"] == pid


def test_run_analysis_multiple_times(client, uploaded_project, auth_headers):
    pid = uploaded_project["id"]
    client.post("/analysis/run", json={"project_id": pid}, headers=auth_headers)
    client.post("/analysis/run", json={"project_id": pid}, headers=auth_headers)
    r = client.get(f"/analysis/history/{pid}?limit=10", headers=auth_headers)
    assert r.status_code == 200
    assert len(r.json()) == 2


def test_analysis_history_empty(client, project, auth_headers):
    r = client.get(f"/analysis/history/{project['id']}", headers=auth_headers)
    assert r.status_code == 200
    assert r.json() == []


def test_get_analysis_result(client, uploaded_project, auth_headers):
    pid = uploaded_project["id"]
    client.post("/analysis/run", json={"project_id": pid}, headers=auth_headers)
    hist = client.get(f"/analysis/history/{pid}", headers=auth_headers).json()
    analysis_id = hist[0]["id"]

    r = client.get(f"/analysis/result/{analysis_id}", headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    assert body["id"] == analysis_id
    assert body["project_id"] == pid
    assert "result" in body
    assert "health_result" in body["result"]


def test_get_analysis_result_not_found(client, auth_headers):
    r = client.get("/analysis/result/99999", headers=auth_headers)
    assert r.status_code == 404


def test_share_link_no_analysis(client, project, auth_headers):
    r = client.post(f"/analysis/share/{project['id']}", headers=auth_headers)
    assert r.status_code == 404


def test_share_link_created(client, uploaded_project, auth_headers):
    pid = uploaded_project["id"]
    client.post("/analysis/run", json={"project_id": pid}, headers=auth_headers)
    r = client.post(f"/analysis/share/{pid}", headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    assert "share_token" in body
    assert len(body["share_token"]) == 32


def test_share_link_idempotent(client, uploaded_project, auth_headers):
    """Calling share twice should return the same token."""
    pid = uploaded_project["id"]
    client.post("/analysis/run", json={"project_id": pid}, headers=auth_headers)
    t1 = client.post(f"/analysis/share/{pid}", headers=auth_headers).json()["share_token"]
    t2 = client.post(f"/analysis/share/{pid}", headers=auth_headers).json()["share_token"]
    assert t1 == t2


def test_get_shared_analysis(client, uploaded_project, auth_headers):
    """Public shared endpoint requires no auth."""
    pid = uploaded_project["id"]
    client.post("/analysis/run", json={"project_id": pid}, headers=auth_headers)
    token = client.post(f"/analysis/share/{pid}", headers=auth_headers).json()["share_token"]

    r = client.get(f"/analysis/shared/{token}")  # No auth headers
    assert r.status_code == 200
    body = r.json()
    assert body["project_id"] == pid
    assert "result" in body
    assert "health_result" in body["result"]


def test_get_shared_analysis_invalid_token(client):
    r = client.get("/analysis/shared/invalidtoken123")
    assert r.status_code == 404


def test_stats_count_analyses(client, uploaded_project, auth_headers):
    pid = uploaded_project["id"]
    client.post("/analysis/run", json={"project_id": pid}, headers=auth_headers)
    stats = client.get("/projects/stats", headers=auth_headers).json()
    assert stats["total_analyses"] == 1


def test_data_story_no_analysis(client, consultant_auth_headers):
    r = client.post("/analysis/story/99999", headers=consultant_auth_headers)
    assert r.status_code == 404


def test_data_story_returns_slides(client, uploaded_project, consultant_auth_headers):
    from app.services.ai_chat.story import STORY_SLIDE_TITLES

    pid = uploaded_project["id"]
    client.post("/analysis/run", json={"project_id": pid}, headers=consultant_auth_headers)
    hist = client.get(f"/analysis/history/{pid}", headers=consultant_auth_headers).json()
    analysis_id = hist[0]["id"]

    r = client.post(f"/analysis/story/{analysis_id}", headers=consultant_auth_headers)
    assert r.status_code == 200
    body = r.json()
    assert "title" in body
    assert "slides" in body
    assert len(body["slides"]) == 5
    for i, slide in enumerate(body["slides"]):
        assert "slide_num" in slide
        assert "title" in slide
        assert "narrative" in slide
        assert "key_points" in slide
        assert isinstance(slide["key_points"], list)
        assert len(slide["key_points"]) == 3
        assert slide["title"] == STORY_SLIDE_TITLES[i]


def test_data_story_persists_story_result_json(client, uploaded_project, consultant_auth_headers):
    from app.models import AnalysisResult
    from tests.conftest import TestingSessionLocal

    pid = uploaded_project["id"]
    client.post("/analysis/run", json={"project_id": pid}, headers=consultant_auth_headers)
    hist = client.get(f"/analysis/history/{pid}", headers=consultant_auth_headers).json()
    analysis_id = hist[0]["id"]

    r = client.post(f"/analysis/story/{analysis_id}", headers=consultant_auth_headers)
    assert r.status_code == 200

    db = TestingSessionLocal()
    try:
        row = db.query(AnalysisResult).filter(AnalysisResult.id == analysis_id).first()
        assert row is not None
        assert row.story_result_json and row.story_result_json.strip()
        stored = json.loads(row.story_result_json)
        assert len(stored.get("slides", [])) == 5
    finally:
        db.close()


def test_deterministic_story_references_columns():
    from app.services.ai_chat.story import deterministic_story_slides

    ar = {
        "dataset_summary": {"rows": 1200, "columns": 8, "numeric_cols": 3, "categorical_cols": 5},
        "insight_results": [
            {
                "title": "Churn is higher among month-to-month contracts",
                "severity": "high",
                "category": "binary_rates",
                "report_safe": True,
                "columns_used": ["Contract", "Churn"],
                "evidence": "~42% churn on month-to-month vs ~11% on two-year in this extract.",
                "recommendation": "Pilot retention offers on month-to-month before renewal season.",
            }
        ],
        "health_result": {
            "health_score": {"total_score": 74, "grade": "B"},
            "health_warnings": [{"severity": "medium", "message": "High-cardinality ID column present"}],
        },
        "cleaning_result": {
            "cleaning_summary": {"steps_applied": 3},
            "suspicious_columns": [{"column": "customerID", "issue_type": "id_like"}],
        },
    }
    s = deterministic_story_slides(ar)
    blob = json.dumps(s)
    assert "Contract" in blob or "Churn" in blob
    assert "1,200" in blob or "1200" in blob
    assert len(s["slides"]) == 5
    assert all(len(sl["key_points"]) == 3 for sl in s["slides"])
