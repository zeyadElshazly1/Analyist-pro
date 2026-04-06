"""
Tests for the health endpoint and project CRUD (Phase 0 + Phase 1).
"""


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["version"] == "2.0.0"


# ── Auth ──────────────────────────────────────────────────────────────────────

def test_get_me(client, auth_headers):
    """First call lazy-creates the user from the JWT, /me returns their data."""
    r = client.get("/auth/me", headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["email"] == "test@example.com"
    assert r.json()["plan"] == "free"


def test_protected_requires_auth(client):
    r = client.get("/projects")
    assert r.status_code == 401


def test_invalid_token_rejected(client):
    r = client.get("/projects", headers={"Authorization": "Bearer not-a-valid-jwt"})
    assert r.status_code == 401


# ── Project creation ──────────────────────────────────────────────────────────

def test_create_project(client, auth_headers):
    r = client.post("/projects", json={"name": "My Analysis"}, headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    assert body["name"] == "My Analysis"
    assert body["status"] == "created"
    assert "id" in body
    assert "created_at" in body


def test_create_project_empty_name(client, auth_headers):
    """API accepts empty name (validation is front-end responsibility)."""
    r = client.post("/projects", json={"name": ""}, headers=auth_headers)
    assert r.status_code == 200


def test_list_projects_empty(client, auth_headers):
    r = client.get("/projects", headers=auth_headers)
    assert r.status_code == 200
    assert r.json() == []


def test_list_projects(client, auth_headers):
    client.post("/projects", json={"name": "Alpha"}, headers=auth_headers)
    client.post("/projects", json={"name": "Beta"}, headers=auth_headers)
    r = client.get("/projects", headers=auth_headers)
    assert r.status_code == 200
    names = [p["name"] for p in r.json()]
    assert "Alpha" in names
    assert "Beta" in names


def test_get_project(client, project, auth_headers):
    pid = project["id"]
    r = client.get(f"/projects/{pid}", headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["id"] == pid


def test_get_project_not_found(client, auth_headers):
    r = client.get("/projects/99999", headers=auth_headers)
    assert r.status_code == 404


# ── Delete ────────────────────────────────────────────────────────────────────

def test_delete_project(client, project, auth_headers):
    pid = project["id"]
    r = client.delete(f"/projects/{pid}", headers=auth_headers)
    assert r.status_code == 204
    r2 = client.get(f"/projects/{pid}", headers=auth_headers)
    assert r2.status_code == 404


def test_delete_nonexistent_project(client, auth_headers):
    r = client.delete("/projects/99999", headers=auth_headers)
    assert r.status_code == 404


# ── Stats ─────────────────────────────────────────────────────────────────────

def test_project_stats_empty(client, auth_headers):
    r = client.get("/projects/stats", headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    assert body["total_projects"] == 0
    assert body["total_files"] == 0
    assert body["total_analyses"] == 0
    assert body["ready_projects"] == 0


def test_project_stats_after_creation(client, auth_headers):
    client.post("/projects", json={"name": "P1"}, headers=auth_headers)
    client.post("/projects", json={"name": "P2"}, headers=auth_headers)
    r = client.get("/projects/stats", headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["total_projects"] == 2
