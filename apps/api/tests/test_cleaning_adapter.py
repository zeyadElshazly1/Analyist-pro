"""
Regression tests for app.services.cleaning_adapter.build_cleaning_result().

Covers the cols_removed clamping fix: when the pipeline expands columns
(e.g. messy/sectioned files), cols_removed must be 0, not negative.
"""
import pytest

from app.services.cleaning_adapter import build_cleaning_result


def _make_summary(**overrides) -> dict:
    """Minimal valid summary dict with sensible defaults."""
    base = {
        "original_rows": 100,
        "original_cols": 8,
        "final_rows": 100,
        "final_cols": 14,
        "rows_removed": 0,
        "cols_removed": -6,   # pipeline may emit this for expanding files
        "steps": 3,
        "confidence_score": 85.0,
        "confidence_grade": "B",
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
