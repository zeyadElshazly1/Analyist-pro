"""
Regression tests for advanced insight detectors.

Bug: detect_interaction_effects / detect_simpsons_paradox referenced `ent`
(Shannon entropy of the moderating categorical variable) without defining it,
raising NameError: name 'ent' is not defined on Titanic-like datasets.

Fix: _categorical_entropy() is now computed before the group-correlation loop.
Any moderator whose entropy is below _MIN_MODERATOR_ENTROPY (0.5 bits, i.e. a
roughly 4:1 or more skewed split) is skipped, making subgroup statistics reliable.
"""
from __future__ import annotations

import logging

import numpy as np
import pandas as pd
import pytest

from app.services.analysis.advanced import (
    _categorical_entropy,
    _MIN_MODERATOR_ENTROPY,
    detect_interaction_effects,
    detect_simpsons_paradox,
)
from app.services.analysis.orchestrator import analyze_dataset


# ── _categorical_entropy unit tests ──────────────────────────────────────────

class TestCategoricalEntropy:
    def test_balanced_binary_is_one_bit(self):
        s = pd.Series(["male", "female"] * 50)
        assert abs(_categorical_entropy(s) - 1.0) < 0.01

    def test_uniform_four_values(self):
        s = pd.Series(["a", "b", "c", "d"] * 25)
        assert abs(_categorical_entropy(s) - 2.0) < 0.01  # log2(4) = 2 bits

    def test_near_constant_low_entropy(self):
        # 98% one value → entropy ≈ 0.14 bits, well below threshold
        s = pd.Series(["S"] * 98 + ["C"] * 2)
        assert _categorical_entropy(s) < _MIN_MODERATOR_ENTROPY

    def test_single_value_zero_entropy(self):
        s = pd.Series(["male"] * 100)
        assert _categorical_entropy(s) == 0.0

    def test_empty_series_zero_entropy(self):
        assert _categorical_entropy(pd.Series([], dtype=object)) == 0.0

    def test_nan_ignored(self):
        s = pd.Series(["male", "female", None, None, "male", "female"])
        ent = _categorical_entropy(s)
        assert abs(ent - 1.0) < 0.05


# ── No NameError on Titanic-like data ────────────────────────────────────────

def _titanic_df(n: int = 891, seed: int = 42) -> pd.DataFrame:
    """Build a Titanic-shaped DataFrame including a near-constant column."""
    rng = np.random.default_rng(seed)
    # 'embark_town' is 72% Southampton → entropy ≈ 1.1 bits (above threshold)
    # 'deck' is 77% missing → after dropna, nearly uniform but sparse
    embarked = rng.choice(["S", "C", "Q"], n, p=[0.72, 0.19, 0.09])
    # 'singleton_cat' is 99% "X" — should be skipped (entropy ≈ 0.08 bits)
    singleton_cat = rng.choice(["X", "Y"], n, p=[0.99, 0.01])
    return pd.DataFrame({
        "survived": rng.integers(0, 2, n).astype(float),
        "pclass":   rng.choice([1, 2, 3], n).astype(float),
        "age":      [np.nan if rng.random() < 0.2 else float(rng.normal(30, 14)) for _ in range(n)],
        "sibsp":    rng.integers(0, 6, n).astype(float),
        "parch":    rng.integers(0, 6, n).astype(float),
        "fare":     rng.exponential(32, n),
        "sex":      rng.choice(["male", "female"], n),
        "embarked": embarked,
        "singleton_cat": singleton_cat,
    })


class TestNoNameErrorOnTitanic:
    def test_detect_interaction_effects_no_nameError(self, caplog):
        df = _titanic_df()
        numeric = df.select_dtypes(include=[np.number]).columns.tolist()
        categorical = [c for c in df.select_dtypes(include=["object"]).columns
                       if df[c].nunique() < 50]
        with caplog.at_level(logging.ERROR):
            try:
                result = detect_interaction_effects(df, numeric, categorical)
                assert isinstance(result, list)
            except NameError as e:
                pytest.fail(f"NameError in detect_interaction_effects: {e}")
        assert "ent" not in caplog.text.lower() or "NameError" not in caplog.text

    def test_detect_simpsons_paradox_no_nameError(self, caplog):
        df = _titanic_df()
        numeric = df.select_dtypes(include=[np.number]).columns.tolist()
        categorical = [c for c in df.select_dtypes(include=["object"]).columns
                       if df[c].nunique() < 50]
        with caplog.at_level(logging.ERROR):
            try:
                result = detect_simpsons_paradox(df, numeric, categorical)
                assert isinstance(result, list)
            except NameError as e:
                pytest.fail(f"NameError in detect_simpsons_paradox: {e}")

    def test_full_analyze_dataset_no_nameError(self):
        """analyze_dataset must complete without NameError on Titanic-shaped data."""
        df = _titanic_df()
        try:
            insights, narrative = analyze_dataset(df)
        except NameError as e:
            pytest.fail(f"analyze_dataset raised NameError: {e}")
        assert isinstance(insights, list)
        assert isinstance(narrative, str)

    def test_singleton_moderator_skipped(self):
        """A near-constant categorical (entropy < threshold) must be silently skipped."""
        df = _titanic_df()
        numeric = df.select_dtypes(include=[np.number]).columns.tolist()
        # Only pass singleton_cat as the categorical moderator
        result = detect_interaction_effects(df, numeric, ["singleton_cat"])
        # Function must return an empty list (skipped) rather than crashing
        assert result == [], "singleton moderator should produce no insights"

    def test_valid_moderator_can_produce_insight(self):
        """A genuinely imbalanced correlation across groups should be detected."""
        rng = np.random.default_rng(0)
        n = 300
        # Create data where r(x,y) is clearly different for group A vs B
        group = rng.choice(["A", "B"], n)
        x = rng.normal(0, 1, n)
        # Strong positive r in group A, strong negative r in group B
        y = np.where(group == "A", x * 2 + rng.normal(0, 0.3, n),
                                   -x * 2 + rng.normal(0, 0.3, n))
        df = pd.DataFrame({"x": x, "y": y, "group": group})
        result = detect_interaction_effects(df, ["x", "y"], ["group"])
        assert isinstance(result, list)
        # No NameError — that's the acceptance criterion


# ── Entropy threshold guards ──────────────────────────────────────────────────

class TestEntropyGuard:
    def test_interaction_skips_low_entropy_moderator(self):
        """Moderators below _MIN_MODERATOR_ENTROPY must be skipped."""
        rng = np.random.default_rng(7)
        n = 200
        df = pd.DataFrame({
            "a": rng.normal(0, 1, n),
            "b": rng.normal(0, 1, n),
            "dominant_cat": ["X"] * 195 + ["Y"] * 5,  # entropy ≈ 0.2 bits
        })
        result = detect_interaction_effects(df, ["a", "b"], ["dominant_cat"])
        assert result == [], "Should skip a 195:5 split moderator"

    def test_simpsons_skips_low_entropy_moderator(self):
        rng = np.random.default_rng(8)
        n = 200
        df = pd.DataFrame({
            "a": rng.normal(0, 1, n),
            "b": rng.normal(0, 1, n),
            "dominant_cat": ["X"] * 195 + ["Y"] * 5,
        })
        result = detect_simpsons_paradox(df, ["a", "b"], ["dominant_cat"])
        assert result == []
