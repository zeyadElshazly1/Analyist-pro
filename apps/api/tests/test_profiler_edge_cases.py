"""
Edge-case tests for app.services.profiler.

Covers zero-row DataFrames, single-column/row inputs, all-constant columns,
distribution fitting correctness, pattern detection weak/strong threshold,
and health score stability.
"""
import numpy as np
import pandas as pd
import pytest

from app.services.profiler import (
    _detect_pattern,
    _fit_distribution,
    calculate_health_score,
    profile_dataset,
)


# ── _fit_distribution ─────────────────────────────────────────────────────────

class TestFitDistribution:
    def test_normal_data_fits_normal(self):
        rng = np.random.default_rng(0)
        series = pd.Series(rng.normal(100, 15, 500))
        result = _fit_distribution(series)
        assert result is not None
        assert result["best_fit"] == "normal"
        assert result["transform_hint"] is None  # no transform needed for normal

    def test_lognormal_data_fits_lognormal(self):
        rng = np.random.default_rng(1)
        series = pd.Series(np.exp(rng.normal(5, 0.8, 500)))
        result = _fit_distribution(series)
        assert result is not None
        assert result["best_fit"] == "lognormal"
        assert result["transform_hint"] is not None
        assert "log" in result["transform_hint"].lower()

    def test_too_small_returns_none(self):
        series = pd.Series([1.0, 2.0, 3.0])
        result = _fit_distribution(series)
        assert result is None

    def test_constant_series_returns_none(self):
        series = pd.Series([5.0] * 50)
        result = _fit_distribution(series)
        assert result is None

    def test_all_fits_key_present(self):
        rng = np.random.default_rng(2)
        series = pd.Series(rng.normal(0, 1, 100))
        result = _fit_distribution(series)
        assert result is not None
        assert isinstance(result["all_fits"], dict)
        assert len(result["all_fits"]) >= 1

    def test_ks_statistic_in_range(self):
        rng = np.random.default_rng(3)
        series = pd.Series(rng.normal(50, 10, 200))
        result = _fit_distribution(series)
        assert result is not None
        assert 0.0 <= result["ks_statistic"] <= 1.0


# ── _detect_pattern ───────────────────────────────────────────────────────────

class TestDetectPattern:
    def test_strong_pattern_all_email(self):
        series = pd.Series([f"user{i}@example.com" for i in range(50)])
        result = _detect_pattern(series)
        assert result is not None
        assert result["pattern"] == "email"
        assert result["pattern_strength"] == "strong"
        assert result["compliance_pct"] == 100.0

    def test_weak_pattern_mixed_email(self):
        emails = [f"user{i}@example.com" for i in range(6)]
        non_emails = ["notanemail", "alsonot", "nope", "nope2"]
        series = pd.Series(emails + non_emails)
        result = _detect_pattern(series)
        assert result is not None
        assert result["pattern_strength"] == "weak"

    def test_low_match_returns_none(self):
        series = pd.Series(["notanemail"] * 7 + ["user@example.com"] * 3)
        result = _detect_pattern(series)
        # 30% compliance — below 50% threshold
        assert result is None

    def test_empty_series_returns_none(self):
        series = pd.Series([], dtype=object)
        result = _detect_pattern(series)
        assert result is None

    def test_all_null_returns_none(self):
        series = pd.Series([None, None, None])
        result = _detect_pattern(series)
        assert result is None

    def test_malformed_count_correct(self):
        good = [f"user{i}@domain.com" for i in range(9)]
        bad = ["notanemail"]
        series = pd.Series(good + bad)
        result = _detect_pattern(series)
        assert result is not None
        assert result["malformed_count"] >= 1


# ── profile_dataset edge cases ────────────────────────────────────────────────

class TestProfileDatasetEdgeCases:
    def test_empty_dataframe_returns_empty_list(self):
        df = pd.DataFrame()
        profile = profile_dataset(df)
        assert profile == []

    def test_single_column(self):
        df = pd.DataFrame({"value": [1.0, 2.0, 3.0, 4.0, 5.0]})
        profile = profile_dataset(df)
        assert len(profile) == 1
        assert profile[0]["column"] == "value"
        assert profile[0]["type"] == "numeric"

    def test_single_row(self):
        df = pd.DataFrame({"a": [42.0], "b": ["hello"]})
        profile = profile_dataset(df)
        assert len(profile) == 2

    def test_all_null_column_profiled(self):
        df = pd.DataFrame({"good": [1.0, 2.0, 3.0], "bad": [None, None, None]})
        profile = profile_dataset(df)
        col_names = [p["column"] for p in profile]
        # all-null columns stay in the profile so user can see them
        assert "bad" in col_names
        bad_profile = next(p for p in profile if p["column"] == "bad")
        assert bad_profile["missing_pct"] == 100.0

    def test_constant_column_flagged(self):
        df = pd.DataFrame({"const": [7.0] * 20, "varied": list(range(20))})
        profile = profile_dataset(df)
        const_p = next(p for p in profile if p["column"] == "const")
        assert "constant column" in const_p["flags"]

    def test_numeric_profile_has_distribution_fit(self):
        rng = np.random.default_rng(0)
        df = pd.DataFrame({"x": rng.normal(50, 10, 100)})
        profile = profile_dataset(df)
        assert profile[0]["distribution_fit"] is not None
        assert "best_fit" in profile[0]["distribution_fit"]

    def test_datetime_column_profiled(self):
        df = pd.DataFrame({
            "dt": pd.date_range("2023-01-01", periods=30, freq="D"),
            "val": range(30),
        })
        profile = profile_dataset(df)
        dt_p = next(p for p in profile if p["column"] == "dt")
        assert dt_p["type"] == "datetime"
        assert "inferred_frequency" in dt_p

    def test_categorical_column_has_top_values(self):
        df = pd.DataFrame({"cat": ["a", "b", "a", "c", "a", "b"] * 5})
        profile = profile_dataset(df)
        cat_p = profile[0]
        assert cat_p["type"] == "categorical"
        assert "top_values" in cat_p
        assert "a" in cat_p["top_values"]

    def test_high_missing_flagged(self):
        df = pd.DataFrame({
            "sparse": [1.0] + [None] * 39,  # 97.5% missing
            "complete": list(range(40)),
        })
        profile = profile_dataset(df)
        sparse_p = next(p for p in profile if p["column"] == "sparse")
        assert any("missing" in f.lower() for f in sparse_p["flags"])


# ── calculate_health_score edge cases ─────────────────────────────────────────

class TestHealthScoreEdgeCases:
    def test_single_row_no_crash(self):
        df = pd.DataFrame({"a": [1.0], "b": [2.0]})
        hs = calculate_health_score(df)
        assert 0 <= hs["total"] <= 100
        assert hs["grade"] in {"A", "B", "C", "D", "F"}

    def test_all_missing_scores_low(self):
        df = pd.DataFrame({"a": [np.nan] * 20, "b": [np.nan] * 20})
        hs = calculate_health_score(df)
        assert hs["total"] < 50, f"Expected low score for all-missing data, got {hs['total']}"

    def test_perfect_data_scores_high(self):
        df = pd.DataFrame({"x": list(range(100)), "y": list(range(100, 200))})
        hs = calculate_health_score(df)
        assert hs["total"] >= 80, f"Expected high score for clean data, got {hs['total']}"

    def test_many_duplicates_penalised(self):
        df = pd.DataFrame({"a": [1.0, 1.0] * 50, "b": [2.0, 2.0] * 50})
        hs = calculate_health_score(df)
        perfect = pd.DataFrame({"a": range(100), "b": range(100, 200)})
        hs_perfect = calculate_health_score(perfect)
        assert hs["total"] < hs_perfect["total"]

    def test_breakdown_sums_to_total(self):
        rng = np.random.default_rng(0)
        df = pd.DataFrame({
            "a": rng.normal(0, 1, 50),
            "b": rng.choice(["x", "y"], 50),
        })
        hs = calculate_health_score(df)
        breakdown_sum = round(sum(hs["breakdown"].values()), 1)
        assert abs(breakdown_sum - hs["total"]) < 0.5, (
            f"breakdown sum {breakdown_sum} != total {hs['total']}"
        )

    def test_health_result_has_required_keys(self):
        df = pd.DataFrame({"x": [1.0, 2.0, 3.0]})
        hs = calculate_health_score(df)
        for key in ("total", "grade", "label", "breakdown", "deductions",
                    "column_health", "business_impact", "fix_suggestions"):
            assert key in hs, f"Missing key '{key}' from health score result"
