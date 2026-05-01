from __future__ import annotations

import pandas as pd

from app.services.analysis.domain import (
    DomainInsightPack,
    DOMAIN_PACKS,
    SnapshotFinanceInsightPack,
    get_domain_pack,
    get_suppression_keys,
    run_domain_pack,
)
from app.services.dataset_context import (
    DatasetContext,
    FINANCIAL_MARKETS_SNAPSHOT,
    FINANCIAL_MARKETS_TIMESERIES,
    GENERIC_TABULAR,
)


def _snapshot_context() -> DatasetContext:
    return DatasetContext(
        dataset_type=FINANCIAL_MARKETS_SNAPSHOT,
        confidence=0.9,
        semantic_roles={"ticker": "asset_id", "ytd_return": "return_period"},
    )


def _generic_context() -> DatasetContext:
    return DatasetContext(dataset_type=GENERIC_TABULAR, confidence=1.0)


def _timeseries_context() -> DatasetContext:
    return DatasetContext(dataset_type=FINANCIAL_MARKETS_TIMESERIES, confidence=0.9)


def test_snapshot_pack_registered():
    assert FINANCIAL_MARKETS_SNAPSHOT in DOMAIN_PACKS
    assert isinstance(DOMAIN_PACKS[FINANCIAL_MARKETS_SNAPSHOT], SnapshotFinanceInsightPack)


def test_snapshot_pack_dataset_type():
    assert SnapshotFinanceInsightPack.dataset_type == FINANCIAL_MARKETS_SNAPSHOT


def test_get_domain_pack_snapshot_returns_real_pack():
    pack = get_domain_pack(FINANCIAL_MARKETS_SNAPSHOT)
    assert isinstance(pack, SnapshotFinanceInsightPack)


def test_get_domain_pack_unknowns_return_none():
    assert get_domain_pack(FINANCIAL_MARKETS_TIMESERIES) is None
    assert get_domain_pack(GENERIC_TABULAR) is None
    assert get_domain_pack("unknown") is None


def test_run_domain_pack_safe_on_empty_df():
    assert isinstance(run_domain_pack(pd.DataFrame(), _snapshot_context()), list)


def test_run_domain_pack_unknown_context_safe():
    ctx = DatasetContext(dataset_type="no_such_domain", confidence=1.0)
    assert run_domain_pack(pd.DataFrame(), ctx) == []


def test_suppression_keys_default_empty():
    assert get_suppression_keys(_snapshot_context()) == set()
    assert get_suppression_keys(_generic_context()) == set()
    assert get_suppression_keys(_timeseries_context()) == set()


def test_base_pack_defaults():
    pack = DomainInsightPack()
    assert pack.run(pd.DataFrame(), _generic_context()) == []
    assert pack.suppression_keys(_generic_context()) == set()
