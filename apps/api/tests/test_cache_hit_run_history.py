"""
80A — Cache-hit run-history tests.

Verifies that POST /analysis/run creates a new AnalysisResult (run) record
even when the result is served from cache, so consultants can see that
analysis was reopened in the history list.
"""
from __future__ import annotations

import io

import pytest

from app.models import AnalysisResult
from tests.conftest import TestingSessionLocal, _make_test_jwt, TEST_USER_ID
from app.plan_names import PLAN_CONSULTANT


# ── helpers ────────────────────────────────────────────────────────────────────

def _consultant_headers(client) -> dict:
    token = _make_test_jwt()
    headers = {"Authorization": f"Bearer {token}"}
    client.get("/auth/me", headers=headers)
    from app.models import User as UserModel
    db = TestingSessionLocal()
    try:
        user = db.query(UserModel).filter(UserModel.id == TEST_USER_ID).first()
        if user:
            user.plan = PLAN_CONSULTANT
            db.commit()
    finally:
        db.close()
    return headers


def _count_runs(project_id: int) -> int:
    db = TestingSessionLocal()
    try:
        return (
            db.query(AnalysisResult)
            .filter(
                AnalysisResult.project_id == project_id,
                AnalysisResult.status == "report_ready",
            )
            .count()
        )
    finally:
        db.close()


def _latest_run_id(project_id: int) -> int | None:
    db = TestingSessionLocal()
    try:
        run = (
            db.query(AnalysisResult)
            .filter(
                AnalysisResult.project_id == project_id,
                AnalysisResult.status == "report_ready",
            )
            .order_by(AnalysisResult.id.desc())
            .first()
        )
        return run.id if run else None
    finally:
        db.close()


CSV = (
    b"name,age,salary\n"
    b"Alice,30,70000\n"
    b"Bob,25,55000\n"
    b"Carol,35,90000\n"
)


def _upload_and_first_run(client, headers) -> tuple[int, int]:
    """Create project, upload CSV, run analysis once. Returns (project_id, run_id)."""
    r = client.post("/projects", json={"name": "Cache Test"}, headers=headers)
    assert r.status_code == 200
    pid = r.json()["id"]

    r = client.post(
        "/upload",
        files={"file": ("data.csv", io.BytesIO(CSV), "text/csv")},
        data={"project_id": str(pid)},
        headers=headers,
    )
    assert r.status_code == 200

    r = client.post("/analysis/run", json={"project_id": pid}, headers=headers)
    assert r.status_code == 200
    first_run_id = r.json().get("run_id")
    return pid, first_run_id


# ── Tests ──────────────────────────────────────────────────────────────────────


class TestCacheHitRunHistory:
    def test_second_run_creates_additional_history_entry(self, client):
        """Cache hit must produce a second report_ready run record."""
        headers = _consultant_headers(client)
        pid, _ = _upload_and_first_run(client, headers)

        assert _count_runs(pid) == 1

        r = client.post("/analysis/run", json={"project_id": pid}, headers=headers)
        assert r.status_code == 200

        assert _count_runs(pid) == 2

    def test_second_run_id_differs_from_first(self, client):
        """The cache-hit response must carry a fresh run_id."""
        headers = _consultant_headers(client)
        pid, first_run_id = _upload_and_first_run(client, headers)

        r = client.post("/analysis/run", json={"project_id": pid}, headers=headers)
        assert r.status_code == 200
        second_run_id = r.json().get("run_id")

        assert second_run_id is not None
        assert second_run_id != first_run_id

    def test_cache_hit_run_id_matches_persisted_run(self, client):
        """run_id in the response must equal the latest DB record."""
        headers = _consultant_headers(client)
        pid, _ = _upload_and_first_run(client, headers)

        r = client.post("/analysis/run", json={"project_id": pid}, headers=headers)
        assert r.status_code == 200
        returned_run_id = r.json().get("run_id")

        assert returned_run_id == _latest_run_id(pid)

    def test_both_runs_are_report_ready(self, client):
        """Both the original run and the cache-hit run must reach report_ready."""
        headers = _consultant_headers(client)
        pid, _ = _upload_and_first_run(client, headers)

        client.post("/analysis/run", json={"project_id": pid}, headers=headers)

        db = TestingSessionLocal()
        try:
            runs = (
                db.query(AnalysisResult)
                .filter(AnalysisResult.project_id == pid)
                .order_by(AnalysisResult.id)
                .all()
            )
        finally:
            db.close()

        assert len(runs) >= 2
        for run in runs:
            assert run.status == "report_ready"

    def test_history_endpoint_shows_two_entries(self, client):
        """GET /analysis/history/{project_id} must list both runs after a cache hit."""
        headers = _consultant_headers(client)
        pid, _ = _upload_and_first_run(client, headers)

        client.post("/analysis/run", json={"project_id": pid}, headers=headers)

        r = client.get(f"/analysis/history/{pid}", headers=headers)
        assert r.status_code == 200
        assert len(r.json()) >= 2
