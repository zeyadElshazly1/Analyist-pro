"""
Cross-user ownership / authorisation tests.

Verifies that the launch-hardening project ownership guards (added in
``app/services/access_guards.py``) correctly reject any attempt by user B
to read, mutate, analyse, export, or report on a project owned by user A.

Coverage:
- /projects/{project_id}                 (GET, DELETE, annotations, latest-insights)
- /upload                                (POST)
- /analysis/run                          (POST)
- /analysis/preview/{project_id}         (GET)
- /analysis/history/{project_id}         (GET)
- /analysis/runs/{project_id}            (GET)
- /analysis/runs/{project_id}/latest     (GET)
- /analysis/run/{run_id}                 (GET)
- /analysis/run/{run_id}/results         (GET)
- /analysis/result/{analysis_id}         (GET)
- /analysis/share/{project_id}           (POST, DELETE)
- /analysis/data-table                   (GET)
- /analysis/download-cleaned/{project_id}(GET)
- /reports/export/{project_id}           (GET)
- /reports/preview/{project_id}          (GET)
- /reports/draft/{project_id}            (GET, POST)
- /charts/suggest                        (POST)
- /chat/query                            (POST)
- /query/execute, /query/schema          (POST/GET)
- /pivot/run, /pivot/columns             (POST/GET)
- /cohorts/rfm, /cohorts/retention,
  /cohorts/columns                       (POST/GET)
- /ml/train, /ml/columns,
  /ml/model-info/{project_id},
  /ml/predict/{project_id}               (POST/GET)
- /stats/test, /stats/columns            (POST/GET)
- /features/create, /features/suggest,
  /features/list                         (POST/GET)
- /explore/* (timeseries, duplicates,
  outliers, correlations, compare,
  multifile, join, segments)             (POST/GET)

For each route we assert:
- The owner (user A) can call it successfully (or fail with the route's
  normal 4xx — but never 404 due to ownership).
- A different authenticated user (user B) gets 404 ("…not found.") when
  passing user A's project / run / analysis identifier.
"""
import io

from tests.conftest import _make_test_jwt


# ── Fixtures / helpers ────────────────────────────────────────────────────────

OTHER_USER_ID = "00000000-0000-0000-0000-0000000000ff"
OTHER_USER_EMAIL = "intruder@example.com"


def _other_headers(client, *, plan: str | None = None) -> dict:
    """Auth headers for a *different* authenticated user (user B).

    The first authenticated request lazy-creates the user record, so we
    immediately hit ``/auth/me`` to ensure user B exists in the DB before
    the ownership-guard tests run.

    When ``plan`` is supplied (e.g. "consultant"), user B's plan is upgraded
    in the test DB.  This is needed for routes that are plan-gated *before*
    the ownership check — without the upgrade we'd hit a 402 plan wall and
    never reach the guard we're trying to verify.
    """
    token = _make_test_jwt(user_id=OTHER_USER_ID, email=OTHER_USER_EMAIL)
    headers = {"Authorization": f"Bearer {token}"}
    r = client.get("/auth/me", headers=headers)
    assert r.status_code == 200, r.text

    if plan:
        from app.models import User as UserModel
        from tests.conftest import TestingSessionLocal

        db = TestingSessionLocal()
        try:
            user = db.query(UserModel).filter(UserModel.id == OTHER_USER_ID).first()
            if user:
                user.plan = plan
                db.commit()
        finally:
            db.close()

    return headers


def _run_analysis(client, pid: int, auth_headers: dict) -> dict:
    """Run an analysis as the project owner and return the run dict."""
    r = client.post("/analysis/run", json={"project_id": pid}, headers=auth_headers)
    assert r.status_code == 200, r.text
    return r.json()


# ── /projects/{project_id} ────────────────────────────────────────────────────

def test_owner_can_get_own_project(client, project, auth_headers):
    pid = project["id"]
    r = client.get(f"/projects/{pid}", headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["id"] == pid


def test_other_user_cannot_get_project(client, project):
    pid = project["id"]
    other = _other_headers(client)
    r = client.get(f"/projects/{pid}", headers=other)
    assert r.status_code == 404
    assert r.json()["detail"] == "Project not found."


def test_other_user_cannot_delete_project(client, project):
    pid = project["id"]
    other = _other_headers(client)
    r = client.delete(f"/projects/{pid}", headers=other)
    assert r.status_code == 404


def test_other_user_cannot_read_annotations(client, project):
    pid = project["id"]
    other = _other_headers(client)
    r = client.get(f"/projects/{pid}/annotations", headers=other)
    assert r.status_code == 404


def test_other_user_cannot_write_annotations(client, project):
    pid = project["id"]
    other = _other_headers(client)
    r = client.put(
        f"/projects/{pid}/annotations/age",
        json={"note": "leak"},
        headers=other,
    )
    assert r.status_code == 404


def test_other_user_cannot_get_latest_insights(client, project):
    pid = project["id"]
    other = _other_headers(client)
    r = client.get(f"/projects/{pid}/latest-insights", headers=other)
    assert r.status_code == 404


def test_invalid_project_id_returns_404(client, auth_headers):
    r = client.get("/projects/9999999", headers=auth_headers)
    assert r.status_code == 404


# ── /upload ───────────────────────────────────────────────────────────────────

def test_other_user_cannot_upload_to_project(client, project, csv_bytes):
    pid = project["id"]
    other = _other_headers(client)
    r = client.post(
        "/upload",
        files={"file": ("data.csv", io.BytesIO(csv_bytes), "text/csv")},
        data={"project_id": str(pid)},
        headers=other,
    )
    assert r.status_code == 404
    assert r.json()["detail"] == "Project not found."


# ── /analysis/* (project_id-keyed) ────────────────────────────────────────────

def test_other_user_cannot_run_analysis(client, uploaded_project):
    pid = uploaded_project["id"]
    other = _other_headers(client)
    r = client.post("/analysis/run", json={"project_id": pid}, headers=other)
    assert r.status_code == 404


def test_other_user_cannot_preview_data(client, uploaded_project):
    pid = uploaded_project["id"]
    other = _other_headers(client)
    r = client.get(f"/analysis/preview/{pid}", headers=other)
    assert r.status_code == 404


def test_other_user_cannot_read_history(client, uploaded_project):
    pid = uploaded_project["id"]
    other = _other_headers(client)
    r = client.get(f"/analysis/history/{pid}", headers=other)
    assert r.status_code == 404


def test_other_user_cannot_list_runs(client, uploaded_project):
    pid = uploaded_project["id"]
    other = _other_headers(client)
    r = client.get(f"/analysis/runs/{pid}", headers=other)
    assert r.status_code == 404


def test_other_user_cannot_get_latest_run(client, uploaded_project):
    pid = uploaded_project["id"]
    other = _other_headers(client)
    r = client.get(f"/analysis/runs/{pid}/latest", headers=other)
    assert r.status_code == 404


def test_other_user_cannot_share_or_unshare(client, uploaded_project):
    pid = uploaded_project["id"]
    other = _other_headers(client)
    r1 = client.post(f"/analysis/share/{pid}", headers=other)
    assert r1.status_code == 404
    r2 = client.delete(f"/analysis/share/{pid}", headers=other)
    assert r2.status_code == 404


def test_other_user_cannot_download_cleaned_csv(client, uploaded_project, auth_headers):
    pid = uploaded_project["id"]
    _run_analysis(client, pid, auth_headers)
    other = _other_headers(client)
    r = client.get(f"/analysis/download-cleaned/{pid}", headers=other)
    assert r.status_code == 404


def test_other_user_cannot_use_data_table(client, uploaded_project):
    pid = uploaded_project["id"]
    other = _other_headers(client)
    r = client.get(f"/analysis/data-table?project_id={pid}", headers=other)
    assert r.status_code == 404


# ── /analysis/run/{run_id} & /analysis/result/{analysis_id} ───────────────────

def _latest_run_id(client, pid: int, auth_headers: dict) -> int:
    """Return the most recent run_id for a project."""
    latest = client.get(f"/analysis/runs/{pid}/latest", headers=auth_headers).json()
    # RunSummary/RunDetail use ``run_id`` as their identifier (mapped from
    # AnalysisResult.id via from_attributes).
    return latest["run_id"]


def test_other_user_cannot_get_run_by_id(client, uploaded_project, auth_headers):
    pid = uploaded_project["id"]
    _run_analysis(client, pid, auth_headers)
    run_id = _latest_run_id(client, pid, auth_headers)
    other = _other_headers(client)
    r = client.get(f"/analysis/run/{run_id}", headers=other)
    assert r.status_code == 404
    assert r.json()["detail"] == "Run not found."


def test_other_user_cannot_get_run_results(client, uploaded_project, auth_headers):
    pid = uploaded_project["id"]
    _run_analysis(client, pid, auth_headers)
    run_id = _latest_run_id(client, pid, auth_headers)
    other = _other_headers(client)
    r = client.get(f"/analysis/run/{run_id}/results", headers=other)
    assert r.status_code == 404


def test_other_user_cannot_get_analysis_result(client, uploaded_project, auth_headers):
    pid = uploaded_project["id"]
    _run_analysis(client, pid, auth_headers)
    analysis_id = _latest_run_id(client, pid, auth_headers)
    other = _other_headers(client)
    r = client.get(f"/analysis/result/{analysis_id}", headers=other)
    assert r.status_code == 404


def test_other_user_cannot_diff_runs(client, uploaded_project, auth_headers):
    pid = uploaded_project["id"]
    _run_analysis(client, pid, auth_headers)
    _run_analysis(client, pid, auth_headers)
    runs = client.get(f"/analysis/runs/{pid}", headers=auth_headers).json()
    assert len(runs) >= 2
    a, b = runs[0]["run_id"], runs[1]["run_id"]
    other = _other_headers(client)
    r = client.get(f"/analysis/diff?run_a={a}&run_b={b}", headers=other)
    assert r.status_code == 404


# ── /reports/* ────────────────────────────────────────────────────────────────

def test_other_user_cannot_export_report(client, uploaded_project, auth_headers):
    pid = uploaded_project["id"]
    _run_analysis(client, pid, auth_headers)
    # User B is upgraded so the plan gate doesn't shadow the ownership guard.
    other = _other_headers(client, plan="consultant")
    r = client.get(f"/reports/export/{pid}?format=html", headers=other)
    assert r.status_code == 404
    assert r.json()["detail"] == "Project not found."


def test_other_user_cannot_preview_report(client, uploaded_project, auth_headers):
    pid = uploaded_project["id"]
    _run_analysis(client, pid, auth_headers)
    other = _other_headers(client)
    r = client.get(f"/reports/preview/{pid}", headers=other)
    assert r.status_code == 404


def test_other_user_cannot_get_report_draft(client, uploaded_project):
    pid = uploaded_project["id"]
    other = _other_headers(client)
    r = client.get(f"/reports/draft/{pid}", headers=other)
    assert r.status_code == 404


def test_other_user_cannot_upsert_report_draft(client, uploaded_project):
    pid = uploaded_project["id"]
    other = _other_headers(client)
    r = client.post(
        f"/reports/draft/{pid}",
        json={"title": "leaked", "summary": "hijacked"},
        headers=other,
    )
    assert r.status_code == 404


# ── /charts ───────────────────────────────────────────────────────────────────

def test_other_user_cannot_suggest_charts(client, uploaded_project):
    pid = uploaded_project["id"]
    other = _other_headers(client)
    r = client.post(
        "/charts/suggest",
        json={"project_id": pid},
        headers=other,
    )
    assert r.status_code == 404


# ── /chat ─────────────────────────────────────────────────────────────────────

def test_other_user_cannot_chat_query(client, uploaded_project):
    pid = uploaded_project["id"]
    other = _other_headers(client, plan="consultant")
    r = client.post(
        "/chat/query",
        json={"project_id": pid, "message": "What is the average salary?"},
        headers=other,
    )
    assert r.status_code == 404


# ── /query ────────────────────────────────────────────────────────────────────

def test_other_user_cannot_execute_sql(client, uploaded_project):
    pid = uploaded_project["id"]
    other = _other_headers(client)
    r = client.post(
        "/query/execute",
        json={"project_id": pid, "sql": "SELECT 1"},
        headers=other,
    )
    assert r.status_code == 404


def test_other_user_cannot_get_schema(client, uploaded_project):
    pid = uploaded_project["id"]
    other = _other_headers(client)
    r = client.get(f"/query/schema?project_id={pid}", headers=other)
    assert r.status_code == 404


# ── /pivot ────────────────────────────────────────────────────────────────────

def test_other_user_cannot_run_pivot(client, uploaded_project):
    pid = uploaded_project["id"]
    other = _other_headers(client)
    r = client.post(
        "/pivot/run",
        json={
            "project_id": pid,
            "rows": ["age"],
            "cols": [],
            "values": "salary",
            "aggfunc": "mean",
        },
        headers=other,
    )
    assert r.status_code == 404


def test_other_user_cannot_get_pivot_columns(client, uploaded_project):
    pid = uploaded_project["id"]
    other = _other_headers(client)
    r = client.get(f"/pivot/columns?project_id={pid}", headers=other)
    assert r.status_code == 404


# ── /cohorts ──────────────────────────────────────────────────────────────────

def test_other_user_cannot_run_rfm(client, uploaded_project):
    pid = uploaded_project["id"]
    other = _other_headers(client)
    r = client.post(
        "/cohorts/rfm",
        json={
            "project_id": pid,
            "customer_col": "name",
            "date_col": "age",
            "revenue_col": "salary",
        },
        headers=other,
    )
    assert r.status_code == 404


def test_other_user_cannot_run_retention(client, uploaded_project):
    pid = uploaded_project["id"]
    other = _other_headers(client)
    r = client.post(
        "/cohorts/retention",
        json={
            "project_id": pid,
            "cohort_col": "name",
            "period_col": "age",
            "user_col": "name",
        },
        headers=other,
    )
    assert r.status_code == 404


def test_other_user_cannot_get_cohort_columns(client, uploaded_project):
    pid = uploaded_project["id"]
    other = _other_headers(client)
    r = client.get(f"/cohorts/columns?project_id={pid}", headers=other)
    assert r.status_code == 404


# ── /ml ───────────────────────────────────────────────────────────────────────

def test_other_user_cannot_train_model(client, uploaded_project):
    pid = uploaded_project["id"]
    other = _other_headers(client)
    r = client.post(
        "/ml/train",
        json={"project_id": pid, "target_col": "salary"},
        headers=other,
    )
    assert r.status_code == 404


def test_other_user_cannot_get_model_info(client, uploaded_project):
    pid = uploaded_project["id"]
    other = _other_headers(client)
    r = client.get(f"/ml/model-info/{pid}", headers=other)
    assert r.status_code == 404


def test_other_user_cannot_predict(client, uploaded_project):
    pid = uploaded_project["id"]
    other = _other_headers(client)
    r = client.post(
        f"/ml/predict/{pid}",
        json={"rows": [{"age": 30}]},
        headers=other,
    )
    assert r.status_code == 404


def test_other_user_cannot_get_ml_columns(client, uploaded_project):
    pid = uploaded_project["id"]
    other = _other_headers(client)
    r = client.get(f"/ml/columns?project_id={pid}", headers=other)
    assert r.status_code == 404


# ── /stats ────────────────────────────────────────────────────────────────────

def test_other_user_cannot_run_stat_test(client, uploaded_project):
    pid = uploaded_project["id"]
    other = _other_headers(client)
    r = client.post(
        "/stats/test",
        json={"project_id": pid, "test_type": "ttest", "col_a": "salary"},
        headers=other,
    )
    assert r.status_code == 404


def test_other_user_cannot_get_stats_columns(client, uploaded_project):
    pid = uploaded_project["id"]
    other = _other_headers(client)
    r = client.get(f"/stats/columns?project_id={pid}", headers=other)
    assert r.status_code == 404


# ── /features ─────────────────────────────────────────────────────────────────

def test_other_user_cannot_create_feature(client, uploaded_project):
    pid = uploaded_project["id"]
    other = _other_headers(client)
    r = client.post(
        "/features/create",
        json={"project_id": pid, "name": "x2", "formula": "age * 2"},
        headers=other,
    )
    assert r.status_code == 404


def test_other_user_cannot_suggest_features(client, uploaded_project):
    pid = uploaded_project["id"]
    other = _other_headers(client)
    r = client.get(f"/features/suggest?project_id={pid}", headers=other)
    assert r.status_code == 404


def test_other_user_cannot_list_features(client, uploaded_project):
    pid = uploaded_project["id"]
    other = _other_headers(client)
    r = client.get(f"/features/list?project_id={pid}", headers=other)
    assert r.status_code == 404


# ── /explore ──────────────────────────────────────────────────────────────────

def test_other_user_cannot_explore_timeseries_columns(client, uploaded_project):
    pid = uploaded_project["id"]
    other = _other_headers(client)
    r = client.get(f"/explore/timeseries/columns?project_id={pid}", headers=other)
    assert r.status_code == 404


def test_other_user_cannot_run_timeseries(client, uploaded_project):
    pid = uploaded_project["id"]
    other = _other_headers(client)
    r = client.post(
        "/explore/timeseries/run",
        json={"project_id": pid, "date_col": "age", "value_col": "salary"},
        headers=other,
    )
    assert r.status_code == 404


def test_other_user_cannot_find_duplicates(client, uploaded_project):
    pid = uploaded_project["id"]
    other = _other_headers(client)
    r = client.post(
        "/explore/duplicates",
        json={"project_id": pid},
        headers=other,
    )
    assert r.status_code == 404


def test_other_user_cannot_run_outliers(client, uploaded_project):
    pid = uploaded_project["id"]
    other = _other_headers(client)
    r = client.post(
        "/explore/outliers/run",
        json={"project_id": pid, "column": "salary"},
        headers=other,
    )
    assert r.status_code == 404


def test_other_user_cannot_get_correlations(client, uploaded_project):
    pid = uploaded_project["id"]
    other = _other_headers(client)
    r = client.post(
        "/explore/correlations",
        json={"project_id": pid},
        headers=other,
    )
    assert r.status_code == 404


def test_other_user_cannot_compare_columns(client, uploaded_project):
    pid = uploaded_project["id"]
    other = _other_headers(client)
    r = client.post(
        "/explore/compare-columns/run",
        json={"project_id": pid, "col_a": "salary", "col_b": "age"},
        headers=other,
    )
    assert r.status_code == 404


def test_other_user_cannot_multifile_compare(client, uploaded_project):
    """Even if the attacker only owns *one* of the two referenced projects,
    the compare endpoint must reject the request."""
    pid_a = uploaded_project["id"]
    other = _other_headers(client, plan="consultant")

    # User B owns their own project (pid_b), but tries to compare it to user A's
    r0 = client.post("/projects", json={"name": "B's project"}, headers=other)
    assert r0.status_code == 200
    pid_b = r0.json()["id"]

    r = client.post(
        "/explore/multifile",
        json={"project_id_a": pid_a, "project_id_b": pid_b},
        headers=other,
    )
    assert r.status_code == 404


def test_other_user_cannot_join(client, uploaded_project):
    pid_a = uploaded_project["id"]
    other = _other_headers(client)
    r0 = client.post("/projects", json={"name": "B's project"}, headers=other)
    assert r0.status_code == 200
    pid_b = r0.json()["id"]
    r = client.post(
        "/explore/join/run",
        json={
            "project_id_left": pid_a,
            "project_id_right": pid_b,
            "left_on": "name",
            "right_on": "name",
        },
        headers=other,
    )
    assert r.status_code == 404


def test_other_user_cannot_segment(client, uploaded_project):
    pid = uploaded_project["id"]
    other = _other_headers(client)
    r = client.post(
        "/explore/segments/run",
        json={"project_id": pid, "segment_col": "name", "metric_col": "salary"},
        headers=other,
    )
    assert r.status_code == 404


# ── Owner happy path sanity check ─────────────────────────────────────────────
# (Make sure nothing we hardened broke the existing happy path.)

def test_owner_happy_path_run_then_export(client, uploaded_project, consultant_auth_headers):
    """Sanity check: the project owner can still run analyses and export
    reports after the launch-hardening guards land."""
    pid = uploaded_project["id"]
    run = _run_analysis(client, pid, consultant_auth_headers)
    assert run["project_id"] == pid

    r = client.get(f"/reports/export/{pid}?format=html", headers=consultant_auth_headers)
    assert r.status_code == 200
    assert b"<html" in r.content[:200].lower()
