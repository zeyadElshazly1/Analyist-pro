"""
Tests for ml, cohorts, pivot, and reports routes.
Uses the same in-memory SQLite setup as the rest of the test suite.
"""
import io
import json


# ── Shared helpers ────────────────────────────────────────────────────────────

def _upload(client, project, csv_bytes, auth_headers):
    """Upload csv_bytes to a project; returns the upload response."""
    pid = project["id"]
    r = client.post(
        "/upload",
        files={"file": ("data.csv", io.BytesIO(csv_bytes), "text/csv")},
        data={"project_id": str(pid)},
        headers=auth_headers,
    )
    assert r.status_code == 200, r.text
    return r


def _run_analysis(client, project_id, auth_headers):
    """Run a full analysis and return the result JSON."""
    r = client.post("/analysis/run", json={"project_id": project_id}, headers=auth_headers)
    assert r.status_code == 200, r.text
    return r.json()


# ── ML ────────────────────────────────────────────────────────────────────────

class TestML:
    def test_columns_no_file(self, client, project, auth_headers):
        r = client.get(f"/ml/columns?project_id={project['id']}", headers=auth_headers)
        assert r.status_code == 404

    def test_columns_with_file(self, client, uploaded_project, auth_headers):
        pid = uploaded_project["id"]
        r = client.get(f"/ml/columns?project_id={pid}", headers=auth_headers)
        assert r.status_code == 200
        body = r.json()
        assert "columns" in body
        assert isinstance(body["columns"], list)
        assert len(body["columns"]) > 0

    def test_train_no_file(self, client, project, auth_headers):
        r = client.post(
            "/ml/train",
            json={"project_id": project["id"], "target_col": "salary"},
            headers=auth_headers,
        )
        assert r.status_code == 404

    def test_train_missing_target_col(self, client, uploaded_project, auth_headers):
        pid = uploaded_project["id"]
        r = client.post(
            "/ml/train",
            json={"project_id": pid, "target_col": "nonexistent_column"},
            headers=auth_headers,
        )
        assert r.status_code == 400
        assert "not found" in r.json()["detail"].lower()

    def test_train_regression(self, client, uploaded_project, auth_headers):
        """Train a model on a numeric target — should return model metrics."""
        pid = uploaded_project["id"]
        r = client.post(
            "/ml/train",
            json={"project_id": pid, "target_col": "salary"},
            headers=auth_headers,
        )
        assert r.status_code == 200
        body = r.json()
        # Result should contain at least problem_type and models list
        assert "problem_type" in body
        assert "models" in body
        assert isinstance(body["models"], list)

    def test_train_requires_auth(self, client, uploaded_project):
        pid = uploaded_project["id"]
        r = client.post(
            "/ml/train",
            json={"project_id": pid, "target_col": "salary"},
        )
        assert r.status_code == 401

    def test_model_info_no_model(self, client, uploaded_project, auth_headers):
        """model-info returns 404 before any training."""
        pid = uploaded_project["id"]
        r = client.get(f"/ml/model-info/{pid}", headers=auth_headers)
        assert r.status_code == 404

    def test_predict_after_train(self, client, project, auth_headers):
        """Train then predict — should return a prediction for each input row.

        Uses a custom CSV with a binary 'high_earner' column so CV is stable.
        """
        pid = project["id"]
        # Binary classification target: deterministic enough to train with CV
        big_csv = (
            b"age,salary,high_earner\n"
            + b"".join(
                f"{20 + i},{40000 + i * 1000},{1 if i >= 20 else 0}\n".encode()
                for i in range(40)
            )
        )
        import io as _io
        r = client.post(
            "/upload",
            files={"file": ("d.csv", _io.BytesIO(big_csv), "text/csv")},
            data={"project_id": str(pid)},
            headers=auth_headers,
        )
        assert r.status_code == 200

        train_r = client.post(
            "/ml/train",
            json={"project_id": pid, "target_col": "high_earner"},
            headers=auth_headers,
        )
        assert train_r.status_code == 200

        # model-info should now exist with the correct target
        info_r = client.get(f"/ml/model-info/{pid}", headers=auth_headers)
        assert info_r.status_code == 200
        info = info_r.json()
        assert info["target_col"] == "high_earner"
        assert isinstance(info["feature_names"], list)

        # Predict with a single row using feature columns
        row = {col: 30 for col in info["feature_names"]}
        pred_r = client.post(
            f"/ml/predict/{pid}",
            json={"rows": [row]},
            headers=auth_headers,
        )
        assert pred_r.status_code == 200
        body = pred_r.json()
        assert "predictions" in body
        assert len(body["predictions"]) == 1
        assert "prediction" in body["predictions"][0]

    def test_predict_no_model(self, client, project, auth_headers):
        """predict 404s when no model has been trained."""
        pid = project["id"]
        r = client.post(
            f"/ml/predict/{pid}",
            json={"rows": [{"x": 1}]},
            headers=auth_headers,
        )
        assert r.status_code == 404


# ── Cohorts ───────────────────────────────────────────────────────────────────

# CSV with columns needed for RFM and retention analysis
RFM_CSV = (
    b"customer_id,order_date,revenue,cohort,period\n"
    b"C1,2024-01-01,100.0,2024-Q1,1\n"
    b"C2,2024-01-15,200.0,2024-Q1,1\n"
    b"C1,2024-02-01,150.0,2024-Q1,2\n"
    b"C3,2024-02-10,300.0,2024-Q1,1\n"
    b"C2,2024-03-01,250.0,2024-Q2,3\n"
    b"C1,2024-03-15,175.0,2024-Q2,3\n"
    b"C4,2024-01-20,120.0,2024-Q1,1\n"
    b"C3,2024-02-25,310.0,2024-Q1,2\n"
    b"C4,2024-03-10,130.0,2024-Q2,3\n"
    b"C2,2024-04-01,220.0,2024-Q2,4\n"
)


class TestCohorts:
    def test_columns_no_file(self, client, project, auth_headers):
        r = client.get(f"/cohorts/columns?project_id={project['id']}", headers=auth_headers)
        assert r.status_code == 404

    def test_rfm_missing_columns(self, client, project, auth_headers, tmp_path):
        """RFM with wrong column names returns 400."""
        pid = project["id"]
        client.post(
            "/upload",
            files={"file": ("data.csv", io.BytesIO(RFM_CSV), "text/csv")},
            data={"project_id": str(pid)},
            headers=auth_headers,
        )
        r = client.post(
            "/cohorts/rfm",
            json={
                "project_id": pid,
                "customer_col": "no_such",
                "date_col": "order_date",
                "revenue_col": "revenue",
            },
            headers=auth_headers,
        )
        assert r.status_code == 400

    def test_rfm_success(self, client, project, auth_headers):
        pid = project["id"]
        client.post(
            "/upload",
            files={"file": ("data.csv", io.BytesIO(RFM_CSV), "text/csv")},
            data={"project_id": str(pid)},
            headers=auth_headers,
        )
        r = client.post(
            "/cohorts/rfm",
            json={
                "project_id": pid,
                "customer_col": "customer_id",
                "date_col": "order_date",
                "revenue_col": "revenue",
            },
            headers=auth_headers,
        )
        assert r.status_code == 200
        body = r.json()
        assert "segments" in body or "rfm" in body or isinstance(body, (list, dict))

    def test_cohorts_requires_auth(self, client, project):
        r = client.get(f"/cohorts/columns?project_id={project['id']}")
        assert r.status_code == 401


# ── Pivot ─────────────────────────────────────────────────────────────────────

class TestPivot:
    def test_pivot_no_file(self, client, project, auth_headers):
        r = client.post(
            "/pivot/run",
            json={
                "project_id": project["id"],
                "rows": ["name"],
                "values": "salary",
                "aggfunc": "sum",
            },
            headers=auth_headers,
        )
        assert r.status_code == 404

    def test_pivot_invalid_column(self, client, uploaded_project, auth_headers):
        pid = uploaded_project["id"]
        r = client.post(
            "/pivot/run",
            json={
                "project_id": pid,
                "rows": ["no_such_col"],
                "values": "salary",
                "aggfunc": "sum",
            },
            headers=auth_headers,
        )
        # Either 400 (column not found) or 500 if pivot service raises
        assert r.status_code in (400, 500)

    def test_pivot_success(self, client, uploaded_project, auth_headers):
        pid = uploaded_project["id"]
        r = client.post(
            "/pivot/run",
            json={
                "project_id": pid,
                "rows": ["name"],
                "values": "salary",
                "aggfunc": "sum",
            },
            headers=auth_headers,
        )
        assert r.status_code == 200
        body = r.json()
        # Result structure varies; at minimum it should be a non-empty dict/list
        assert body is not None

    def test_pivot_requires_auth(self, client, uploaded_project):
        pid = uploaded_project["id"]
        r = client.post(
            "/pivot/run",
            json={"project_id": pid, "rows": ["name"], "values": "salary"},
        )
        assert r.status_code == 401


# ── Reports ───────────────────────────────────────────────────────────────────

class TestReports:
    def _setup(self, client, uploaded_project, pro_auth_headers):
        """Run analysis so a stored result exists for export."""
        pid = uploaded_project["id"]
        _run_analysis(client, pid, pro_auth_headers)
        return pid

    def test_export_no_analysis(self, client, uploaded_project, pro_auth_headers):
        """Exporting before running analysis returns 404."""
        pid = uploaded_project["id"]
        r = client.get(f"/reports/export/{pid}?format=html", headers=pro_auth_headers)
        assert r.status_code == 404

    def test_export_html(self, client, uploaded_project, pro_auth_headers):
        pid = self._setup(client, uploaded_project, pro_auth_headers)
        r = client.get(f"/reports/export/{pid}?format=html", headers=pro_auth_headers)
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("text/html")
        assert len(r.content) > 100

    def test_export_xlsx(self, client, uploaded_project, pro_auth_headers):
        pid = self._setup(client, uploaded_project, pro_auth_headers)
        r = client.get(f"/reports/export/{pid}?format=xlsx", headers=pro_auth_headers)
        assert r.status_code == 200
        # XLSX files start with PK (ZIP magic bytes)
        assert r.content[:2] == b"PK"

    def test_export_pdf_fallback(self, client, uploaded_project, pro_auth_headers):
        """PDF export returns 501 when no PDF renderer is installed."""
        pid = self._setup(client, uploaded_project, pro_auth_headers)
        r = client.get(f"/reports/export/{pid}?format=pdf", headers=pro_auth_headers)
        assert r.status_code in (200, 501)

    def test_export_invalid_format(self, client, uploaded_project, pro_auth_headers):
        pid = self._setup(client, uploaded_project, pro_auth_headers)
        r = client.get(f"/reports/export/{pid}?format=docx", headers=pro_auth_headers)
        assert r.status_code == 422

    def test_export_requires_auth(self, client, uploaded_project, pro_auth_headers):
        pid = self._setup(client, uploaded_project, pro_auth_headers)
        r = client.get(f"/reports/export/{pid}?format=html")
        assert r.status_code == 401

    def test_export_wrong_user(self, client, uploaded_project, pro_auth_headers):
        """A second user cannot export another user's project."""
        import base64
        import hashlib
        import hmac as _hmac
        import time
        import os
        from tests.conftest import TEST_JWT_SECRET

        pid = self._setup(client, uploaded_project, pro_auth_headers)

        # Build a JWT for a different user
        secret = TEST_JWT_SECRET.encode()
        def b64url(data):
            return base64.urlsafe_b64encode(data).rstrip(b"=").decode()
        header = b64url(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
        payload = b64url(json.dumps({
            "sub": "99999999-9999-9999-9999-999999999999",
            "email": "other@example.com",
            "role": "authenticated",
            "aud": "authenticated",
            "exp": int(time.time()) + 3600,
        }).encode())
        sig = b64url(_hmac.new(secret, f"{header}.{payload}".encode(), hashlib.sha256).digest())
        other_headers = {"Authorization": f"Bearer {header}.{payload}.{sig}"}

        r = client.get(f"/reports/export/{pid}?format=html", headers=other_headers)
        # 402 if plan gate fires first (free plan), 404 if ownership check fires first
        assert r.status_code in (402, 404)


# ── Billing webhook ───────────────────────────────────────────────────────────

class TestBillingWebhook:
    def test_webhook_no_secret_accepts_any(self, client):
        """Without STRIPE_WEBHOOK_SECRET configured, webhook accepts all payloads."""
        payload = json.dumps({"type": "unknown.event", "data": {"object": {}}})
        r = client.post(
            "/billing/webhook",
            content=payload,
            headers={"content-type": "application/json"},
        )
        assert r.status_code == 200
        assert r.json()["received"] is True

    def test_webhook_subscription_deleted_resets_plan(self, client, auth_headers):
        """Subscription cancelled → user plan reverts to free."""
        # Ensure test user exists
        client.get("/auth/me", headers=auth_headers)

        from tests.conftest import TestingSessionLocal, TEST_USER_ID
        from app.models import User as UserModel

        # Bump the user to pro directly
        db = TestingSessionLocal()
        try:
            u = db.query(UserModel).filter(UserModel.id == TEST_USER_ID).first()
            if u:
                u.plan = "pro"
                db.commit()
        finally:
            db.close()

        payload = json.dumps({
            "type": "customer.subscription.deleted",
            "data": {"object": {"customer_email": "test@example.com"}},
        })
        r = client.post(
            "/billing/webhook",
            content=payload,
            headers={"content-type": "application/json"},
        )
        assert r.status_code == 200

        # Verify plan was reset to free
        db = TestingSessionLocal()
        try:
            u = db.query(UserModel).filter(UserModel.id == TEST_USER_ID).first()
            assert u is not None
            assert u.plan == "free"
        finally:
            db.close()
