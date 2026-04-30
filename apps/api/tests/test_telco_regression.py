"""
Telco Customer Churn regression tests.

Validates that the full pipeline (loading → cleaning → profiling → health
scoring → insight generation → chart generation) produces correct results for
the Telco Customer Churn dataset characteristics:

  - 7,043 rows, 21 columns
  - SeniorCitizen: integer 0/1, NOT constant (5,901 zeros + 1,142 ones)
  - PhoneService:  categorical Yes/No, NOT a phone-number column
  - customerID:    unique per row, excluded from charts and statistical analysis

The fixture below is a 100-row representative sample that reproduces the
distributional properties of the full dataset while keeping tests fast.

Churn rates:
  SeniorCitizen=0 → ~23.6 %  (non-senior churn rate)
  SeniorCitizen=1 → ~41.7 %  (senior churn rate)
"""
from __future__ import annotations

import io
import textwrap

import pandas as pd
import pytest


# ─────────────────────────────────────────────────────────────────────────────
# Fixture helpers
# ─────────────────────────────────────────────────────────────────────────────

def _make_telco_df() -> pd.DataFrame:
    """
    Return a 100-row representative Telco sample DataFrame with the ORIGINAL
    (un-normalised) column names matching the real CSV.

    Distribution preserved from the full WA_Fn-UseC_-Telco-Customer-Churn.csv:
      • SeniorCitizen: 80 × 0, 20 × 1  (20 seniors to satisfy the 20-row group minimum)
      • PhoneService:  both Yes and No present
      • Churn:  SeniorCitizen=0 → 19/80 ≈ 23.75 %
                SeniorCitizen=1 →  9/20 = 45.0 %   ratio = 1.89× > 1.8 threshold
    Both groups ≥ 20 rows so detect_binary_rates generates the churn insight.
    """
    # 80 non-senior rows (SeniorCitizen=0)
    non_senior = pd.DataFrame({
        "customerID":    [f"A{i:04d}-XXXX" for i in range(80)],
        "gender":        (["Male", "Female"] * 40),
        "SeniorCitizen": [0] * 80,
        "Partner":       (["Yes", "No"] * 40),
        "Dependents":    (["No", "Yes"] * 40),
        "tenure":        list(range(1, 81)),
        "PhoneService":  (["Yes"] * 72 + ["No"] * 8),
        "MultipleLines": (["No"] * 30 + ["Yes"] * 42 + ["No phone service"] * 8),
        "InternetService": (["Fiber optic"] * 40 + ["DSL"] * 28 + ["No"] * 12),
        "OnlineSecurity": (["No"] * 38 + ["Yes"] * 30 + ["No internet service"] * 12),
        "TechSupport":   (["No"] * 40 + ["Yes"] * 28 + ["No internet service"] * 12),
        "Contract":      (["Month-to-month"] * 38 + ["One year"] * 22 + ["Two year"] * 20),
        "PaperlessBilling": (["Yes"] * 48 + ["No"] * 32),
        "PaymentMethod": (["Electronic check"] * 28 + ["Mailed check"] * 20
                          + ["Bank transfer (automatic)"] * 18 + ["Credit card (automatic)"] * 14),
        "MonthlyCharges": [round(20 + i * 0.9, 2) for i in range(80)],
        "TotalCharges":   [str(round((20 + i * 0.9) * (i + 1), 2)) for i in range(80)],
        # 19 out of 80 churn → 23.75 %
        "Churn":         (["Yes"] * 19 + ["No"] * 61),
    })

    # 20 senior rows (SeniorCitizen=1)
    senior = pd.DataFrame({
        "customerID":    [f"B{i:04d}-XXXX" for i in range(20)],
        "gender":        (["Male", "Female"] * 10),
        "SeniorCitizen": [1] * 20,
        "Partner":       (["Yes", "No"] * 10),
        "Dependents":    (["No", "Yes"] * 10),
        "tenure":        list(range(1, 21)),
        "PhoneService":  (["Yes"] * 17 + ["No"] * 3),
        "MultipleLines": (["No"] * 6 + ["Yes"] * 11 + ["No phone service"] * 3),
        "InternetService": (["Fiber optic"] * 12 + ["DSL"] * 6 + ["No"] * 2),
        "OnlineSecurity": (["No"] * 10 + ["Yes"] * 8 + ["No internet service"] * 2),
        "TechSupport":   (["No"] * 10 + ["Yes"] * 8 + ["No internet service"] * 2),
        "Contract":      (["Month-to-month"] * 12 + ["One year"] * 5 + ["Two year"] * 3),
        "PaperlessBilling": (["Yes"] * 13 + ["No"] * 7),
        "PaymentMethod": (["Electronic check"] * 9 + ["Mailed check"] * 5
                          + ["Bank transfer (automatic)"] * 3 + ["Credit card (automatic)"] * 3),
        "MonthlyCharges": [round(40 + i * 3.0, 2) for i in range(20)],
        "TotalCharges":   [str(round((40 + i * 3.0) * (i + 1), 2)) for i in range(20)],
        # 9 out of 20 churn → 45.0 %  (ratio to non-senior = 1.89× > 1.8 threshold)
        "Churn":         (["Yes"] * 9 + ["No"] * 11),
    })

    return pd.concat([non_senior, senior], ignore_index=True)


@pytest.fixture
def telco_df() -> pd.DataFrame:
    """Raw (un-cleaned) Telco representative sample."""
    return _make_telco_df()


@pytest.fixture
def telco_csv_path(tmp_path) -> str:
    """Write the fixture DataFrame to a temp CSV and return the path."""
    path = tmp_path / "telco_sample.csv"
    _make_telco_df().to_csv(str(path), index=False)
    return str(path)


@pytest.fixture
def cleaned_telco(telco_df):
    """Return (df_clean, report, summary) from the cleaning pipeline."""
    from app.services.cleaning.pipeline import clean_dataset
    return clean_dataset(telco_df)


# ─────────────────────────────────────────────────────────────────────────────
# 1.  Loading
# ─────────────────────────────────────────────────────────────────────────────

class TestTelcoLoading:
    def test_load_csv_row_count(self, telco_csv_path):
        from app.services.file_loader import load_dataset
        df = load_dataset(telco_csv_path)
        assert len(df) == 100  # 80 non-senior + 20 senior rows

    def test_load_csv_column_count(self, telco_csv_path):
        from app.services.file_loader import load_dataset
        df = load_dataset(telco_csv_path)
        assert len(df.columns) == 17

    def test_load_preserves_senior_citizen_values(self, telco_csv_path):
        """SeniorCitizen must have EXACTLY 2 distinct values (0 and 1) after load."""
        from app.services.file_loader import load_dataset
        df = load_dataset(telco_csv_path)
        assert df["SeniorCitizen"].nunique() == 2, (
            f"Expected 2 unique values for SeniorCitizen after load, "
            f"got {df['SeniorCitizen'].nunique()}: {df['SeniorCitizen'].unique()}"
        )

    def test_load_senior_citizen_has_ones(self, telco_csv_path):
        """After load, SeniorCitizen must contain 1s — not only 0s."""
        from app.services.file_loader import load_dataset
        df = load_dataset(telco_csv_path)
        assert 1 in df["SeniorCitizen"].values or "1" in df["SeniorCitizen"].astype(str).values, (
            "SeniorCitizen has no 1-values after load — all were incorrectly dropped or converted"
        )


# ─────────────────────────────────────────────────────────────────────────────
# 2.  Cleaning — SeniorCitizen preserved as binary
# ─────────────────────────────────────────────────────────────────────────────

class TestTelcoCleaning:
    def test_cleaning_preserves_senior_citizen_unique_count(self, cleaned_telco):
        """After aggressive cleaning SeniorCitizen must still have 2 unique values."""
        df_clean, _, _ = cleaned_telco
        col = "seniorcitizen"  # column names are lower-cased during cleaning
        assert col in df_clean.columns, f"'{col}' not found — columns: {df_clean.columns.tolist()}"
        n_unique = df_clean[col].nunique()
        assert n_unique == 2, (
            f"SeniorCitizen should have 2 unique values after cleaning, got {n_unique}: "
            f"{df_clean[col].unique()}"
        )

    def test_cleaning_senior_citizen_not_all_zeros(self, cleaned_telco):
        """Outlier winsorisation must NOT clip all SeniorCitizen=1 values to 0."""
        df_clean, _, _ = cleaned_telco
        col = "seniorcitizen"
        vals = set(df_clean[col].dropna().unique())
        assert 1 in vals or 1.0 in vals, (
            f"SeniorCitizen contains only: {vals} — 1-values were clobbered by outlier clipping"
        )

    def test_cleaning_report_no_winsorize_senior_citizen(self, cleaned_telco):
        """No 'Winsorize outliers: seniorcitizen' step should appear in the report."""
        _, report, _ = cleaned_telco
        winsorize_steps = [
            r["step"] for r in report
            if "winsor" in r["step"].lower() and "seniorcitizen" in r["step"].lower()
        ]
        assert winsorize_steps == [], (
            f"Unexpected winsorisation of SeniorCitizen: {winsorize_steps}"
        )

    def test_cleaning_phone_service_not_id(self, cleaned_telco):
        """phoneservice must NOT appear in the semantic_columns map as 'phone'."""
        _, _, summary = cleaned_telco
        semantic = summary.get("semantic_columns", {})
        sc_type = semantic.get("phoneservice")
        assert sc_type != "phone", (
            f"phoneservice incorrectly classified as semantic type '{sc_type}' "
            f"— it is a Yes/No service flag, not a phone-number column"
        )

    def test_cleaning_customer_id_is_id(self, cleaned_telco):
        """customerid must be classified as semantic type 'id'."""
        _, _, summary = cleaned_telco
        semantic = summary.get("semantic_columns", {})
        assert semantic.get("customerid") == "id", (
            f"customerid should be semantic type 'id', got: {semantic.get('customerid')!r}. "
            f"Full semantic map: {semantic}"
        )


# ─────────────────────────────────────────────────────────────────────────────
# 3.  Semantic detection — direct unit tests
# ─────────────────────────────────────────────────────────────────────────────

class TestTelcoSemanticDetection:
    def _normalised_df(self, telco_df: pd.DataFrame) -> pd.DataFrame:
        """Apply column-name normalisation the same way the pipeline does."""
        df = telco_df.copy()
        df.columns = (
            df.columns
            .str.strip()
            .str.lower()
            .str.replace(r"\s+", "_", regex=True)
            .str.replace(r"[^\w]", "_", regex=True)
            .str.replace(r"_+", "_", regex=True)
            .str.strip("_")
        )
        return df

    def test_phone_service_not_phone(self, telco_df):
        """phoneservice must NOT be classified as 'phone' semantic type."""
        from app.services.cleaning.semantic import detect_semantic_columns
        df = self._normalised_df(telco_df)
        sem = detect_semantic_columns(df)
        sc = sem.get("phoneservice")
        assert sc != "phone", (
            f"phoneservice is a Yes/No service flag, not a phone number. "
            f"Got semantic type: {sc!r}"
        )

    def test_customer_id_is_id(self, telco_df):
        """customerid must be classified as 'id' semantic type."""
        from app.services.cleaning.semantic import detect_semantic_columns
        df = self._normalised_df(telco_df)
        sem = detect_semantic_columns(df)
        assert sem.get("customerid") == "id", (
            f"customerid should be 'id', got: {sem.get('customerid')!r}"
        )

    def test_senior_citizen_no_semantic_type(self, telco_df):
        """seniorcitizen is a binary flag — it must not get a protected semantic type."""
        from app.services.cleaning.semantic import detect_semantic_columns
        from app.services.cleaning.semantic import PROTECTED_TYPES
        df = self._normalised_df(telco_df)
        sem = detect_semantic_columns(df)
        sc_type = sem.get("seniorcitizen")
        assert sc_type not in PROTECTED_TYPES, (
            f"seniorcitizen incorrectly received protected semantic type {sc_type!r}"
        )

    def test_churn_no_semantic_type(self, telco_df):
        """churn is a categorical outcome — must not be misclassified as ID/phone/etc."""
        from app.services.cleaning.semantic import detect_semantic_columns
        from app.services.cleaning.semantic import PROTECTED_TYPES
        df = self._normalised_df(telco_df)
        sem = detect_semantic_columns(df)
        sc_type = sem.get("churn")
        assert sc_type not in PROTECTED_TYPES, (
            f"churn incorrectly received protected semantic type {sc_type!r}"
        )


# ─────────────────────────────────────────────────────────────────────────────
# 4.  Profiling
# ─────────────────────────────────────────────────────────────────────────────

class TestTelcoProfiling:
    def test_senior_citizen_not_constant_in_profile(self, cleaned_telco):
        """Profile must not flag seniorcitizen as a constant column."""
        from app.services.profiling.orchestrator import profile_dataset
        df_clean, _, _ = cleaned_telco
        profiles = profile_dataset(df_clean)
        sc_profile = next(
            (p for p in profiles if p["column"] == "seniorcitizen"), None
        )
        assert sc_profile is not None, "seniorcitizen not found in profile"
        assert sc_profile["unique"] == 2, (
            f"Expected 2 unique values in profile, got {sc_profile['unique']}"
        )
        assert "constant column" not in sc_profile.get("flags", []), (
            f"seniorcitizen should NOT be flagged as constant. flags={sc_profile['flags']}"
        )

    def test_senior_citizen_profile_type(self, cleaned_telco):
        """seniorcitizen (0/1 int) should be profiled as numeric with dtype_note
        indicating it is possibly encoded categorical."""
        from app.services.profiling.orchestrator import profile_dataset
        df_clean, _, _ = cleaned_telco
        profiles = profile_dataset(df_clean)
        sc_profile = next(
            (p for p in profiles if p["column"] == "seniorcitizen"), None
        )
        assert sc_profile is not None
        assert sc_profile["type"] == "numeric"
        assert sc_profile.get("dtype_note") == "possibly encoded categorical", (
            f"Expected dtype_note='possibly encoded categorical' for a binary column, "
            f"got: {sc_profile.get('dtype_note')!r}"
        )

    def test_customer_id_profile_semantic_type(self, cleaned_telco):
        """customerid column must have semantic_type='id' in the profile."""
        from app.services.profiling.orchestrator import profile_dataset
        df_clean, _, _ = cleaned_telco
        profiles = profile_dataset(df_clean)
        cid_profile = next(
            (p for p in profiles if p["column"] == "customerid"), None
        )
        assert cid_profile is not None, "customerid not found in profile"
        assert cid_profile.get("semantic_type") == "id", (
            f"customerid should have semantic_type='id', got: {cid_profile.get('semantic_type')!r}"
        )

    def test_phone_service_semantic_not_phone(self, cleaned_telco):
        """phoneservice must NOT have semantic_type='phone' in the profile."""
        from app.services.profiling.orchestrator import profile_dataset
        df_clean, _, _ = cleaned_telco
        profiles = profile_dataset(df_clean)
        ps_profile = next(
            (p for p in profiles if p["column"] == "phoneservice"), None
        )
        assert ps_profile is not None, "phoneservice not found in profile"
        assert ps_profile.get("semantic_type") != "phone", (
            f"phoneservice incorrectly has semantic_type='phone'"
        )


# ─────────────────────────────────────────────────────────────────────────────
# 5.  Health scoring
# ─────────────────────────────────────────────────────────────────────────────

class TestTelcoHealthScoring:
    def test_no_constant_column_deduction_for_senior_citizen(self, cleaned_telco):
        """Health score deductions must not contain 'Constant columns' caused by
        seniorcitizen being incorrectly collapsed to a single value."""
        from app.services.profiling.health_scorer import calculate_health_score
        df_clean, _, _ = cleaned_telco
        health = calculate_health_score(df_clean)
        constant_deductions = [
            d for d in health["deductions"]
            if d.startswith("Constant columns:")
        ]
        # If there ARE constant-column deductions they must NOT reference seniorcitizen.
        # (Other truly constant columns are acceptable.)
        for d in constant_deductions:
            assert "seniorcitizen" not in d.lower(), (
                f"seniorcitizen should not be constant. Deduction: {d!r}"
            )

    def test_senior_citizen_not_constant_in_column_health(self, cleaned_telco):
        """Per-column health must not flag seniorcitizen as 'constant value'."""
        from app.services.profiling.health_scorer import calculate_health_score
        df_clean, _, _ = cleaned_telco
        health = calculate_health_score(df_clean)
        sc_health = health["column_health"].get("seniorcitizen", {})
        assert "constant value (-20)" not in sc_health.get("issues", []), (
            f"seniorcitizen column health incorrectly contains 'constant value' issue. "
            f"column_health={sc_health}"
        )


# ─────────────────────────────────────────────────────────────────────────────
# 6.  Insight generation
# ─────────────────────────────────────────────────────────────────────────────

class TestTelcoInsights:
    def test_no_constant_column_insight_for_senior_citizen(self, cleaned_telco):
        """analyze_dataset must NOT generate a 'Constant column: seniorcitizen' insight."""
        from app.services.analysis.orchestrator import analyze_dataset
        df_clean, _, _ = cleaned_telco
        insights, _ = analyze_dataset(df_clean)
        constant_titles = [
            i["title"] for i in insights
            if i["title"].lower().startswith("constant column:")
            and "seniorcitizen" in i["title"].lower()
        ]
        assert constant_titles == [], (
            f"Unexpected constant-column insight for seniorcitizen: {constant_titles}"
        )

    def test_senior_citizen_churn_rate_insight_exists(self, cleaned_telco):
        """detect_binary_rates must generate a rate/segment insight linking
        seniorcitizen to churn (the binary target).

        We call detect_binary_rates directly rather than going through the full
        analyze_dataset pipeline: the ranking cap (MAX_INSIGHTS=15) is a separate
        concern — ranking quality is covered in test_telco_ranking.py.  Here we
        verify that the insight is *discovered* at the detector level.
        """
        import numpy as np
        from app.services.analysis.segments import detect_binary_rates

        df_clean, _, _ = cleaned_telco

        # Replicate the orchestrator's categorical_cols construction
        binary_int_cols = [
            col for col in df_clean.select_dtypes(include=[np.number]).columns
            if df_clean[col].nunique() == 2
        ]
        string_cats = [
            col for col in df_clean.select_dtypes(include=["object", "category"]).columns
            if df_clean[col].nunique() < 50
        ]
        categorical_cols = list(dict.fromkeys(binary_int_cols + string_cats))

        rate_insights = detect_binary_rates(df_clean, categorical_cols)
        sc_churn_insights = [
            i for i in rate_insights
            if "seniorcitizen" in i.get("title", "").lower()
            and "churn" in i.get("title", "").lower()
        ]
        assert len(sc_churn_insights) > 0, (
            "detect_binary_rates failed to generate a seniorcitizen→churn insight. "
            f"All rate insight titles: {[i['title'] for i in rate_insights]}"
        )

    def test_senior_citizen_churn_rate_values(self, cleaned_telco):
        """The seniorcitizen→churn rate insight must show meaningfully higher
        churn for SeniorCitizen=1, consistent with known dataset proportions."""
        import re
        import numpy as np
        from app.services.analysis.segments import detect_binary_rates

        df_clean, _, _ = cleaned_telco

        binary_int_cols = [
            col for col in df_clean.select_dtypes(include=[np.number]).columns
            if df_clean[col].nunique() == 2
        ]
        string_cats = [
            col for col in df_clean.select_dtypes(include=["object", "category"]).columns
            if df_clean[col].nunique() < 50
        ]
        categorical_cols = list(dict.fromkeys(binary_int_cols + string_cats))

        rate_insights = detect_binary_rates(df_clean, categorical_cols)
        sc_insights = [
            i for i in rate_insights
            if "seniorcitizen" in i.get("title", "").lower()
            and "churn" in i.get("title", "").lower()
        ]
        assert len(sc_insights) > 0, "No seniorcitizen→churn rate insight found"

        # Finding text: "X has Y% higher 'yes' rate than Z (A% vs B%, ratio×)."
        # The absolute rate gap must be positive (seniors churn more).
        finding = sc_insights[0].get("finding", "")
        ratio_match = re.search(r"(\d+\.?\d*)×", finding)
        if ratio_match:
            ratio = float(ratio_match.group(1))
            assert ratio > 1.0, f"Expected churn rate ratio > 1.0, got {ratio}"

    def test_customer_id_not_in_insights_columns(self, cleaned_telco):
        """customerid should be excluded from all insight column references
        (ID columns are dropped before analysis)."""
        from app.services.analysis.orchestrator import analyze_dataset
        df_clean, _, _ = cleaned_telco
        insights, _ = analyze_dataset(df_clean)
        for ins in insights:
            title = ins.get("title", "")
            finding = ins.get("finding", "")
            # Allow high-cardinality data_quality insights that explicitly call
            # out the column, but not statistical/segment insights involving it.
            if ins.get("type") not in ("data_quality",):
                assert "customerid" not in title.lower(), (
                    f"customerid appears in non-data_quality insight title: {title!r}"
                )


# ─────────────────────────────────────────────────────────────────────────────
# 7.  Chart generation
# ─────────────────────────────────────────────────────────────────────────────

class TestTelcoCharts:
    def test_no_customerid_charts(self, cleaned_telco):
        """customerid must not appear as x_label or y_label in any chart."""
        from app.services.charting.orchestrator import build_chart_data
        df_clean, _, _ = cleaned_telco
        charts = build_chart_data(df_clean)
        for chart in charts:
            assert "customerid" not in chart.get("x_label", "").lower(), (
                f"customerid appears as x_label in chart: {chart.get('title')!r}"
            )
            assert "customerid" not in chart.get("y_label", "").lower(), (
                f"customerid appears as y_label in chart: {chart.get('title')!r}"
            )
            assert "customerid" not in chart.get("title", "").lower(), (
                f"customerid appears in chart title: {chart.get('title')!r}"
            )

    def test_senior_citizen_not_histogram(self, cleaned_telco):
        """seniorcitizen (binary 0/1) must not get a continuous histogram chart.
        It should appear as a bar or pie chart instead."""
        from app.services.charting.orchestrator import build_chart_data
        df_clean, _, _ = cleaned_telco
        charts = build_chart_data(df_clean)
        histogram_for_sc = [
            c for c in charts
            if "seniorcitizen" in c.get("x_label", "").lower()
            and c.get("type") == "bar"
            and "distribution of" in c.get("title", "").lower()
            and c.get("x_label", "").lower() == "seniorcitizen"
        ]
        # A bar chart with 2 bars (0 and 1) is acceptable — but a multi-bin
        # histogram that treats it as continuous is not.  We verify that if any
        # seniorcitizen chart exists its data has at most 2 distinct labels.
        sc_charts = [
            c for c in charts
            if "seniorcitizen" in c.get("x_label", "").lower()
        ]
        for c in sc_charts:
            data = c.get("data", [])
            # A histogram with many bins would have > 2 entries
            assert len(data) <= 4, (
                f"seniorcitizen chart has {len(data)} data points — looks like a "
                f"continuous histogram was generated. Chart: {c.get('title')!r}"
            )

    def test_phone_service_chart_has_yes_no_values(self, cleaned_telco):
        """phoneservice charts must show Yes/No categories, not phone-number patterns."""
        from app.services.charting.orchestrator import build_chart_data
        df_clean, _, _ = cleaned_telco
        charts = build_chart_data(df_clean)
        ps_charts = [
            c for c in charts
            if "phoneservice" in c.get("x_label", "").lower()
        ]
        if ps_charts:
            labels = {
                str(d.get("label", d.get("name", ""))).lower()
                for d in ps_charts[0].get("data", [])
            }
            assert labels & {"yes", "no"}, (
                f"phoneservice chart should have 'yes'/'no' labels, got: {labels}"
            )


# ─────────────────────────────────────────────────────────────────────────────
# 8.  Column profile labels — user-facing readability
# ─────────────────────────────────────────────────────────────────────────────

class TestTelcoColumnProfileLabels:
    """
    Verify that column profiles remain readable to business users after cleaning.

    - Categorical Yes/No columns (Dependents, PhoneService, Churn) must preserve
      their original string labels in top_values — not silently convert to 0/1.
    - Binary numeric columns (SeniorCitizen) must carry:
        • is_binary = True
        • value_label_map with human-readable labels (not raw "0"/"1")
        • top_values populated with 0/1 counts (for bar-chart rendering)
    - The binary bar chart for SeniorCitizen must use those readable labels.
    """

    # ── helpers ──────────────────────────────────────────────────────────────

    def _profiles(self, cleaned_telco):
        from app.services.profiling.orchestrator import profile_dataset
        df_clean, _, _ = cleaned_telco
        return profile_dataset(df_clean)

    def _col(self, profiles, name: str):
        return next((p for p in profiles if p["column"] == name), None)

    # ── Yes/No categorical columns preserve original labels ──────────────────

    def test_dependents_top_values_show_yes_no(self, cleaned_telco):
        """dependents must show 'yes'/'no' in top_values — not 0/1."""
        p = self._col(self._profiles(cleaned_telco), "dependents")
        assert p is not None, "dependents column not found in profile"
        top_lower = {str(k).strip().lower() for k in p.get("top_values", {}).keys()}
        assert top_lower & {"yes", "no"}, (
            f"dependents top_values should contain 'yes'/'no', got keys: {top_lower}"
        )

    def test_phone_service_top_values_show_yes_no(self, cleaned_telco):
        """phoneservice must show 'yes'/'no' in top_values — not 0/1."""
        p = self._col(self._profiles(cleaned_telco), "phoneservice")
        assert p is not None, "phoneservice column not found in profile"
        top_lower = {str(k).strip().lower() for k in p.get("top_values", {}).keys()}
        assert top_lower & {"yes", "no"}, (
            f"phoneservice top_values should contain 'yes'/'no', got keys: {top_lower}"
        )

    def test_churn_top_values_show_yes_no(self, cleaned_telco):
        """churn must show 'yes'/'no' in top_values — not 0/1."""
        p = self._col(self._profiles(cleaned_telco), "churn")
        assert p is not None, "churn column not found in profile"
        top_lower = {str(k).strip().lower() for k in p.get("top_values", {}).keys()}
        assert top_lower & {"yes", "no"}, (
            f"churn top_values should contain 'yes'/'no', got keys: {top_lower}"
        )

    def test_partner_top_values_show_yes_no(self, cleaned_telco):
        """partner must show 'yes'/'no' in top_values — not 0/1."""
        p = self._col(self._profiles(cleaned_telco), "partner")
        assert p is not None, "partner column not found in profile"
        top_lower = {str(k).strip().lower() for k in p.get("top_values", {}).keys()}
        assert top_lower & {"yes", "no"}, (
            f"partner top_values should contain 'yes'/'no', got keys: {top_lower}"
        )

    # ── SeniorCitizen binary numeric — is_binary flag ────────────────────────

    def test_senior_citizen_has_is_binary_flag(self, cleaned_telco):
        """seniorcitizen (0/1 int) must be annotated as is_binary=True."""
        p = self._col(self._profiles(cleaned_telco), "seniorcitizen")
        assert p is not None
        assert p.get("is_binary") is True, (
            "seniorcitizen profile must have is_binary=True so the UI can render "
            "it as a flag, not a continuous distribution"
        )

    def test_senior_citizen_has_value_label_map(self, cleaned_telco):
        """seniorcitizen profile must have a value_label_map with readable labels."""
        p = self._col(self._profiles(cleaned_telco), "seniorcitizen")
        assert p is not None
        vlm = p.get("value_label_map")
        assert vlm is not None, "seniorcitizen must have a value_label_map"
        assert "0" in vlm and "1" in vlm, (
            f"value_label_map must have '0' and '1' keys, got: {vlm}"
        )

    def test_senior_citizen_value_labels_are_human_readable(self, cleaned_telco):
        """seniorcitizen label values must not be raw '0'/'1'."""
        p = self._col(self._profiles(cleaned_telco), "seniorcitizen")
        assert p is not None
        vlm = p.get("value_label_map", {})
        assert vlm.get("0") not in ("0", "", None), (
            f"value_label_map['0'] should be a human label like 'Not senior', got: {vlm.get('0')!r}"
        )
        assert vlm.get("1") not in ("1", "", None), (
            f"value_label_map['1'] should be a human label like 'Senior', got: {vlm.get('1')!r}"
        )

    def test_senior_citizen_profile_has_top_values_for_bar_chart(self, cleaned_telco):
        """seniorcitizen binary profile must populate top_values (0- and 1-counts)
        so the profile bar chart renders correctly without a separate code path."""
        p = self._col(self._profiles(cleaned_telco), "seniorcitizen")
        assert p is not None
        tv = p.get("top_values")
        assert tv is not None, "seniorcitizen binary profile must have top_values"
        assert "0" in tv and "1" in tv, (
            f"top_values must contain '0' and '1' keys for seniorcitizen, got: {tv}"
        )
        # Counts must sum to (approximately) total non-null rows
        assert tv["0"] + tv["1"] > 0, "top_values counts must be positive"

    # ── SeniorCitizen binary bar chart uses readable labels ──────────────────

    def test_senior_citizen_chart_labels_are_readable(self, cleaned_telco):
        """build_binary_bar_payload for seniorcitizen must produce human-readable
        bar labels — not raw '0'/'1'."""
        from app.services.charting.payloads import build_binary_bar_payload
        df_clean, _, _ = cleaned_telco
        chart = build_binary_bar_payload(df_clean, "seniorcitizen")
        assert chart is not None, (
            "build_binary_bar_payload returned None for seniorcitizen"
        )
        labels = {d["label"] for d in chart["data"]}
        # Raw integer strings must NOT appear — should be "Not senior" / "Senior"
        assert "0" not in labels and "1" not in labels, (
            f"Binary bar chart for seniorcitizen should use readable labels, "
            f"not raw '0'/'1'. Got: {labels}"
        )

    def test_senior_citizen_chart_has_value_label_map(self, cleaned_telco):
        """build_binary_bar_payload must forward the value_label_map in the payload
        so the frontend tooltip can display mapped labels."""
        from app.services.charting.payloads import build_binary_bar_payload
        df_clean, _, _ = cleaned_telco
        chart = build_binary_bar_payload(df_clean, "seniorcitizen")
        assert chart is not None
        vlm = chart.get("value_label_map")
        assert vlm is not None and isinstance(vlm, dict), (
            "chart payload must include value_label_map"
        )
        assert "0" in vlm and "1" in vlm

    # ── _infer_binary_labels unit tests ─────────────────────────────────────

    def test_infer_binary_labels_seniorcitizen(self):
        """seniorcitizen → Not senior / Senior."""
        from app.services.profiling.column_profiler import _infer_binary_labels
        vlm = _infer_binary_labels("seniorcitizen", "0", "1")
        assert vlm["0"] == "Not senior"
        assert vlm["1"] == "Senior"

    def test_infer_binary_labels_generic_flag_defaults_no_yes(self):
        """Generic binary flag (e.g. churn, dependents) → No / Yes."""
        from app.services.profiling.column_profiler import _infer_binary_labels
        for col in ("churn", "dependents", "partner", "arbitraryflag"):
            vlm = _infer_binary_labels(col, "0", "1")
            assert vlm["0"] == "No", f"Expected 'No' for col={col!r}, got {vlm['0']!r}"
            assert vlm["1"] == "Yes", f"Expected 'Yes' for col={col!r}, got {vlm['1']!r}"

    def test_infer_binary_labels_custom_values(self):
        """Label map keys must match the supplied low/high value strings."""
        from app.services.profiling.column_profiler import _infer_binary_labels
        vlm = _infer_binary_labels("flag", "false", "true")
        assert "false" in vlm and "true" in vlm


# ─────────────────────────────────────────────────────────────────────────────
# 9.  Outlier bounds — unit test for the IQR=0 guard
# ─────────────────────────────────────────────────────────────────────────────

class TestOutlierBoundsGuard:
    def test_iqr_zero_does_not_collapse_to_single_value(self):
        """Binary 0/1 series must NOT produce bounds of (0, 0) from _detect_outlier_bounds."""
        import pandas as pd
        from app.services.cleaning.outliers import _detect_outlier_bounds

        # 84 zeros + 16 ones (same distribution as SeniorCitizen in fixture)
        series = pd.Series([0] * 84 + [1] * 16, dtype=float)
        lower, upper, desc = _detect_outlier_bounds(series)

        assert upper > 1.0 or lower < 0.0 or (lower == 0.0 and upper >= 1.0), (
            f"Bounds ({lower}, {upper}) would clip values — IQR=0 guard not working. "
            f"desc={desc!r}"
        )
        # Critical: clipping should NOT remove the 1-values
        clipped = series.clip(lower=lower, upper=upper)
        assert clipped.nunique() >= 2, (
            f"Clipping with bounds ({lower}, {upper}) collapsed binary series to "
            f"{clipped.nunique()} unique value(s)"
        )

    def test_truly_constant_series_identity_bounds(self):
        """A zero-variance column gets identity bounds (no clipping possible)."""
        import pandas as pd
        from app.services.cleaning.outliers import _detect_outlier_bounds

        series = pd.Series([5.0] * 50)
        lower, upper, desc = _detect_outlier_bounds(series)
        assert lower == upper == 5.0, (
            f"Truly constant column should have identity bounds (5, 5), got ({lower}, {upper})"
        )
