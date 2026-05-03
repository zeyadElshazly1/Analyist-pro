"""
Report Draft Export tests
=========================

Verifies that the saved Report Builder draft drives what comes out of the
``/reports/export`` and ``/reports/preview`` endpoints:

- Edited summary appears in HTML and Excel exports.
- Selected findings appear; deselected findings do not.
- Preview uses the same (filtered) context as export.
- A draft pinned to an older analysis run does not silently switch to the
  latest run.
- A draft whose ``analysis_result_id`` points at a different project's run
  is rejected and falls back to the project's own latest run.
- The draft-applied helper in isolation behaves correctly.
- build_context exposes selected_chart_payloads resolved from stored chart
  blocks.

These tests are the contract for the launch-hardening report-export fix.
"""
from __future__ import annotations

import io
import json

import pandas as pd
import pytest
from openpyxl import load_workbook

from app.models import AnalysisResult, ReportDraft
from app.services.reporting.charts import resolve_selected_chart_payloads
from app.services.reporting.context import build_context
from app.services.reporting.draft_context import apply_draft_to_result
from tests.conftest import TestingSessionLocal


# ── Helpers ───────────────────────────────────────────────────────────────────

def _seed_run(
    project_id: int,
    *,
    insight_titles: list[str],
    narrative: str = "Pipeline-generated narrative.",
) -> int:
    """Insert an AnalysisResult directly with deterministic insight_results.

    Returns the run id.  Each insight has stable, easy-to-grep ``title`` and
    ``explanation`` strings so tests can assert presence/absence.
    """
    db = TestingSessionLocal()
    try:
        insight_results = []
        for idx, title in enumerate(insight_titles):
            insight_results.append({
                "insight_id": f"ins_{idx}",
                "title": title,
                "explanation": f"{title} — detail body line.",
                "category": "outlier",
                "severity": "high" if idx == 0 else "medium",
                "columns_used": ["salary"],
                "method_used": "IQR fence",
                "evidence": f"n={50 + idx}",
                "confidence": 0.9,
                "report_safe": True,
                "caveats": [],
                "why_it_matters": "Matters because the test says so.",
                "recommendation": f"Investigate {title}",
                "chart_suggestion": "none",
            })

        result = {
            "project_id": project_id,
            "narrative": narrative,
            "insight_results": insight_results,
            "health_score": {"total": 80, "breakdown": {"Overall": 80}},
            "dataset_summary": {"rows": 10, "columns": 3, "numeric_cols": 2, "categorical_cols": 1, "missing_pct": 0.0},
            "cleaning_report": [],
            "profile": [],
        }
        run = AnalysisResult(
            project_id=project_id,
            file_hash="seed-hash",
            result_json=json.dumps(result),
            status="report_ready",
        )
        db.add(run)
        db.commit()
        db.refresh(run)
        return run.id
    finally:
        db.close()


def _save_draft(
    client,
    project_id: int,
    headers,
    *,
    summary: str | None = None,
    selected: list[int] | None = None,
    title: str | None = None,
):
    """POST to /reports/draft/{pid}; returns the response body."""
    payload: dict = {}
    if summary is not None:
        payload["summary"] = summary
    if selected is not None:
        payload["selected_insight_ids"] = selected
    if title is not None:
        payload["title"] = title
    r = client.post(f"/reports/draft/{project_id}", json=payload, headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


def _link_draft_to_run(project_id: int, run_id: int) -> None:
    """Force the latest draft for ``project_id`` to point at ``run_id``."""
    db = TestingSessionLocal()
    try:
        draft = (
            db.query(ReportDraft)
            .filter(ReportDraft.project_id == project_id)
            .order_by(ReportDraft.created_at.desc())
            .first()
        )
        assert draft is not None, "No draft exists yet — call _save_draft first"
        draft.analysis_result_id = run_id
        db.commit()
    finally:
        db.close()


# ── apply_draft_to_result unit tests ──────────────────────────────────────────

class TestApplyDraftToResultUnit:
    def test_filters_insight_results_by_selected_indices(self):
        result = {
            "narrative": "original",
            "insight_results": [
                {"title": "Finding A"},
                {"title": "Finding B"},
                {"title": "Finding C"},
            ],
        }
        applied = apply_draft_to_result(result, selected_indices=[0, 2])
        titles = [i["title"] for i in applied["insight_results"]]
        assert titles == ["Finding A", "Finding C"]
        # Original input must not be mutated.
        assert len(result["insight_results"]) == 3

    def test_filters_legacy_insights_when_canonical_missing(self):
        result = {"insights": [{"finding": "X"}, {"finding": "Y"}]}
        applied = apply_draft_to_result(result, selected_indices=[1])
        assert [i["finding"] for i in applied["insights"]] == ["Y"]

    def test_mirrors_filter_to_legacy_when_both_present(self):
        result = {
            "insight_results": [{"title": "A"}, {"title": "B"}, {"title": "C"}],
            "insights":         [{"finding": "A"}, {"finding": "B"}, {"finding": "C"}],
        }
        applied = apply_draft_to_result(result, selected_indices=[1])
        assert [i["title"]   for i in applied["insight_results"]] == ["B"]
        assert [i["finding"] for i in applied["insights"]]        == ["B"]

    def test_replaces_narrative_with_draft_summary(self):
        result = {"narrative": "auto", "insight_results": []}
        applied = apply_draft_to_result(result, draft_summary="My edited summary")
        assert applied["narrative"] == "My edited summary"
        assert applied["draft_summary"] == "My edited summary"

    def test_blank_summary_does_not_overwrite_narrative(self):
        result = {"narrative": "auto", "insight_results": []}
        applied = apply_draft_to_result(result, draft_summary="   ")
        assert applied["narrative"] == "auto"
        assert "draft_summary" not in applied

    def test_none_selected_indices_keeps_full_list(self):
        result = {"insight_results": [{"title": "A"}, {"title": "B"}]}
        applied = apply_draft_to_result(result, selected_indices=None)
        assert len(applied["insight_results"]) == 2

    def test_invalid_indices_are_clamped(self):
        result = {"insight_results": [{"title": "A"}, {"title": "B"}]}
        applied = apply_draft_to_result(result, selected_indices=[0, 99, -1, "bad"])  # type: ignore[list-item]
        assert [i["title"] for i in applied["insight_results"]] == ["A"]


# ── End-to-end: HTML export honours the draft ────────────────────────────────

class TestHtmlExportUsesDraft:
    def test_edited_summary_and_selected_findings_appear(
        self, client, uploaded_project, consultant_auth_headers
    ):
        pid = uploaded_project["id"]
        _seed_run(pid, insight_titles=[
            "ALPHA_KEEP_FINDING",
            "BETA_DESELECTED_FINDING",
            "GAMMA_KEEP_FINDING",
        ])

        edited = "EDITED_SUMMARY_TOKEN — this is what the consultant wrote."
        _save_draft(
            client, pid, consultant_auth_headers,
            summary=edited,
            selected=[0, 2],  # keep ALPHA + GAMMA, drop BETA
        )

        r = client.get(f"/reports/export/{pid}?format=html", headers=consultant_auth_headers)
        assert r.status_code == 200, r.text
        body = r.text

        assert edited in body, "Edited summary must appear in HTML export"
        assert "ALPHA_KEEP_FINDING" in body
        assert "GAMMA_KEEP_FINDING" in body
        assert "BETA_DESELECTED_FINDING" not in body, (
            "Deselected finding must not appear in HTML export"
        )

    def test_html_uses_pinned_run_not_latest(
        self, client, uploaded_project, consultant_auth_headers
    ):
        """A draft pinned to an older run must not export the latest run's data."""
        pid = uploaded_project["id"]

        # Older run — what the draft was built against.
        old_run_id = _seed_run(pid, insight_titles=["OLD_RUN_FINDING"])

        # Save a draft against the old run (currently the "latest").
        _save_draft(
            client, pid, consultant_auth_headers,
            summary="Summary tied to OLD run.",
            selected=[0],
        )
        _link_draft_to_run(pid, old_run_id)

        # Now seed a *newer* run with a clearly different finding.
        _seed_run(pid, insight_titles=["NEW_RUN_FINDING"])

        r = client.get(f"/reports/export/{pid}?format=html", headers=consultant_auth_headers)
        assert r.status_code == 200, r.text
        assert "OLD_RUN_FINDING" in r.text
        assert "NEW_RUN_FINDING" not in r.text, (
            "Export must stay on the draft-linked analysis run, not silently "
            "switch to the latest run."
        )


# ── End-to-end: Excel export honours the draft ───────────────────────────────

class TestExcelExportUsesDraft:
    def test_edited_summary_and_selected_findings_appear(
        self, client, uploaded_project, consultant_auth_headers
    ):
        pid = uploaded_project["id"]
        _seed_run(pid, insight_titles=[
            "EXCEL_ALPHA_KEEP",
            "EXCEL_BETA_DROP",
            "EXCEL_GAMMA_KEEP",
        ])

        edited = "EXCEL_SUMMARY_EDIT_TOKEN — written by the consultant."
        _save_draft(
            client, pid, consultant_auth_headers,
            summary=edited,
            selected=[0, 2],
        )

        r = client.get(f"/reports/export/{pid}?format=xlsx", headers=consultant_auth_headers)
        assert r.status_code == 200
        wb = load_workbook(io.BytesIO(r.content), data_only=True)

        # Summary sheet should contain the edited executive summary.
        summary_text = "\n".join(
            str(c.value) for row in wb["Summary"].iter_rows() for c in row if c.value
        )
        assert edited in summary_text, "Edited summary must appear on the Summary sheet"

        # Insights sheet should include only selected findings.
        insights_text = "\n".join(
            str(c.value) for row in wb["Insights"].iter_rows() for c in row if c.value
        )
        assert "EXCEL_ALPHA_KEEP" in insights_text
        assert "EXCEL_GAMMA_KEEP" in insights_text
        assert "EXCEL_BETA_DROP" not in insights_text


# ── Preview parity ────────────────────────────────────────────────────────────

class TestPreviewMatchesExport:
    def test_preview_returns_filtered_context(
        self, client, uploaded_project, consultant_auth_headers
    ):
        pid = uploaded_project["id"]
        _seed_run(pid, insight_titles=[
            "PREVIEW_ALPHA",
            "PREVIEW_BETA_DROP",
            "PREVIEW_GAMMA",
        ])

        edited = "PREVIEW_SUMMARY_TOKEN."
        _save_draft(
            client, pid, consultant_auth_headers,
            summary=edited,
            selected=[0, 2],
        )

        r = client.get(f"/reports/preview/{pid}", headers=consultant_auth_headers)
        assert r.status_code == 200, r.text
        body = r.json()

        assert body["narrative"] == edited
        titles = [i.get("title") for i in body.get("insight_results", [])]
        assert titles == ["PREVIEW_ALPHA", "PREVIEW_GAMMA"]


# ── Cross-project draft / analysis_result mismatch is rejected ───────────────

class TestCrossProjectMismatchRejected:
    def test_draft_with_other_project_run_falls_back_to_own_latest(
        self, client, uploaded_project, consultant_auth_headers, csv_bytes, auth_headers
    ):
        """A draft whose analysis_result_id points at another project's run
        must not pull data from that other project — the resolver falls back
        to this project's own latest run.
        """
        pid_a = uploaded_project["id"]

        # Project B for the same user — different project, different run.
        r = client.post("/projects", json={"name": "Project B"}, headers=consultant_auth_headers)
        assert r.status_code == 200, r.text
        pid_b = r.json()["id"]
        client.post(
            "/upload",
            files={"file": ("data.csv", io.BytesIO(csv_bytes), "text/csv")},
            data={"project_id": str(pid_b)},
            headers=consultant_auth_headers,
        )
        run_b_id = _seed_run(pid_b, insight_titles=["PROJECT_B_FINDING"])

        # Project A: own analysis exists.
        run_a_id = _seed_run(pid_a, insight_titles=["PROJECT_A_FINDING"])

        # Save a draft for project A and forcibly point it at project B's run id.
        _save_draft(
            client, pid_a, consultant_auth_headers,
            summary="Cross-project summary.",
            selected=[0],
        )
        _link_draft_to_run(pid_a, run_b_id)

        r = client.get(f"/reports/export/{pid_a}?format=html", headers=consultant_auth_headers)
        assert r.status_code == 200, r.text
        body = r.text
        assert "PROJECT_A_FINDING" in body
        assert "PROJECT_B_FINDING" not in body, (
            "A tampered draft must not be able to pull data from another "
            "project's analysis run."
        )


# ── Backwards compatibility: no draft yet ─────────────────────────────────────

class TestNoDraftFallback:
    def test_export_without_draft_uses_latest_run(
        self, client, uploaded_project, consultant_auth_headers
    ):
        """When no draft has been saved, export still works against the
        latest run — preserves existing behaviour for users who never opened
        the Report Builder."""
        pid = uploaded_project["id"]
        _seed_run(pid, insight_titles=["DEFAULT_FINDING_NO_DRAFT"])

        r = client.get(f"/reports/export/{pid}?format=html", headers=consultant_auth_headers)
        assert r.status_code == 200, r.text
        assert "DEFAULT_FINDING_NO_DRAFT" in r.text


# ── apply_draft_to_result: selected_chart_ids propagation ─────────────────────

class TestApplyDraftSelectedChartIds:
    def test_stores_chart_ids_in_result(self):
        result = {"insight_results": []}
        applied = apply_draft_to_result(result, selected_chart_ids=["c1", "c2"])
        assert applied["selected_chart_ids"] == ["c1", "c2"]

    def test_none_chart_ids_does_not_add_key(self):
        result = {"insight_results": []}
        applied = apply_draft_to_result(result, selected_chart_ids=None)
        assert "selected_chart_ids" not in applied

    def test_empty_list_stored_explicitly(self):
        result = {"insight_results": []}
        applied = apply_draft_to_result(result, selected_chart_ids=[])
        assert applied["selected_chart_ids"] == []

    def test_does_not_mutate_original(self):
        result = {"insight_results": [], "charts": [{"chart_id": "x"}]}
        apply_draft_to_result(result, selected_chart_ids=["x"])
        assert "selected_chart_ids" not in result

    def test_combined_with_insight_selection(self):
        result = {
            "insight_results": [
                {"insight_id": "a", "title": "A"},
                {"insight_id": "b", "title": "B"},
            ],
        }
        applied = apply_draft_to_result(
            result, selected_indices=["a"], selected_chart_ids=["c9"]
        )
        assert [i["title"] for i in applied["insight_results"]] == ["A"]
        assert applied["selected_chart_ids"] == ["c9"]


# ── resolve_selected_chart_payloads unit tests ────────────────────────────────

class TestResolveSelectedChartPayloads:
    def test_returns_empty_when_no_key(self):
        assert resolve_selected_chart_payloads({}) == []

    def test_returns_empty_when_key_is_empty_list(self):
        assert resolve_selected_chart_payloads({"selected_chart_ids": []}) == []

    def test_resolves_string_id_from_charts_block(self):
        result = {
            "selected_chart_ids": ["c1"],
            "charts": [{"chart_id": "c1", "title": "Revenue", "type": "bar"}],
        }
        out = resolve_selected_chart_payloads(result)
        assert len(out) == 1
        assert out[0]["chart_id"] == "c1"
        assert out[0]["title"] == "Revenue"
        assert out[0]["chart_type"] == "bar"

    def test_resolves_from_chart_results_block(self):
        result = {
            "selected_chart_ids": ["cr1"],
            "chart_results": [{"chart_id": "cr1", "title": "Sector split", "type": "pie"}],
        }
        out = resolve_selected_chart_payloads(result)
        assert out[0]["chart_id"] == "cr1"
        assert out[0]["chart_type"] == "pie"

    def test_resolves_from_suggested_charts_block(self):
        result = {
            "selected_chart_ids": ["s1"],
            "suggested_charts": [{"chart_id": "s1", "title": "Trend", "type": "line"}],
        }
        out = resolve_selected_chart_payloads(result)
        assert out[0]["chart_id"] == "s1"

    def test_resolves_from_chart_gallery_block(self):
        result = {
            "selected_chart_ids": ["g1"],
            "chart_gallery": [{"chart_id": "g1", "title": "Gallery item", "type": "scatter"}],
        }
        out = resolve_selected_chart_payloads(result)
        assert out[0]["chart_id"] == "g1"

    def test_skips_unresolvable_ids(self):
        result = {
            "selected_chart_ids": ["known", "ghost"],
            "charts": [{"chart_id": "known", "title": "Known chart", "type": "bar"}],
        }
        out = resolve_selected_chart_payloads(result)
        assert len(out) == 1
        assert out[0]["chart_id"] == "known"

    def test_deduplicates_by_chart_id(self):
        result = {
            "selected_chart_ids": ["dup", "dup"],
            "charts": [{"chart_id": "dup", "title": "Dup", "type": "bar"}],
        }
        out = resolve_selected_chart_payloads(result)
        assert len(out) == 1

    def test_preserves_order_matching_selected_ids(self):
        result = {
            "selected_chart_ids": ["b", "a"],
            "charts": [
                {"chart_id": "a", "title": "A"},
                {"chart_id": "b", "title": "B"},
            ],
        }
        out = resolve_selected_chart_payloads(result)
        assert [e["chart_id"] for e in out] == ["b", "a"]

    def test_legacy_integer_index_resolved(self):
        result = {
            "selected_chart_ids": [1],
            "charts": [
                {"title": "First", "type": "bar"},
                {"title": "Second", "type": "line"},
            ],
        }
        out = resolve_selected_chart_payloads(result)
        assert len(out) == 1
        assert out[0]["chart_id"] == "idx_1"
        assert out[0]["title"] == "Second"
        assert out[0]["chart_type"] == "line"

    def test_integer_index_out_of_range_skipped(self):
        result = {
            "selected_chart_ids": [99],
            "charts": [{"chart_id": "only", "title": "Only", "type": "bar"}],
        }
        assert resolve_selected_chart_payloads(result) == []

    def test_integer_index_resolves_to_existing_chart_id(self):
        result = {
            "selected_chart_ids": [0],
            "charts": [{"chart_id": "has_id", "title": "Has ID", "type": "bar"}],
        }
        out = resolve_selected_chart_payloads(result)
        assert out[0]["chart_id"] == "has_id"

    def test_dict_slot_resolved_by_chart_id_field(self):
        result = {
            "selected_chart_ids": [{"chart_id": "d1", "title": "override"}],
            "charts": [{"chart_id": "d1", "title": "Stored", "type": "bar"}],
        }
        out = resolve_selected_chart_payloads(result)
        assert out[0]["chart_id"] == "d1"

    def test_preserves_all_stored_fields(self):
        result = {
            "selected_chart_ids": ["rich"],
            "charts": [{
                "chart_id": "rich",
                "title": "Rich chart",
                "type": "bar",
                "data": {"labels": ["A"], "datasets": [{"data": [1]}]},
                "options": {"responsive": True},
            }],
        }
        out = resolve_selected_chart_payloads(result)
        assert "data" in out[0]
        assert "options" in out[0]

    def test_normalises_chart_type_from_type_field(self):
        result = {
            "selected_chart_ids": ["t1"],
            "charts": [{"chart_id": "t1", "title": "T", "type": "scatter"}],
        }
        out = resolve_selected_chart_payloads(result)
        assert out[0]["chart_type"] == "scatter"

    def test_unknown_chart_type_when_missing(self):
        result = {
            "selected_chart_ids": ["no_type"],
            "charts": [{"chart_id": "no_type", "title": "No type chart"}],
        }
        out = resolve_selected_chart_payloads(result)
        assert out[0]["chart_type"] == "unknown"

    def test_booleans_in_selected_ids_are_skipped(self):
        result = {
            "selected_chart_ids": [True, False, "real"],
            "charts": [{"chart_id": "real", "title": "R", "type": "bar"}],
        }
        out = resolve_selected_chart_payloads(result)
        assert len(out) == 1
        assert out[0]["chart_id"] == "real"

    def test_empty_charts_block_falls_through_to_chart_results(self):
        result = {
            "selected_chart_ids": ["x"],
            "charts": [],
            "chart_results": [{"chart_id": "x", "title": "X", "type": "bar"}],
        }
        out = resolve_selected_chart_payloads(result)
        assert out[0]["chart_id"] == "x"


# ── build_context: selected_chart_payloads integration ───────────────────────

_MINIMAL_DF = pd.DataFrame({"a": [1, 2, 3]})


class TestBuildContextSelectedChartPayloads:
    def test_key_present_and_empty_when_no_selection(self):
        result = {
            "insight_results": [],
            "health_score": {"total": 80, "breakdown": {"Overall": 80}},
        }
        ctx = build_context(_MINIMAL_DF, result, "Test")
        assert "selected_chart_payloads" in ctx
        assert ctx["selected_chart_payloads"] == []

    def test_resolves_payloads_when_selection_present(self):
        result = {
            "selected_chart_ids": ["c1"],
            "charts": [{"chart_id": "c1", "title": "Revenue", "type": "bar"}],
            "insight_results": [],
            "health_score": {"total": 70},
        }
        ctx = build_context(_MINIMAL_DF, result, "Test")
        payloads = ctx["selected_chart_payloads"]
        assert len(payloads) == 1
        assert payloads[0]["chart_id"] == "c1"
        assert payloads[0]["title"] == "Revenue"
        assert payloads[0]["chart_type"] == "bar"

    def test_skips_unresolvable_ids_in_context(self):
        result = {
            "selected_chart_ids": ["present", "absent"],
            "charts": [{"chart_id": "present", "title": "Here", "type": "line"}],
            "insight_results": [],
            "health_score": {"total": 70},
        }
        ctx = build_context(_MINIMAL_DF, result, "Test")
        ids = [p["chart_id"] for p in ctx["selected_chart_payloads"]]
        assert ids == ["present"]

    def test_legacy_health_and_missing_charts_unchanged(self):
        result = {
            "health_score": {"total": 65, "breakdown": {"Completeness": 65}},
            "profile": [{"name": "col_a", "missing_pct": 20}],
            "insight_results": [],
        }
        ctx = build_context(_MINIMAL_DF, result, "Test")
        assert ctx["health_chart"] is not None
        assert ctx["missing_chart"] is not None
        assert "selected_chart_payloads" in ctx

    def test_full_pipeline_apply_draft_then_build_context(self):
        analysis_result = {
            "narrative": "original",
            "insight_results": [
                {"insight_id": "ins_a", "title": "Insight A", "severity": "high"},
            ],
            "charts": [
                {"chart_id": "ch_1", "title": "Top performers", "type": "bar"},
                {"chart_id": "ch_2", "title": "Risk scatter", "type": "scatter"},
            ],
            "health_score": {"total": 75},
        }
        applied = apply_draft_to_result(
            analysis_result,
            draft_summary="Consultant summary.",
            selected_indices=["ins_a"],
            selected_chart_ids=["ch_2", "ch_1"],
        )
        ctx = build_context(_MINIMAL_DF, applied, "Project X")
        payloads = ctx["selected_chart_payloads"]
        assert [p["chart_id"] for p in payloads] == ["ch_2", "ch_1"]
        assert payloads[0]["chart_type"] == "scatter"
        assert payloads[1]["chart_type"] == "bar"
        assert ctx["narrative"] == "Consultant summary."
