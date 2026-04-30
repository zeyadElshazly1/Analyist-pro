"""Auto materialisation of default report drafts on GET /reports/draft."""

from __future__ import annotations

import io
import json

from app.models import AnalysisResult, ReportDraft
from app.services.reporting.default_draft import (
    build_fallback_executive_summary,
    select_default_insight_selection,
)
from tests.conftest import TestingSessionLocal


def test_select_prefers_report_safe_then_pads_to_three():
    raw = [
        {"insight_id": "a", "report_safe": False, "severity": "high", "category": "outlier"},
        {"insight_id": "b", "report_safe": True, "severity": "medium", "category": "correlation"},
        {"insight_id": "c", "report_safe": True, "severity": "low", "category": "trend"},
        {"insight_id": "d", "report_safe": True, "severity": "high", "category": "outlier"},
        {"insight_id": "e", "report_safe": False, "severity": "high", "category": "outlier"},
    ]
    sel = select_default_insight_selection(raw)
    assert sel[:3] == ["b", "c", "d"]
    assert len(sel) >= 3
    assert len(sel) <= 5


def test_select_without_report_safe_skips_dq_until_exhausted():
    raw = [
        {"insight_id": "dq", "severity": "high", "category": "data_quality"},
        {"insight_id": "x", "severity": "high", "category": "outlier"},
        {"insight_id": "y", "severity": "medium", "category": "correlation"},
    ]
    sel = select_default_insight_selection(raw)
    assert sel[0] == "x"
    assert "dq" in sel or len(sel) == 2


def test_select_only_dq_high_medium_falls_back_to_any():
    raw = [
        {"insight_id": "dq1", "severity": "high", "category": "data_quality"},
        {"insight_id": "dq2", "severity": "medium", "category": "missing_pattern"},
    ]
    sel = select_default_insight_selection(raw)
    assert len(sel) >= 1
    assert set(sel) <= {"dq1", "dq2"}


def test_fallback_summary_uses_dataset_and_insights():
    result = {
        "narrative": "",
        "dataset_summary": {"rows": 100, "columns": 5},
        "health_score": {"total": 82},
        "insight_results": [
            {"title": "Alpha finding", "severity": "high"},
            {"title": "Beta finding", "severity": "medium"},
        ],
    }
    text = build_fallback_executive_summary(result)
    assert "100" in text and "columns" in text
    assert "82" in text
    assert "Alpha finding" in text
    assert "associated" in text.lower()


def test_fallback_summary_prefers_long_narrative():
    long_n = "X" * 200
    result = {"narrative": long_n, "insight_results": []}
    assert build_fallback_executive_summary(result) == long_n


def test_get_draft_auto_creates_when_analysis_exists(client, uploaded_project, auth_headers):
    """GET creates and returns a persisted draft when analysis is present."""
    pid = uploaded_project["id"]
    body = {
        "narrative": "Short.",
        "insight_results": [
            {
                "insight_id": "sid_a",
                "title": "Finding A",
                "severity": "high",
                "category": "outlier",
                "report_safe": True,
            },
            {
                "insight_id": "sid_b",
                "title": "Finding B",
                "severity": "medium",
                "category": "correlation",
                "report_safe": True,
            },
            {
                "insight_id": "sid_c",
                "title": "Finding C",
                "severity": "low",
                "category": "trend",
                "report_safe": True,
            },
        ],
        "dataset_summary": {"rows": 10, "columns": 3},
        "health_score": {"total": 75},
    }
    db = TestingSessionLocal()
    try:
        run = AnalysisResult(
            project_id=pid,
            file_hash="t-hash",
            result_json=json.dumps(body),
            status="report_ready",
        )
        db.add(run)
        db.commit()
    finally:
        db.close()

    r = client.get(f"/reports/draft/{pid}", headers=auth_headers)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data is not None
    assert data["title"] == "Test Project"
    assert data["summary"]
    assert len(data["selected_insight_ids"]) >= 1
    rr = data["report_result"]
    assert len(rr["included_sections"]) >= 1
    assert len(rr["included_insights"]) >= 1

    db = TestingSessionLocal()
    try:
        n = db.query(ReportDraft).filter(ReportDraft.project_id == pid).count()
        assert n == 1
    finally:
        db.close()

    r2 = client.get(f"/reports/draft/{pid}", headers=auth_headers)
    assert r2.status_code == 200
    assert r2.json()["id"] == data["id"]


def test_get_draft_still_null_without_analysis(client, project, auth_headers):
    r = client.get(f"/reports/draft/{project['id']}", headers=auth_headers)
    assert r.status_code == 200
    assert r.json() is None
