"""
Export history hydration tests (Task 8)
=======================================

Locks in the trust-hardening fix that makes the Report Builder's
"Export history" strip survive a refresh.  The strip used to live in
pure local React state — these tests prove the backend persists every
attempt to the audit log and surfaces it via
``GET /reports/draft/{project_id}.report_result.export_statuses``.

Coverage
--------
* Successful HTML / Excel / PDF exports each write an ``export_completed``
  audit row that comes back through the draft endpoint.
* PDF "unavailable" (501) writes ``export_unavailable`` instead of pretending
  the export succeeded — and is surfaced on the strip.
* Failed generation writes ``export_failed`` with the error message.
* The draft endpoint's ``export_statuses`` carries ``format``, ``status``,
  ``exported_at`` and an ``error_message`` for failed/unavailable rows.
* Histories are scoped per project — a different user (or project) cannot
  see another consultant's exports.
* A draft with no exports yet returns an empty ``export_statuses`` list
  (no crash, no fake rows).
"""
from __future__ import annotations

import io
import json

from app.models import AnalysisResult
from tests.conftest import TestingSessionLocal


# ── Helpers ───────────────────────────────────────────────────────────────────

def _seed_run(project_id: int, *, insight_titles: list[str] | None = None) -> int:
    titles = insight_titles or ["FINDING_X"]
    db = TestingSessionLocal()
    try:
        insight_results = [
            {
                "insight_id": f"sid_{t}",
                "title": t,
                "explanation": f"{t} body",
                "category": "outlier",
                "severity": "high",
                "columns_used": ["salary"],
                "method_used": "IQR",
                "evidence": "n=10",
                "confidence": 0.9,
                "report_safe": True,
                "caveats": [],
                "why_it_matters": "x",
                "recommendation": f"investigate {t}",
                "chart_suggestion": "none",
            }
            for t in titles
        ]
        result = {
            "project_id": project_id,
            "narrative": "Pipeline-generated narrative.",
            "insight_results": insight_results,
            "health_score": {"total": 80, "breakdown": {"Overall": 80}},
            "dataset_summary": {
                "rows": 10, "columns": 3,
                "numeric_cols": 2, "categorical_cols": 1, "missing_pct": 0.0,
            },
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


def _save_draft(client, project_id: int, headers, *, summary: str = "Draft summary."):
    r = client.post(
        f"/reports/draft/{project_id}",
        json={"summary": summary, "selected_insight_ids": ["sid_FINDING_X"]},
        headers=headers,
    )
    assert r.status_code == 200, r.text
    return r.json()


def _draft(client, project_id: int, headers) -> dict:
    r = client.get(f"/reports/draft/{project_id}", headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


def _export_statuses(draft_body: dict) -> list[dict]:
    return draft_body.get("report_result", {}).get("export_statuses", [])


# ── Empty state ──────────────────────────────────────────────────────────────

class TestEmptyHistory:
    def test_draft_with_no_exports_returns_empty_list(
        self, client, uploaded_project, consultant_auth_headers
    ):
        pid = uploaded_project["id"]
        _seed_run(pid)
        _save_draft(client, pid, consultant_auth_headers)

        body = _draft(client, pid, consultant_auth_headers)
        assert _export_statuses(body) == []


# ── Successful exports are persisted ─────────────────────────────────────────

class TestSuccessfulExportPersistence:
    def test_html_export_writes_completed_row(
        self, client, uploaded_project, consultant_auth_headers
    ):
        pid = uploaded_project["id"]
        _seed_run(pid)
        _save_draft(client, pid, consultant_auth_headers)

        r = client.get(f"/reports/export/{pid}?format=html", headers=consultant_auth_headers)
        assert r.status_code == 200, r.text

        statuses = _export_statuses(_draft(client, pid, consultant_auth_headers))
        # Newest-first; expect exactly one row from this single export.
        assert len(statuses) == 1
        rec = statuses[0]
        assert rec["format"] == "html"
        assert rec["status"] == "completed"
        assert rec["exported_at"] is not None
        assert rec.get("error_message") in (None, "")

    def test_xlsx_export_writes_completed_row(
        self, client, uploaded_project, consultant_auth_headers
    ):
        pid = uploaded_project["id"]
        _seed_run(pid)
        _save_draft(client, pid, consultant_auth_headers)

        r = client.get(f"/reports/export/{pid}?format=xlsx", headers=consultant_auth_headers)
        assert r.status_code == 200

        statuses = _export_statuses(_draft(client, pid, consultant_auth_headers))
        assert len(statuses) == 1
        assert statuses[0]["format"] == "xlsx"
        assert statuses[0]["status"] == "completed"

    def test_multiple_exports_appear_newest_first(
        self, client, uploaded_project, consultant_auth_headers
    ):
        pid = uploaded_project["id"]
        _seed_run(pid)
        _save_draft(client, pid, consultant_auth_headers)

        # Three exports in order: html, xlsx, html.
        for fmt in ("html", "xlsx", "html"):
            r = client.get(f"/reports/export/{pid}?format={fmt}", headers=consultant_auth_headers)
            assert r.status_code == 200

        statuses = _export_statuses(_draft(client, pid, consultant_auth_headers))
        formats = [s["format"] for s in statuses]
        # Newest-first → reversed insertion order.
        assert formats == ["html", "xlsx", "html"]
        # All three should be ``completed``.
        assert all(s["status"] == "completed" for s in statuses)


# ── PDF unavailable is honest ────────────────────────────────────────────────

class TestPdfUnavailableHonest:
    def test_pdf_runtime_error_writes_unavailable(
        self, client, uploaded_project, consultant_auth_headers, monkeypatch
    ):
        """When the PDF generator raises ``RuntimeError`` (deps missing) the
        endpoint returns 501 *and* records ``export_unavailable`` so the
        strip can show an honest "PDF unavailable" badge after a refresh."""
        from app.routes import reports as reports_mod

        def _raise_runtime(*args, **kwargs):
            raise RuntimeError("PDF generation requires WeasyPrint or pdfkit.")

        monkeypatch.setattr(reports_mod, "generate_pdf_report", _raise_runtime)

        pid = uploaded_project["id"]
        _seed_run(pid)
        _save_draft(client, pid, consultant_auth_headers)

        r = client.get(f"/reports/export/{pid}?format=pdf", headers=consultant_auth_headers)
        assert r.status_code == 501, r.text

        statuses = _export_statuses(_draft(client, pid, consultant_auth_headers))
        assert len(statuses) == 1
        rec = statuses[0]
        assert rec["format"] == "pdf"
        assert rec["status"] == "unavailable"
        # Honest error surfaced — must not pretend success.
        assert rec.get("error_message") and "WeasyPrint" in rec["error_message"]

    def test_pdf_runtime_error_does_not_log_completed(
        self, client, uploaded_project, consultant_auth_headers, monkeypatch
    ):
        """Defence: the unavailable path must never write a fake
        ``export_completed`` row alongside the unavailable one."""
        from app.routes import reports as reports_mod

        def _raise_runtime(*args, **kwargs):
            raise RuntimeError("deps missing")

        monkeypatch.setattr(reports_mod, "generate_pdf_report", _raise_runtime)

        pid = uploaded_project["id"]
        _seed_run(pid)
        _save_draft(client, pid, consultant_auth_headers)

        client.get(f"/reports/export/{pid}?format=pdf", headers=consultant_auth_headers)
        statuses = _export_statuses(_draft(client, pid, consultant_auth_headers))
        completed = [s for s in statuses if s["status"] == "completed"]
        assert completed == []


# ── PDF generation failure (not deps) is logged as failed ────────────────────

class TestPdfGenericFailureLogged:
    def test_pdf_unexpected_exception_writes_failed(
        self, client, uploaded_project, consultant_auth_headers, monkeypatch
    ):
        from app.routes import reports as reports_mod

        def _raise_generic(*args, **kwargs):
            raise ValueError("unexpected pdf bug")

        monkeypatch.setattr(reports_mod, "generate_pdf_report", _raise_generic)

        pid = uploaded_project["id"]
        _seed_run(pid)
        _save_draft(client, pid, consultant_auth_headers)

        r = client.get(f"/reports/export/{pid}?format=pdf", headers=consultant_auth_headers)
        assert r.status_code == 500

        statuses = _export_statuses(_draft(client, pid, consultant_auth_headers))
        assert len(statuses) == 1
        rec = statuses[0]
        assert rec["format"] == "pdf"
        assert rec["status"] == "failed"
        assert rec.get("error_message") and "unexpected pdf bug" in rec["error_message"]


# ── Excel/HTML generator failure is honest too ───────────────────────────────

class TestNonPdfGenerationFailure:
    def test_xlsx_failure_writes_failed_row(
        self, client, uploaded_project, consultant_auth_headers, monkeypatch
    ):
        from app.routes import reports as reports_mod

        def _boom(*args, **kwargs):
            raise RuntimeError("xlsx writer crashed")

        monkeypatch.setattr(reports_mod, "generate_excel_report", _boom)

        pid = uploaded_project["id"]
        _seed_run(pid)
        _save_draft(client, pid, consultant_auth_headers)

        r = client.get(f"/reports/export/{pid}?format=xlsx", headers=consultant_auth_headers)
        assert r.status_code == 500

        statuses = _export_statuses(_draft(client, pid, consultant_auth_headers))
        assert len(statuses) == 1
        rec = statuses[0]
        assert rec["format"] == "xlsx"
        assert rec["status"] == "failed"
        assert "xlsx writer crashed" in (rec.get("error_message") or "")


# ── History is scoped per project, not leaked across users ───────────────────

class TestHistoryIsolation:
    def test_history_does_not_leak_across_projects_for_same_user(
        self, client, uploaded_project, consultant_auth_headers, csv_bytes
    ):
        """One user, two projects.  Exporting from project A must not show
        up on project B's history strip."""
        pid_a = uploaded_project["id"]
        _seed_run(pid_a)
        _save_draft(client, pid_a, consultant_auth_headers)

        # Project B for the same user.
        r = client.post("/projects", json={"name": "Project B"}, headers=consultant_auth_headers)
        assert r.status_code == 200
        pid_b = r.json()["id"]
        client.post(
            "/upload",
            files={"file": ("data.csv", io.BytesIO(csv_bytes), "text/csv")},
            data={"project_id": str(pid_b)},
            headers=consultant_auth_headers,
        )
        _seed_run(pid_b)
        _save_draft(client, pid_b, consultant_auth_headers)

        # Export only from A.
        r = client.get(f"/reports/export/{pid_a}?format=html", headers=consultant_auth_headers)
        assert r.status_code == 200

        a_history = _export_statuses(_draft(client, pid_a, consultant_auth_headers))
        b_history = _export_statuses(_draft(client, pid_b, consultant_auth_headers))

        assert len(a_history) == 1
        assert b_history == []

    def test_other_user_cannot_read_export_history_via_draft(
        self, client, uploaded_project, consultant_auth_headers
    ):
        """A different authenticated user must not be able to fetch the
        draft (and thus the export-history strip) for someone else's
        project — Task 1's ownership guard remains intact for this surface."""
        from tests.test_ownership_guards import _other_headers

        pid = uploaded_project["id"]
        _seed_run(pid)
        _save_draft(client, pid, consultant_auth_headers)
        client.get(f"/reports/export/{pid}?format=html", headers=consultant_auth_headers)

        other = _other_headers(client, plan="consultant")
        r = client.get(f"/reports/draft/{pid}", headers=other)
        # Ownership guard returns 404 to avoid leaking project existence.
        assert r.status_code == 404, r.text


# ── error_message length cap ─────────────────────────────────────────────────

class TestErrorMessageCap:
    def test_long_error_messages_are_truncated(
        self, client, uploaded_project, consultant_auth_headers, monkeypatch
    ):
        """Defence: a misbehaving generator that raises with a huge message
        must not blow up the audit row.  The endpoint truncates to ~500."""
        from app.routes import reports as reports_mod

        huge = "X" * 5000

        def _raise_huge(*args, **kwargs):
            raise RuntimeError(huge)

        monkeypatch.setattr(reports_mod, "generate_excel_report", _raise_huge)

        pid = uploaded_project["id"]
        _seed_run(pid)
        _save_draft(client, pid, consultant_auth_headers)

        r = client.get(f"/reports/export/{pid}?format=xlsx", headers=consultant_auth_headers)
        assert r.status_code == 500

        statuses = _export_statuses(_draft(client, pid, consultant_auth_headers))
        assert len(statuses) == 1
        msg = statuses[0].get("error_message") or ""
        assert 0 < len(msg) <= 500


# ── Draft endpoint: export history must not take down the whole response ─────

class TestDraftResilientToAuditExportHistoryFailure:
    def test_get_draft_200_with_sections_and_insights_when_audit_history_fails(
        self, client, uploaded_project, consultant_auth_headers, monkeypatch
    ):
        """If the audit-log query for export history fails (e.g. schema drift),
        GET /reports/draft still returns 200 with sections and insights."""
        from app.routes import reports as reports_mod

        def _boom(*_args, **_kwargs):
            raise RuntimeError("simulated audit_logs UndefinedColumn")

        monkeypatch.setattr(reports_mod, "_load_export_statuses_from_audit", _boom)

        pid = uploaded_project["id"]
        _seed_run(pid)
        _save_draft(client, pid, consultant_auth_headers)

        r = client.get(f"/reports/draft/{pid}", headers=consultant_auth_headers)
        assert r.status_code == 200, r.text
        body = r.json()
        rr = body["report_result"]
        assert rr["export_statuses"] == []
        assert len(rr["included_sections"]) >= 1
        assert len(rr["included_insights"]) >= 1
