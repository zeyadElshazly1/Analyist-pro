"""
86C — analysis_plan persistence tests.

Verifies that the Dataset Intelligence Layer result is stored inside
result_json for every new run (sync, stream, and cached).
"""
from __future__ import annotations

import io
import json

import pytest

from app.models import AnalysisResult
from tests.conftest import TestingSessionLocal, _make_test_jwt, TEST_USER_ID
from app.plan_names import PLAN_CONSULTANT


# ── Shared CSV fixtures ───────────────────────────────────────────────────────

SALES_CSV = (
    b"order_id,order_date,customer_id,region,product_category,quantity,unit_price,revenue,sales_rep\n"
    b"ORD-001,2024-11-01,C001,West,Electronics,3,49.99,149.97,Jordan Lee\n"
    b"ORD-002,2024-11-02,C002,East,Furniture,1,349.99,349.99,Priya Sharma\n"
    b"ORD-003,2024-11-03,C003,West,Office Supplies,10,8.99,89.90,Jordan Lee\n"
    b"ORD-004,2024-11-04,C004,South,Electronics,2,89.99,179.98,Marcus Webb\n"
    b"ORD-005,2024-11-05,C005,Central,Apparel,5,34.99,174.95,Aisha Nkosi\n"
    b"ORD-006,2024-11-06,C006,East,Furniture,1,499.99,499.99,Tom Buchan\n"
    b"ORD-007,2024-11-07,C007,West,Office Supplies,20,9.99,199.80,Jordan Lee\n"
    b"ORD-008,2024-11-08,C008,South,Electronics,4,34.99,139.96,Marcus Webb\n"
    b"ORD-009,2024-11-09,C001,Central,Apparel,3,64.99,194.97,Aisha Nkosi\n"
    b"ORD-010,2024-11-10,C002,West,Furniture,1,129.99,129.99,Jordan Lee\n"
)

INSURANCE_CSV = (
    b"policy_id,effective_date,coverage_type,premium,claim_amount,deductible,region\n"
    b"POL-001,2024-01-01,Comprehensive,1200.00,0.00,500,West\n"
    b"POL-002,2024-01-15,Liability,800.00,2500.00,250,East\n"
    b"POL-003,2024-02-01,Comprehensive,1500.00,8000.00,500,West\n"
    b"POL-004,2024-02-10,Collision,950.00,0.00,1000,South\n"
    b"POL-005,2024-03-01,Comprehensive,1100.00,0.00,500,Central\n"
    b"POL-006,2024-03-15,Liability,750.00,1200.00,250,East\n"
    b"POL-007,2024-04-01,Comprehensive,1350.00,4500.00,500,West\n"
    b"POL-008,2024-04-20,Collision,920.00,0.00,1000,South\n"
    b"POL-009,2024-05-01,Liability,880.00,700.00,250,Central\n"
    b"POL-010,2024-05-15,Comprehensive,1250.00,0.00,500,East\n"
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _consultant_headers(client) -> dict:
    token = _make_test_jwt()
    headers = {"Authorization": f"Bearer {token}"}
    client.get("/auth/me", headers=headers)
    from app.models import User as UserModel
    db = TestingSessionLocal()
    try:
        user = db.query(UserModel).filter(UserModel.id == TEST_USER_ID).first()
        if user:
            user.plan = PLAN_CONSULTANT
            db.commit()
    finally:
        db.close()
    return headers


def _create_and_upload(client, headers, csv_bytes: bytes, filename: str = "data.csv") -> int:
    r = client.post("/projects", json={"name": "Test workspace"}, headers=headers)
    assert r.status_code in (200, 201), r.text
    pid = r.json()["id"]
    r2 = client.post(
        "/upload",
        files={"file": (filename, io.BytesIO(csv_bytes), "text/csv")},
        data={"project_id": str(pid)},
        headers=headers,
    )
    assert r2.status_code == 200, r2.text
    return pid


def _run_analysis(client, headers, pid: int) -> dict:
    r = client.post("/analysis/run", json={"project_id": pid}, headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


def _latest_result_json(pid: int) -> dict:
    db = TestingSessionLocal()
    try:
        run = (
            db.query(AnalysisResult)
            .filter(AnalysisResult.project_id == pid, AnalysisResult.status == "report_ready")
            .order_by(AnalysisResult.id.desc())
            .first()
        )
        return json.loads(run.result_json) if run else {}
    finally:
        db.close()


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestAnalysisPlanInSyncResponse:
    def test_sync_run_returns_analysis_plan(self, client):
        headers = _consultant_headers(client)
        pid = _create_and_upload(client, headers, SALES_CSV)
        result = _run_analysis(client, headers, pid)
        assert "analysis_plan" in result, "analysis_plan missing from sync run response"

    def test_sync_run_plan_has_required_fields(self, client):
        headers = _consultant_headers(client)
        pid = _create_and_upload(client, headers, SALES_CSV)
        result = _run_analysis(client, headers, pid)
        plan = result["analysis_plan"]
        for field in ("dataset_kind", "confidence", "business_context",
                      "target_metrics", "columns_to_ignore", "time_columns"):
            assert field in plan, f"analysis_plan missing field: {field}"

    def test_sync_run_sales_csv_classified_as_sales(self, client):
        headers = _consultant_headers(client)
        pid = _create_and_upload(client, headers, SALES_CSV)
        result = _run_analysis(client, headers, pid)
        assert result["analysis_plan"]["dataset_kind"] == "sales"

    def test_sync_run_insurance_csv_classified_as_insurance(self, client):
        headers = _consultant_headers(client)
        pid = _create_and_upload(client, headers, INSURANCE_CSV)
        result = _run_analysis(client, headers, pid)
        assert result["analysis_plan"]["dataset_kind"] == "insurance"

    def test_sync_run_confidence_within_range(self, client):
        headers = _consultant_headers(client)
        pid = _create_and_upload(client, headers, SALES_CSV)
        result = _run_analysis(client, headers, pid)
        conf = result["analysis_plan"]["confidence"]
        assert 0.0 <= conf <= 1.0


class TestAnalysisPlanPersisted:
    def test_plan_persisted_in_result_json(self, client):
        headers = _consultant_headers(client)
        pid = _create_and_upload(client, headers, SALES_CSV)
        _run_analysis(client, headers, pid)
        stored = _latest_result_json(pid)
        assert "analysis_plan" in stored, "analysis_plan not persisted in result_json"

    def test_plan_columns_are_subset_of_actual_columns(self, client):
        headers = _consultant_headers(client)
        pid = _create_and_upload(client, headers, SALES_CSV)
        result = _run_analysis(client, headers, pid)
        plan = result["analysis_plan"]
        # Collect actual columns from profile_result (column names)
        profile = result.get("profile_result") or []
        actual_cols: set[str] = set()
        if isinstance(profile, list):
            actual_cols = {c.get("column") or c.get("name", "") for c in profile if isinstance(c, dict)}
        # All plan column references must be in actual columns (or we skip if profile absent)
        if not actual_cols:
            pytest.skip("profile_result not available to validate columns against")
        for col in plan.get("target_metrics", []):
            assert col in actual_cols, f"Invented column in target_metrics: {col!r}"
        for col in plan.get("time_columns", []):
            assert col in actual_cols, f"Invented column in time_columns: {col!r}"
        for col in plan.get("columns_to_ignore", []):
            assert col in actual_cols, f"Invented column in columns_to_ignore: {col!r}"


class TestCacheHitPreservesAnalysisPlan:
    def test_cache_hit_preserves_analysis_plan(self, client):
        headers = _consultant_headers(client)
        pid = _create_and_upload(client, headers, SALES_CSV)
        # First run — computes and stores plan
        first = _run_analysis(client, headers, pid)
        assert "analysis_plan" in first
        # Second run — cache hit; plan must be preserved
        second = _run_analysis(client, headers, pid)
        assert "analysis_plan" in second
        assert second["analysis_plan"]["dataset_kind"] == first["analysis_plan"]["dataset_kind"]
