"""
Tests for analysis endpoints: run, preview, history, result, share (Phase 0 + Phase 1).
"""
import io
import json


def test_preview_no_file(client, project):
    pid = project["id"]
    r = client.get(f"/analysis/preview/{pid}")
    assert r.status_code == 404


def test_preview_with_file(client, uploaded_project):
    pid = uploaded_project["id"]
    r = client.get(f"/analysis/preview/{pid}?rows=3")
    assert r.status_code == 200
    body = r.json()
    assert "columns" in body
    assert "rows" in body
    assert "total_rows" in body
    assert "total_columns" in body
    assert "missing_pct" in body
    # rows should be list-of-lists (not list-of-dicts)
    assert isinstance(body["rows"], list)
    if body["rows"]:
        assert isinstance(body["rows"][0], list)
    assert len(body["rows"]) <= 3
    assert body["total_rows"] == 10   # 10 data rows in fixture CSV
    assert body["total_columns"] == 3  # name, age, salary


def test_run_analysis_no_file(client, project):
    r = client.post("/analysis/run", json={"project_id": project["id"]})
    assert r.status_code == 404


def test_run_analysis(client, uploaded_project):
    pid = uploaded_project["id"]
    r = client.post("/analysis/run", json={"project_id": pid})
    assert r.status_code == 200
    body = r.json()
    assert body["project_id"] == pid
    assert "dataset_summary" in body
    assert "health_score" in body
    assert "insights" in body
    assert "profile" in body
    assert "cleaning_report" in body
    assert "cleaning_summary" in body


def test_run_analysis_persists_to_history(client, uploaded_project):
    pid = uploaded_project["id"]
    client.post("/analysis/run", json={"project_id": pid})
    r = client.get(f"/analysis/history/{pid}")
    assert r.status_code == 200
    hist = r.json()
    assert len(hist) == 1
    assert hist[0]["project_id"] == pid


def test_run_analysis_multiple_times(client, uploaded_project):
    pid = uploaded_project["id"]
    client.post("/analysis/run", json={"project_id": pid})
    client.post("/analysis/run", json={"project_id": pid})
    r = client.get(f"/analysis/history/{pid}?limit=10")
    assert r.status_code == 200
    assert len(r.json()) == 2


def test_analysis_history_empty(client, project):
    r = client.get(f"/analysis/history/{project['id']}")
    assert r.status_code == 200
    assert r.json() == []


def test_get_analysis_result(client, uploaded_project):
    pid = uploaded_project["id"]
    client.post("/analysis/run", json={"project_id": pid})
    hist = client.get(f"/analysis/history/{pid}").json()
    analysis_id = hist[0]["id"]

    r = client.get(f"/analysis/result/{analysis_id}")
    assert r.status_code == 200
    body = r.json()
    assert body["id"] == analysis_id
    assert body["project_id"] == pid
    assert "result" in body
    assert "dataset_summary" in body["result"]


def test_get_analysis_result_not_found(client):
    r = client.get("/analysis/result/99999")
    assert r.status_code == 404


def test_share_link_no_analysis(client, project):
    r = client.post(f"/analysis/share/{project['id']}")
    assert r.status_code == 404


def test_share_link_created(client, uploaded_project):
    pid = uploaded_project["id"]
    client.post("/analysis/run", json={"project_id": pid})
    r = client.post(f"/analysis/share/{pid}")
    assert r.status_code == 200
    body = r.json()
    assert "share_token" in body
    assert len(body["share_token"]) == 32  # UUID hex


def test_share_link_idempotent(client, uploaded_project):
    """Calling share twice should return the same token."""
    pid = uploaded_project["id"]
    client.post("/analysis/run", json={"project_id": pid})
    t1 = client.post(f"/analysis/share/{pid}").json()["share_token"]
    t2 = client.post(f"/analysis/share/{pid}").json()["share_token"]
    assert t1 == t2


def test_get_shared_analysis(client, uploaded_project):
    pid = uploaded_project["id"]
    client.post("/analysis/run", json={"project_id": pid})
    token = client.post(f"/analysis/share/{pid}").json()["share_token"]

    r = client.get(f"/analysis/shared/{token}")
    assert r.status_code == 200
    body = r.json()
    assert body["project_id"] == pid
    assert "result" in body
    assert "dataset_summary" in body["result"]


def test_get_shared_analysis_invalid_token(client):
    r = client.get("/analysis/shared/invalidtoken123")
    assert r.status_code == 404


def test_stats_count_analyses(client, uploaded_project):
    pid = uploaded_project["id"]
    client.post("/analysis/run", json={"project_id": pid})
    stats = client.get("/projects/stats").json()
    assert stats["total_analyses"] == 1
