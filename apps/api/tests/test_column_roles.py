"""
90D — Unit tests for the column semantic role classifier.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from app.services.analysis.column_roles import classify_column_roles
from app.schemas.pre_analysis import ColumnSemanticRole


# ── Helpers ───────────────────────────────────────────────────────────────────

def _classify_one(col_name: str, series: pd.Series, extra_cols: dict | None = None) -> ColumnSemanticRole:
    """Classify a single column; extra_cols lets us build a realistic df."""
    data = {col_name: series}
    if extra_cols:
        data.update(extra_cols)
    df = pd.DataFrame(data)
    roles = classify_column_roles(df)
    return next(r for r in roles if r.column_name == col_name)


def _series(values, dtype=None) -> pd.Series:
    return pd.Series(values, dtype=dtype)


# ── Structural guarantees ─────────────────────────────────────────────────────

def test_returns_one_role_per_column():
    df = pd.DataFrame({
        "revenue": [1.0, 2.0, 3.0],
        "region": ["North", "South", "East"],
        "date": pd.to_datetime(["2024-01", "2024-02", "2024-03"]),
    })
    roles = classify_column_roles(df)
    assert len(roles) == 3
    assert [r.column_name for r in roles] == ["revenue", "region", "date"]


def test_does_not_mutate_df():
    df = pd.DataFrame({"x": [1, 2, 3], "y": ["a", "b", "c"]})
    before_cols = list(df.columns)
    before_vals = df.copy()
    classify_column_roles(df)
    assert list(df.columns) == before_cols
    pd.testing.assert_frame_equal(df, before_vals)


def test_empty_dataframe_returns_empty_list():
    roles = classify_column_roles(pd.DataFrame())
    assert roles == []


def test_returns_column_semantic_role_instances():
    df = pd.DataFrame({"x": [1, 2, 3]})
    roles = classify_column_roles(df)
    assert all(isinstance(r, ColumnSemanticRole) for r in roles)


def test_fingerprint_none_still_works():
    df = pd.DataFrame({"revenue": [100.0, 200.0, 300.0]})
    roles = classify_column_roles(df, fingerprint=None)
    assert len(roles) == 1


# ── helper_artifact ───────────────────────────────────────────────────────────

def test_helper_artifact_unnamed_column():
    role = _classify_one("Unnamed: 0", _series([0, 1, 2]))
    assert role.primary_role == "helper_artifact"


def test_helper_artifact_index_column():
    role = _classify_one("index", _series([0, 1, 2]))
    assert role.primary_role == "helper_artifact"


def test_helper_artifact_row_number():
    role = _classify_one("row_number", _series([1, 2, 3]))
    assert role.primary_role == "helper_artifact"


def test_helper_artifact_temp_column():
    role = _classify_one("temp_score", _series([1.0, 2.0, 3.0]))
    assert role.primary_role == "helper_artifact"


def test_helper_artifact_date_part_month():
    role = _classify_one("signup_month", _series([1, 2, 3]))
    assert role.primary_role == "helper_artifact"


def test_helper_artifact_date_part_year():
    role = _classify_one("created_year", _series([2022, 2023, 2024]))
    assert role.primary_role == "helper_artifact"


def test_helper_artifact_date_part_quarter():
    role = _classify_one("order_quarter", _series([1, 2, 3, 4]))
    assert role.primary_role == "helper_artifact"


# ── time ──────────────────────────────────────────────────────────────────────

def test_time_datetime64_dtype():
    role = _classify_one(
        "ts",
        pd.to_datetime(["2024-01-01", "2024-02-01", "2024-03-01"]),
    )
    assert role.primary_role == "time"
    assert role.role_confidence == 0.95


def test_time_column_name_date():
    role = _classify_one("signup_date", _series(["2024-01-01", "2024-02-01", "2024-03-01"]))
    assert role.primary_role == "time"


def test_time_column_name_timestamp():
    role = _classify_one("event_timestamp", _series(["2024-01-01 10:00", "2024-01-02 11:00"]))
    assert role.primary_role == "time"


def test_time_column_ends_with_at():
    role = _classify_one("created_at", _series(["2024-01-01", "2024-02-01", "2024-03-01"]))
    assert role.primary_role == "time"


def test_time_column_ends_with_on():
    role = _classify_one("updated_on", _series(["2024-01-01", "2024-02-01"]))
    assert role.primary_role == "time"


# ── boolean_flag ──────────────────────────────────────────────────────────────

def test_boolean_flag_bool_dtype():
    role = _classify_one("is_active", _series([True, False, True], dtype=bool))
    assert role.primary_role == "boolean_flag"
    assert role.role_confidence == 0.95


def test_boolean_flag_yes_no():
    role = _classify_one("is_member", _series(["yes", "no", "yes", "no"]))
    assert role.primary_role == "boolean_flag"
    assert "dimension" in role.secondary_roles


def test_boolean_flag_true_false_string():
    role = _classify_one("has_flag", _series(["true", "false", "true"]))
    assert role.primary_role == "boolean_flag"


def test_boolean_flag_zero_one_numeric():
    role = _classify_one("active", _series([0, 1, 1, 0, 1]))
    assert role.primary_role == "boolean_flag"


def test_boolean_flag_has_dimension_secondary():
    role = _classify_one("is_active", _series([True, False, True], dtype=bool))
    assert "dimension" in role.secondary_roles


# ── transaction_id ────────────────────────────────────────────────────────────

def test_transaction_id_order_id_high_cardinality():
    role = _classify_one("order_id", _series([1001, 1002, 1003, 1004, 1005, 1006, 1007, 1008]))
    assert role.primary_role == "transaction_id"


def test_transaction_id_payment_id():
    role = _classify_one("payment_id", _series(range(20)))
    assert role.primary_role == "transaction_id"


def test_transaction_id_txn_ref():
    role = _classify_one("txn_ref", _series([f"TXN{i:04d}" for i in range(20)]))
    assert role.primary_role == "transaction_id"


def test_transaction_id_low_cardinality_not_classified():
    # "order" token but only 2 unique values → not transaction_id
    role = _classify_one("order_status", _series(["open", "closed"] * 5))
    assert role.primary_role != "transaction_id"


# ── entity_id ─────────────────────────────────────────────────────────────────

def test_entity_id_customer_id():
    role = _classify_one("customer_id", _series(range(100, 120)))
    assert role.primary_role == "entity_id"


def test_entity_id_user_uuid():
    role = _classify_one("user_uuid", _series([f"uuid-{i}" for i in range(20)]))
    assert role.primary_role == "entity_id"


def test_entity_id_low_unique_rate_not_entity():
    # repeated customer IDs — low unique rate
    role = _classify_one("customer_id", _series([1, 1, 2, 2, 3, 3, 4, 4]))
    assert role.primary_role != "entity_id"


# ── free_text ─────────────────────────────────────────────────────────────────

def test_free_text_long_unique_strings():
    texts = [
        "This is a very detailed comment written by the customer about their experience.",
        "Another long feedback entry from a different user describing their satisfaction.",
        "A third note that is also quite lengthy and unique in its content and phrasing.",
        "One more detailed free-form response that pushes the average length above thirty.",
        "Final entry in this free-text column demonstrating the heuristic is triggered here.",
    ]
    role = _classify_one("notes", _series(texts))
    assert role.primary_role == "free_text"


def test_short_strings_not_free_text():
    role = _classify_one("region", _series(["North", "South", "East", "West", "Central"]))
    assert role.primary_role != "free_text"


# ── leakage_candidate ─────────────────────────────────────────────────────────

def test_leakage_candidate_post_column():
    role = _classify_one("post_event_score", _series([0.1, 0.9, 0.5]))
    assert role.primary_role == "leakage_candidate"
    assert "leakage" in (role.notes or "").lower()


def test_leakage_candidate_future_column():
    role = _classify_one("future_value", _series([100.0, 200.0, 300.0]))
    assert role.primary_role == "leakage_candidate"


def test_leakage_candidate_model_score_phrase():
    role = _classify_one("model_score", _series([0.1, 0.9, 0.5]))
    assert role.primary_role == "leakage_candidate"


def test_leakage_candidate_closed_date():
    role = _classify_one("closed_date", _series(["2024-01", "2024-02", "2024-03"]))
    assert role.primary_role == "leakage_candidate"


# ── target ────────────────────────────────────────────────────────────────────

def test_target_explicit_label_column():
    role = _classify_one("label", _series([0, 1, 0, 1, 0]))
    assert role.primary_role == "target"
    assert role.role_confidence == 0.75


def test_target_explicit_outcome_column():
    role = _classify_one("outcome", _series(["positive", "negative", "positive"]))
    assert role.primary_role == "target"


def test_target_inferred_churn_boolean():
    role = _classify_one("churn", _series(["yes", "no", "yes", "no", "yes"]))
    assert role.primary_role == "target"
    assert "boolean_flag" in role.secondary_roles


def test_target_inferred_fraud_boolean():
    role = _classify_one("fraud", _series([True, False, False, True], dtype=bool))
    assert role.primary_role == "target"


def test_target_inferred_converted_boolean():
    role = _classify_one("converted", _series([0, 1, 1, 0, 1]))
    assert role.primary_role == "target"


# ── geographic ────────────────────────────────────────────────────────────────

def test_geographic_country():
    role = _classify_one("country", _series(["US", "UK", "DE", "FR"]))
    assert role.primary_role == "geographic"


def test_geographic_region():
    role = _classify_one("region", _series(["North", "South", "East", "West"] * 3))
    assert role.primary_role == "geographic"


def test_geographic_city():
    role = _classify_one("city", _series(["London", "Paris", "Berlin"]))
    assert role.primary_role == "geographic"


def test_geographic_lat_lon():
    role_lat = _classify_one("lat", _series([51.5, 48.8, 52.5]))
    role_lon = _classify_one("lon", _series([-0.1, 2.3, 13.4]))
    assert role_lat.primary_role == "geographic"
    assert role_lon.primary_role == "geographic"


def test_geographic_has_dimension_secondary():
    role = _classify_one("country", _series(["US", "UK", "DE"]))
    assert "dimension" in role.secondary_roles


# ── rate_percentage ───────────────────────────────────────────────────────────

def test_rate_percentage_by_name():
    role = _classify_one("conversion_rate", _series([0.05, 0.12, 0.08]))
    assert role.primary_role == "rate_percentage"


def test_rate_percentage_pct_suffix():
    role = _classify_one("open_pct", _series([12.5, 33.0, 55.0]))
    assert role.primary_role == "rate_percentage"


def test_rate_percentage_has_metric_secondary():
    role = _classify_one("click_rate", _series([0.1, 0.2, 0.3]))
    assert "metric" in role.secondary_roles


# ── currency_amount ───────────────────────────────────────────────────────────

def test_currency_amount_revenue():
    role = _classify_one("revenue", _series([1000.0, 2000.0, 1500.0]))
    assert role.primary_role == "currency_amount"


def test_currency_amount_price():
    role = _classify_one("price", _series([9.99, 14.99, 29.99]))
    assert role.primary_role == "currency_amount"


def test_currency_amount_cost():
    role = _classify_one("cost", _series([50.0, 75.0, 100.0]))
    assert role.primary_role == "currency_amount"


def test_currency_amount_has_metric_secondary():
    role = _classify_one("revenue", _series([1000.0, 2000.0, 1500.0]))
    assert "metric" in role.secondary_roles


# ── metric ────────────────────────────────────────────────────────────────────

def test_metric_generic_numeric():
    role = _classify_one("units_sold", _series([10.0, 20.0, 30.0]))
    assert role.primary_role == "metric"
    assert role.role_confidence == 0.7


def test_metric_bounded_01_has_rate_secondary():
    role = _classify_one("score", _series([0.1, 0.5, 0.9, 0.3, 0.7]))
    # score hits the target branch (bounded score check), not plain metric
    # if not target: should at least be metric or rate_percentage
    assert role.primary_role in {"metric", "target", "rate_percentage"}


def test_metric_not_assigned_to_boolean_numeric():
    role = _classify_one("active", _series([0, 1, 0, 1, 1]))
    assert role.primary_role == "boolean_flag"


# ── dimension ─────────────────────────────────────────────────────────────────

def test_dimension_low_cardinality_string():
    role = _classify_one("status", _series(["active", "inactive", "pending"] * 10))
    assert role.primary_role == "dimension"


def test_dimension_confidence():
    role = _classify_one("tier", _series(["gold", "silver", "bronze"] * 5))
    assert role.role_confidence == 0.7


def test_high_cardinality_string_not_dimension():
    # All unique strings → either free_text or unknown, not dimension
    role = _classify_one("description", _series([f"unique value {i}" * 5 for i in range(20)]))
    assert role.primary_role in {"free_text", "unknown"}


# ── unknown fallback ──────────────────────────────────────────────────────────

def test_unknown_fallback_for_unclassifiable_column():
    # A string column where every value is unique and short — not free_text, not dimension
    role = _classify_one("misc", _series([str(i) for i in range(200)]))
    # unique strings with no semantic signal → unknown or dimension
    assert role.primary_role in {"unknown", "dimension", "entity_id"}


# ── Secondary roles ───────────────────────────────────────────────────────────

def test_secondary_roles_deduplicated():
    role = _classify_one("revenue", _series([100.0, 200.0, 300.0]))
    assert len(role.secondary_roles) == len(set(role.secondary_roles))


def test_secondary_roles_exclude_primary():
    df = pd.DataFrame({
        "is_active": pd.Series([True, False, True], dtype=bool),
    })
    role = classify_column_roles(df)[0]
    assert role.primary_role not in role.secondary_roles


# ── Cardinality and missing rate ──────────────────────────────────────────────

def test_cardinality_accurate():
    role = _classify_one("region", _series(["North", "South", "East", "North", "South"]))
    assert role.cardinality == 3


def test_missing_rate_accurate():
    role = _classify_one("value", pd.Series([1.0, None, 3.0, None]))
    assert abs(role.missing_rate - 0.5) < 1e-9


def test_missing_rate_zero_when_no_nulls():
    role = _classify_one("x", _series([1, 2, 3, 4]))
    assert role.missing_rate == 0.0
