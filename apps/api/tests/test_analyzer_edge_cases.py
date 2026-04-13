"""
Edge-case tests for app.services.analyzer.

Covers scenarios the happy-path suite misses: single-row data, constant
columns, no datetime for leading indicators, multicollinearity detection,
trend detection, MAX_INSIGHTS cap, and col_a/col_b on correlation insights.
"""
import numpy as np
import pandas as pd
import pytest

from app.services.analyzer import analyze_dataset, get_dataset_summary


class TestAnalyzerEdgeCases:

    # ── Basic robustness ──────────────────────────────────────────────────────

    def test_single_row_no_crash(self):
        df = pd.DataFrame({"a": [1.0], "b": [2.0], "c": ["x"]})
        insights, narrative = analyze_dataset(df)
        assert isinstance(insights, list)
        assert isinstance(narrative, str)
        # No correlation/segment insights possible with 1 row
        assert all(i["type"] in {"data_quality", "constant", "anomaly"}
                   for i in insights if i["type"] not in {"data_quality"})

    def test_two_rows_no_crash(self):
        df = pd.DataFrame({"a": [1.0, 2.0], "b": [3.0, 4.0]})
        insights, narrative = analyze_dataset(df)
        assert isinstance(insights, list)

    def test_all_constant_columns_flagged(self):
        df = pd.DataFrame({
            "x": [5.0] * 30,
            "y": [3.0] * 30,
            "z": [1.0] * 30,
        })
        insights, _ = analyze_dataset(df)
        constant_insights = [i for i in insights if i["type"] == "data_quality"
                              and "constant" in i["title"].lower()]
        assert len(constant_insights) >= 1, "Constant columns should be flagged"

    def test_all_missing_column_flagged(self):
        df = pd.DataFrame({
            "a": [1.0, 2.0, 3.0] * 20,
            "b": [np.nan] * 60,
        })
        insights, _ = analyze_dataset(df)
        missing_insights = [i for i in insights
                            if "missing" in i.get("title", "").lower()]
        assert len(missing_insights) >= 1

    def test_no_numeric_columns_no_crash(self):
        df = pd.DataFrame({
            "cat1": ["a", "b", "c"] * 20,
            "cat2": ["x", "y", "z"] * 20,
        })
        insights, narrative = analyze_dataset(df)
        assert isinstance(insights, list)
        assert isinstance(narrative, str)

    # ── Leading indicators require datetime ───────────────────────────────────

    def test_no_leading_indicator_without_datetime(self):
        rng = np.random.default_rng(0)
        df = pd.DataFrame({
            "a": rng.normal(0, 1, 50),
            "b": rng.normal(0, 1, 50),
        })
        insights, _ = analyze_dataset(df)
        li = [i for i in insights if i["type"] == "leading_indicator"]
        assert len(li) == 0, f"Got leading indicators without datetime column: {li}"

    def test_leading_indicator_eligible_with_datetime(self):
        # With a datetime column present, the function is allowed to run (may or may not find one)
        dates = pd.date_range("2023-01-01", periods=60, freq="D")
        rng = np.random.default_rng(42)
        df = pd.DataFrame({
            "date": dates,
            "a": rng.normal(0, 1, 60),
            "b": rng.normal(0, 1, 60),
        })
        insights, _ = analyze_dataset(df)
        # Should not raise; may or may not contain leading_indicator
        assert isinstance(insights, list)

    # ── Trend detection ───────────────────────────────────────────────────────

    def test_trend_detected_on_monotonic_series(self):
        dates = pd.date_range("2023-01-01", periods=100, freq="D")
        df = pd.DataFrame({
            "date": dates,
            "revenue": np.arange(100, dtype=float) * 10 + 500,  # perfect linear trend
        })
        insights, _ = analyze_dataset(df)
        trend_insights = [i for i in insights if i["type"] == "trend"]
        assert len(trend_insights) >= 1
        assert "revenue" in trend_insights[0]["title"]

    def test_no_trend_on_flat_series(self):
        rng = np.random.default_rng(1)
        df = pd.DataFrame({
            "a": rng.normal(100, 1, 50),  # effectively flat
            "b": rng.normal(200, 1, 50),
        })
        insights, _ = analyze_dataset(df)
        trend_insights = [i for i in insights if i["type"] == "trend"]
        # Should not fire on truly flat data (R² < 0.15 guard)
        assert len(trend_insights) == 0

    # ── Multicollinearity detection ───────────────────────────────────────────

    def test_multicollinearity_detected(self):
        rng = np.random.default_rng(0)
        base = rng.normal(50000, 10000, 100)
        df = pd.DataFrame({
            "salary":     base,
            "hourly_rate": base / 2080 + rng.normal(0, 0.1, 100),  # near-perfect linear transform
            "total_comp":  base * 1.3 + rng.normal(0, 200, 100),   # collinear
            "age":         rng.uniform(25, 65, 100),                 # independent
        })
        insights, _ = analyze_dataset(df)
        vif_insights = [i for i in insights if i["type"] == "multicollinearity"]
        assert len(vif_insights) == 1
        assert "VIF" in vif_insights[0]["evidence"]

    def test_no_multicollinearity_on_independent_columns(self):
        rng = np.random.default_rng(2)
        df = pd.DataFrame({
            "a": rng.normal(0, 1, 100),
            "b": rng.normal(0, 1, 100),
            "c": rng.normal(0, 1, 100),
        })
        insights, _ = analyze_dataset(df)
        vif_insights = [i for i in insights if i["type"] == "multicollinearity"]
        assert len(vif_insights) == 0

    # ── Insight quality guarantees ────────────────────────────────────────────

    def test_correlation_insights_have_col_a_col_b(self):
        rng = np.random.default_rng(5)
        x = rng.normal(0, 1, 80)
        df = pd.DataFrame({
            "revenue": x * 100 + 1000,
            "profit":  x * 60 + rng.normal(0, 5, 80),
            "region":  rng.choice(["A", "B"], 80),
        })
        insights, _ = analyze_dataset(df)
        corr_insights = [i for i in insights if i["type"] == "correlation"]
        for ci in corr_insights:
            assert "col_a" in ci, f"col_a missing from correlation insight: {ci['title']}"
            assert "col_b" in ci, f"col_b missing from correlation insight: {ci['title']}"

    def test_all_insights_have_evidence_with_numbers(self):
        import re
        rng = np.random.default_rng(7)
        x = rng.normal(50, 10, 80)
        df = pd.DataFrame({
            "a": x,
            "b": x * 2 + rng.normal(0, 3, 80),
            "cat": rng.choice(["X", "Y"], 80),
        })
        insights, _ = analyze_dataset(df)
        for ins in insights:
            evidence = ins.get("evidence", "")
            assert re.search(r"\d", evidence), (
                f"Evidence string has no numbers for insight '{ins['title']}': {evidence!r}"
            )

    def test_max_insights_cap_respected(self):
        from app.config import MAX_INSIGHTS
        rng = np.random.default_rng(9)
        n = 200
        # Create a dataset designed to trigger many different insight types
        df = pd.DataFrame({
            f"num_{i}": rng.normal(i * 10, i + 1, n) for i in range(1, 8)
        })
        df["cat"] = rng.choice(["A", "B", "C"], n)
        df["binary"] = rng.choice(["yes", "no"], n, p=[0.2, 0.8])
        insights, _ = analyze_dataset(df)
        assert len(insights) <= MAX_INSIGHTS, (
            f"Too many insights returned: {len(insights)} > {MAX_INSIGHTS}"
        )

    def test_narrative_is_non_empty_string(self):
        rng = np.random.default_rng(11)
        df = pd.DataFrame({"x": rng.normal(0, 1, 30), "y": rng.normal(0, 1, 30)})
        _, narrative = analyze_dataset(df)
        assert isinstance(narrative, str)
        assert len(narrative) > 50

    # ── Dataset summary ───────────────────────────────────────────────────────

    def test_get_dataset_summary_keys(self):
        df = pd.DataFrame({"a": [1.0, 2.0], "b": ["x", "y"]})
        summary = get_dataset_summary(df)
        for key in ("rows", "columns", "numeric_cols", "categorical_cols", "missing_pct"):
            assert key in summary, f"Missing key '{key}' from dataset summary"

    def test_get_dataset_summary_values(self):
        df = pd.DataFrame({
            "num":  [1.0, 2.0, np.nan],
            "cat":  ["a", "b", "c"],
            "date": pd.to_datetime(["2023-01-01", "2023-01-02", "2023-01-03"]),
        })
        s = get_dataset_summary(df)
        assert s["rows"] == 3
        assert s["columns"] == 3
        assert s["numeric_cols"] == 1
        assert s["datetime_cols"] == 1
        assert s["missing_pct"] > 0
