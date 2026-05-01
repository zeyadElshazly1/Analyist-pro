"""Report Builder draft behaviour — executive summary (75A) and default insight selection (75B)."""

from __future__ import annotations

import re

import pytest

from app.services.dataset_context.schema import FINANCIAL_MARKETS_SNAPSHOT, GENERIC_TABULAR
from app.services.reporting.default_draft import (
    select_default_insight_selection,
    select_default_insight_selection_for_result,
)
from app.services.reporting.executive_summary_draft import (
    build_fallback_executive_summary,
    build_financial_snapshot_executive_summary,
)


def _ds_context_snapshot() -> dict:
    return {
        "dataset_type": FINANCIAL_MARKETS_SNAPSHOT,
        "confidence": 0.9,
        "matched_signals": ("return_period",),
        "semantic_roles": {},
        "warnings": [],
    }


def _snapshot_result(
    *,
    narrative: str = "",
    warnings: tuple[str, ...] | None = None,
) -> dict:
    """Minimal analysis payload shaped like stored result_json."""
    w = warnings if warnings is not None else ()
    return {
        "narrative": narrative,
        "dataset_summary": {
            "rows": 55,
            "columns": 14,
            "numeric_cols": 8,
            "categorical_cols": 4,
            "dataset_context": {
                "dataset_type": FINANCIAL_MARKETS_SNAPSHOT,
                "confidence": 0.88,
                "matched_signals": ("return_period",),
                "semantic_roles": {
                    "ticker": "asset_id",
                    "asset_class": "asset_class",
                    "sector": "sector",
                    "ytd_return": "return_period",
                    "volatility": "volatility",
                },
                "warnings": list(w),
            },
        },
        "health_result": {"health_score": {"grade": "B", "total_score": 78}},
        "cleaning_result": {"cleaning_summary": {"steps_applied": 0}},
        "insight_results": [
            {
                "domain": FINANCIAL_MARKETS_SNAPSHOT,
                "title": "Top return leaders",
                "finding": "NVDA ranks first by year-to-date return within the trimmed universe snapshot.",
                "severity": "medium",
            },
            {
                "domain": FINANCIAL_MARKETS_SNAPSHOT,
                "title": "Largest return laggards",
                "finding": "The bottom cohort posts negative trailing returns clustered around the −12% zone.",
                "severity": "medium",
            },
            {
                "domain": FINANCIAL_MARKETS_SNAPSHOT,
                "title": "Highest volatility assets",
                "finding": "A handful of Crypto names dominates annualized dispersion bands.",
                "severity": "medium",
            },
            {
                "domain": FINANCIAL_MARKETS_SNAPSHOT,
                "title": "Best risk-adjusted performers",
                "finding": "Several large-cap ETFs show the strongest Sharpe-style ratios in-sample.",
                "severity": "medium",
            },
            {
                "domain": FINANCIAL_MARKETS_SNAPSHOT,
                "title": "Asset classes show different return profiles",
                "finding": "Equity sleeves average higher dispersion than Bond sleeves in this upload.",
                "severity": "low",
            },
            {
                "domain": FINANCIAL_MARKETS_SNAPSHOT,
                "title": "Sectors show different return profiles",
                "finding": "Technology sector means sit above Utilities in trailing return space.",
                "severity": "low",
            },
            {
                "domain": FINANCIAL_MARKETS_SNAPSHOT,
                "title": "Highest analyst-implied upside",
                "finding": "Consensus uplift ranges from flat to modestly positive for screened names.",
                "severity": "low",
            },
            {
                "domain": FINANCIAL_MARKETS_SNAPSHOT,
                "title": "Assets cluster at different 52-week positions",
                "finding": "Names span the breadth of the trailing 52-week corridor without pinning to a single hinge.",
                "severity": "low",
            },
        ],
    }


def test_financial_snapshot_fallback_is_finance_structured_and_includes_findings() -> None:
    res = _snapshot_result(narrative="Some short fluff.")
    text = build_fallback_executive_summary(res)
    low = text.lower()
    assert "financial market snapshot" in low
    assert "nvda ranks first by year-to-date return" in low
    assert "bottom cohort posts negative trailing returns" in low
    assert "screening analysis, not investment advice" in low


@pytest.mark.parametrize(
    "bad_word",
    ["buy", "sell", "hold", "undervalued", "overvalued"],
)
def test_finance_summary_avoids_sales_language(bad_word: str) -> None:
    res = _snapshot_result()
    text = build_fallback_executive_summary(res).lower()
    assert re.search(rf"\b{re.escape(bad_word)}\b", text) is None


def test_finance_fallback_includes_mixed_asset_warning_when_present() -> None:
    res = _snapshot_result(
        warnings=(
            "This dataset contains mixed asset classes. "
            "Risk and return metrics should be interpreted with caution across classes.",
        ),
    )
    text = build_fallback_executive_summary(res).lower()
    assert "because the dataset mixes asset classes" in text
    assert "compare results within similar asset" in text


def test_generic_structured_path_when_not_snapshot_domain() -> None:
    """Generic payload stays on structured business summary — not finance opener."""
    telco = {
        "narrative": "",
        "dataset_summary": {
            "rows": 7000,
            "columns": 20,
            "numeric_cols": 4,
            "dataset_context": {
                "dataset_type": GENERIC_TABULAR,
                "confidence": 1.0,
                "matched_signals": [],
                "semantic_roles": {"x": "unknown"},
                "warnings": [],
            },
        },
        "health_score": {"total": 70},
        "insight_results": [
            {"title": "Churn concentrates in month-to-month plans", "severity": "high"},
        ],
        "cleaning_result": {},
    }
    text = build_fallback_executive_summary(telco).lower()
    assert "financial market snapshot" not in text
    assert "churn" in text or "month-to-month" in text


def test_snapshot_always_finance_builder_when_narrative_weak() -> None:
    res = _snapshot_result(narrative="Too short.")
    out = build_fallback_executive_summary(res)
    assert "financial market snapshot" in out.lower()


def test_snapshot_reuses_finance_rich_pipeline_narrative() -> None:
    rich = (
        "This cross-sectional pass highlights dispersion in volatility and Sharpe-ranked sleeves "
        "when clustered by sector, with return gaps worth desk review before reallocating workloads. "
        "Analyst overlays and multi-horizon benchmarks should be refreshed before staking operational capacity."
    )
    res = _snapshot_result(narrative=rich)
    assert build_fallback_executive_summary(res) == rich[:8000]


def test_weak_long_generic_narrative_still_replaced_for_snapshot() -> None:
    fluff = (
        "This dataset provides valuable insights and important patterns across segments. "
        "We should delve deeper into comprehensive overview of behavior. "
    ) * 4
    assert len(fluff) > 160
    res = _snapshot_result(narrative=fluff)
    out = build_fallback_executive_summary(res).lower()
    assert "valuable insights" not in out
    assert "financial market snapshot" in out


def _finance_title_insight(insight_id: str, title: str) -> dict:
    return {
        "domain": FINANCIAL_MARKETS_SNAPSHOT,
        "title": title,
        "finding": ".",
        "severity": "medium",
        "insight_id": insight_id,
    }


def test_finance_selection_prioritizes_titles_despite_payload_order() -> None:
    res = {
        "dataset_summary": {"rows": 1, "dataset_context": _ds_context_snapshot()},
        "insight_results": [
            _finance_title_insight("id_sectors", "Sectors show different return profiles"),
            _finance_title_insight("id_top", "Top return leaders"),
            _finance_title_insight("id_lag", "Largest return laggards"),
            _finance_title_insight("id_vol", "Highest volatility assets"),
        ],
    }
    sel = select_default_insight_selection_for_result(res)
    assert sel == ["id_top", "id_lag", "id_vol", "id_sectors"]


def test_finance_selection_caps_at_five_prefers_priority_titles() -> None:
    priority = (
        "Top return leaders",
        "Largest return laggards",
        "Highest volatility assets",
        "Best risk-adjusted performers",
        "Asset classes show different return profiles",
        "Sectors show different return profiles",
        "Highest analyst-implied upside",
        "Assets cluster at different 52-week positions",
        "Price fields are highly overlapping",
    )
    res = {
        "dataset_summary": {"rows": 1, "dataset_context": _ds_context_snapshot()},
        "insight_results": [
            _finance_title_insight(f"k{n}", priority[n])
            for n in (8, 0, 7, 1, 6, 2, 5, 3, 4)
        ],
    }
    sel = select_default_insight_selection_for_result(res)
    assert len(sel) == 5
    assert sel == ["k0", "k1", "k2", "k3", "k4"]


def test_finance_selection_uses_legacy_index_when_missing_insight_id() -> None:
    res = {
        "dataset_summary": {"rows": 1, "dataset_context": _ds_context_snapshot()},
        "insights": [
            {"title": "Other telemetry", "severity": "high"},
            {"domain": FINANCIAL_MARKETS_SNAPSHOT, "title": "Top return leaders"},
            {"domain": FINANCIAL_MARKETS_SNAPSHOT, "title": "Largest return laggards"},
            {"domain": FINANCIAL_MARKETS_SNAPSHOT, "title": "Highest volatility assets"},
        ],
    }
    sel = select_default_insight_selection_for_result(res)
    assert sel == [1, 2, 3]


def test_finance_selection_fills_short_stack_from_generic_without_duplicates() -> None:
    res = {
        "dataset_summary": {"rows": 1, "dataset_context": _ds_context_snapshot()},
        "insight_results": [
            {
                "domain": FINANCIAL_MARKETS_SNAPSHOT,
                "title": "Highest volatility assets",
                "insight_id": "solo_fin",
                "severity": "medium",
            },
            {
                "insight_id": "g1",
                "title": "Generic high one",
                "severity": "high",
                "category": "outlier",
                "report_safe": True,
            },
            {
                "insight_id": "g2",
                "title": "Generic high two",
                "severity": "high",
                "category": "correlation",
                "report_safe": True,
            },
        ],
    }
    sel = select_default_insight_selection_for_result(res)
    assert sel[0] == "solo_fin"
    assert len(sel) == 3
    assert set(sel) == {"solo_fin", "g1", "g2"}


def test_generic_result_delegates_to_original_selector() -> None:
    raw = [
        {"insight_id": "a", "report_safe": True, "severity": "medium", "category": "correlation"},
        {"insight_id": "b", "report_safe": True, "severity": "high", "category": "outlier"},
        {"insight_id": "c", "report_safe": True, "severity": "low", "category": "trend"},
    ]
    result = {
        "dataset_summary": {
            "rows": 50,
            "dataset_context": {
                "dataset_type": GENERIC_TABULAR,
                "confidence": 1.0,
                "warnings": [],
            },
        },
        "insight_results": raw,
    }
    assert select_default_insight_selection_for_result(result) == select_default_insight_selection(raw)


def test_direct_financial_builder_surfaces_price_overlap_insight() -> None:
    base = _snapshot_result()
    ins = list(base["insight_results"])
    ins.append(
        {
            "domain": FINANCIAL_MARKETS_SNAPSHOT,
            "title": "Price fields are highly overlapping",
            "finding": "Open, high, low, and live price columns move in lockstep; correlations are not independent.",
            "severity": "medium",
        },
    )
    base["insight_results"] = ins
    text = build_financial_snapshot_executive_summary(base).lower()
    assert "price fields are highly overlapping" in text
