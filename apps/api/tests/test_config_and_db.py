"""
Tests for config constants and database/ORM layer (Phase 0).
"""
import pytest


class TestConfig:
    def test_max_upload_bytes(self):
        from app.config import MAX_UPLOAD_BYTES
        assert MAX_UPLOAD_BYTES == 100 * 1024 * 1024

    def test_allowed_extensions(self):
        from app.config import ALLOWED_EXTENSIONS
        assert ".csv" in ALLOWED_EXTENSIONS
        assert ".xlsx" in ALLOWED_EXTENSIONS
        assert ".xls" in ALLOWED_EXTENSIONS
        assert ".pdf" not in ALLOWED_EXTENSIONS

    def test_zscore_threshold_positive(self):
        from app.config import ZSCORE_THRESHOLD
        assert ZSCORE_THRESHOLD > 0

    def test_automl_n_estimators(self):
        from app.config import AUTOML_N_ESTIMATORS
        assert AUTOML_N_ESTIMATORS > 0

    def test_max_insights(self):
        from app.config import MAX_INSIGHTS
        assert MAX_INSIGHTS > 0


class TestModels:
    def test_project_to_dict(self):
        from app.models import Project
        p = Project(id=1, name="Test", status="created")
        d = p.to_dict()
        assert d["id"] == 1
        assert d["name"] == "Test"
        assert d["status"] == "created"

    def test_analysis_result_round_trip(self):
        from app.models import AnalysisResult
        import json
        payload = {"score": 42, "insights": ["a", "b"]}
        ar = AnalysisResult(project_id=1, result_json=json.dumps(payload))
        assert ar.result == payload

    def test_analysis_result_setter(self):
        from app.models import AnalysisResult
        ar = AnalysisResult(project_id=1, result_json="{}")
        ar.result = {"key": "value"}
        import json
        assert json.loads(ar.result_json) == {"key": "value"}

    def test_project_file_to_dict(self):
        from app.models import ProjectFile
        pf = ProjectFile(
            id=5,
            project_id=1,
            filename="data.csv",
            stored_path="/uploads/data.csv",
            size_bytes=1024,
        )
        d = pf.to_dict()
        assert d["filename"] == "data.csv"
        assert d["size_bytes"] == 1024
