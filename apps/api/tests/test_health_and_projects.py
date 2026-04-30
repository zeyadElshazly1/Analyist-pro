"""
Tests for the health endpoint and project CRUD (Phase 0 + Phase 1).
"""
import json
import time

import jwt
from cryptography.hazmat.primitives.asymmetric import ec
from jwt.algorithms import ECAlgorithm

import app.middleware.auth as auth_mod
from app.models import (
    AnalysisResult,
    PreparedDataset,
    Project,
    ProjectFeature,
    ProjectFile,
    ReportDraft,
)
from tests.conftest import TestingSessionLocal, _make_test_jwt


OTHER_USER_ID = "00000000-0000-0000-0000-0000000000aa"
OTHER_USER_EMAIL = "other-project-user@example.com"
ES256_USER_ID = "00000000-0000-0000-0000-0000000000ee"
ES256_USER_EMAIL = "es256@example.com"


def _other_headers(client) -> dict:
    token = _make_test_jwt(user_id=OTHER_USER_ID, email=OTHER_USER_EMAIL)
    headers = {"Authorization": f"Bearer {token}"}
    r = client.get("/auth/me", headers=headers)
    assert r.status_code == 200, r.text
    return headers


def _es256_headers(monkeypatch) -> dict:
    supabase_url = "https://test-project.supabase.co"
    kid = "test-es256-key"
    private_key = ec.generate_private_key(ec.SECP256R1())
    jwk = json.loads(ECAlgorithm.to_jwk(private_key.public_key()))
    jwk.update({"kid": kid, "alg": "ES256", "use": "sig"})

    monkeypatch.setenv("SUPABASE_URL", supabase_url)
    monkeypatch.setattr(auth_mod, "_jwks_cache", None)
    monkeypatch.setattr(auth_mod, "_jwks_cache_expires_at", 0.0)
    monkeypatch.setattr(auth_mod, "_fetch_jwks", lambda: {"keys": [jwk]})

    token = jwt.encode(
        {
            "sub": ES256_USER_ID,
            "email": ES256_USER_EMAIL,
            "role": "authenticated",
            "aud": "authenticated",
            "iss": f"{supabase_url}/auth/v1",
            "exp": int(time.time()) + 3600,
        },
        private_key,
        algorithm="ES256",
        headers={"kid": kid},
    )
    return {"Authorization": f"Bearer {token}"}


def _seed_project_children(project_id: int) -> None:
    db = TestingSessionLocal()
    try:
        project_file = ProjectFile(
            project_id=project_id,
            filename="source.csv",
            stored_path="/tmp/source.csv",
            size_bytes=12,
            file_hash="abc123",
        )
        db.add(project_file)
        db.flush()

        analysis = AnalysisResult(
            project_id=project_id,
            file_id=project_file.id,
            file_hash="abc123",
            result_json=json.dumps({"insights": []}),
            status="report_ready",
        )
        db.add(analysis)
        db.flush()

        db.add_all(
            [
                ReportDraft(
                    project_id=project_id,
                    analysis_result_id=analysis.id,
                    title="Draft",
                    summary="Saved draft",
                ),
                ProjectFeature(
                    project_id=project_id,
                    name="margin",
                    formula="revenue - cost",
                    dtype="number",
                ),
                PreparedDataset(
                    project_id=project_id,
                    file_hash="abc123",
                    stored_path="/tmp/prepared.parquet",
                    rows=10,
                    columns=3,
                ),
            ]
        )
        db.commit()
    finally:
        db.close()


def _seed_project_file(project_id: int) -> int:
    db = TestingSessionLocal()
    try:
        project_file = ProjectFile(
            project_id=project_id,
            filename="source.csv",
            stored_path="/tmp/source.csv",
            size_bytes=12,
            file_hash="abc123",
        )
        db.add(project_file)
        db.commit()
        db.refresh(project_file)
        return project_file.id
    finally:
        db.close()


def _seed_prepared_dataset(project_id: int) -> int:
    db = TestingSessionLocal()
    try:
        prepared = PreparedDataset(
            project_id=project_id,
            file_hash="abc123",
            stored_path="/tmp/prepared.parquet",
            rows=10,
            columns=3,
        )
        db.add(prepared)
        db.commit()
        db.refresh(prepared)
        return prepared.id
    finally:
        db.close()


def _seed_analysis_result(project_id: int) -> int:
    db = TestingSessionLocal()
    try:
        analysis = AnalysisResult(
            project_id=project_id,
            file_hash="abc123",
            result_json=json.dumps({"insights": []}),
            status="report_ready",
        )
        db.add(analysis)
        db.commit()
        db.refresh(analysis)
        return analysis.id
    finally:
        db.close()


def _seed_report_draft(project_id: int, analysis_result_id: int | None = None) -> int:
    db = TestingSessionLocal()
    try:
        draft = ReportDraft(
            project_id=project_id,
            analysis_result_id=analysis_result_id,
            title="Draft",
            summary="Saved draft",
        )
        db.add(draft)
        db.commit()
        db.refresh(draft)
        return draft.id
    finally:
        db.close()


def _seed_project_feature(project_id: int) -> int:
    db = TestingSessionLocal()
    try:
        feature = ProjectFeature(
            project_id=project_id,
            name="margin",
            formula="revenue - cost",
            dtype="number",
        )
        db.add(feature)
        db.commit()
        db.refresh(feature)
        return feature.id
    finally:
        db.close()


def _count_project_children(project_id: int) -> dict[str, int]:
    db = TestingSessionLocal()
    try:
        return {
            "report_drafts": db.query(ReportDraft).filter(ReportDraft.project_id == project_id).count(),
            "project_features": db.query(ProjectFeature).filter(ProjectFeature.project_id == project_id).count(),
            "analysis_results": db.query(AnalysisResult).filter(AnalysisResult.project_id == project_id).count(),
            "prepared_datasets": db.query(PreparedDataset).filter(PreparedDataset.project_id == project_id).count(),
            "project_files": db.query(ProjectFile).filter(ProjectFile.project_id == project_id).count(),
            "projects": db.query(Project).filter(Project.id == project_id).count(),
        }
    finally:
        db.close()


def _assert_project_deleted(client, project_id: int, auth_headers) -> None:
    r = client.delete(f"/projects/{project_id}", headers=auth_headers)
    assert r.status_code == 200
    assert r.json() == {"ok": True, "project_id": project_id}

    listed = client.get("/projects", headers=auth_headers)
    assert listed.status_code == 200
    assert all(p["id"] != project_id for p in listed.json())
    assert _count_project_children(project_id) == {
        "report_drafts": 0,
        "project_features": 0,
        "analysis_results": 0,
        "prepared_datasets": 0,
        "project_files": 0,
        "projects": 0,
    }


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
    body = r.json()
    assert body["email"] == "test@example.com"
    assert body["plan"] == "free"
    # Notification prefs should be present with defaults
    prefs = body["notification_prefs"]
    assert prefs["analysis_complete"] is True
    assert prefs["weekly_digest"] is True
    assert prefs["product_updates"] is False
    assert prefs["marketing_emails"] is False


def test_update_notification_prefs(client, auth_headers):
    """PATCH /auth/me/notifications persists individual preference flags."""
    # Turn off weekly digest
    r = client.patch("/auth/me/notifications", json={"weekly_digest": False}, headers=auth_headers)
    assert r.status_code == 200
    prefs = r.json()["notification_prefs"]
    assert prefs["weekly_digest"] is False
    assert prefs["analysis_complete"] is True  # others unchanged

    # Verify persisted on subsequent GET /auth/me
    r2 = client.get("/auth/me", headers=auth_headers)
    assert r2.json()["notification_prefs"]["weekly_digest"] is False


def test_update_notification_prefs_partial(client, auth_headers):
    """Only the keys provided in the payload are updated."""
    client.patch("/auth/me/notifications", json={"product_updates": True}, headers=auth_headers)
    client.patch("/auth/me/notifications", json={"marketing_emails": True}, headers=auth_headers)
    r = client.get("/auth/me", headers=auth_headers)
    prefs = r.json()["notification_prefs"]
    assert prefs["product_updates"] is True
    assert prefs["marketing_emails"] is True
    assert prefs["analysis_complete"] is True   # untouched default


def test_protected_requires_auth(client):
    r = client.get("/projects")
    assert r.status_code == 401
    assert r.status_code != 503


def test_invalid_token_rejected(client):
    r = client.get("/projects", headers={"Authorization": "Bearer not-a-valid-jwt"})
    assert r.status_code == 401
    assert r.status_code != 503


def test_hs256_token_can_create_and_delete_project(client, auth_headers):
    r = client.post("/projects", json={"name": "HS256 Project"}, headers=auth_headers)
    assert r.status_code == 200, r.text
    project_id = r.json()["id"]

    deleted = client.delete(f"/projects/{project_id}", headers=auth_headers)
    assert deleted.status_code == 200, deleted.text
    assert deleted.json() == {"ok": True, "project_id": project_id}


def test_es256_jwks_token_can_use_project_routes(client, monkeypatch):
    headers = _es256_headers(monkeypatch)

    created = client.post("/projects", json={"name": "ES256 Project"}, headers=headers)
    assert created.status_code == 200, created.text
    project_id = created.json()["id"]

    listed = client.get("/projects", headers=headers)
    assert listed.status_code == 200, listed.text
    assert any(p["id"] == project_id for p in listed.json())

    detail = client.get(f"/projects/{project_id}", headers=headers)
    assert detail.status_code == 200, detail.text

    insights = client.get(f"/projects/{project_id}/latest-insights", headers=headers)
    assert insights.status_code == 200, insights.text
    assert insights.status_code != 503

    deleted = client.delete(f"/projects/{project_id}", headers=headers)
    assert deleted.status_code == 200, deleted.text
    assert deleted.json() == {"ok": True, "project_id": project_id}


# ── Project creation ──────────────────────────────────────────────────────────

def test_create_project(client, auth_headers):
    r = client.post("/projects", json={"name": "My Analysis"}, headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    project_id = body["id"]
    assert body["name"] == "My Analysis"
    assert body["status"] == "created"
    assert isinstance(project_id, int)
    assert body["created_at"]

    listed = client.get("/projects", headers=auth_headers)
    assert listed.status_code == 200
    assert any(p["id"] == project_id and p["name"] == "My Analysis" for p in listed.json())


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
    assert r.status_code == 200
    assert r.json() == {"ok": True, "project_id": pid}
    r2 = client.get(f"/projects/{pid}", headers=auth_headers)
    assert r2.status_code == 404


def test_delete_project_with_child_rows(client, project, auth_headers):
    pid = project["id"]
    _seed_project_children(pid)

    _assert_project_deleted(client, pid, auth_headers)


def test_delete_project_with_project_files(client, project, auth_headers):
    pid = project["id"]
    _seed_project_file(pid)

    _assert_project_deleted(client, pid, auth_headers)


def test_delete_project_with_prepared_datasets(client, project, auth_headers):
    pid = project["id"]
    _seed_prepared_dataset(pid)

    _assert_project_deleted(client, pid, auth_headers)


def test_delete_project_with_analysis_results(client, project, auth_headers):
    pid = project["id"]
    _seed_analysis_result(pid)

    _assert_project_deleted(client, pid, auth_headers)


def test_delete_project_with_report_draft_linked_to_analysis_result(client, project, auth_headers):
    pid = project["id"]
    analysis_id = _seed_analysis_result(pid)
    _seed_report_draft(pid, analysis_result_id=analysis_id)

    _assert_project_deleted(client, pid, auth_headers)


def test_delete_project_with_project_features(client, project, auth_headers):
    pid = project["id"]
    _seed_project_feature(pid)

    _assert_project_deleted(client, pid, auth_headers)


def test_cannot_delete_another_users_project(client, project, auth_headers):
    pid = project["id"]
    r = client.delete(f"/projects/{pid}", headers=_other_headers(client))
    assert r.status_code == 404
    assert r.json()["detail"] == "Project not found."

    owner_can_still_read = client.get(f"/projects/{pid}", headers=auth_headers)
    assert owner_can_still_read.status_code == 200


def test_delete_nonexistent_project(client, auth_headers):
    r = client.delete("/projects/99999", headers=auth_headers)
    assert r.status_code == 404
    assert r.json()["detail"] == "Project not found."


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
