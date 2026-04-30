"""
Chart quality regression tests.

Verifies that chart generation:
  1. Suppresses ID / high-cardinality columns from all chart types.
  2. Routes binary numeric columns (0/1 flags) to build_binary_bar_payload,
     never to the continuous-histogram path.
  3. Produces statistically correct narration — binary flag columns never
     receive normality / skewness / distribution-fit language.
  4. Applies the correct thresholds:
       unique_ratio >= 0.9  → ID column (excluded)
       unique_count == nrows → absolute ID (excluded)
       semantic type in ID set → excluded via semantic map
  5. customerID and SeniorCitizen specific scenarios.
"""
from __future__ import annotations

import pandas as pd
import pytest


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def basic_df() -> pd.DataFrame:
    """Small DataFrame with a numeric ID, binary flag, continuous column, and string cat."""
    import numpy as np
    rng = np.random.default_rng(42)
    n = 100
    return pd.DataFrame({
        "order_id":      list(range(n)),                          # numeric, 100% unique
        "seniorcitizen": ([0] * 80 + [1] * 20),                  # binary int flag
        "monthly_charges": rng.normal(65, 25, n).clip(10, 150).tolist(),  # continuous
        "contract":      (["Month-to-month"] * 50 + ["One year"] * 30 + ["Two year"] * 20),
    })


@pytest.fixture
def telco_like_df() -> pd.DataFrame:
    """100-row DataFrame mimicking Telco Customer Churn column structure."""
    n = 100
    return pd.DataFrame({
        "customerid":      [f"AB{i:04d}-XXXX" for i in range(n)],  # string, 100% unique
        "seniorcitizen":   ([0] * 80 + [1] * 20),
        "phoneservice":    (["Yes"] * 85 + ["No"] * 15),
        "tenure":          list(range(1, n + 1)),
        "monthlycharges":  [round(20 + i * 0.8, 2) for i in range(n)],
        "churn":           (["Yes"] * 27 + ["No"] * 73),
    })


# ─────────────────────────────────────────────────────────────────────────────
# 1.  _is_id_col — unit tests for the ID-column detector
# ─────────────────────────────────────────────────────────────────────────────

class TestIsIdCol:
    def test_fully_unique_string_col_is_id(self):
        from app.services.charting.orchestrator import _is_id_col
        df = pd.DataFrame({"id": [f"X{i}" for i in range(50)]})
        assert _is_id_col("id", df) is True

    def test_fully_unique_integer_col_is_id(self):
        from app.services.charting.orchestrator import _is_id_col
        df = pd.DataFrame({"order_id": list(range(100))})
        assert _is_id_col("order_id", df) is True

    def test_90pct_unique_col_is_id(self):
        from app.services.charting.orchestrator import _is_id_col
        # 93 unique out of 100 rows → 93% unique
        vals = list(range(93)) + [0, 1, 2, 3, 4, 5, 6]
        df = pd.DataFrame({"near_id": vals})
        assert _is_id_col("near_id", df) is True

    def test_binary_col_is_not_id(self):
        from app.services.charting.orchestrator import _is_id_col
        df = pd.DataFrame({"seniorcitizen": [0] * 80 + [1] * 20})
        assert _is_id_col("seniorcitizen", df) is False

    def test_low_cardinality_categorical_is_not_id(self):
        from app.services.charting.orchestrator import _is_id_col
        df = pd.DataFrame({"contract": ["Month-to-month", "One year", "Two year"] * 30})
        assert _is_id_col("contract", df) is False

    def test_semantic_type_id_overrides_cardinality(self):
        """A column with semantic_type='id' is always excluded even at low cardinality."""
        from app.services.charting.orchestrator import _is_id_col
        df = pd.DataFrame({"user_ref": list(range(10))})
        semantic_map = {"user_ref": "id"}
        assert _is_id_col("user_ref", df, semantic_map) is True

    def test_semantic_type_phone_is_excluded(self):
        from app.services.charting.orchestrator import _is_id_col
        df = pd.DataFrame({"contact_number": [f"555-{i:04d}" for i in range(50)]})
        semantic_map = {"contact_number": "phone"}
        assert _is_id_col("contact_number", df, semantic_map) is True

    def test_below_threshold_not_id(self):
        """80% unique with <= 20 distinct values should NOT be treated as ID."""
        from app.services.charting.orchestrator import _is_id_col
        # 16 unique out of 20 rows = 80% < 90%
        df = pd.DataFrame({"col": list(range(16)) + [0, 0, 0, 0]})
        assert _is_id_col("col", df) is False

    def test_small_dataset_not_flagged_as_id(self):
        """<= 20 unique values should not trigger ID detection even at 100% unique."""
        from app.services.charting.orchestrator import _is_id_col
        df = pd.DataFrame({"tiny": list(range(15))})
        assert _is_id_col("tiny", df) is False


# ─────────────────────────────────────────────────────────────────────────────
# 2.  build_histogram_payload — binary guard
# ─────────────────────────────────────────────────────────────────────────────

class TestHistogramBinaryGuard:
    def test_binary_column_returns_none(self):
        """build_histogram_payload must return None for a 0/1 binary column."""
        from app.services.charting.payloads import build_histogram_payload
        df = pd.DataFrame({"seniorcitizen": [0] * 80 + [1] * 20})
        result = build_histogram_payload(df, "seniorcitizen", is_first_chart=False)
        assert result is None, (
            "A binary column (0/1) must not produce a continuous histogram. "
            f"Got: {result}"
        )

    def test_continuous_column_returns_payload(self):
        """build_histogram_payload must still work for genuine continuous columns."""
        from app.services.charting.payloads import build_histogram_payload
        df = pd.DataFrame({"charges": [round(20 + i * 0.8, 2) for i in range(100)]})
        result = build_histogram_payload(df, "charges", is_first_chart=True)
        assert result is not None
        assert result["type"] == "bar"
        assert "Distribution of charges" in result["title"]

    def test_normality_badge_absent_for_binary(self):
        """After the guard, no normality badge is ever attached to a binary payload."""
        from app.services.charting.payloads import build_binary_bar_payload
        df = pd.DataFrame({"flag": [0] * 80 + [1] * 20})
        result = build_binary_bar_payload(df, "flag")
        assert result is not None
        assert "significance_badge" not in result, (
            "Binary bar chart must not carry a significance_badge field"
        )
        assert "normality_p" not in result, (
            "Binary bar chart must not carry a normality_p field"
        )


# ─────────────────────────────────────────────────────────────────────────────
# 3.  build_binary_bar_payload — structure and narration
# ─────────────────────────────────────────────────────────────────────────────

class TestBinaryBarPayload:
    def test_returns_two_bars(self):
        from app.services.charting.payloads import build_binary_bar_payload
        df = pd.DataFrame({"seniorcitizen": [0] * 80 + [1] * 20})
        p = build_binary_bar_payload(df, "seniorcitizen")
        assert p is not None
        assert len(p["data"]) == 2, f"Expected 2 bars, got {len(p['data'])}"

    def test_labels_are_zero_and_one(self):
        from app.services.charting.payloads import build_binary_bar_payload
        df = pd.DataFrame({"flag": [0] * 80 + [1] * 20})
        p = build_binary_bar_payload(df, "flag")
        labels = {d["label"] for d in p["data"]}
        assert labels == {"0", "1"}, f"Expected labels {{'0','1'}}, got {labels}"

    def test_is_binary_flag_set(self):
        from app.services.charting.payloads import build_binary_bar_payload
        df = pd.DataFrame({"seniorcitizen": [0] * 80 + [1] * 20})
        p = build_binary_bar_payload(df, "seniorcitizen")
        assert p.get("is_binary") is True, "is_binary flag must be True for binary bar chart"

    def test_counts_are_correct(self):
        from app.services.charting.payloads import build_binary_bar_payload
        df = pd.DataFrame({"x": [0] * 80 + [1] * 20})
        p = build_binary_bar_payload(df, "x")
        counts = {d["label"]: d["value"] for d in p["data"]}
        assert counts["0"] == 80
        assert counts["1"] == 20

    def test_pct_sums_to_100(self):
        from app.services.charting.payloads import build_binary_bar_payload
        df = pd.DataFrame({"x": [0] * 80 + [1] * 20})
        p = build_binary_bar_payload(df, "x")
        total_pct = sum(d["pct"] for d in p["data"])
        assert abs(total_pct - 100.0) < 0.2, f"Percentages should sum to ~100, got {total_pct}"

    def test_returns_none_for_non_binary(self):
        """Must return None if the column has more than 2 distinct values."""
        from app.services.charting.payloads import build_binary_bar_payload
        df = pd.DataFrame({"x": [0, 1, 2, 3] * 25})
        assert build_binary_bar_payload(df, "x") is None

    def test_returns_none_for_constant_column(self):
        from app.services.charting.payloads import build_binary_bar_payload
        df = pd.DataFrame({"x": [0] * 100})
        assert build_binary_bar_payload(df, "x") is None


# ─────────────────────────────────────────────────────────────────────────────
# 4.  _narrate_binary — language correctness
# ─────────────────────────────────────────────────────────────────────────────

class TestNarrateBinary:
    # Phrases that must NEVER appear in binary narration
    FORBIDDEN = [
        "normal distribution",
        "normally distributed",
        "parametric",
        "log transform",
        "skew",
        "shapiro",
        "jarque",
        "kurtosis",
        "mean ",       # mean as a statistic (not "meaning")
        "median",
        "standard deviation",
    ]

    def test_no_normality_language(self):
        from app.services.charting.narrator import _narrate_binary
        narration = _narrate_binary("seniorcitizen", n_zero=80, n_one=20, total=100)
        low = narration.lower()
        for phrase in self.FORBIDDEN:
            assert phrase not in low, (
                f"Forbidden phrase '{phrase}' found in binary narration:\n{narration}"
            )

    def test_mentions_binary_condition(self):
        from app.services.charting.narrator import _narrate_binary
        narration = _narrate_binary("seniorcitizen", n_zero=80, n_one=20, total=100)
        low = narration.lower()
        assert any(kw in low for kw in ["binary", "flag", "yes/no", "0", "1"]), (
            "Binary narration should mention binary/flag/yes-no language"
        )

    def test_class_imbalance_note_for_skewed(self):
        """When minority class < 20%, narration should mention imbalance."""
        from app.services.charting.narrator import _narrate_binary
        narration = _narrate_binary("rare_flag", n_zero=95, n_one=5, total=100)
        assert "imbalance" in narration.lower() or "minority" in narration.lower(), (
            "Heavily skewed binary columns should trigger an imbalance warning"
        )

    def test_balanced_note_for_even_split(self):
        """When classes are roughly equal, narration should be positive."""
        from app.services.charting.narrator import _narrate_binary
        narration = _narrate_binary("even_flag", n_zero=50, n_one=50, total=100)
        low = narration.lower()
        assert any(kw in low for kw in ["balanced", "balance", "favourable", "reasonable"]), (
            "Balanced binary column should have a positive balance note"
        )

    def test_correct_counts_in_narration(self):
        from app.services.charting.narrator import _narrate_binary
        narration = _narrate_binary("seniorcitizen", n_zero=80, n_one=20, total=100)
        assert "20" in narration and "80" in narration, (
            f"Narration should include actual counts 20 and 80. Got:\n{narration}"
        )

    def test_insight_field_no_normality_language(self):
        """The full build_binary_bar_payload insight must also be free of
        normality language (integration test of narrator + payload)."""
        from app.services.charting.payloads import build_binary_bar_payload
        df = pd.DataFrame({"seniorcitizen": [0] * 80 + [1] * 20})
        p = build_binary_bar_payload(df, "seniorcitizen")
        assert p is not None
        insight = p.get("insight", "")
        for phrase in self.FORBIDDEN:
            assert phrase not in insight.lower(), (
                f"Forbidden phrase '{phrase}' found in binary bar insight:\n{insight}"
            )


# ─────────────────────────────────────────────────────────────────────────────
# 5.  build_chart_data — integration: customerID and SeniorCitizen
# ─────────────────────────────────────────────────────────────────────────────

class TestBuildChartDataQuality:
    def test_no_chart_for_string_id_column(self, telco_like_df):
        """customerid (100% unique strings) must not appear in any chart."""
        from app.services.charting.orchestrator import build_chart_data
        charts = build_chart_data(telco_like_df)
        for c in charts:
            for field in ("x_label", "y_label", "title", "description"):
                assert "customerid" not in c.get(field, "").lower(), (
                    f"customerid appears in chart field '{field}': {c.get(field)!r}"
                )

    def test_no_chart_for_numeric_id_column(self, basic_df):
        """order_id (100% unique integers) must not appear in any chart."""
        from app.services.charting.orchestrator import build_chart_data
        charts = build_chart_data(basic_df)
        for c in charts:
            for field in ("x_label", "y_label", "title"):
                assert "order_id" not in c.get(field, "").lower(), (
                    f"order_id appears in chart field '{field}': {c.get(field)!r}"
                )

    def test_senior_citizen_gets_binary_bar_not_histogram(self, basic_df):
        """seniorcitizen must produce a binary bar chart, not a continuous histogram."""
        from app.services.charting.orchestrator import build_chart_data
        charts = build_chart_data(basic_df)
        sc_charts = [
            c for c in charts
            if c.get("x_label", "").lower() == "seniorcitizen"
            or "seniorcitizen" in c.get("title", "").lower()
        ]
        assert len(sc_charts) > 0, (
            "SeniorCitizen should have at least one chart. "
            f"All chart x_labels: {[c.get('x_label') for c in charts]}"
        )
        for c in sc_charts:
            assert c.get("is_binary") is True, (
                f"SeniorCitizen chart should be a binary bar, got: "
                f"type={c.get('type')!r}, is_binary={c.get('is_binary')!r}, "
                f"title={c.get('title')!r}"
            )

    def test_senior_citizen_insight_no_normality_language(self, basic_df):
        """The SeniorCitizen chart insight must not contain normality language."""
        from app.services.charting.orchestrator import build_chart_data
        forbidden = [
            "normal distribution", "normally distributed",
            "parametric", "log transform", "skew",
        ]
        charts = build_chart_data(basic_df)
        sc_charts = [
            c for c in charts
            if "seniorcitizen" in c.get("x_label", "").lower()
        ]
        for c in sc_charts:
            insight = c.get("insight", "")
            for phrase in forbidden:
                assert phrase not in insight.lower(), (
                    f"Forbidden phrase '{phrase}' in SeniorCitizen chart insight:\n{insight}"
                )

    def test_telco_customerid_excluded(self, telco_like_df):
        """Full Telco-like dataset: customerid absent from all chart labels."""
        from app.services.charting.orchestrator import build_chart_data
        charts = build_chart_data(telco_like_df)
        offending = [
            c for c in charts
            if "customerid" in " ".join([
                c.get("x_label", ""), c.get("y_label", ""), c.get("title", "")
            ]).lower()
        ]
        assert offending == [], (
            f"customerid appears in {len(offending)} chart(s):\n"
            + "\n".join(f"  {c.get('title')!r}" for c in offending)
        )

    def test_telco_seniorcitizen_is_binary_bar(self, telco_like_df):
        """Full Telco-like dataset: seniorcitizen → binary bar chart."""
        from app.services.charting.orchestrator import build_chart_data
        charts = build_chart_data(telco_like_df)
        sc = [c for c in charts if c.get("x_label", "").lower() == "seniorcitizen"]
        assert len(sc) > 0, "seniorcitizen chart should exist"
        assert all(c.get("is_binary") is True for c in sc), (
            f"All seniorcitizen charts must be binary bars. Got: {sc}"
        )

    def test_continuous_column_still_gets_histogram(self, telco_like_df):
        """Continuous numeric columns must still produce histograms (no regression)."""
        from app.services.charting.orchestrator import build_chart_data
        charts = build_chart_data(telco_like_df)
        hist_charts = [
            c for c in charts
            if c.get("type") == "bar"
            and "distribution of" in c.get("title", "").lower()
            and not c.get("is_binary")
        ]
        assert len(hist_charts) > 0, (
            "At least one continuous histogram should be generated. "
            f"All charts: {[(c.get('title'), c.get('type')) for c in charts]}"
        )

    def test_categorical_column_still_gets_bar_chart(self, telco_like_df):
        """String categorical columns must still get bar charts (no regression)."""
        from app.services.charting.orchestrator import build_chart_data
        charts = build_chart_data(telco_like_df)
        phone_charts = [
            c for c in charts
            if c.get("x_label", "").lower() == "phoneservice"
        ]
        assert len(phone_charts) > 0, "phoneservice should have a chart"
        for c in phone_charts:
            assert c.get("is_binary") is not True, (
                "phoneservice (Yes/No string) should not be tagged as is_binary=True; "
                "that flag is reserved for numeric 0/1 columns"
            )

    def test_no_id_chart_at_90pct_unique(self):
        """Columns with 90%+ unique values (but not 100%) are also excluded."""
        from app.services.charting.orchestrator import build_chart_data
        n = 100
        # 92 unique values out of 100 rows
        vals = list(range(92)) + [0, 1, 2, 3, 4, 5, 6, 7]
        df = pd.DataFrame({
            "near_unique_id": vals,
            "revenue":        [float(i * 10) for i in range(n)],
        })
        charts = build_chart_data(df)
        for c in charts:
            assert "near_unique_id" not in c.get("x_label", "").lower(), (
                "near_unique_id (92% unique) should not be charted"
            )
