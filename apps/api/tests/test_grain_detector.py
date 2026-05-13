"""
90E — Unit tests for the grain/entity detector.
"""
from __future__ import annotations

import pytest

from app.schemas.pre_analysis import ColumnSemanticRole, DatasetFingerprint
from app.services.analysis.grain_detector import detect_grain


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _fp(**kwargs) -> DatasetFingerprint:
    defaults = {"row_count": 100, "column_count": 4, "dataset_shape": "snapshot"}
    defaults.update(kwargs)
    return DatasetFingerprint(**defaults)


def _role(name: str, primary: str = "dimension", confidence: float = 0.7) -> ColumnSemanticRole:
    return ColumnSemanticRole(
        column_name=name,
        primary_role=primary,
        role_confidence=confidence,
        cardinality=10,
        missing_rate=0.0,
    )


def _tx_id(name: str) -> ColumnSemanticRole:
    return _role(name, primary="transaction_id", confidence=0.9)


def _ent_id(name: str) -> ColumnSemanticRole:
    return _role(name, primary="entity_id", confidence=0.85)


def _time(name: str = "timestamp") -> ColumnSemanticRole:
    return _role(name, primary="time", confidence=0.95)


def _metric(name: str) -> ColumnSemanticRole:
    return _role(name, primary="metric", confidence=0.7)


def _dim(name: str) -> ColumnSemanticRole:
    return _role(name, primary="dimension", confidence=0.7)


# ── survey_response ───────────────────────────────────────────────────────────

def test_survey_shape_returns_survey_response():
    fp = _fp(dataset_shape="survey")
    roles = [_role("q1"), _role("q2"), _role("q3"), _role("q4")]
    label, conf = detect_grain(fp, roles)
    assert label == "survey_response"
    assert conf == 0.9


def test_question_field_pattern_returns_survey_response():
    fp = _fp(dataset_shape="snapshot")
    roles = [_role("q1"), _role("q2"), _role("q3"), _metric("age")]
    label, conf = detect_grain(fp, roles)
    assert label == "survey_response"
    assert conf == 0.75


def test_question_prefixed_columns_survey_response():
    fp = _fp(dataset_shape="snapshot")
    roles = [_role("question_1"), _role("question_2"), _metric("score")]
    label, conf = detect_grain(fp, roles)
    assert label == "survey_response"
    assert conf == 0.75


def test_survey_prefixed_columns_survey_response():
    fp = _fp(dataset_shape="snapshot")
    roles = [_role("survey_satisfaction"), _role("survey_nps"), _metric("revenue")]
    label, conf = detect_grain(fp, roles)
    assert label == "survey_response"
    assert conf == 0.75


# ── time_period ───────────────────────────────────────────────────────────────

def test_time_series_shape_returns_time_period():
    fp = _fp(dataset_shape="time_series")
    roles = [_time("month"), _metric("revenue"), _metric("units")]
    label, conf = detect_grain(fp, roles)
    assert label == "time_period"
    assert conf == 0.85


def test_one_time_column_no_ids_returns_time_period():
    fp = _fp(dataset_shape="snapshot")
    roles = [_time("report_date"), _metric("revenue"), _metric("units")]
    label, conf = detect_grain(fp, roles)
    assert label == "time_period"
    assert conf == 0.7


def test_time_column_with_entity_id_not_time_period():
    # entity_id present → falls through to a more specific grain
    fp = _fp(dataset_shape="snapshot")
    roles = [_time("created_at"), _ent_id("customer_id"), _metric("spend")]
    label, _ = detect_grain(fp, roles)
    assert label != "time_period"


# ── event ─────────────────────────────────────────────────────────────────────

def test_event_log_shape_returns_event():
    fp = _fp(dataset_shape="event_log")
    roles = [_time("ts"), _dim("event_type"), _ent_id("user_id")]
    label, conf = detect_grain(fp, roles)
    assert label == "event"
    assert conf == 0.9


def test_event_name_plus_time_column_returns_event():
    fp = _fp(dataset_shape="snapshot")
    roles = [_time("ts"), _dim("event_type"), _metric("value")]
    label, conf = detect_grain(fp, roles)
    assert label == "event"
    assert conf == 0.75


def test_action_name_plus_time_returns_event():
    fp = _fp(dataset_shape="snapshot")
    roles = [_time("occurred_at"), _dim("action"), _ent_id("user_id")]
    label, conf = detect_grain(fp, roles)
    assert label == "event"
    assert conf == 0.75


# ── session ───────────────────────────────────────────────────────────────────

def test_session_id_as_transaction_id_returns_session():
    fp = _fp(dataset_shape="snapshot")
    roles = [_tx_id("session_id"), _time("started_at"), _metric("page_views")]
    label, conf = detect_grain(fp, roles)
    assert label == "session"
    assert conf == 0.85


def test_session_token_without_tx_role_returns_session():
    fp = _fp(dataset_shape="snapshot")
    roles = [_dim("session"), _metric("duration"), _metric("clicks")]
    label, conf = detect_grain(fp, roles)
    assert label == "session"
    assert conf == 0.7


# ── order ─────────────────────────────────────────────────────────────────────

def test_order_id_transaction_role_returns_order():
    fp = _fp(dataset_shape="snapshot")
    roles = [_tx_id("order_id"), _ent_id("customer_id"), _metric("amount")]
    label, conf = detect_grain(fp, roles)
    assert label == "order"
    assert conf == 0.9


def test_invoice_id_transaction_role_returns_order():
    fp = _fp(dataset_shape="snapshot")
    roles = [_tx_id("invoice_id"), _metric("total"), _dim("status")]
    label, conf = detect_grain(fp, roles)
    assert label == "order"
    assert conf == 0.9


def test_purchase_name_signal_returns_order():
    fp = _fp(dataset_shape="snapshot")
    roles = [_dim("purchase"), _metric("amount"), _time("purchase_at")]
    label, conf = detect_grain(fp, roles)
    assert label == "order"
    assert conf == 0.75


# ── policy ────────────────────────────────────────────────────────────────────

def test_policy_id_transaction_role_returns_policy():
    fp = _fp(dataset_shape="snapshot")
    roles = [_tx_id("policy_id"), _ent_id("customer_id"), _metric("premium")]
    label, conf = detect_grain(fp, roles)
    assert label == "policy"
    assert conf == 0.85


def test_subscription_name_returns_policy():
    fp = _fp(dataset_shape="snapshot")
    roles = [_dim("subscription"), _metric("mrr"), _ent_id("account_id")]
    label, conf = detect_grain(fp, roles)
    assert label == "policy"
    assert conf == 0.7


def test_contract_name_returns_policy():
    fp = _fp(dataset_shape="snapshot")
    roles = [_dim("contract"), _metric("value"), _time("start_date")]
    label, conf = detect_grain(fp, roles)
    assert label == "policy"
    assert conf == 0.7


# ── transaction ───────────────────────────────────────────────────────────────

def test_transactional_shape_returns_transaction():
    fp = _fp(dataset_shape="transactional")
    roles = [_tx_id("txn_id"), _metric("amount"), _dim("region")]
    label, conf = detect_grain(fp, roles)
    assert label == "transaction"
    assert conf == 0.85


def test_generic_transaction_id_returns_transaction():
    # transaction_id role with no more-specific token → transaction
    fp = _fp(dataset_shape="snapshot")
    roles = [_tx_id("txn_ref"), _metric("amount"), _dim("channel")]
    label, conf = detect_grain(fp, roles)
    assert label == "transaction"
    assert conf == 0.8


def test_payment_name_signal_returns_transaction():
    fp = _fp(dataset_shape="snapshot")
    roles = [_dim("payment"), _metric("amount"), _metric("fee")]
    label, conf = detect_grain(fp, roles)
    assert label == "transaction"
    assert conf == 0.65


# ── customer ──────────────────────────────────────────────────────────────────

def test_customer_entity_id_returns_customer():
    fp = _fp(dataset_shape="entity_table")
    roles = [_ent_id("customer_id"), _dim("tier"), _dim("region")]
    label, conf = detect_grain(fp, roles)
    assert label == "customer"
    assert conf == 0.8


def test_user_entity_id_returns_customer():
    fp = _fp(dataset_shape="entity_table")
    roles = [_ent_id("user_id"), _dim("plan"), _metric("age")]
    label, conf = detect_grain(fp, roles)
    assert label == "customer"
    assert conf == 0.8


def test_customer_name_signal_returns_customer():
    fp = _fp(dataset_shape="snapshot")
    roles = [_dim("customer"), _dim("region"), _metric("score")]
    label, conf = detect_grain(fp, roles)
    assert label == "customer"
    assert conf == 0.65


# ── product ───────────────────────────────────────────────────────────────────

def test_product_entity_id_returns_product():
    fp = _fp(dataset_shape="entity_table")
    roles = [_ent_id("product_id"), _dim("category"), _metric("price")]
    label, conf = detect_grain(fp, roles)
    assert label == "product"
    assert conf == 0.8


def test_sku_name_returns_product():
    fp = _fp(dataset_shape="snapshot")
    roles = [_dim("sku"), _dim("category"), _metric("price")]
    label, conf = detect_grain(fp, roles)
    assert label == "product"
    assert conf == 0.65


# ── employee ──────────────────────────────────────────────────────────────────

def test_employee_entity_id_returns_employee():
    fp = _fp(dataset_shape="entity_table")
    roles = [_ent_id("employee_id"), _dim("department"), _metric("salary")]
    label, conf = detect_grain(fp, roles)
    assert label == "employee"
    assert conf == 0.8


def test_staff_name_returns_employee():
    fp = _fp(dataset_shape="snapshot")
    roles = [_dim("staff"), _dim("role"), _metric("tenure")]
    label, conf = detect_grain(fp, roles)
    assert label == "employee"
    assert conf == 0.65


# ── unknown ───────────────────────────────────────────────────────────────────

def test_unknown_fallback_returns_unknown_zero():
    fp = _fp(dataset_shape="snapshot")
    roles = [_metric("col_a"), _metric("col_b"), _metric("col_c")]
    label, conf = detect_grain(fp, roles)
    assert label == "unknown"
    assert conf == 0.0


def test_empty_roles_returns_unknown():
    fp = _fp(dataset_shape="unknown", row_count=0, column_count=0)
    label, conf = detect_grain(fp, [])
    assert label == "unknown"
    assert conf == 0.0


# ── Priority / disambiguation ─────────────────────────────────────────────────

def test_priority_event_log_with_user_id_returns_event_not_customer():
    # event_log shape wins over customer entity_id
    fp = _fp(dataset_shape="event_log")
    roles = [_time("ts"), _dim("event_type"), _ent_id("user_id")]
    label, _ = detect_grain(fp, roles)
    assert label == "event"


def test_priority_order_id_with_customer_id_returns_order_not_customer():
    fp = _fp(dataset_shape="snapshot")
    roles = [_tx_id("order_id"), _ent_id("customer_id"), _metric("amount")]
    label, _ = detect_grain(fp, roles)
    assert label == "order"


def test_priority_session_beats_customer():
    fp = _fp(dataset_shape="snapshot")
    roles = [_tx_id("session_id"), _ent_id("user_id"), _metric("clicks")]
    label, _ = detect_grain(fp, roles)
    assert label == "session"


def test_priority_policy_beats_customer():
    fp = _fp(dataset_shape="snapshot")
    roles = [_tx_id("policy_id"), _ent_id("customer_id"), _metric("premium")]
    label, _ = detect_grain(fp, roles)
    assert label == "policy"


# ── Non-mutation ──────────────────────────────────────────────────────────────

def test_does_not_mutate_column_roles():
    fp = _fp(dataset_shape="snapshot")
    roles = [_tx_id("order_id"), _ent_id("customer_id")]
    original = [
        ColumnSemanticRole(**r.model_dump()) for r in roles
    ]
    detect_grain(fp, roles)
    for before, after in zip(original, roles):
        assert before.model_dump() == after.model_dump()


# ── Return type ───────────────────────────────────────────────────────────────

def test_returns_tuple_of_str_and_float():
    fp = _fp()
    roles = [_metric("x")]
    result = detect_grain(fp, roles)
    assert isinstance(result, tuple)
    assert len(result) == 2
    assert isinstance(result[0], str)
    assert isinstance(result[1], float)


def test_grain_label_is_valid_schema_value():
    from app.schemas.pre_analysis import PreAnalysisProfile
    fp = DatasetFingerprint(row_count=10, column_count=2, dataset_shape="snapshot")
    roles = [_tx_id("order_id")]
    label, conf = detect_grain(fp, roles)
    # Should not raise ValidationError
    profile = PreAnalysisProfile(
        fingerprint=fp,
        grain_label=label,
        grain_confidence=conf,
        generated_at="2026-05-13T00:00:00Z",
    )
    assert profile.grain_label == label
