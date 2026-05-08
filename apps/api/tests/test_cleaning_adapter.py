"""
Regression tests for app.services.cleaning_adapter.build_cleaning_result().

Covers:
- cols_removed clamping: when the pipeline expands columns cols_removed must be 0
- grade formatting: confidence_grade must be a human-readable string, never a raw dict
"""
import pytest

from app.services.cleaning_adapter import build_cleaning_result, _format_grade


def _make_summary(**overrides) -> dict:
    """Minimal valid summary dict with sensible defaults.

    confidence_grade mirrors real pipeline output: score_to_grade() returns a
    dict, not a string. The adapter is responsible for formatting it.
    """
    base = {
        "original_rows": 100,
        "original_cols": 8,
        "final_rows": 100,
        "final_cols": 14,
        "rows_removed": 0,
        "cols_removed": -6,   # pipeline may emit this for expanding files
        "steps": 3,
        "confidence_score": 85.0,
        "confidence_grade": {"score": 85, "grade": "A", "label": "High Quality"},
        "time_saved_estimate": "~2 minutes",
        "mode": "aggressive",
    }
    base.update(overrides)
    return base


class TestColsRemovedClamping:
    def test_column_expansion_cols_removed_is_zero(self):
        """original_cols=8, clean_cols=14 → pipeline expanded; cols_removed must be 0."""
        original_cols = [f"col_{i}" for i in range(8)]
        clean_cols    = [f"col_{i}" for i in range(14)]
        summary = _make_summary(
            original_cols=8,
            final_cols=14,
            cols_removed=-6,
        )
        result = build_cleaning_result(original_cols, clean_cols, [], summary)
        assert result.cleaning_summary.cols_removed == 0

    def test_column_removal_cols_removed_correct(self):
        """original_cols=10, clean_cols=7 → 3 columns dropped; cols_removed must be 3."""
        original_cols = [f"col_{i}" for i in range(10)]
        clean_cols    = [f"col_{i}" for i in range(7)]
        summary = _make_summary(
            original_cols=10,
            final_cols=7,
            cols_removed=3,
        )
        result = build_cleaning_result(original_cols, clean_cols, [], summary)
        assert result.cleaning_summary.cols_removed == 3

    def test_schema_validates_successfully_on_expansion(self):
        """Pydantic must not raise ValidationError when cols_removed would have been negative."""
        original_cols = [f"col_{i}" for i in range(8)]
        clean_cols    = [f"col_{i}" for i in range(14)]
        summary = _make_summary(cols_removed=-6)
        # Should not raise
        result = build_cleaning_result(original_cols, clean_cols, [], summary)
        assert result.cleaning_summary.cols_removed >= 0

    def test_rows_removed_never_negative(self):
        """rows_removed from a buggy pipeline value must be clamped to 0."""
        original_cols = ["a", "b"]
        clean_cols    = ["a", "b"]
        summary = _make_summary(
            original_cols=2, final_cols=2,
            original_rows=50, final_rows=60,
            rows_removed=-10,
            cols_removed=0,
        )
        result = build_cleaning_result(original_cols, clean_cols, [], summary)
        assert result.cleaning_summary.rows_removed == 0


class TestGradeFormatting:
    """confidence_grade must be a human-readable string — never a raw Python dict."""

    def _build(self, score: float) -> str:
        summary = _make_summary(confidence_score=score)
        result = build_cleaning_result(["a"], ["a"], [], summary)
        return result.cleaning_summary.confidence_grade

    def test_grade_is_string(self):
        assert isinstance(self._build(85.0), str)

    def test_grade_contains_no_raw_dict(self):
        grade = self._build(70.0)
        assert "{'score':" not in grade
        assert "{" not in grade

    def test_grade_contains_grade_prefix(self):
        assert self._build(85.0).startswith("Grade ")

    def test_grade_contains_score_out_of_100(self):
        assert "/100" in self._build(85.0)

    def test_grade_letter_A_for_high_score(self):
        assert "Grade A" in self._build(90.0)

    def test_grade_letter_B_for_mid_score(self):
        assert "Grade B" in self._build(70.0)

    def test_grade_letter_C_for_low_score(self):
        assert "Grade C" in self._build(55.0)

    def test_grade_unavailable_when_score_missing(self):
        summary = _make_summary(confidence_score=None)
        # remove confidence_score key entirely to simulate missing value
        summary.pop("confidence_score", None)
        result = build_cleaning_result(["a"], ["a"], [], summary)
        assert result.cleaning_summary.confidence_grade == "Grade unavailable"

    def test_format_grade_helper_directly(self):
        out = _format_grade(70)
        assert out == "Grade B — 70/100 · Good"

    def test_format_grade_helper_none(self):
        assert _format_grade(None) == "Grade unavailable"
