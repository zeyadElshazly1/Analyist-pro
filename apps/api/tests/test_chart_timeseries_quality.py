"""
Time-series chart quality: gates, narration, and ID suppression.

Ensures misleading 'over time' line charts and nonsense % narration do not ship.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest


@pytest.fixture
def date_range_100() -> pd.DatetimeIndex:
    return pd.date_range("2019-01-01", periods=100, freq="D")


class TestTimeseriesQualityGates:
    def test_discrete_accidents_blocked(self, date_range_100: pd.DatetimeIndex):
        from app.services.charting.payloads import build_timeseries_payload

        df = pd.DataFrame({
            "claim_date": date_range_100,
            "number_of_previous_accidents": np.tile(np.arange(5), 20),
        })
        assert build_timeseries_payload(df, "claim_date", "number_of_previous_accidents") is None

    def test_vehicle_year_blocked_even_with_many_uniques(self, date_range_100: pd.DatetimeIndex):
        from app.services.charting.payloads import build_timeseries_payload

        df = pd.DataFrame({
            "claim_date": date_range_100,
            "vehicle_year": np.linspace(1998, 2022, 100).astype(int),
        })
        assert build_timeseries_payload(df, "claim_date", "vehicle_year") is None

    def test_age_distribution_histogram_still_builds(self, date_range_100: pd.DatetimeIndex):
        from app.services.charting.payloads import build_histogram_payload, build_timeseries_payload

        rng = np.random.default_rng(0)
        df = pd.DataFrame({
            "claim_date": date_range_100,
            "age": rng.integers(18, 80, size=100),
        })
        assert build_timeseries_payload(df, "claim_date", "age") is not None
        hist = build_histogram_payload(df, "age", is_first_chart=True)
        assert hist is not None
        assert hist["type"] == "bar"
        assert "Distribution" in hist["title"]

    def test_flat_date_axis_blocked(self):
        from app.services.charting.payloads import build_timeseries_payload

        df = pd.DataFrame({
            "claim_date": [pd.Timestamp("2022-06-01")] * 100,
            "premium": np.linspace(100, 500, 100),
        })
        assert build_timeseries_payload(df, "claim_date", "premium") is None

    def test_orchestrator_no_line_for_policyholder_high_cardinality(self, date_range_100):
        from app.services.charting.orchestrator import build_chart_data

        df = pd.DataFrame({
            "claim_date": date_range_100,
            "policyholderid": [f"P{i:05d}" for i in range(100)],
            "age": np.random.default_rng(1).integers(25, 75, size=100),
        })
        charts = build_chart_data(df)
        for c in charts:
            assert "policyholderid" not in (c.get("y_label") or "").lower()
            assert "policyholderid" not in (c.get("title") or "").lower()
        line_titles = [c.get("title", "") for c in charts if c.get("type") == "line"]
        assert not any("policyholderid" in t.lower() for t in line_titles)

    def test_high_cardinality_categorical_bar_skipped_or_other(self):
        from app.services.charting.payloads import build_cat_bar_payload

        n = 500
        df = pd.DataFrame({
            "noisy_cat": [f"cat_{i % 450}" for i in range(n)],
            "age": np.random.default_rng(2).integers(20, 70, size=n),
        })
        p = build_cat_bar_payload(df, "noisy_cat")
        if p is not None:
            assert any(str(r.get("label")) == "Other" for r in p["data"])


class TestTimeseriesNarration:
    def test_near_zero_baseline_avoids_absurd_percent(self):
        from app.services.charting.narrator import _narrate_timeseries

        s = pd.Series([0.0, 1.0, 2.0, 4.0, 8.0, 100.0])
        out = _narrate_timeseries("loss_ratio", s, "period")
        low = out.lower()
        assert "near-zero" in low or "not meaningful" in low
        assert "4000000000000" not in out

    def test_tiny_first_value_vs_typical_magnitude(self):
        from app.services.charting.narrator import _narrate_timeseries

        s = pd.Series([0.001, 50.0, 52.0, 48.0, 51.0, 49.0])
        out = _narrate_timeseries("metric", s, "t")
        assert "not meaningful" in out.lower() or "near-zero" in out.lower()

    def test_sane_percent_still_narrated(self):
        from app.services.charting.narrator import _narrate_timeseries

        s = pd.Series([100.0, 102.0, 104.0, 110.0])
        out = _narrate_timeseries("revenue", s, "month")
        assert "%" in out
        assert "increased" in out or "decreased" in out
