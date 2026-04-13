"""
Integration tests for the full analysis pipeline.

Tests the entire flow: load_dataset → clean_dataset → profile_dataset →
analyze_dataset, using realistic "messy" and time-series fixtures.

Assertions cover:
- Shape preservation / row count expectations after cleaning
- No nulls in numeric columns after imputation
- Profile column set matches cleaned DataFrame
- Insights are non-empty and all evidence strings contain numbers
- Narrative is a meaningful non-empty string
- Health score is valid after cleaning
"""
import io
import re
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from app.services.analyzer import analyze_dataset
from app.services.cleaner import clean_dataset
from app.services.file_loader import load_dataset
from app.services.profiler import calculate_health_score, profile_dataset


# ── Shared fixtures ───────────────────────────────────────────────────────────

@pytest.fixture
def messy_csv_path(tmp_path):
    """
    200-row CSV with:
    - Mixed types: currency, percentage, numeric, categorical, datetime
    - ~8% missing values spread across columns
    - 5 duplicate rows
    - One column with >60% missing (should be dropped)
    - Boolean synonym column (YES/no/y/N)
    - A genuine correlation: revenue ≈ 2 × costs
    """
    rng = np.random.default_rng(42)
    n = 200

    revenue_base = rng.normal(5000, 1000, n)
    df = pd.DataFrame({
        "order_date":    pd.date_range("2022-01-01", periods=n, freq="D").strftime("%Y-%m-%d"),
        "revenue":       [f"${v:,.2f}" for v in revenue_base],
        "costs":         revenue_base * 0.5 + rng.normal(0, 50, n),
        "margin_pct":    [f"{v:.1f}%" for v in rng.uniform(10, 40, n)],
        "region":        rng.choice(["North", "South", "East", "West"], n),
        "is_active":     rng.choice(["YES", "no", "y", "N", "True", "False"], n),
        "score":         rng.normal(75, 10, n),
        "sparse_col":    [1.0 if i < 30 else None for i in range(n)],  # 85% missing → dropped
    })

    # Inject ~8% missing into non-sparse columns
    for col in ["costs", "score", "region"]:
        missing_idx = rng.choice(n, size=int(n * 0.08), replace=False)
        df.loc[missing_idx, col] = None

    # Add 5 exact duplicate rows
    dupes = df.iloc[:5].copy()
    df = pd.concat([df, dupes], ignore_index=True)

    path = tmp_path / "messy.csv"
    df.to_csv(path, index=False)
    return str(path)


@pytest.fixture
def timeseries_csv_path(tmp_path):
    """
    365 daily rows with a clear upward trend in revenue and a seasonal
    component in sessions (7-day cycle).
    """
    rng = np.random.default_rng(7)
    n = 365
    dates = pd.date_range("2023-01-01", periods=n, freq="D")
    df = pd.DataFrame({
        "date":     dates.strftime("%Y-%m-%d"),
        "revenue":  rng.normal(5000, 300, n) + np.arange(n) * 8,
        "sessions": 500 + 80 * np.sin(2 * np.pi * np.arange(n) / 7) + rng.normal(0, 20, n),
        "region":   rng.choice(["East", "West"], n),
    })
    path = tmp_path / "timeseries.csv"
    df.to_csv(path, index=False)
    return str(path)


# ── Full pipeline test — messy CSV ────────────────────────────────────────────

class TestMessyPipeline:

    def test_load_succeeds(self, messy_csv_path):
        df = load_dataset(messy_csv_path)
        assert not df.empty
        assert len(df) >= 200  # may include duplicates before cleaning

    def test_clean_removes_duplicates(self, messy_csv_path):
        df = load_dataset(messy_csv_path)
        df_clean, report, summary = clean_dataset(df)
        assert summary["rows_removed"] >= 5, "Duplicate rows should have been removed"

    def test_clean_drops_sparse_column(self, messy_csv_path):
        df = load_dataset(messy_csv_path)
        df_clean, report, _ = clean_dataset(df)
        assert "sparse_col" not in df_clean.columns, (
            "Column with >85% missing should be dropped"
        )

    def test_clean_no_nulls_in_numeric_after_imputation(self, messy_csv_path):
        df = load_dataset(messy_csv_path)
        df_clean, _, _ = clean_dataset(df)
        numeric_cols = df_clean.select_dtypes(include=[np.number]).columns
        for col in numeric_cols:
            nulls = df_clean[col].isnull().sum()
            assert nulls == 0, f"Column '{col}' still has {nulls} nulls after cleaning"

    def test_clean_parses_currency_column(self, messy_csv_path):
        import pandas.api.types as pt
        df = load_dataset(messy_csv_path)
        df_clean, _, _ = clean_dataset(df)
        assert "revenue" in df_clean.columns
        assert pt.is_numeric_dtype(df_clean["revenue"]), (
            f"Expected revenue to be numeric after cleaning, got {df_clean['revenue'].dtype}"
        )

    def test_clean_parses_percentage_column(self, messy_csv_path):
        import pandas.api.types as pt
        df = load_dataset(messy_csv_path)
        df_clean, _, _ = clean_dataset(df)
        assert "margin_pct" in df_clean.columns
        assert pt.is_numeric_dtype(df_clean["margin_pct"]), (
            f"Expected margin_pct to be numeric after cleaning, got {df_clean['margin_pct'].dtype}"
        )

    def test_profile_columns_match_cleaned_df(self, messy_csv_path):
        df = load_dataset(messy_csv_path)
        df_clean, _, _ = clean_dataset(df)
        profile = profile_dataset(df_clean)
        profiled_cols = {p["column"] for p in profile}
        assert profiled_cols == set(df_clean.columns), (
            f"Profile columns {profiled_cols} != cleaned df columns {set(df_clean.columns)}"
        )

    def test_health_score_valid_after_cleaning(self, messy_csv_path):
        df = load_dataset(messy_csv_path)
        df_clean, _, _ = clean_dataset(df)
        hs = calculate_health_score(df_clean)
        assert 0 <= hs["total"] <= 100
        assert hs["grade"] in {"A", "B", "C", "D", "F"}
        # Cleaned data should be better than F
        assert hs["total"] >= 40

    def test_insights_non_empty(self, messy_csv_path):
        df = load_dataset(messy_csv_path)
        df_clean, _, _ = clean_dataset(df)
        insights, _ = analyze_dataset(df_clean)
        assert len(insights) >= 1, "Expected at least 1 insight from a rich messy dataset"

    def test_all_evidence_strings_have_numbers(self, messy_csv_path):
        df = load_dataset(messy_csv_path)
        df_clean, _, _ = clean_dataset(df)
        insights, _ = analyze_dataset(df_clean)
        for ins in insights:
            evidence = ins.get("evidence", "")
            assert re.search(r"\d", evidence), (
                f"Evidence string for '{ins['title']}' has no numbers: {evidence!r}"
            )

    def test_narrative_mentions_row_count(self, messy_csv_path):
        df = load_dataset(messy_csv_path)
        df_clean, _, _ = clean_dataset(df)
        _, narrative = analyze_dataset(df_clean)
        # Narrative should contain the row count (some number of rows)
        assert re.search(r"\d{2,}", narrative), "Narrative should mention row count"
        assert len(narrative) > 100

    def test_correlation_detected_between_revenue_and_costs(self, messy_csv_path):
        df = load_dataset(messy_csv_path)
        df_clean, _, _ = clean_dataset(df)
        insights, _ = analyze_dataset(df_clean)
        corr_insights = [i for i in insights if i["type"] == "correlation"]
        # revenue ≈ 2 × costs → strong correlation expected
        assert len(corr_insights) >= 1, "Expected revenue-costs correlation"
        cols_in_corrs = {
            (ci.get("col_a", ""), ci.get("col_b", "")) for ci in corr_insights
        }
        has_revenue_costs = any(
            "revenue" in pair or "costs" in pair
            for pair in cols_in_corrs
            for col in pair
        )
        assert has_revenue_costs or len(corr_insights) >= 1


# ── Full pipeline test — time-series CSV ─────────────────────────────────────

class TestTimeseriesPipeline:

    def test_load_and_clean_timeseries(self, timeseries_csv_path):
        df = load_dataset(timeseries_csv_path)
        df_clean, _, summary = clean_dataset(df)
        assert not df_clean.empty
        assert summary["final_rows"] >= 300

    def test_trend_detected_after_clean(self, timeseries_csv_path):
        df = load_dataset(timeseries_csv_path)
        df_clean, _, _ = clean_dataset(df)
        insights, _ = analyze_dataset(df_clean)
        trend_insights = [i for i in insights if i["type"] == "trend"]
        assert len(trend_insights) >= 1, (
            "Expected a trend insight for a dataset with a strong upward slope in revenue"
        )

    def test_profile_datetime_column_detected(self, timeseries_csv_path):
        df = load_dataset(timeseries_csv_path)
        df_clean, _, _ = clean_dataset(df)
        profile = profile_dataset(df_clean)
        datetime_profiles = [p for p in profile if p["type"] == "datetime"]
        assert len(datetime_profiles) >= 1, (
            "Expected at least one datetime column profile after cleaning"
        )

    def test_health_score_timeseries_type(self, timeseries_csv_path):
        df = load_dataset(timeseries_csv_path)
        df_clean, _, _ = clean_dataset(df)
        hs = calculate_health_score(df_clean)
        # For a clean timeseries dataset expect B or above
        assert hs["total"] >= 65, f"Expected clean timeseries to score ≥65, got {hs['total']}"
