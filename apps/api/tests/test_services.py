"""
Unit tests for core services: file_loader, cleaner, profiler, analyzer, automl (Phase 0).
These don't require a running server — they test logic directly.
"""
import io
import numpy as np
import pandas as pd
import pytest


# ── file_loader ───────────────────────────────────────────────────────────────

class TestFileLoader:
    def test_load_utf8_csv(self, tmp_path):
        from app.services.file_loader import load_dataset
        f = tmp_path / "test.csv"
        f.write_text("a,b,c\n1,2,3\n4,5,6\n", encoding="utf-8")
        df = load_dataset(str(f))
        assert list(df.columns) == ["a", "b", "c"]
        assert len(df) == 2

    def test_load_latin1_csv(self, tmp_path):
        from app.services.file_loader import load_dataset
        f = tmp_path / "latin.csv"
        content = "name,city\nJosé,México\nMaría,Bogotá\n"
        f.write_bytes(content.encode("latin-1"))
        df = load_dataset(str(f))
        assert len(df) == 2

    def test_load_missing_file(self):
        from app.services.file_loader import load_dataset
        with pytest.raises(FileNotFoundError):
            load_dataset("/tmp/this_does_not_exist_xyz.csv")

    def test_load_xlsx(self, tmp_path):
        import openpyxl
        from app.services.file_loader import load_dataset
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.append(["x", "y"])
        for i in range(5):
            ws.append([i, i * 2])
        p = tmp_path / "sheet.xlsx"
        wb.save(str(p))
        df = load_dataset(str(p))
        assert list(df.columns) == ["x", "y"]
        assert len(df) == 5


# ── cleaner ───────────────────────────────────────────────────────────────────

class TestCleaner:
    def _df(self):
        return pd.DataFrame({
            "name": ["Alice", "Bob", None, "Dave"],
            "age": [30, None, 25, 40],
            "score": [88.5, 92.0, None, 77.0],
        })

    def test_returns_three_values(self):
        from app.services.cleaner import clean_dataset
        result = clean_dataset(self._df())
        assert len(result) == 3

    def test_no_missing_after_clean(self):
        from app.services.cleaner import clean_dataset
        df_clean, _, _ = clean_dataset(self._df())
        assert df_clean.isnull().sum().sum() == 0

    def test_cleaning_report_is_list(self):
        from app.services.cleaner import clean_dataset
        _, report, _ = clean_dataset(self._df())
        assert isinstance(report, list)

    def test_cleaning_summary_has_steps(self):
        from app.services.cleaner import clean_dataset
        _, _, summary = clean_dataset(self._df())
        assert "steps" in summary


# ── profiler ──────────────────────────────────────────────────────────────────

class TestProfiler:
    def _df(self):
        return pd.DataFrame({
            "age": [25, 30, 35, 40, 45],
            "salary": [50000.0, 60000.0, 75000.0, 90000.0, 110000.0],
            "dept": ["Eng", "Mkt", "Eng", "HR", "Eng"],
        })

    def test_profile_keys(self):
        from app.services.profiler import profile_dataset
        profile = profile_dataset(self._df())
        assert isinstance(profile, list)
        assert len(profile) == 3
        for col in profile:
            assert "column" in col
            assert "dtype" in col

    def test_health_score_structure(self):
        from app.services.profiler import calculate_health_score
        hs = calculate_health_score(self._df())
        assert "grade" in hs
        # score is stored under 'total' key
        score_key = "total" if "total" in hs else "score"
        assert 0 <= float(hs[score_key]) <= 100
        assert hs["grade"] in {"A", "B", "C", "D", "F"}

    def test_health_score_perfect_data(self):
        from app.services.profiler import calculate_health_score
        df = pd.DataFrame({"x": range(100), "y": range(100)})
        hs = calculate_health_score(df)
        # Clean data should score well
        score_key = "total" if "total" in hs else "score"
        assert float(hs[score_key]) >= 80


# ── analyzer ──────────────────────────────────────────────────────────────────

class TestAnalyzer:
    def _df(self):
        rng = np.random.default_rng(42)
        n = 50
        x = rng.normal(50, 10, n)
        return pd.DataFrame({
            "revenue": x,
            "ad_spend": x * 2 + rng.normal(0, 5, n),
            "region": rng.choice(["North", "South", "East", "West"], n),
        })

    def test_analyze_returns_tuple(self):
        from app.services.analyzer import analyze_dataset
        result = analyze_dataset(self._df())
        assert len(result) == 2
        insights, narrative = result
        assert isinstance(insights, list)
        assert isinstance(narrative, str)

    def test_insights_have_required_keys(self):
        from app.services.analyzer import analyze_dataset
        insights, _ = analyze_dataset(self._df())
        for ins in insights:
            assert "type" in ins
            assert "finding" in ins

    def test_dataset_summary(self):
        from app.services.analyzer import get_dataset_summary
        summary = get_dataset_summary(self._df())
        assert "rows" in summary
        assert "columns" in summary
        assert summary["rows"] == 50


# ── automl_service ────────────────────────────────────────────────────────────

class TestAutoML:
    def _regression_df(self):
        rng = np.random.default_rng(0)
        n = 60
        x1 = rng.normal(0, 1, n)
        x2 = rng.normal(0, 1, n)
        y = 3 * x1 - 2 * x2 + rng.normal(0, 0.1, n)
        return pd.DataFrame({"x1": x1, "x2": x2, "target": y})

    def _classification_df(self):
        rng = np.random.default_rng(1)
        n = 60
        x1 = rng.normal(0, 1, n)
        x2 = rng.normal(0, 1, n)
        y = (x1 + x2 > 0).astype(int)
        return pd.DataFrame({"x1": x1, "x2": x2, "target": y})

    def test_regression_output_structure(self):
        from app.services.automl_service import train_models
        result = train_models(self._regression_df(), "target")
        assert result["problem_type"] == "regression"
        assert len(result["models"]) > 0
        assert result["best_model"] != ""
        assert "feature_importance" in result
        assert result["n_rows"] == 60

    def test_classification_output_structure(self):
        from app.services.automl_service import train_models
        result = train_models(self._classification_df(), "target")
        assert result["problem_type"] == "classification"
        assert len(result["models"]) > 0
        for m in result["models"]:
            if "error" not in m:
                assert "accuracy" in m or "cv_score" in m

    def test_insufficient_rows_raises(self):
        from app.services.automl_service import train_models
        df = pd.DataFrame({"x": [1, 2, 3], "y": [1, 2, 3]})
        with pytest.raises(ValueError, match="at least 10"):
            train_models(df, "y")

    def test_regression_models_have_cv_score(self):
        from app.services.automl_service import train_models
        result = train_models(self._regression_df(), "target")
        successful = [m for m in result["models"] if "error" not in m]
        assert len(successful) > 0
        for m in successful:
            assert "cv_score" in m

    def test_detect_problem_type(self):
        from app.services.automl_service import detect_problem_type
        df_reg = self._regression_df()
        df_clf = self._classification_df()
        assert detect_problem_type(df_reg, "target") == "regression"
        assert detect_problem_type(df_clf, "target") == "classification"
