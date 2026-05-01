from __future__ import annotations

import pandas as pd

from app.services.analysis.domain import SnapshotFinanceInsightPack, get_domain_pack
from app.services.dataset_context import DatasetContext, FINANCIAL_MARKETS_SNAPSHOT


REQUIRED_FIELDS = {"type", "title", "finding", "severity", "confidence", "evidence", "action"}


def _context(roles: dict[str, str]) -> DatasetContext:
    return DatasetContext(dataset_type=FINANCIAL_MARKETS_SNAPSHOT, confidence=0.9, semantic_roles=roles)


def _valid_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "ticker": ["AAA", "BBB", "CCC", "DDD", "EEE"],
            "ytd_return": [0.21, -0.13, 0.34, -0.25, 0.08],
        }
    )


def test_pack_registered_for_snapshot():
    assert isinstance(get_domain_pack(FINANCIAL_MARKETS_SNAPSHOT), SnapshotFinanceInsightPack)


def test_run_returns_two_insights_for_valid_snapshot_df():
    pack = SnapshotFinanceInsightPack()
    insights = pack.run(_valid_df(), _context({"ticker": "asset_id", "ytd_return": "return_period"}))
    assert len(insights) == 2
    assert {i["title"] for i in insights} == {"Top return leaders", "Largest return laggards"}


def test_leaders_names_top_assets_correctly():
    pack = SnapshotFinanceInsightPack()
    insights = pack.run(_valid_df(), _context({"ticker": "asset_id", "ytd_return": "return_period"}))
    leaders = next(i for i in insights if i["title"] == "Top return leaders")
    assert "CCC" in leaders["finding"] and "AAA" in leaders["finding"] and "EEE" in leaders["finding"]


def test_laggards_names_bottom_assets_correctly():
    pack = SnapshotFinanceInsightPack()
    insights = pack.run(_valid_df(), _context({"ticker": "asset_id", "ytd_return": "return_period"}))
    laggards = next(i for i in insights if i["title"] == "Largest return laggards")
    assert "DDD" in laggards["finding"] and "BBB" in laggards["finding"] and "EEE" in laggards["finding"]


def test_no_insight_without_return_period_role():
    pack = SnapshotFinanceInsightPack()
    insights = pack.run(_valid_df(), _context({"ticker": "asset_id"}))
    assert insights == []


def test_no_insight_with_fewer_than_three_valid_returns():
    pack = SnapshotFinanceInsightPack()
    df = pd.DataFrame({"ticker": ["A", "B", "C"], "ytd_return": [0.1, None, "x"]})
    insights = pack.run(df, _context({"ticker": "asset_id", "ytd_return": "return_period"}))
    assert insights == []


def test_pack_never_raises_on_empty_dataframe():
    pack = SnapshotFinanceInsightPack()
    insights = pack.run(pd.DataFrame(), _context({}))
    assert insights == []


def test_all_insights_include_required_fields():
    pack = SnapshotFinanceInsightPack()
    insights = pack.run(_valid_df(), _context({"ticker": "asset_id", "ytd_return": "return_period"}))
    assert insights
    for insight in insights:
        assert REQUIRED_FIELDS.issubset(set(insight))


def test_no_buy_or_sell_language():
    pack = SnapshotFinanceInsightPack()
    insights = pack.run(_valid_df(), _context({"ticker": "asset_id", "ytd_return": "return_period"}))
    combined = " ".join(f"{ins['finding']} {ins.get('action', '')}".lower() for ins in insights)
    assert "buy" not in combined
    assert "sell" not in combined
