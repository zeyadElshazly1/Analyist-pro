"""
Edge-case tests for app.services.cleaner.

Covers scenarios that the original happy-path tests miss:
empty DataFrames, all-null columns, tiny datasets, mixed-format inputs,
pandas 3.x string dtype compatibility, and threshold enforcement.
"""
import numpy as np
import pandas as pd
import pytest

from app.services.cleaner import (
    _safe_knn_k,
    _try_parse_currency,
    _try_parse_percentage,
    clean_dataset,
)


# ── _safe_knn_k ───────────────────────────────────────────────────────────────

class TestSafeKnnK:
    def test_normal_dataset_returns_default(self):
        df = pd.DataFrame({"a": list(range(20)), "b": list(range(20))})
        assert _safe_knn_k(df, "a", default_k=5) == 5

    def test_tiny_dataset_capped(self):
        # Only 3 non-null values in 'a' — k must be <= 2
        df = pd.DataFrame({"a": [1.0, 2.0, np.nan, np.nan, 3.0], "b": range(5)})
        k = _safe_knn_k(df, "a", default_k=5)
        assert k <= 2

    def test_minimum_k_is_one(self):
        # Even if dataset is tiny, k should never be 0
        df = pd.DataFrame({"a": [1.0, np.nan], "b": [2.0, 3.0]})
        k = _safe_knn_k(df, "a", default_k=5)
        assert k >= 1


# ── Currency/percentage threshold enforcement ─────────────────────────────────

class TestCurrencyParsing:
    def test_high_match_rate_converts(self):
        series = pd.Series(["$100.00", "$200.50", "$300.75", "$400.00", "$500.10"])
        parsed, n = _try_parse_currency(series)
        assert parsed is not None
        assert n == 5

    def test_low_match_rate_rejects(self):
        # 60% currency — below 0.95 threshold, should not convert
        series = pd.Series(["$100.00", "$200.00", "$300.00", "notcurrency", "alsono",
                             "$400.00", "nope", "123abc", "nope2", "nope3"])
        parsed, n = _try_parse_currency(series)
        assert parsed is None

    def test_numeric_dtype_skipped(self):
        series = pd.Series([100.0, 200.0, 300.0])
        parsed, n = _try_parse_currency(series)
        assert parsed is None

    def test_percentage_high_match_converts(self):
        series = pd.Series(["45%", "50%", "60%", "70%", "80%"])
        parsed, n = _try_parse_percentage(series)
        assert parsed is not None
        assert n == 5

    def test_percentage_low_match_rejects(self):
        # 50% match — below 0.90 threshold
        series = pd.Series(["45%", "50%", "notpct", "alsonot", "60%",
                             "nope", "nope2", "75%", "nope3", "nope4"])
        parsed, n = _try_parse_percentage(series)
        assert parsed is None


# ── clean_dataset edge cases ──────────────────────────────────────────────────

class TestCleanDatasetEdgeCases:
    def test_empty_dataframe_returns_empty(self):
        df = pd.DataFrame()
        df_clean, report, summary = clean_dataset(df)
        assert df_clean.empty
        assert isinstance(report, list)

    def test_all_null_column_dropped(self):
        df = pd.DataFrame({
            "a": [1.0, 2.0, 3.0],
            "all_null": [None, None, None],
        })
        df_clean, report, _ = clean_dataset(df)
        assert "all_null" not in df_clean.columns
        # Step should appear in report
        step_types = [r["step"] for r in report]
        assert any("empty" in s.lower() for s in step_types)

    def test_all_null_row_dropped(self):
        df = pd.DataFrame({
            "a": [1.0, None, 3.0],
            "b": [4.0, None, 6.0],
        })
        df_clean, _, _ = clean_dataset(df)
        # The all-null row should be removed
        assert len(df_clean) < len(df) or df_clean.isnull().sum().sum() == 0

    def test_duplicate_rows_removed(self):
        df = pd.DataFrame({
            "x": [1, 1, 2, 3],
            "y": [10, 10, 20, 30],
        })
        df_clean, report, _ = clean_dataset(df)
        assert len(df_clean) == 3
        assert any("duplicate" in r["step"].lower() for r in report)

    def test_whitespace_stripped(self):
        df = pd.DataFrame({"name": ["  Alice  ", "Bob", "  Charlie"]})
        df_clean, _, _ = clean_dataset(df)
        assert all(not str(v).startswith(" ") and not str(v).endswith(" ")
                   for v in df_clean["name"].dropna())

    def test_knn_imputation_safe_on_tiny_dataset(self):
        # 4 rows, 2 numeric cols — k=5 would crash without the safety cap
        df = pd.DataFrame({
            "a": [1.0, np.nan, 3.0, 4.0],
            "b": [2.0, 3.0, 4.0, 5.0],
        })
        df_clean, _, _ = clean_dataset(df)
        assert df_clean["a"].isnull().sum() == 0

    def test_column_names_standardized(self):
        df = pd.DataFrame({"First Name": ["Alice"], "AGE (years)": [30]})
        df_clean, _, _ = clean_dataset(df)
        assert "first_name" in df_clean.columns
        # "AGE (years)" → lowercase → replace spaces → strip special chars → collapse underscores → strip trailing
        assert any(c.startswith("age") and "year" in c for c in df_clean.columns)

    def test_pandas3_string_dtype_parsed(self):
        """Columns with pandas 3.x 'str' dtype (not 'object') must still be parsed."""
        df = pd.DataFrame({
            "revenue": pd.array(["$1,000.00", "$2,000.00", "$3,000.00",
                                  "$4,000.00", "$5,000.00"], dtype="string"),
        })
        df_clean, report, _ = clean_dataset(df)
        import pandas.api.types as pt
        assert pt.is_numeric_dtype(df_clean["revenue"]), (
            "Currency column with pandas 'string' dtype was not parsed"
        )

    def test_boolean_synonyms_standardized(self):
        df = pd.DataFrame({"active": ["YES", "no", "y", "N", "True", "FALSE"]})
        df_clean, report, _ = clean_dataset(df)
        values = set(df_clean["active"].dropna().str.lower().unique())
        assert values.issubset({"yes", "no"}), f"Unexpected values after bool standardization: {values}"

    def test_single_column_dataframe(self):
        df = pd.DataFrame({"value": [1.0, 2.0, np.nan, 4.0, 5.0]})
        df_clean, _, _ = clean_dataset(df)
        assert len(df_clean.columns) >= 1
        assert df_clean["value"].isnull().sum() == 0
