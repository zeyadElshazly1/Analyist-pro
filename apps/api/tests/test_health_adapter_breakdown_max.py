"""
Unit tests: HealthScore.breakdown_max is populated correctly from the
dataset-specific weights returned by calculate_health_score().

Key regression: a transactional dataset uses uniqueness=30 (not 20).
Before this fix the frontend hardcoded uniqueness/20, producing "30 / 20"
which looks impossible and untrustworthy.

After the fix:
  • _build_health_score() maps health["max_scores"] → HealthScore.breakdown_max
  • The frontend reads breakdown_max and uses those denominators exclusively.
"""
import pytest
import pandas as pd

from app.services.profiling.health_scorer import calculate_health_score, _HEALTH_WEIGHTS
from app.services.health_adapter import build_health_result, _build_health_score


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _make_general_df() -> pd.DataFrame:
    """Clean, general-purpose dataset — uses 'general' weights."""
    return pd.DataFrame({
        "id":    range(50),
        "value": [float(i) for i in range(50)],
        "label": [f"cat_{i % 5}" for i in range(50)],
    })


def _make_transactional_df() -> pd.DataFrame:
    """
    Dataset that the classifier will detect as 'transactional'.
    It has order_id, amount, and customer_id — keywords that push the
    classifier toward transactional, which uses uniqueness=30.
    """
    return pd.DataFrame({
        "order_id":   [f"ORD-{i:04d}" for i in range(100)],
        "customer_id": [f"CUST-{i % 20:04d}" for i in range(100)],
        "amount":      [float(10 + i % 500) for i in range(100)],
        "quantity":    [1 + i % 10 for i in range(100)],
        "status":      [("paid" if i % 3 != 0 else "pending") for i in range(100)],
    })


def _make_duplicate_df() -> pd.DataFrame:
    """Dataset with 50% duplicate rows — uniqueness score will be < max."""
    base = pd.DataFrame({
        "order_id":   [f"ORD-{i:04d}" for i in range(60)],
        "customer_id": [f"CUST-{i % 10:04d}" for i in range(60)],
        "amount":     [float(100 + i) for i in range(60)],
        "quantity":   [1 + i % 5 for i in range(60)],
        "status":     ["paid"] * 60,
    })
    dupe_block = base.iloc[:40].copy()
    return pd.concat([base, dupe_block], ignore_index=True)


# ── Tests: raw health_scorer.calculate_health_score ──────────────────────────

class TestHealthScorerMaxScores:
    """Verify that the raw scorer already returns max_scores correctly."""

    def test_max_scores_present_and_match_detected_type(self):
        health = calculate_health_score(_make_general_df())
        assert "max_scores" in health, "scorer must return max_scores"
        dt = health["dataset_type"]
        expected = _HEALTH_WEIGHTS[dt]
        assert health["max_scores"] == expected, (
            f"max_scores {health['max_scores']} must equal weights for "
            f"detected type '{dt}': {expected}"
        )

    def test_transactional_max_uniqueness_is_30(self):
        df = _make_transactional_df()
        health = calculate_health_score(df)
        if health["dataset_type"] == "transactional":
            assert health["max_scores"]["uniqueness"] == 30, (
                "transactional datasets must have uniqueness max = 30"
            )
        # If the classifier chose a different type, still verify max_scores
        # matches the HEALTH_WEIGHTS entry for that type.
        dt = health["dataset_type"]
        assert health["max_scores"] == _HEALTH_WEIGHTS[dt]

    def test_all_breakdown_values_within_max(self):
        """No dimension score should exceed its own max — regression guard."""
        for df in [_make_general_df(), _make_transactional_df(), _make_duplicate_df()]:
            health = calculate_health_score(df)
            breakdown = health["breakdown"]
            mx = health["max_scores"]
            for dim, val in breakdown.items():
                assert val <= mx[dim] + 1e-9, (
                    f"breakdown[{dim}]={val} exceeds max_scores[{dim}]={mx[dim]}"
                )


# ── Tests: _build_health_score adapter ───────────────────────────────────────

class TestBuildHealthScoreBreakdownMax:
    """Verify the adapter propagates max_scores → HealthScore.breakdown_max."""

    def test_breakdown_max_populated_and_matches_detected_type(self):
        health = calculate_health_score(_make_general_df())
        hs = _build_health_score(health)
        assert hs.breakdown_max, "breakdown_max must not be empty"
        dt = health["dataset_type"]
        expected = _HEALTH_WEIGHTS[dt]
        for dim, max_val in expected.items():
            assert hs.breakdown_max[dim] == float(max_val), (
                f"breakdown_max[{dim}] expected {max_val} for type '{dt}', "
                f"got {hs.breakdown_max[dim]}"
            )

    def test_breakdown_max_populated_for_transactional(self):
        health = calculate_health_score(_make_transactional_df())
        hs = _build_health_score(health)
        dt = health["dataset_type"]
        expected = _HEALTH_WEIGHTS[dt]
        for dim, max_val in expected.items():
            assert hs.breakdown_max[dim] == float(max_val), (
                f"breakdown_max[{dim}] should be {max_val} for {dt} dataset"
            )

    def test_breakdown_max_explicitly_30_for_uniqueness_when_transactional(self):
        """
        Regression: the displayed denominator for uniqueness on a transactional
        dataset must be 30, not the hardcoded general fallback of 20.
        """
        health = calculate_health_score(_make_transactional_df())
        if health["dataset_type"] != "transactional":
            pytest.skip("classifier did not choose transactional for this fixture")
        hs = _build_health_score(health)
        assert hs.breakdown_max["uniqueness"] == 30.0, (
            "transactional datasets: uniqueness denominator must be 30, not 20"
        )

    def test_no_breakdown_value_exceeds_its_max(self):
        """Displayed score can never exceed displayed max — ever."""
        for df in [_make_general_df(), _make_transactional_df(), _make_duplicate_df()]:
            health = calculate_health_score(df)
            hs = _build_health_score(health)
            for dim, val in hs.breakdown.items():
                max_val = hs.breakdown_max.get(dim, 100.0)
                assert val <= max_val + 1e-9, (
                    f"breakdown[{dim}]={val} > breakdown_max[{dim}]={max_val} — "
                    "would display an impossible fraction"
                )

    def test_breakdown_max_contains_all_five_dimensions(self):
        health = calculate_health_score(_make_general_df())
        hs = _build_health_score(health)
        expected_dims = {"completeness", "uniqueness", "consistency", "validity", "structure"}
        assert set(hs.breakdown_max.keys()) == expected_dims

    def test_breakdown_max_values_are_floats(self):
        health = calculate_health_score(_make_general_df())
        hs = _build_health_score(health)
        for dim, val in hs.breakdown_max.items():
            assert isinstance(val, float), f"breakdown_max[{dim}] must be float, got {type(val)}"

    def test_missing_max_scores_key_produces_empty_breakdown_max(self):
        """Legacy health dicts without max_scores should produce empty breakdown_max."""
        health = calculate_health_score(_make_general_df())
        health_without_max = {k: v for k, v in health.items() if k != "max_scores"}
        hs = _build_health_score(health_without_max)
        assert hs.breakdown_max == {}, (
            "absent max_scores should produce empty breakdown_max (not an error)"
        )


# ── Tests: full build_health_result integration ───────────────────────────────

class TestBuildHealthResultBreakdownMax:
    """End-to-end: build_health_result must expose breakdown_max on HealthResult."""

    def _minimal_profile(self, df: pd.DataFrame) -> list[dict]:
        return [{"column": col} for col in df.columns]

    def test_health_result_exposes_breakdown_max(self):
        df = _make_general_df()
        health = calculate_health_score(df)
        result = build_health_result(df, health, self._minimal_profile(df))
        assert result.health_score.breakdown_max, "breakdown_max must be present"

    def test_health_result_breakdown_max_matches_weights(self):
        df = _make_transactional_df()
        health = calculate_health_score(df)
        result = build_health_result(df, health, self._minimal_profile(df))
        dt = result.health_score.dataset_type
        expected = _HEALTH_WEIGHTS[dt]
        for dim, max_val in expected.items():
            actual = result.health_score.breakdown_max.get(dim)
            assert actual == float(max_val), (
                f"health_result.health_score.breakdown_max[{dim}] "
                f"expected {max_val}, got {actual}"
            )

    def test_serialised_json_includes_breakdown_max(self):
        """Ensure Pydantic serialises breakdown_max — it must reach the frontend."""
        df = _make_general_df()
        health = calculate_health_score(df)
        result = build_health_result(df, health, self._minimal_profile(df))
        payload = result.model_dump()
        assert "breakdown_max" in payload["health_score"], (
            "breakdown_max must appear in the serialised JSON payload"
        )
        assert payload["health_score"]["breakdown_max"] != {}, (
            "breakdown_max must not be empty in the JSON payload"
        )
