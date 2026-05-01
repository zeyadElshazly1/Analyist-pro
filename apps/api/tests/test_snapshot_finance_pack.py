from __future__ import annotations

import re

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


def _full_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "ticker": ["AAA", "BBB", "CCC", "DDD", "EEE"],
            "ytd_return": [0.21, -0.13, 0.34, -0.25, 0.08],
            "volatility_1y_ann": [0.22, 0.45, 0.30, 0.12, 0.41],
            "sharpe_1y": [1.21, -0.10, 1.55, 0.23, 1.31],
        }
    )


def _full_roles() -> dict[str, str]:
    return {
        "ticker": "asset_id",
        "ytd_return": "return_period",
        "volatility_1y_ann": "volatility",
        "sharpe_1y": "sharpe_ratio",
    }


def _full_df_with_asset_class() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "ticker": [f"T{i}" for i in range(9)],
            "asset_class": ["Crypto"] * 3 + ["Equity"] * 3 + ["Bond"] * 3,
            "return_1y_pct": [
                0.184,
                0.190,
                0.180,
                0.041,
                0.043,
                0.042,
                0.085,
                0.088,
                0.086,
            ],
            "volatility_1y_ann": [0.22, 0.45, 0.30, 0.12, 0.41, 0.35, 0.28, 0.31, 0.29],
            "sharpe_1y": [1.21, -0.10, 1.55, 0.23, 1.31, 0.9, 1.0, 1.05, 1.02],
        }
    )


def _full_roles_with_asset_class() -> dict[str, str]:
    return {
        "ticker": "asset_id",
        "return_1y_pct": "return_period",
        "asset_class": "asset_class",
        "volatility_1y_ann": "volatility",
        "sharpe_1y": "sharpe_ratio",
    }


def _full_df_with_sector_and_asset_class() -> pd.DataFrame:
    base = _full_df_with_asset_class().copy()
    base["sector"] = ["Technology"] * 3 + ["Energy"] * 3 + ["Healthcare"] * 3
    return base


def _full_roles_with_sector_and_asset_class() -> dict[str, str]:
    r = dict(_full_roles_with_asset_class())
    r["sector"] = "sector"
    return r


def _full_df_with_analyst_sector_and_asset_class() -> pd.DataFrame:
    df = _full_df_with_sector_and_asset_class().copy()
    df["analyst_upside_pct"] = [0.152, 0.183, 0.241, -0.05, -0.04, -0.06, 0.08, 0.07, 0.065]
    return df


def _full_roles_with_analyst_sector_and_asset_class() -> dict[str, str]:
    r = dict(_full_roles_with_sector_and_asset_class())
    r["analyst_upside_pct"] = "analyst_upside"
    return r


def _full_df_with_52w_analyst_sector_and_asset_class() -> pd.DataFrame:
    df = _full_df_with_analyst_sector_and_asset_class().copy()
    df["pct_of_52w_high"] = [
        0.98,
        0.95,
        0.90,
        0.55,
        0.52,
        0.50,
        0.20,
        0.12,
        0.10,
    ]
    return df


def _full_roles_with_52w_analyst_sector_and_asset_class() -> dict[str, str]:
    r = dict(_full_roles_with_analyst_sector_and_asset_class())
    r["pct_of_52w_high"] = "position_52w"
    return r


def test_run_returns_eight_insights_when_52w_analyst_sector_asset_class_and_metrics_present():
    pack = SnapshotFinanceInsightPack()
    insights = pack.run(
        _full_df_with_52w_analyst_sector_and_asset_class(),
        _context(_full_roles_with_52w_analyst_sector_and_asset_class()),
    )
    assert len(insights) == 8
    assert {i["title"] for i in insights} == {
        "Top return leaders",
        "Largest return laggards",
        "Highest volatility assets",
        "Best risk-adjusted performers",
        "Asset classes show different return profiles",
        "Sectors show different return profiles",
        "Highest analyst-implied upside",
        "Assets cluster at different 52-week positions",
    }


def test_52w_position_insight_present():
    pack = SnapshotFinanceInsightPack()
    insights = pack.run(
        _full_df_with_52w_analyst_sector_and_asset_class(),
        _context(_full_roles_with_52w_analyst_sector_and_asset_class()),
    )
    assert "Assets cluster at different 52-week positions" in {i["title"] for i in insights}


def test_52w_position_finding_names_near_high_and_low_assets():
    pack = SnapshotFinanceInsightPack()
    insights = pack.run(
        _full_df_with_52w_analyst_sector_and_asset_class(),
        _context(_full_roles_with_52w_analyst_sector_and_asset_class()),
    )
    w = next(i for i in insights if i["title"] == "Assets cluster at different 52-week positions")
    assert "T0" in w["finding"] and "T1" in w["finding"]
    assert "T8" in w["finding"] and "T7" in w["finding"]


def test_52w_position_evidence_structure():
    pack = SnapshotFinanceInsightPack()
    insights = pack.run(
        _full_df_with_52w_analyst_sector_and_asset_class(),
        _context(_full_roles_with_52w_analyst_sector_and_asset_class()),
    )
    ev = next(i for i in insights if i["title"] == "Assets cluster at different 52-week positions")["evidence"]
    assert ev["selected_52w_position_column"] == "pct_of_52w_high"
    assert len(ev["near_high_assets"]) == 3
    assert len(ev["low_position_assets"]) == 3
    assert "valid_row_count" in ev


def test_no_52w_insight_when_position_role_missing():
    pack = SnapshotFinanceInsightPack()
    roles = {
        k: v
        for k, v in _full_roles_with_52w_analyst_sector_and_asset_class().items()
        if k != "pct_of_52w_high"
    }
    insights = pack.run(_full_df_with_52w_analyst_sector_and_asset_class(), _context(roles))
    assert "Assets cluster at different 52-week positions" not in {i["title"] for i in insights}
    assert len(insights) == 7


def test_no_52w_insight_when_fewer_than_three_valid_rows():
    pack = SnapshotFinanceInsightPack()
    df = _full_df_with_52w_analyst_sector_and_asset_class().copy()
    df["pct_of_52w_high"] = [0.9, None, "x", None, None, None, None, None, None]
    insights = pack.run(df, _context(_full_roles_with_52w_analyst_sector_and_asset_class()))
    assert "Assets cluster at different 52-week positions" not in {i["title"] for i in insights}


def test_position_52w_column_priority_prefers_pct_of_52w_high():
    pack = SnapshotFinanceInsightPack()
    df = _full_df_with_52w_analyst_sector_and_asset_class().copy()
    df["week52_position"] = df["pct_of_52w_high"] * 0.5
    roles = dict(_full_roles_with_52w_analyst_sector_and_asset_class())
    roles["week52_position"] = "position_52w"
    insights = pack.run(df, _context(roles))
    ev = next(i for i in insights if i["title"] == "Assets cluster at different 52-week positions")[
        "evidence"
    ]
    assert ev["selected_52w_position_column"] == "pct_of_52w_high"


def test_run_returns_seven_insights_when_analyst_sector_asset_class_and_full_metrics_present():
    pack = SnapshotFinanceInsightPack()
    insights = pack.run(
        _full_df_with_analyst_sector_and_asset_class(),
        _context(_full_roles_with_analyst_sector_and_asset_class()),
    )
    assert len(insights) == 7
    assert {i["title"] for i in insights} == {
        "Top return leaders",
        "Largest return laggards",
        "Highest volatility assets",
        "Best risk-adjusted performers",
        "Asset classes show different return profiles",
        "Sectors show different return profiles",
        "Highest analyst-implied upside",
    }


def test_analyst_upside_insight_present():
    pack = SnapshotFinanceInsightPack()
    insights = pack.run(
        _full_df_with_analyst_sector_and_asset_class(),
        _context(_full_roles_with_analyst_sector_and_asset_class()),
    )
    assert "Highest analyst-implied upside" in {i["title"] for i in insights}


def test_analyst_upside_names_top_three_tickers():
    pack = SnapshotFinanceInsightPack()
    insights = pack.run(
        _full_df_with_analyst_sector_and_asset_class(),
        _context(_full_roles_with_analyst_sector_and_asset_class()),
    )
    up = next(i for i in insights if i["title"] == "Highest analyst-implied upside")
    assert "T2" in up["finding"] and "T1" in up["finding"] and "T0" in up["finding"]


def test_analyst_upside_evidence_keys():
    pack = SnapshotFinanceInsightPack()
    insights = pack.run(
        _full_df_with_analyst_sector_and_asset_class(),
        _context(_full_roles_with_analyst_sector_and_asset_class()),
    )
    ev = next(i for i in insights if i["title"] == "Highest analyst-implied upside")["evidence"]
    assert ev["selected_analyst_upside_column"] == "analyst_upside_pct"
    assert "top_values" in ev and len(ev["top_values"]) == 3
    assert "median_analyst_upside" in ev


def test_no_analyst_upside_insight_when_role_missing():
    pack = SnapshotFinanceInsightPack()
    roles = {
        k: v
        for k, v in _full_roles_with_analyst_sector_and_asset_class().items()
        if k != "analyst_upside_pct"
    }
    insights = pack.run(_full_df_with_analyst_sector_and_asset_class(), _context(roles))
    assert "Highest analyst-implied upside" not in {i["title"] for i in insights}
    assert len(insights) == 6


def test_no_analyst_upside_insight_when_fewer_than_three_valid_rows():
    pack = SnapshotFinanceInsightPack()
    df = _full_df_with_analyst_sector_and_asset_class().copy()
    df["analyst_upside_pct"] = [0.10, None, "x", None, None, None, None, None, None]
    insights = pack.run(df, _context(_full_roles_with_analyst_sector_and_asset_class()))
    assert "Highest analyst-implied upside" not in {i["title"] for i in insights}


def test_no_analyst_upside_insight_when_top_three_not_positive():
    pack = SnapshotFinanceInsightPack()
    df = _full_df_with_analyst_sector_and_asset_class().copy()
    df["analyst_upside_pct"] = [-0.10, -0.11, -0.09, -0.20, -0.15, -0.08, -0.05, -0.06, -0.04]
    insights = pack.run(df, _context(_full_roles_with_analyst_sector_and_asset_class()))
    assert "Highest analyst-implied upside" not in {i["title"] for i in insights}


def test_analyst_upside_column_priority_prefers_analyst_upside_pct():
    pack = SnapshotFinanceInsightPack()
    df = _full_df_with_analyst_sector_and_asset_class().copy()
    df["generic_upside"] = df["analyst_upside_pct"] * 0.5
    roles = dict(_full_roles_with_analyst_sector_and_asset_class())
    roles["generic_upside"] = "analyst_upside"
    insights = pack.run(df, _context(roles))
    ev = next(i for i in insights if i["title"] == "Highest analyst-implied upside")["evidence"]
    assert ev["selected_analyst_upside_column"] == "analyst_upside_pct"


def test_pack_registered_for_snapshot():
    assert isinstance(get_domain_pack(FINANCIAL_MARKETS_SNAPSHOT), SnapshotFinanceInsightPack)


def test_run_returns_six_insights_when_sector_asset_class_and_full_metrics_present():
    pack = SnapshotFinanceInsightPack()
    insights = pack.run(
        _full_df_with_sector_and_asset_class(),
        _context(_full_roles_with_sector_and_asset_class()),
    )
    assert len(insights) == 6
    assert {i["title"] for i in insights} == {
        "Top return leaders",
        "Largest return laggards",
        "Highest volatility assets",
        "Best risk-adjusted performers",
        "Asset classes show different return profiles",
        "Sectors show different return profiles",
    }


def test_sector_comparison_insight_present():
    pack = SnapshotFinanceInsightPack()
    insights = pack.run(
        _full_df_with_sector_and_asset_class(),
        _context(_full_roles_with_sector_and_asset_class()),
    )
    assert "Sectors show different return profiles" in {i["title"] for i in insights}


def test_sector_comparison_names_top_and_bottom_sectors():
    pack = SnapshotFinanceInsightPack()
    insights = pack.run(
        _full_df_with_sector_and_asset_class(),
        _context(_full_roles_with_sector_and_asset_class()),
    )
    sec = next(i for i in insights if i["title"] == "Sectors show different return profiles")
    assert "Technology" in sec["finding"] and "Energy" in sec["finding"]
    assert "1Y return" in sec["finding"]


def test_sector_evidence_includes_columns_and_group_structures():
    pack = SnapshotFinanceInsightPack()
    insights = pack.run(
        _full_df_with_sector_and_asset_class(),
        _context(_full_roles_with_sector_and_asset_class()),
    )
    ev = next(i for i in insights if i["title"] == "Sectors show different return profiles")["evidence"]
    assert ev["selected_sector_column"] == "sector"
    assert len(ev["top_groups"]) >= 2
    assert isinstance(ev["bottom_group"], dict)
    assert "sector" in ev["bottom_group"]
    assert ev["group_count"] >= 2


def test_no_sector_insight_when_sector_role_missing():
    pack = SnapshotFinanceInsightPack()
    roles = {k: v for k, v in _full_roles_with_sector_and_asset_class().items() if k != "sector"}
    insights = pack.run(_full_df_with_sector_and_asset_class(), _context(roles))
    assert "Sectors show different return profiles" not in {i["title"] for i in insights}
    assert len(insights) == 5


def test_no_sector_insight_when_return_period_role_missing():
    pack = SnapshotFinanceInsightPack()
    roles = {k: v for k, v in _full_roles_with_sector_and_asset_class().items() if k != "return_1y_pct"}
    insights = pack.run(_full_df_with_sector_and_asset_class(), _context(roles))
    assert "Sectors show different return profiles" not in {i["title"] for i in insights}
    assert {i["title"] for i in insights} == {
        "Highest volatility assets",
        "Best risk-adjusted performers",
    }


def test_no_sector_insight_when_fewer_than_two_qualified_sector_groups():
    pack = SnapshotFinanceInsightPack()
    df = pd.DataFrame(
        {
            "ticker": ["A", "B", "C", "D", "E"],
            "sector": ["Technology", "Technology", "Technology", "Technology", "Energy"],
            "asset_class": ["Crypto"] * 5,
            "return_1y_pct": [0.10, 0.11, 0.12, 0.13, 0.02],
            "volatility_1y_ann": [0.2, 0.21, 0.22, 0.23, 0.15],
            "sharpe_1y": [1.0, 1.1, 1.2, 1.3, 0.5],
        }
    )
    insights = pack.run(df, _context(_full_roles_with_sector_and_asset_class()))
    assert "Sectors show different return profiles" not in {i["title"] for i in insights}


def test_run_returns_two_insights_when_only_return_columns_present():
    pack = SnapshotFinanceInsightPack()
    insights = pack.run(_valid_df(), _context({"ticker": "asset_id", "ytd_return": "return_period"}))
    assert len(insights) == 2
    assert {i["title"] for i in insights} == {"Top return leaders", "Largest return laggards"}


def test_run_returns_five_insights_when_asset_class_and_full_metrics_present():
    pack = SnapshotFinanceInsightPack()
    insights = pack.run(_full_df_with_asset_class(), _context(_full_roles_with_asset_class()))
    assert len(insights) == 5
    assert {i["title"] for i in insights} == {
        "Top return leaders",
        "Largest return laggards",
        "Highest volatility assets",
        "Best risk-adjusted performers",
        "Asset classes show different return profiles",
    }


def test_asset_class_comparison_insight_present():
    pack = SnapshotFinanceInsightPack()
    insights = pack.run(_full_df_with_asset_class(), _context(_full_roles_with_asset_class()))
    titles = {i["title"] for i in insights}
    assert "Asset classes show different return profiles" in titles


def test_asset_class_comparison_names_top_and_bottom_classes():
    pack = SnapshotFinanceInsightPack()
    insights = pack.run(_full_df_with_asset_class(), _context(_full_roles_with_asset_class()))
    ac = next(i for i in insights if i["title"] == "Asset classes show different return profiles")
    assert "Crypto" in ac["finding"] and "Equity" in ac["finding"]
    assert "1Y return" in ac["finding"]


def test_asset_class_evidence_includes_columns_and_group_structures():
    pack = SnapshotFinanceInsightPack()
    insights = pack.run(_full_df_with_asset_class(), _context(_full_roles_with_asset_class()))
    ev = next(i for i in insights if i["title"] == "Asset classes show different return profiles")[
        "evidence"
    ]
    assert ev["selected_asset_class_column"] == "asset_class"
    assert "top_groups" in ev and len(ev["top_groups"]) >= 2
    assert "bottom_group" in ev
    assert isinstance(ev["bottom_group"], dict)
    assert "asset_class" in ev["bottom_group"]
    assert ev["group_count"] >= 2


def test_no_asset_class_insight_when_asset_class_role_missing():
    pack = SnapshotFinanceInsightPack()
    roles = {k: v for k, v in _full_roles_with_asset_class().items() if k != "asset_class"}
    insights = pack.run(_full_df_with_asset_class(), _context(roles))
    assert "Asset classes show different return profiles" not in {i["title"] for i in insights}
    assert len(insights) == 4


def test_no_asset_class_insight_when_return_period_role_missing():
    pack = SnapshotFinanceInsightPack()
    roles = {k: v for k, v in _full_roles_with_asset_class().items() if k != "return_1y_pct"}
    insights = pack.run(_full_df_with_asset_class(), _context(roles))
    assert "Asset classes show different return profiles" not in {i["title"] for i in insights}
    assert {i["title"] for i in insights} == {
        "Highest volatility assets",
        "Best risk-adjusted performers",
    }


def test_no_asset_class_insight_when_fewer_than_two_qualified_groups():
    pack = SnapshotFinanceInsightPack()
    df = pd.DataFrame(
        {
            "ticker": ["A", "B", "C", "D", "E"],
            "asset_class": ["Crypto", "Crypto", "Crypto", "Crypto", "Equity"],
            "return_1y_pct": [0.10, 0.11, 0.12, 0.13, 0.02],
            "volatility_1y_ann": [0.2, 0.21, 0.22, 0.23, 0.15],
            "sharpe_1y": [1.0, 1.1, 1.2, 1.3, 0.5],
        }
    )
    roles = {
        "ticker": "asset_id",
        "return_1y_pct": "return_period",
        "asset_class": "asset_class",
        "volatility_1y_ann": "volatility",
        "sharpe_1y": "sharpe_ratio",
    }
    insights = pack.run(df, _context(roles))
    assert "Asset classes show different return profiles" not in {i["title"] for i in insights}


def test_run_returns_four_insights_when_return_volatility_sharpe_present():
    pack = SnapshotFinanceInsightPack()
    insights = pack.run(_full_df(), _context(_full_roles()))
    assert len(insights) == 4
    assert {i["title"] for i in insights} == {
        "Top return leaders",
        "Largest return laggards",
        "Highest volatility assets",
        "Best risk-adjusted performers",
    }


def test_volatility_leaders_names_top_assets_correctly():
    pack = SnapshotFinanceInsightPack()
    insights = pack.run(_full_df(), _context(_full_roles()))
    volatility = next(i for i in insights if i["title"] == "Highest volatility assets")
    assert "BBB" in volatility["finding"] and "EEE" in volatility["finding"] and "CCC" in volatility["finding"]


def test_volatility_insight_includes_median_in_evidence():
    pack = SnapshotFinanceInsightPack()
    insights = pack.run(_full_df(), _context(_full_roles()))
    volatility = next(i for i in insights if i["title"] == "Highest volatility assets")
    assert "median_volatility" in volatility["evidence"]


def test_sharpe_leaders_names_top_assets_correctly():
    pack = SnapshotFinanceInsightPack()
    insights = pack.run(_full_df(), _context(_full_roles()))
    sharpe = next(i for i in insights if i["title"] == "Best risk-adjusted performers")
    assert "CCC" in sharpe["finding"] and "EEE" in sharpe["finding"] and "AAA" in sharpe["finding"]


def test_no_volatility_insight_when_column_missing_from_roles():
    pack = SnapshotFinanceInsightPack()
    roles = dict(_full_roles())
    del roles["volatility_1y_ann"]
    insights = pack.run(_full_df(), _context(roles))
    assert "Highest volatility assets" not in {i["title"] for i in insights}
    assert len(insights) == 3


def test_no_sharpe_insight_when_column_missing_from_roles():
    pack = SnapshotFinanceInsightPack()
    roles = dict(_full_roles())
    del roles["sharpe_1y"]
    insights = pack.run(_full_df(), _context(roles))
    assert "Best risk-adjusted performers" not in {i["title"] for i in insights}
    assert len(insights) == 3


def test_no_volatility_insight_when_fewer_than_three_valid_numeric_rows():
    pack = SnapshotFinanceInsightPack()
    df = pd.DataFrame(
        {
            "ticker": ["A", "B", "C", "D"],
            "ytd_return": [0.1, 0.2, 0.3, 0.4],
            "volatility_1y_ann": [0.2, None, "x", 0.3],
            "sharpe_1y": [1.0, 1.1, 1.2, 1.3],
        }
    )
    insights = pack.run(df, _context(_full_roles()))
    assert "Highest volatility assets" not in {i["title"] for i in insights}


def test_no_sharpe_insight_when_fewer_than_three_valid_numeric_rows():
    pack = SnapshotFinanceInsightPack()
    df = pd.DataFrame(
        {
            "ticker": ["A", "B", "C", "D"],
            "ytd_return": [0.1, 0.2, 0.3, 0.4],
            "volatility_1y_ann": [0.2, 0.21, 0.22, 0.23],
            "sharpe_1y": [1.0, None, "x", 1.3],
        }
    )
    insights = pack.run(df, _context(_full_roles()))
    assert "Best risk-adjusted performers" not in {i["title"] for i in insights}


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
    for df, roles in (
        (_full_df(), _full_roles()),
        (_full_df_with_asset_class(), _full_roles_with_asset_class()),
        (_full_df_with_sector_and_asset_class(), _full_roles_with_sector_and_asset_class()),
        (_full_df_with_analyst_sector_and_asset_class(), _full_roles_with_analyst_sector_and_asset_class()),
        (_full_df_with_52w_analyst_sector_and_asset_class(), _full_roles_with_52w_analyst_sector_and_asset_class()),
    ):
        insights = pack.run(df, _context(roles))
        assert insights
        for insight in insights:
            assert REQUIRED_FIELDS.issubset(set(insight))


def test_no_forbidden_investment_advice_language():
    pack = SnapshotFinanceInsightPack()
    forb_substrings = (
        "buy",
        "sell",
        "undervalued",
        "overvalued",
        "investment advice",
        "recommendation",
    )
    rows = (
        (_full_df(), _full_roles()),
        (_full_df_with_asset_class(), _full_roles_with_asset_class()),
        (_full_df_with_sector_and_asset_class(), _full_roles_with_sector_and_asset_class()),
        (_full_df_with_analyst_sector_and_asset_class(), _full_roles_with_analyst_sector_and_asset_class()),
        (_full_df_with_52w_analyst_sector_and_asset_class(), _full_roles_with_52w_analyst_sector_and_asset_class()),
    )
    for df, roles in rows:
        insights = pack.run(df, _context(roles))
        combined = " ".join(
            f"{ins.get('title', '')} {ins['finding']} {ins.get('action', '')} "
            f"{ins.get('why_it_matters', '')}".lower()
            for ins in insights
        )
        for s in forb_substrings:
            assert s not in combined
        assert re.search(r"\bhold\b", combined) is None


def test_return_column_priority_prefers_1y_over_ytd():
    pack = SnapshotFinanceInsightPack()
    df = pd.DataFrame(
        {
            "sym": ["A", "B", "C", "D"],
            "ytd_return": [0.10, 0.20, 0.30, 0.40],
            "return_1y_pct": [0.50, 0.40, 0.30, 0.20],
            "volatility_1y_ann": [0.2, 0.21, 0.22, 0.23],
            "sharpe_1y": [1.0, 1.1, 1.2, 1.3],
        }
    )
    roles = {
        "sym": "asset_id",
        "ytd_return": "return_period",
        "return_1y_pct": "return_period",
        "volatility_1y_ann": "volatility",
        "sharpe_1y": "sharpe_ratio",
    }
    insights = pack.run(df, _context(roles))
    for ins in insights:
        ev = ins["evidence"]
        if "selected_return_column" in ev:
            assert ev["selected_return_column"] == "return_1y_pct"


def test_detectors_skip_when_fewer_than_three_valid_numeric_returns():
    pack = SnapshotFinanceInsightPack()
    df = pd.DataFrame(
        {
            "ticker": ["A", "B", "C"],
            "ytd_return": [0.1, None, "x"],
        }
    )
    assert pack.run(df, _context({"ticker": "asset_id", "ytd_return": "return_period"})) == []
