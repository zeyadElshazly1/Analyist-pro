"""
81D — Deterministic latest-run resolver tests.

Verifies that resolve_latest_run returns the expected run under all
priority and tie-breaking scenarios, proving that id DESC is the
deterministic secondary sort within each priority class.
"""
from __future__ import annotations

import pytest

from app.models import AnalysisResult
from app.services.run_resolver import resolve_latest_run
from tests.conftest import TestingSessionLocal


PROJECT_ID = 42  # arbitrary project id for isolation within each test


def _make_run(db, status: str, result_json: str = "{}") -> AnalysisResult:
    run = AnalysisResult(
        project_id=PROJECT_ID,
        status=status,
        result_json=result_json,
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


# ── Priority: report_ready beats everything ────────────────────────────────────

class TestReportReadyPriority:
    def test_report_ready_beats_failed(self, client):
        db = TestingSessionLocal()
        try:
            old_ready = _make_run(db, "report_ready")
            _make_run(db, "failed")
            result = resolve_latest_run(db, PROJECT_ID)
            assert result is not None
            assert result.id == old_ready.id
        finally:
            db.close()

    def test_report_ready_beats_newer_failed(self, client):
        db = TestingSessionLocal()
        try:
            ready = _make_run(db, "report_ready")
            newer_failed = _make_run(db, "failed")
            assert newer_failed.id > ready.id
            result = resolve_latest_run(db, PROJECT_ID)
            assert result is not None
            assert result.id == ready.id
        finally:
            db.close()

    def test_report_ready_beats_incomplete(self, client):
        db = TestingSessionLocal()
        try:
            ready = _make_run(db, "report_ready")
            _make_run(db, "cleaning_complete")
            result = resolve_latest_run(db, PROJECT_ID)
            assert result is not None
            assert result.id == ready.id
        finally:
            db.close()

    def test_report_ready_beats_newer_incomplete(self, client):
        db = TestingSessionLocal()
        try:
            ready = _make_run(db, "report_ready")
            newer_incomplete = _make_run(db, "profiling_complete")
            assert newer_incomplete.id > ready.id
            result = resolve_latest_run(db, PROJECT_ID)
            assert result is not None
            assert result.id == ready.id
        finally:
            db.close()


# ── Tie-breaking within priority class: highest id wins ───────────────────────

class TestTieBreaking:
    def test_multiple_report_ready_newest_id_wins(self, client):
        db = TestingSessionLocal()
        try:
            _make_run(db, "report_ready")
            newer_ready = _make_run(db, "report_ready")
            result = resolve_latest_run(db, PROJECT_ID)
            assert result is not None
            assert result.id == newer_ready.id
        finally:
            db.close()

    def test_multiple_failed_newest_id_wins(self, client):
        db = TestingSessionLocal()
        try:
            _make_run(db, "failed")
            newer_failed = _make_run(db, "failed")
            result = resolve_latest_run(db, PROJECT_ID)
            assert result is not None
            assert result.id == newer_failed.id
        finally:
            db.close()

    def test_multiple_incomplete_newest_id_wins(self, client):
        db = TestingSessionLocal()
        try:
            _make_run(db, "created")
            _make_run(db, "cleaning_complete")
            newest_incomplete = _make_run(db, "profiling_complete")
            result = resolve_latest_run(db, PROJECT_ID)
            assert result is not None
            assert result.id == newest_incomplete.id
        finally:
            db.close()


# ── Priority order: incomplete beats failed ────────────────────────────────────

class TestIncompleteBeatsFailed:
    def test_incomplete_beats_failed(self, client):
        db = TestingSessionLocal()
        try:
            _make_run(db, "failed")
            incomplete = _make_run(db, "insights_complete")
            result = resolve_latest_run(db, PROJECT_ID)
            assert result is not None
            assert result.id == incomplete.id
        finally:
            db.close()

    def test_older_incomplete_beats_newer_failed(self, client):
        db = TestingSessionLocal()
        try:
            incomplete = _make_run(db, "created")
            newer_failed = _make_run(db, "failed")
            assert newer_failed.id > incomplete.id
            result = resolve_latest_run(db, PROJECT_ID)
            assert result is not None
            assert result.id == incomplete.id
        finally:
            db.close()


# ── Edge cases ─────────────────────────────────────────────────────────────────

class TestEdgeCases:
    def test_no_runs_returns_none(self, client):
        db = TestingSessionLocal()
        try:
            result = resolve_latest_run(db, PROJECT_ID)
            assert result is None
        finally:
            db.close()

    def test_single_failed_run_returned(self, client):
        db = TestingSessionLocal()
        try:
            failed = _make_run(db, "failed")
            result = resolve_latest_run(db, PROJECT_ID)
            assert result is not None
            assert result.id == failed.id
            assert result.status == "failed"
        finally:
            db.close()
