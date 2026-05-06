"""Auto materialisation of default report drafts on GET /reports/draft."""

from __future__ import annotations

import io
import json

from app.models import AnalysisResult, ReportDraft
from app.services.analysis.domain.timeseries_finance import FINANCE_TS_PREMIUM_TITLE_ORDER
from app.services.dataset_context.schema import (
    FINANCIAL_MARKETS_SNAPSHOT,
    FINANCIAL_MARKETS_TIMESERIES,
    GENERIC_TABULAR,
)
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
    assert rr["included_charts"] == []
    assert data["selected_chart_ids"] == []

    db = TestingSessionLocal()
    try:
        n = db.query(ReportDraft).filter(ReportDraft.project_id == pid).count()
        assert n == 1
    finally:
        db.close()

    r2 = client.get(f"/reports/draft/{pid}", headers=auth_headers)
    assert r2.status_code == 200
    assert r2.json()["id"] == data["id"]


def test_get_draft_auto_create_uses_finance_aware_insight_order(client, project, auth_headers):
    """finance_markets_snapshot analyses get default selection in finance title priority."""
    pid = project["id"]
    body = {
        "narrative": "Short.",
        "dataset_summary": {
            "rows": 10,
            "columns": 5,
            "dataset_context": {
                "dataset_type": FINANCIAL_MARKETS_SNAPSHOT,
                "confidence": 0.9,
                "warnings": [],
            },
        },
        "health_score": {"total": 75},
        "insight_results": [
            {
                "domain": FINANCIAL_MARKETS_SNAPSHOT,
                "title": "Highest volatility assets",
                "insight_id": "id_vol",
                "severity": "medium",
            },
            {
                "domain": FINANCIAL_MARKETS_SNAPSHOT,
                "title": "Top return leaders",
                "insight_id": "id_top",
                "severity": "medium",
            },
            {
                "domain": FINANCIAL_MARKETS_SNAPSHOT,
                "title": "Largest return laggards",
                "insight_id": "id_lag",
                "severity": "medium",
            },
        ],
    }
    db = TestingSessionLocal()
    try:
        run = AnalysisResult(
            project_id=pid,
            file_hash="finance-sel-hash",
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
    assert data["selected_insight_ids"] == ["id_top", "id_lag", "id_vol"]
    assert data["selected_chart_ids"] == []
    assert data["report_result"]["included_charts"] == []


def test_get_draft_finance_auto_selects_default_charts_when_payload_present(client, project, auth_headers):
    pid = project["id"]
    insights = [
        {
            "domain": FINANCIAL_MARKETS_SNAPSHOT,
            "title": "Highest volatility assets",
            "insight_id": "id_vol",
            "severity": "medium",
        },
        {
            "domain": FINANCIAL_MARKETS_SNAPSHOT,
            "title": "Top return leaders",
            "insight_id": "id_top",
            "severity": "medium",
        },
        {
            "domain": FINANCIAL_MARKETS_SNAPSHOT,
            "title": "Largest return laggards",
            "insight_id": "id_lag",
            "severity": "medium",
        },
    ]
    charts = [
        {"chart_id": "c_sector", "title": "Average return by sector", "type": "bar"},
        {"chart_id": "c_top", "title": "Top assets by return", "type": "bar"},
        {"chart_id": "c_rr", "title": "Risk vs return", "type": "scatter"},
        {"chart_id": "c_vol", "title": "Highest volatility assets", "type": "bar"},
        {"chart_id": "c_cls", "title": "Average return by asset class", "type": "bar"},
        {"chart_id": "c_an", "title": "Highest analyst-implied upside", "type": "bar"},
        {"chart_id": "c52", "title": "Assets by 52-week position", "type": "bar"},
        {"chart_id": "c_lag", "title": "Largest return laggards", "type": "bar"},
    ]
    body = {
        "narrative": "Short.",
        "dataset_summary": {
            "rows": 12,
            "columns": 8,
            "dataset_context": {
                "dataset_type": FINANCIAL_MARKETS_SNAPSHOT,
                "confidence": 0.9,
                "warnings": [],
            },
        },
        "health_score": {"total": 75},
        "insight_results": insights,
        "charts": charts,
    }
    db = TestingSessionLocal()
    try:
        run = AnalysisResult(
            project_id=pid,
            file_hash="finance-chart-default-hash",
            result_json=json.dumps(body),
            status="report_ready",
        )
        db.add(run)
        db.commit()
    finally:
        db.close()

    r = client.get(f"/reports/draft/{pid}", headers=auth_headers)
    assert r.status_code == 200, r.text
    payload = r.json()
    assert payload["selected_chart_ids"] == ["c_top", "c_rr", "c_cls", "c_sector"]
    inc = payload["report_result"]["included_charts"]
    assert len(inc) == 4
    assert [c["chart_id"] for c in inc] == ["c_top", "c_rr", "c_cls", "c_sector"]
    assert inc[2]["chart_type"] == "bar"
    titles_in_order = [c["title"] for c in inc]
    assert titles_in_order == ["Top assets by return", "Risk vs return", "Average return by asset class", "Average return by sector"]


def test_get_draft_finance_chart_results_populates_selected_and_included_charts(client, project, auth_headers):
    """Chart payloads under ``chart_results`` (without ``charts``) auto-select exactly like canonical ``charts``."""
    pid = project["id"]
    insights = [
        {
            "domain": FINANCIAL_MARKETS_SNAPSHOT,
            "title": "Highest volatility assets",
            "insight_id": "id_vol",
            "severity": "medium",
        },
        {
            "domain": FINANCIAL_MARKETS_SNAPSHOT,
            "title": "Top return leaders",
            "insight_id": "id_top",
            "severity": "medium",
        },
        {
            "domain": FINANCIAL_MARKETS_SNAPSHOT,
            "title": "Largest return laggards",
            "insight_id": "id_lag",
            "severity": "medium",
        },
    ]
    charts = [
        {"chart_id": "c_sector", "title": "Average return by sector", "type": "bar"},
        {"chart_id": "c_top", "title": "Top assets by return", "type": "bar"},
        {"chart_id": "c_rr", "title": "Risk vs return", "type": "scatter"},
        {"chart_id": "c_vol", "title": "Highest volatility assets", "type": "bar"},
        {"chart_id": "c_cls", "title": "Average return by asset class", "type": "bar"},
        {"chart_id": "c_an", "title": "Highest analyst-implied upside", "type": "bar"},
        {"chart_id": "c52", "title": "Assets by 52-week position", "type": "bar"},
        {"chart_id": "c_lag", "title": "Largest return laggards", "type": "bar"},
    ]
    body = {
        "narrative": "Short.",
        "dataset_summary": {
            "rows": 12,
            "columns": 8,
            "dataset_context": {
                "dataset_type": FINANCIAL_MARKETS_SNAPSHOT,
                "confidence": 0.9,
                "warnings": [],
            },
        },
        "health_score": {"total": 75},
        "insight_results": insights,
        "chart_results": charts,
    }
    db = TestingSessionLocal()
    try:
        run = AnalysisResult(
            project_id=pid,
            file_hash="finance-chart-results-key-hash",
            result_json=json.dumps(body),
            status="report_ready",
        )
        db.add(run)
        db.commit()
    finally:
        db.close()

    r = client.get(f"/reports/draft/{pid}", headers=auth_headers)
    assert r.status_code == 200, r.text
    payload = r.json()
    assert payload["selected_chart_ids"] == ["c_top", "c_rr", "c_cls", "c_sector"]
    inc = payload["report_result"]["included_charts"]
    assert [c["chart_id"] for c in inc] == ["c_top", "c_rr", "c_cls", "c_sector"]


def test_get_draft_finance_legacy_chart_indices_in_included_charts(client, project, auth_headers):
    """No ``chart_id`` / ``id`` on payloads → stored selection uses indices; ``included_charts`` carries idx_* + titles."""
    pid = project["id"]
    insights = [
        {
            "domain": FINANCIAL_MARKETS_SNAPSHOT,
            "title": "Highest volatility assets",
            "insight_id": "id_vol",
            "severity": "medium",
        },
        {
            "domain": FINANCIAL_MARKETS_SNAPSHOT,
            "title": "Top return leaders",
            "insight_id": "id_top",
            "severity": "medium",
        },
        {
            "domain": FINANCIAL_MARKETS_SNAPSHOT,
            "title": "Largest return laggards",
            "insight_id": "id_lag",
            "severity": "medium",
        },
    ]
    charts = [
        {"title": "Risk vs return", "type": "scatter"},
        {"title": "Average return by sector"},
        {"title": "Average return by asset class"},
        {"title": "Top assets by return"},
    ]
    body = {
        "narrative": "Short.",
        "dataset_summary": {
            "rows": 8,
            "columns": 4,
            "dataset_context": {
                "dataset_type": FINANCIAL_MARKETS_SNAPSHOT,
                "confidence": 0.9,
                "warnings": [],
            },
        },
        "health_score": {"total": 75},
        "insight_results": insights,
        "charts": charts,
    }
    db = TestingSessionLocal()
    try:
        run = AnalysisResult(
            project_id=pid,
            file_hash="finance-legacy-chart-idx-hash",
            result_json=json.dumps(body),
            status="report_ready",
        )
        db.add(run)
        db.commit()
    finally:
        db.close()

    r = client.get(f"/reports/draft/{pid}", headers=auth_headers)
    assert r.status_code == 200, r.text
    payload = r.json()
    assert payload["selected_chart_ids"] == [3, 0, 2, 1]
    inc = payload["report_result"]["included_charts"]
    assert [c["chart_id"] for c in inc] == ["idx_3", "idx_0", "idx_2", "idx_1"]
    assert inc[0]["title"] == "Top assets by return"
    assert inc[0]["chart_type"] == "unknown"
    assert inc[1]["title"] == "Risk vs return"
    assert inc[1]["chart_type"] == "scatter"


def test_get_draft_generic_does_not_auto_select_charts_even_with_finance_like_titles(client, project, auth_headers):
    pid = project["id"]
    body = {
        "narrative": "n",
        "dataset_summary": {
            "rows": 5,
            "columns": 3,
            "dataset_context": {
                "dataset_type": GENERIC_TABULAR,
                "confidence": 1.0,
                "warnings": [],
            },
        },
        "health_score": {"total": 70},
        "insight_results": [
            {"insight_id": "g1", "title": "Insight one", "severity": "high", "report_safe": True},
            {"insight_id": "g2", "title": "Insight two", "severity": "medium", "report_safe": True},
            {"insight_id": "g3", "title": "Insight three", "severity": "low", "report_safe": True},
        ],
        "charts": [
            {"chart_id": "bogus", "title": "Top assets by return", "type": "bar"},
        ],
    }
    db = TestingSessionLocal()
    try:
        run = AnalysisResult(
            project_id=pid,
            file_hash="generic-with-finance-chart-titles",
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
    assert data["selected_chart_ids"] == []
    assert data["report_result"]["included_charts"] == []


def test_get_draft_generic_does_not_auto_select_timeseries_finance_charts(client, project, auth_headers):
    pid = project["id"]
    body = {
        "narrative": "n",
        "dataset_summary": {
            "rows": 5,
            "columns": 3,
            "dataset_context": {
                "dataset_type": GENERIC_TABULAR,
                "confidence": 1.0,
                "warnings": [],
            },
        },
        "health_score": {"total": 70},
        "insight_results": [
            {"insight_id": "g1", "title": "Insight one", "severity": "high", "report_safe": True},
            {"insight_id": "g2", "title": "Insight two", "severity": "medium", "report_safe": True},
            {"insight_id": "g3", "title": "Insight three", "severity": "low", "report_safe": True},
        ],
        "charts": [
            {"chart_id": "bogus_ts", "title": "Price trend by symbol", "type": "line"},
        ],
    }
    db = TestingSessionLocal()
    try:
        run = AnalysisResult(
            project_id=pid,
            file_hash="generic-with-ts-chart-titles",
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
    assert data["selected_chart_ids"] == []
    assert data["report_result"]["included_charts"] == []


def test_get_draft_auto_create_timeseries_uses_finance_insight_priority(client, project, auth_headers):
    pid = project["id"]
    titles = list(FINANCE_TS_PREMIUM_TITLE_ORDER)
    body = {
        "narrative": "Short.",
        "dataset_summary": {
            "rows": 10,
            "columns": 8,
            "dataset_context": {
                "dataset_type": FINANCIAL_MARKETS_TIMESERIES,
                "confidence": 0.9,
                "warnings": [],
            },
        },
        "health_score": {"total": 75},
        "insight_results": [
            {
                "domain": FINANCIAL_MARKETS_TIMESERIES,
                "title": titles[2],
                "insight_id": "ts_vol",
                "severity": "medium",
            },
            {
                "domain": FINANCIAL_MARKETS_TIMESERIES,
                "title": titles[0],
                "insight_id": "ts_top",
                "severity": "medium",
            },
            {
                "domain": FINANCIAL_MARKETS_TIMESERIES,
                "title": titles[1],
                "insight_id": "ts_worst",
                "severity": "medium",
            },
            {
                "domain": FINANCIAL_MARKETS_TIMESERIES,
                "title": titles[3],
                "insight_id": "ts_dd",
                "severity": "medium",
            },
            {
                "domain": FINANCIAL_MARKETS_TIMESERIES,
                "title": titles[4],
                "insight_id": "ts_liq",
                "severity": "medium",
            },
        ],
    }
    db = TestingSessionLocal()
    try:
        run = AnalysisResult(
            project_id=pid,
            file_hash="ts-insight-default-hash",
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
    assert data["selected_insight_ids"] == ["ts_top", "ts_worst", "ts_vol", "ts_dd", "ts_liq"]
    assert data["selected_chart_ids"] == []
    assert data["report_result"]["included_charts"] == []


def test_get_draft_timeseries_auto_selects_default_charts_when_payload_present(client, project, auth_headers):
    pid = project["id"]
    titles = list(FINANCE_TS_PREMIUM_TITLE_ORDER)
    insights = [
        {
            "domain": FINANCIAL_MARKETS_TIMESERIES,
            "title": titles[i],
            "insight_id": f"id_{i}",
            "severity": "medium",
        }
        for i in range(min(5, len(titles)))
    ]
    charts = [
        {"chart_id": "c_vol", "title": "Volatility leaderboard", "type": "bar"},
        {"chart_id": "c_tr", "title": "Total return leaderboard", "type": "bar"},
        {"chart_id": "c_price", "title": "Price trend by symbol", "type": "line"},
        {"chart_id": "c_dd", "title": "Drawdown chart", "type": "bar"},
        {"chart_id": "c_liq", "title": "Volume leaderboard", "type": "bar"},
        {"chart_id": "c_ret", "title": "Return distribution", "type": "bar"},
    ]
    body = {
        "narrative": "Short.",
        "dataset_summary": {
            "rows": 120,
            "columns": 8,
            "dataset_context": {
                "dataset_type": FINANCIAL_MARKETS_TIMESERIES,
                "confidence": 0.9,
                "warnings": [],
            },
        },
        "health_score": {"total": 75},
        "insight_results": insights,
        "charts": charts,
    }
    db = TestingSessionLocal()
    try:
        run = AnalysisResult(
            project_id=pid,
            file_hash="ts-chart-default-hash",
            result_json=json.dumps(body),
            status="report_ready",
        )
        db.add(run)
        db.commit()
    finally:
        db.close()

    r = client.get(f"/reports/draft/{pid}", headers=auth_headers)
    assert r.status_code == 200, r.text
    payload = r.json()
    assert payload["selected_chart_ids"] == ["c_price", "c_tr", "c_vol", "c_dd"]
    inc = payload["report_result"]["included_charts"]
    assert len(inc) == 4
    assert [c["chart_id"] for c in inc] == ["c_price", "c_tr", "c_vol", "c_dd"]
    titles_in_order = [c["title"] for c in inc]
    assert titles_in_order == [
        "Price trend by symbol",
        "Total return leaderboard",
        "Volatility leaderboard",
        "Drawdown chart",
    ]


def test_get_draft_populates_included_charts_from_selection_and_run(client, project, auth_headers):
    pid = project["id"]
    result_body = {
        "narrative": "",
        "insight_results": [
            {"title": "Finding A", "insight_id": "a", "severity": "high", "report_safe": True},
            {"title": "Finding B", "insight_id": "b", "severity": "medium", "report_safe": True},
            {"title": "Finding C", "insight_id": "c", "severity": "low", "report_safe": True},
        ],
        "charts": [
            {"chart_id": "chg_1", "type": "bar", "title": "Revenue by segment"},
        ],
        "dataset_summary": {"rows": 3, "columns": 2},
        "health_score": {"total": 80},
    }
    db = TestingSessionLocal()
    try:
        run = AnalysisResult(
            project_id=pid,
            file_hash="chart-catalog-hash",
            result_json=json.dumps(result_body),
            status="report_ready",
        )
        db.add(run)
        db.commit()
        db.add(
            ReportDraft(
                project_id=pid,
                analysis_result_id=run.id,
                title="T",
                summary="S",
                selected_insight_ids_json=json.dumps(["a"]),
                selected_chart_ids_json=json.dumps(["chg_1", "missing_id"]),
            ),
        )
        db.commit()
    finally:
        db.close()

    r = client.get(f"/reports/draft/{pid}", headers=auth_headers)
    assert r.status_code == 200, r.text
    payload = r.json()
    assert payload["selected_chart_ids"] == ["chg_1", "missing_id"]
    charts = payload["report_result"]["included_charts"]
    assert len(charts) == 2
    by_id = {c["chart_id"]: c for c in charts}
    assert by_id["chg_1"]["chart_type"] == "bar"
    assert by_id["chg_1"]["title"] == "Revenue by segment"
    assert by_id["missing_id"]["chart_type"] == "unknown"
    assert by_id["missing_id"]["title"] == "missing_id"


def test_get_draft_survives_malformed_selected_chart_ids_json(client, project, auth_headers):
    pid = project["id"]
    result_body = {
        "insight_results": [{"insight_id": "x", "title": "Only", "severity": "high", "report_safe": True}],
        "dataset_summary": {"rows": 1, "columns": 1},
        "health_score": {"total": 50},
    }
    db = TestingSessionLocal()
    try:
        run = AnalysisResult(
            project_id=pid,
            file_hash="mal-chart-json",
            result_json=json.dumps(result_body),
            status="report_ready",
        )
        db.add(run)
        db.commit()
        db.add(
            ReportDraft(
                project_id=pid,
                analysis_result_id=run.id,
                title="T",
                summary="S",
                selected_insight_ids_json=json.dumps(["x"]),
                selected_chart_ids_json="<<<not-json>>>",
            ),
        )
        db.commit()
    finally:
        db.close()

    r = client.get(f"/reports/draft/{pid}", headers=auth_headers)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["selected_chart_ids"] == []
    assert data["report_result"]["included_charts"] == []


def test_get_draft_still_null_without_analysis(client, project, auth_headers):
    r = client.get(f"/reports/draft/{project['id']}", headers=auth_headers)
    assert r.status_code == 200
    assert r.json() is None


# ── available_charts catalog in draft response ────────────────────────────────

class TestAvailableCharts:
    """GET /reports/draft exposes available_charts from the linked run."""

    def _seed(self, project_id: int, charts: list[dict], selected_chart_ids: list | None = None) -> None:
        db = TestingSessionLocal()
        try:
            result_body = {
                "narrative": "n",
                "insight_results": [
                    {"insight_id": "a", "title": "Finding A", "severity": "high", "report_safe": True},
                ],
                "dataset_summary": {"rows": 5, "columns": 3},
                "health_score": {"total": 75},
                "charts": charts,
            }
            run = AnalysisResult(
                project_id=project_id,
                file_hash=f"avail-charts-{project_id}",
                result_json=json.dumps(result_body),
                status="report_ready",
            )
            db.add(run)
            db.commit()
            draft = ReportDraft(
                project_id=project_id,
                analysis_result_id=run.id,
                title="T",
                summary="S",
                selected_insight_ids_json=json.dumps(["a"]),
                selected_chart_ids_json=json.dumps(selected_chart_ids) if selected_chart_ids is not None else None,
            )
            db.add(draft)
            db.commit()
        finally:
            db.close()

    def test_available_charts_present_when_charts_exist(self, client, project, auth_headers):
        pid = project["id"]
        self._seed(pid, [
            {"chart_id": "c1", "title": "Revenue", "type": "bar"},
            {"chart_id": "c2", "title": "Trend",   "type": "line"},
        ], selected_chart_ids=["c1"])

        r = client.get(f"/reports/draft/{pid}", headers=auth_headers)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "available_charts" in data
        assert len(data["available_charts"]) == 2

    def test_available_charts_preserves_stored_order(self, client, project, auth_headers):
        pid = project["id"]
        self._seed(pid, [
            {"chart_id": "first",  "title": "First",  "type": "bar"},
            {"chart_id": "second", "title": "Second", "type": "line"},
            {"chart_id": "third",  "title": "Third",  "type": "pie"},
        ], selected_chart_ids=["first"])

        data = client.get(f"/reports/draft/{pid}", headers=auth_headers).json()
        ids = [c["chart_id"] for c in data["available_charts"]]
        assert ids == ["first", "second", "third"]

    def test_selected_charts_marked_true(self, client, project, auth_headers):
        pid = project["id"]
        self._seed(pid, [
            {"chart_id": "sel",   "title": "Selected",   "type": "bar"},
            {"chart_id": "unsel", "title": "Unselected", "type": "line"},
        ], selected_chart_ids=["sel"])

        data = client.get(f"/reports/draft/{pid}", headers=auth_headers).json()
        by_id = {c["chart_id"]: c for c in data["available_charts"]}
        assert by_id["sel"]["selected"] is True
        assert by_id["unsel"]["selected"] is False

    def test_unselected_charts_marked_false(self, client, project, auth_headers):
        pid = project["id"]
        self._seed(pid, [
            {"chart_id": "a", "title": "A", "type": "bar"},
            {"chart_id": "b", "title": "B", "type": "bar"},
            {"chart_id": "c", "title": "C", "type": "bar"},
        ], selected_chart_ids=["b"])

        data = client.get(f"/reports/draft/{pid}", headers=auth_headers).json()
        by_id = {c["chart_id"]: c for c in data["available_charts"]}
        assert by_id["a"]["selected"] is False
        assert by_id["b"]["selected"] is True
        assert by_id["c"]["selected"] is False

    def test_legacy_index_charts_appear_with_idx_ids(self, client, project, auth_headers):
        pid = project["id"]
        # Charts without chart_id/id → catalog uses idx_N
        self._seed(pid, [
            {"title": "No-id chart zero",  "type": "bar"},
            {"title": "No-id chart one",   "type": "line"},
        ], selected_chart_ids=[0])

        data = client.get(f"/reports/draft/{pid}", headers=auth_headers).json()
        ids = [c["chart_id"] for c in data["available_charts"]]
        assert ids == ["idx_0", "idx_1"]
        by_id = {c["chart_id"]: c for c in data["available_charts"]}
        assert by_id["idx_0"]["selected"] is True
        assert by_id["idx_1"]["selected"] is False

    def test_no_chart_payload_returns_empty_list(self, client, project, auth_headers):
        pid = project["id"]
        # Seed a run with no charts block at all
        db = TestingSessionLocal()
        try:
            result_body = {
                "narrative": "n",
                "insight_results": [
                    {"insight_id": "x", "title": "X", "severity": "high", "report_safe": True},
                ],
                "dataset_summary": {"rows": 3, "columns": 2},
                "health_score": {"total": 70},
            }
            run = AnalysisResult(
                project_id=pid,
                file_hash="no-chart-block",
                result_json=json.dumps(result_body),
                status="report_ready",
            )
            db.add(run)
            db.commit()
            db.add(ReportDraft(
                project_id=pid,
                analysis_result_id=run.id,
                title="T",
                summary="S",
                selected_insight_ids_json=json.dumps(["x"]),
            ))
            db.commit()
        finally:
            db.close()

        data = client.get(f"/reports/draft/{pid}", headers=auth_headers).json()
        assert data["available_charts"] == []

    def test_available_charts_includes_title_and_chart_type(self, client, project, auth_headers):
        pid = project["id"]
        self._seed(pid, [
            {"chart_id": "scatter1", "title": "Risk scatter", "type": "scatter"},
        ], selected_chart_ids=["scatter1"])

        data = client.get(f"/reports/draft/{pid}", headers=auth_headers).json()
        ch = data["available_charts"][0]
        assert ch["chart_id"] == "scatter1"
        assert ch["title"] == "Risk scatter"
        assert ch["chart_type"] == "scatter"
        assert ch["selected"] is True
