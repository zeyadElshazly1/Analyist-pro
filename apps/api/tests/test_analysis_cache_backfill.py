"""
88V — Route-level cache-hit regression test for insight_selection_meta.

Proves that POST /analysis/run returns a backfilled insight_selection_meta
block when the cached payload predates 88M and is missing the key.
Uses the same fixture/monkeypatch style as test_intake_persistence.py.
"""
from __future__ import annotations

import io

import app.routes.analysis as analysis_mod
from app.state import PROJECT_FILES


def _upload(client, project_id: int, headers) -> None:
    csv = (
        b"region,revenue,units\n"
        b"North,120000,300\n"
        b"South,85000,210\n"
        b"East,95000,240\n"
        b"West,110000,275\n"
    )
    r = client.post(
        "/upload",
        files={"file": ("sales.csv", io.BytesIO(csv), "text/csv")},
        data={"project_id": str(project_id)},
        headers=headers,
    )
    assert r.status_code == 200, r.text


def _run(client, project_id: int, headers):
    return client.post("/analysis/run", json={"project_id": project_id}, headers=headers)


def test_analysis_run_cache_hit_backfills_insight_selection_meta(
    client, project, auth_headers, monkeypatch
):
    """
    1. Run /analysis/run once to produce and cache a fresh result.
    2. Replace the cached payload with a legacy version that has no insight_selection_meta.
    3. Call /analysis/run again → cache-hit branch executes.
    4. Assert the response includes a backfilled insight_selection_meta block.
    """
    pid = project["id"]
    _upload(client, pid, auth_headers)

    # First run — fresh pipeline populates the real cache.
    r = _run(client, pid, auth_headers)
    assert r.status_code == 200, r.text

    # Seed a fake in-memory cache with a legacy payload (no insight_selection_meta).
    fh = (PROJECT_FILES.get(pid) or {}).get("file_hash")
    assert fh, "Upload must have populated PROJECT_FILES with a file hash"

    _fake_cache: dict[str, dict] = {}
    _fake_cache[f"{pid}:{fh}"] = {
        "project_id": pid,
        "cleaning_summary": {"steps": 0},
        "cleaning_result": {},
        "profile_result": [],
        "health_result": {"score": 0.8},
        "insight_results": [
            {"title": "Revenue trend", "confidence": 0.75, "suppressed_by_plan": False},
            {"title": "Unit anomaly", "confidence": 0.3, "suppressed_by_plan": False},
        ],
        "narrative": "Legacy narrative — predates 88M.",
        "executive_panel": {},
        "analysis_plan": {},
        # NOTE: insight_selection_meta intentionally absent
    }

    def fake_get(project_id: int, file_hash: str | None):
        return _fake_cache.get(f"{project_id}:{file_hash}")

    def fake_set(project_id: int, file_hash: str | None, result: dict):
        if file_hash:
            _fake_cache[f"{project_id}:{file_hash}"] = result

    monkeypatch.setattr(analysis_mod, "get_cached_analysis", fake_get)
    monkeypatch.setattr(analysis_mod, "set_cached_analysis", fake_set)

    # Second run → must hit the fake cache and backfill the missing block.
    r = _run(client, pid, auth_headers)
    assert r.status_code == 200, r.text
    payload = r.json()

    # Core backfill assertions.
    assert payload["insight_selection_meta"] is not None
    assert payload["insight_selection_meta"]["backfilled_from_cache"] is True
    assert (
        payload["insight_selection_meta"]["visible_insight_count"]
        == len(payload["insight_results"])
    )
    assert "summary_eligible_visible_count" in payload["insight_selection_meta"]
    assert "summary_ineligible_visible_count" in payload["insight_selection_meta"]

    # The cache itself must have been updated so subsequent hits find it populated.
    cached_after = fake_get(pid, fh)
    assert cached_after is not None
    assert cached_after.get("insight_selection_meta") is not None
    assert cached_after["insight_selection_meta"]["backfilled_from_cache"] is True
