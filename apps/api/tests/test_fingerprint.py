"""
90C — Unit tests for the dataset fingerprint extractor.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from app.services.analysis.fingerprint import (
    _is_boolean_like,
    _is_free_text,
    extract_dataset_fingerprint,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _df(**kwargs) -> pd.DataFrame:
    return pd.DataFrame(kwargs)


# ── Empty / degenerate inputs ─────────────────────────────────────────────────

def test_empty_dataframe_returns_zero_counts_and_unknown_shape():
    fp = extract_dataset_fingerprint(pd.DataFrame())
    assert fp.row_count == 0
    assert fp.column_count == 0
    assert fp.dataset_shape == "unknown"


def test_no_columns_returns_column_count_zero():
    df = pd.DataFrame(index=range(10))  # rows but no columns
    fp = extract_dataset_fingerprint(df)
    assert fp.column_count == 0
    assert fp.dataset_shape == "unknown"


def test_zero_rows_returns_row_count_zero():
    df = pd.DataFrame({"x": pd.Series([], dtype=float)})
    fp = extract_dataset_fingerprint(df)
    assert fp.row_count == 0


def test_empty_dataframe_density_is_zero():
    fp = extract_dataset_fingerprint(pd.DataFrame())
    assert fp.overall_data_density == 0.0


# ── Column type counts ────────────────────────────────────────────────────────

def test_numeric_and_categorical_counts():
    df = _df(
        revenue=[100, 200, 300],
        units=[10, 20, 30],
        region=["North", "South", "East"],
        product=["A", "B", "C"],
    )
    fp = extract_dataset_fingerprint(df)
    assert fp.numeric_column_count == 2
    assert fp.categorical_column_count == 2
    assert fp.datetime_column_count == 0
    assert fp.boolean_column_count == 0
    assert fp.free_text_column_count == 0


def test_datetime_column_counted():
    df = _df(
        ts=pd.to_datetime(["2024-01-01", "2024-02-01", "2024-03-01"]),
        value=[1.0, 2.0, 3.0],
    )
    fp = extract_dataset_fingerprint(df)
    assert fp.datetime_column_count == 1
    assert fp.numeric_column_count == 1


def test_bool_dtype_counted_as_boolean():
    df = _df(
        flag=[True, False, True, False],
        score=[1.0, 2.0, 3.0, 4.0],
    )
    fp = extract_dataset_fingerprint(df)
    assert fp.boolean_column_count == 1
    assert fp.numeric_column_count == 1


def test_yes_no_object_column_counted_as_boolean():
    df = _df(is_active=["yes", "no", "yes", "yes"])
    fp = extract_dataset_fingerprint(df)
    assert fp.boolean_column_count == 1


def test_true_false_string_counted_as_boolean():
    df = _df(flag=["true", "false", "true", "false"])
    fp = extract_dataset_fingerprint(df)
    assert fp.boolean_column_count == 1


def test_free_text_column_detected():
    long_texts = [
        "This is a very long customer comment about their experience with the product.",
        "Another lengthy review written by a different user describing what they liked.",
        "A third detailed note from a customer explaining the issue they encountered.",
        "More free-form text that goes on and on to push the average length above threshold.",
        "Yet another entry with substantial text content that triggers the heuristic.",
    ]
    df = _df(notes=long_texts, amount=[10, 20, 30, 40, 50])
    fp = extract_dataset_fingerprint(df)
    assert fp.free_text_column_count == 1
    assert fp.numeric_column_count == 1


def test_short_string_column_not_counted_as_free_text():
    df = _df(region=["North", "South", "East", "West", "Central"])
    fp = extract_dataset_fingerprint(df)
    assert fp.free_text_column_count == 0
    assert fp.categorical_column_count == 1


# ── Missingness ───────────────────────────────────────────────────────────────

def test_missingness_rate_computed_correctly():
    df = pd.DataFrame({
        "a": [1.0, None, 3.0, None],  # 2 missing
        "b": [1.0, 2.0, 3.0, 4.0],   # 0 missing
    })
    fp = extract_dataset_fingerprint(df)
    # 2 missing out of 8 total cells = 0.25
    assert abs(fp.overall_missing_rate - 0.25) < 1e-9


def test_no_missing_values_gives_zero_missing_rate():
    df = _df(x=[1, 2, 3], y=["a", "b", "c"])
    fp = extract_dataset_fingerprint(df)
    assert fp.overall_missing_rate == 0.0


def test_duplicate_row_count():
    df = pd.DataFrame({
        "a": [1, 1, 2, 3],
        "b": ["x", "x", "y", "z"],
    })
    fp = extract_dataset_fingerprint(df)
    assert fp.duplicate_row_count == 1


def test_no_duplicate_rows_gives_zero():
    df = _df(a=[1, 2, 3], b=["x", "y", "z"])
    fp = extract_dataset_fingerprint(df)
    assert fp.duplicate_row_count == 0


# ── Data density ──────────────────────────────────────────────────────────────

def test_empty_string_treated_as_missing_for_density():
    df = pd.DataFrame({
        "name": ["Alice", "", "Carol"],   # 1 empty
        "score": [1.0, 2.0, 3.0],        # 0 empty
    })
    fp = extract_dataset_fingerprint(df)
    # 5 non-empty out of 6 cells = 5/6
    expected = 5 / 6
    assert abs(fp.overall_data_density - expected) < 1e-9


def test_whitespace_only_string_treated_as_missing_for_density():
    df = pd.DataFrame({"notes": ["hello", "   ", "world"]})
    fp = extract_dataset_fingerprint(df)
    expected = 2 / 3
    assert abs(fp.overall_data_density - expected) < 1e-9


def test_fully_populated_numeric_dataframe_has_density_one():
    df = _df(a=[1, 2, 3], b=[4, 5, 6])
    fp = extract_dataset_fingerprint(df)
    assert fp.overall_data_density == 1.0


# ── Boolean helper ────────────────────────────────────────────────────────────

def test_is_boolean_like_true_for_bool_dtype():
    assert _is_boolean_like(pd.Series([True, False, True]))


def test_is_boolean_like_true_for_yes_no():
    assert _is_boolean_like(pd.Series(["yes", "no", "yes"]))


def test_is_boolean_like_true_for_0_1_numeric():
    assert _is_boolean_like(pd.Series([0, 1, 0, 1]))


def test_is_boolean_like_false_for_multivalue():
    assert not _is_boolean_like(pd.Series(["a", "b", "c"]))


# ── Free-text helper ──────────────────────────────────────────────────────────

def test_is_free_text_true_for_long_unique_strings():
    texts = [f"Row {i}: " + "x" * 40 for i in range(10)]
    assert _is_free_text(pd.Series(texts))


def test_is_free_text_false_for_short_strings():
    assert not _is_free_text(pd.Series(["a", "b", "c", "d"]))


def test_is_free_text_false_for_numeric_series():
    assert not _is_free_text(pd.Series([1.0, 2.0, 3.0]))


# ── Dataset shape classification ──────────────────────────────────────────────

def test_time_series_shape():
    df = pd.DataFrame({
        "date": pd.to_datetime(["2024-01", "2024-02", "2024-03", "2024-04", "2024-05"]),
        "revenue": [100.0, 120.0, 110.0, 130.0, 140.0],
    })
    fp = extract_dataset_fingerprint(df)
    assert fp.dataset_shape == "time_series"


def test_panel_data_shape():
    # datetime + entity_id column with repeated entities
    df = pd.DataFrame({
        "date": pd.to_datetime(["2024-01", "2024-02", "2024-01", "2024-02", "2024-01"]),
        "customer_id": [1, 1, 2, 2, 3],
        "spend": [50.0, 60.0, 70.0, 80.0, 90.0],
    })
    fp = extract_dataset_fingerprint(df)
    assert fp.dataset_shape == "panel_data"


def test_event_log_shape():
    df = pd.DataFrame({
        "timestamp": pd.to_datetime([
            "2024-01-01 10:00", "2024-01-01 10:05", "2024-01-01 10:10",
            "2024-01-01 10:15", "2024-01-01 10:20",
        ]),
        "event_type": ["click", "view", "click", "purchase", "view"],
        "user_id": [1, 2, 1, 3, 2],
    })
    fp = extract_dataset_fingerprint(df)
    assert fp.dataset_shape == "event_log"


def test_survey_shape():
    df = pd.DataFrame({
        "q1": ["agree", "disagree", "neutral", "agree", "agree"],
        "q2": ["yes", "no", "yes", "no", "yes"],
        "q3": ["satisfied", "neutral", "dissatisfied", "satisfied", "neutral"],
        "q4": ["often", "rarely", "sometimes", "often", "always"],
        "q5": ["yes", "yes", "no", "no", "yes"],
    })
    fp = extract_dataset_fingerprint(df)
    assert fp.dataset_shape == "survey"


def test_entity_table_shape():
    df = pd.DataFrame({
        "customer_id": [101, 102, 103, 104, 105],
        "name": ["Alice", "Bob", "Carol", "Dave", "Eve"],
        "email": ["a@x.com", "b@x.com", "c@x.com", "d@x.com", "e@x.com"],
        "tier": ["gold", "silver", "gold", "bronze", "silver"],
    })
    fp = extract_dataset_fingerprint(df)
    assert fp.dataset_shape == "entity_table"


def test_transactional_shape():
    df = pd.DataFrame({
        "order_id": [1001, 1002, 1003, 1004, 1005],
        "amount": [50.0, 120.0, 30.0, 80.0, 95.0],
        "product": ["A", "B", "A", "C", "B"],
        "region": ["North", "South", "East", "West", "North"],
    })
    fp = extract_dataset_fingerprint(df)
    assert fp.dataset_shape == "transactional"


def test_snapshot_shape_fallback():
    # Non-empty but no shape-specific signals → snapshot
    df = pd.DataFrame({
        "col_a": [1.0, 2.0, 3.0],
        "col_b": [4.0, 5.0, 6.0],
        "col_c": [7.0, 8.0, 9.0],
    })
    fp = extract_dataset_fingerprint(df)
    assert fp.dataset_shape == "snapshot"


# ── Return type ───────────────────────────────────────────────────────────────

def test_returns_dataset_fingerprint_instance():
    from app.schemas.pre_analysis import DatasetFingerprint
    df = _df(x=[1, 2, 3], y=["a", "b", "c"])
    fp = extract_dataset_fingerprint(df)
    assert isinstance(fp, DatasetFingerprint)


def test_column_count_matches_dataframe():
    df = _df(a=[1], b=[2], c=[3], d=[4])
    fp = extract_dataset_fingerprint(df)
    assert fp.column_count == 4


def test_row_count_matches_dataframe():
    df = _df(x=[10, 20, 30, 40, 50])
    fp = extract_dataset_fingerprint(df)
    assert fp.row_count == 5
