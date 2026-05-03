"""
Regression tests for _run_analysis_stream SSE error handling.

Verifies that pipeline failures are emitted as SSE {"error": "..."} events
and never escape the async generator as unhandled exceptions (which would
cause Starlette's "Caught handled exception, but response already started").
"""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from app.routes.analysis_stream import _run_analysis_stream


# ── helpers ───────────────────────────────────────────────────────────────────

async def _collect(gen) -> list[dict]:
    """Drain an async generator and return parsed SSE data payloads."""
    events = []
    async for chunk in gen:
        chunk = chunk.strip()
        if chunk.startswith("data:"):
            events.append(json.loads(chunk[len("data:"):].strip()))
    return events


def _file_info():
    return {"path": "/fake/file.csv", "file_hash": "abc123"}


# ── build_cleaning_result failure (the original crash scenario) ───────────────

class TestCleaningAdapterSSEFallback:
    @pytest.mark.anyio
    async def test_validation_error_becomes_sse_error_event(self):
        """
        A ValidationError from build_cleaning_result must be caught and
        emitted as {"error": "..."} — not re-raised into Starlette.
        """
        from pydantic import ValidationError

        with (
            patch("app.routes.analysis_stream.get_project_file_info", return_value=_file_info()),
            patch("app.routes.analysis_stream.get_cached_analysis", return_value=None),
            patch("app.routes.analysis_stream.SessionLocal") as mock_session_cls,
            patch("app.routes.analysis_stream.load_dataset") as mock_load,
            patch("app.routes.analysis_stream.clean_dataset") as mock_clean,
            patch("app.routes.analysis_stream.build_cleaning_result", side_effect=ValueError("cols_removed is negative")),
            patch("app.routes.analysis_stream.create_run_stub", return_value=MagicMock(id=99)),
            patch("app.routes.analysis_stream.fail_run"),
        ):
            import pandas as pd
            mock_load.return_value = pd.DataFrame({"a": [1, 2], "b": [3, 4]})
            mock_clean.return_value = (
                pd.DataFrame({"a": [1, 2], "b": [3, 4]}),
                [],
                {"steps": 0, "original_rows": 2, "original_cols": 2,
                 "final_rows": 2, "final_cols": 2, "rows_removed": 0,
                 "cols_removed": 0, "confidence_score": 80.0,
                 "confidence_grade": "B", "time_saved_estimate": "~1 min",
                 "mode": "aggressive"},
            )
            mock_session_cls.return_value = MagicMock()

            events = await _collect(_run_analysis_stream(project_id=1, use_cleaned=True))

        error_events = [e for e in events if "error" in e]
        assert error_events, f"Expected at least one SSE error event, got: {events}"
        assert "error" in error_events[0]
        # Must not contain a result (success) event
        assert not any("result" in e for e in events)

    @pytest.mark.anyio
    async def test_clean_dataset_failure_becomes_sse_error_event(self):
        """clean_dataset() crash → SSE error, not an unhandled exception."""
        with (
            patch("app.routes.analysis_stream.get_project_file_info", return_value=_file_info()),
            patch("app.routes.analysis_stream.get_cached_analysis", return_value=None),
            patch("app.routes.analysis_stream.SessionLocal") as mock_session_cls,
            patch("app.routes.analysis_stream.load_dataset") as mock_load,
            patch("app.routes.analysis_stream.clean_dataset", side_effect=RuntimeError("memory error")),
            patch("app.routes.analysis_stream.create_run_stub", return_value=MagicMock(id=42)),
            patch("app.routes.analysis_stream.fail_run"),
        ):
            import pandas as pd
            mock_load.return_value = pd.DataFrame({"x": [1, 2, 3]})
            mock_session_cls.return_value = MagicMock()

            events = await _collect(_run_analysis_stream(project_id=2, use_cleaned=True))

        error_events = [e for e in events if "error" in e]
        assert error_events
        assert "error" in error_events[0]

    @pytest.mark.anyio
    async def test_load_dataset_failure_becomes_sse_error_event(self):
        """load_dataset() crash → SSE error, not an unhandled exception."""
        with (
            patch("app.routes.analysis_stream.get_project_file_info", return_value=_file_info()),
            patch("app.routes.analysis_stream.get_cached_analysis", return_value=None),
            patch("app.routes.analysis_stream.SessionLocal") as mock_session_cls,
            patch("app.routes.analysis_stream.load_dataset", side_effect=OSError("file not found")),
        ):
            mock_session_cls.return_value = MagicMock()

            events = await _collect(_run_analysis_stream(project_id=3, use_cleaned=True))

        error_events = [e for e in events if "error" in e]
        assert error_events

    @pytest.mark.anyio
    async def test_unhandled_exception_in_generator_emits_sse_error(self):
        """
        An unexpected exception that bypasses every per-stage handler must
        still be caught by the top-level except and emitted as SSE error.
        """
        with (
            patch("app.routes.analysis_stream.get_project_file_info", side_effect=Exception("unexpected!")),
            patch("app.routes.analysis_stream.SessionLocal") as mock_session_cls,
        ):
            mock_session_cls.return_value = MagicMock()

            # Must not raise — must yield an error SSE event instead
            events = await _collect(_run_analysis_stream(project_id=4))

        error_events = [e for e in events if "error" in e]
        assert error_events, "Top-level catch-all must emit an SSE error event"
