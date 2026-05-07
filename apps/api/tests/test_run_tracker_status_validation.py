"""
81C — Run-status validation tests.

Verifies that set_run_status rejects unknown status strings immediately
(ValueError) so typos cannot be silently persisted to the DB.
"""
from __future__ import annotations

import pytest

from app.services.run_tracker import (
    VALID_RUN_STATUSES,
    _validate_status,
    create_run_stub,
    fail_run,
    finalise_run,
    set_run_status,
)
from tests.conftest import TestingSessionLocal, TEST_USER_ID


# ── _validate_status unit tests ────────────────────────────────────────────────

class TestValidateStatus:
    def test_all_canonical_statuses_accepted(self):
        for status in VALID_RUN_STATUSES:
            _validate_status(status)  # must not raise

    def test_typo_raises_value_error(self):
        with pytest.raises(ValueError, match="cleanng_complete"):
            _validate_status("cleanng_complete")

    def test_empty_string_raises(self):
        with pytest.raises(ValueError):
            _validate_status("")

    def test_unknown_string_raises(self):
        with pytest.raises(ValueError, match="totally_wrong"):
            _validate_status("totally_wrong")

    def test_error_message_lists_valid_statuses(self):
        with pytest.raises(ValueError) as exc_info:
            _validate_status("bad_status")
        msg = str(exc_info.value)
        assert "created" in msg
        assert "report_ready" in msg
        assert "failed" in msg


# ── set_run_status integration tests ──────────────────────────────────────────

class TestSetRunStatus:
    def _make_run(self, db):
        return create_run_stub(db, project_id=1, file_hash=None, user_id=TEST_USER_ID)

    def test_valid_status_is_persisted(self, client):
        db = TestingSessionLocal()
        try:
            run = self._make_run(db)
            assert run is not None
            set_run_status(db, run, "cleaning_complete")
            db.refresh(run)
            assert run.status == "cleaning_complete"
        finally:
            db.close()

    def test_invalid_status_raises_before_mutating(self, client):
        db = TestingSessionLocal()
        try:
            run = self._make_run(db)
            assert run is not None
            original_status = run.status

            with pytest.raises(ValueError):
                set_run_status(db, run, "cleanng_complete")

            # Status must not have changed
            db.refresh(run)
            assert run.status == original_status
        finally:
            db.close()

    def test_none_run_is_noop(self, client):
        db = TestingSessionLocal()
        try:
            # Must not raise even with invalid status when run is None
            set_run_status(db, None, "created")
        finally:
            db.close()

    def test_all_pipeline_statuses_accepted(self, client):
        pipeline_statuses = [
            "cleaning_complete",
            "profiling_complete",
            "insights_complete",
        ]
        db = TestingSessionLocal()
        try:
            for status in pipeline_statuses:
                run = self._make_run(db)
                assert run is not None
                set_run_status(db, run, status)
                db.refresh(run)
                assert run.status == status
        finally:
            db.close()


# ── fail_run / finalise_run still work ────────────────────────────────────────

class TestTerminalTransitions:
    def _make_run(self, db):
        return create_run_stub(db, project_id=1, file_hash=None, user_id=TEST_USER_ID)

    def test_fail_run_sets_failed(self, client):
        db = TestingSessionLocal()
        try:
            run = self._make_run(db)
            fail_run(db, run, "something went wrong")
            db.refresh(run)
            assert run.status == "failed"
            assert run.error_summary == "something went wrong"
        finally:
            db.close()

    def test_finalise_run_sets_report_ready(self, client):
        import json
        db = TestingSessionLocal()
        try:
            run = self._make_run(db)
            finalise_run(db, run, json.dumps({"run_id": run.id}))
            db.refresh(run)
            assert run.status == "report_ready"
        finally:
            db.close()
