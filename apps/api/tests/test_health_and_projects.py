"""
Tests for the health endpoint and project CRUD (Phase 0 + Phase 1).
"""


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["version"] == "2.0.0"


# ── Project creation ──────────────────────────────────────────────────────────

def test_create_project(client):
    r = client.post("/projects", json={"name": "My Analysis"})
    assert r.status_code == 200
    body = r.json()
    assert body["name"] == "My Analysis"
    assert body["status"] == "created"
    assert "id" in body
    assert "created_at" in body


def test_create_project_empty_name(client):
    """API accepts empty name (validation is front-end responsibility)."""
    r = client.post("/projects", json={"name": ""})
    # Should succeed at API level — empty string is a valid str
    assert r.status_code == 200


def test_list_projects_empty(client):
    r = client.get("/projects")
    assert r.status_code == 200
    assert r.json() == []


def test_list_projects(client):
    client.post("/projects", json={"name": "Alpha"})
    client.post("/projects", json={"name": "Beta"})
    r = client.get("/projects")
    assert r.status_code == 200
    names = [p["name"] for p in r.json()]
    assert "Alpha" in names
    assert "Beta" in names


def test_get_project(client, project):
    pid = project["id"]
    r = client.get(f"/projects/{pid}")
    assert r.status_code == 200
    assert r.json()["id"] == pid


def test_get_project_not_found(client):
    r = client.get("/projects/99999")
    assert r.status_code == 404


# ── Delete ────────────────────────────────────────────────────────────────────

def test_delete_project(client, project):
    pid = project["id"]
    r = client.delete(f"/projects/{pid}")
    assert r.status_code == 204
    # Confirm it's gone
    r2 = client.get(f"/projects/{pid}")
    assert r2.status_code == 404


def test_delete_nonexistent_project(client):
    r = client.delete("/projects/99999")
    assert r.status_code == 404


# ── Stats ─────────────────────────────────────────────────────────────────────

def test_project_stats_empty(client):
    r = client.get("/projects/stats")
    assert r.status_code == 200
    body = r.json()
    assert body["total_projects"] == 0
    assert body["total_files"] == 0
    assert body["total_analyses"] == 0
    assert body["ready_projects"] == 0


def test_project_stats_after_creation(client):
    client.post("/projects", json={"name": "P1"})
    client.post("/projects", json={"name": "P2"})
    r = client.get("/projects/stats")
    assert r.status_code == 200
    assert r.json()["total_projects"] == 2
