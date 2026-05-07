"""
Default Report Builder draft materialisation.

When a project has a finished analysis but no persisted ``ReportDraft`` yet,
``GET /reports/draft/{project_id}`` auto-creates a sensible starting draft:
executive summary text derived from ``result_json``, 3–5 recommended
findings, and—on ``financial_markets_snapshot`` / ``financial_markets_timeseries``
runs—chart picks when payloads already exist under standard chart keys on
``result_json``.
"""
from __future__ import annotations

from typing import Any

from app.services.analysis.domain.timeseries_finance import FINANCE_TS_PREMIUM_TITLE_ORDER
from app.services.dataset_context.schema import FINANCIAL_MARKETS_SNAPSHOT, FINANCIAL_MARKETS_TIMESERIES
from app.services.reporting.executive_summary_draft import build_fallback_executive_summary

# Chart gallery titles preferred on auto-draft (must match payloads under ``charts`` / etc.).
_FINANCE_SNAPSHOT_CHART_PRIORITY_TITLES: tuple[str, ...] = (
    "Top assets by return",
    "Risk vs return",
    "Average return by asset class",
    "Average return by sector",
    "Highest volatility assets",
    "Highest analyst-implied upside",
    "Assets by 52-week position",
    "Largest return laggards",
)


# Insight titles preferred on ``financial_markets_snapshot`` default draft selection.
_FINANCE_SNAPSHOT_PRIORITY_TITLES: tuple[str, ...] = (
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

# Panel OHLC history — must match TimeseriesFinanceInsightPack titles + overlap caveat.
_FINANCE_TS_INSIGHT_PRIORITY_TITLES: tuple[str, ...] = FINANCE_TS_PREMIUM_TITLE_ORDER + (
    "Price fields are highly overlapping",
)

# Stored chart titles from ``build_financial_timeseries_charts`` (Task 77A).
# Total return leaderboard covers cross-sectional winners/losers in one view.
_FINANCE_TS_CHART_PRIORITY_TITLES: tuple[str, ...] = (
    "Price trend by symbol",
    "Total return leaderboard",
    "Volatility leaderboard",
    "Drawdown chart",
    "Volume leaderboard",
    "Return distribution",
)


def _severity_rank(ins: dict) -> int:
    s = (ins.get("severity") or "").lower()
    return {"high": 0, "medium": 1, "low": 2}.get(s, 3)


def _is_dq_category(ins: dict) -> bool:
    cat = (ins.get("category") or "").lower()
    return cat in ("data_quality", "missing_pattern")


def _insight_key(idx: int, ins: dict) -> str | int:
    iid = ins.get("insight_id")
    if isinstance(iid, str) and iid:
        return iid
    return idx


def _chart_key(idx: int, chart: dict[str, Any]) -> str | int:
    for field in ("chart_id", "id"):
        v = chart.get(field)
        if isinstance(v, str) and v.strip():
            return v.strip()
        if isinstance(v, bool):
            continue
        if isinstance(v, int):
            return v
        if isinstance(v, float) and v == int(v):
            return int(v)
    return idx


def _chart_dicts_from_result(result_data: dict[str, Any]) -> list[dict[str, Any]]:
    if not isinstance(result_data, dict):
        return []
    for key in ("charts", "chart_results", "suggested_charts", "chart_gallery"):
        blk = result_data.get(key)
        if isinstance(blk, list):
            vals = [c for c in blk if isinstance(c, dict)]
            if vals:
                return vals
    return []


def select_default_insight_selection(raw: list[dict], *, min_sel: int = 3, max_sel: int = 5) -> list[str | int]:
    """Pick 3–5 insight keys (stable ``insight_id`` or legacy index) for a new draft."""
    if not raw:
        return []

    entries = list(enumerate(raw))
    has_any_safe = any(ins.get("report_safe") is True for _, ins in entries)

    picked: list[tuple[int, dict]] = []
    picked_idx: set[int] = set()

    def add_entry(i: int, ins: dict) -> None:
        if i not in picked_idx and len(picked) < max_sel:
            picked_idx.add(i)
            picked.append((i, ins))

    if has_any_safe:
        for i, ins in entries:
            if ins.get("report_safe") is True:
                add_entry(i, ins)
                if len(picked) >= max_sel:
                    break
        if len(picked) < min_sel:
            rest = [
                (i, ins)
                for i, ins in entries
                if i not in picked_idx
                and not _is_dq_category(ins)
                and (ins.get("severity") or "").lower() in ("high", "medium")
            ]
            rest.sort(key=lambda t: (_severity_rank(t[1]), t[0]))
            for i, ins in rest:
                add_entry(i, ins)
                if len(picked) >= min_sel:
                    break
        if len(picked) < min_sel:
            rest = [
                (i, ins)
                for i, ins in entries
                if i not in picked_idx and (ins.get("severity") or "").lower() in ("high", "medium")
            ]
            rest.sort(key=lambda t: (_severity_rank(t[1]), t[0]))
            for i, ins in rest:
                add_entry(i, ins)
                if len(picked) >= min_sel:
                    break
        if len(picked) < min_sel:
            for i, ins in entries:
                add_entry(i, ins)
                if len(picked) >= min_sel:
                    break
    else:
        rest = [
            (i, ins)
            for i, ins in entries
            if not _is_dq_category(ins) and (ins.get("severity") or "").lower() in ("high", "medium")
        ]
        rest.sort(key=lambda t: (_severity_rank(t[1]), t[0]))
        for i, ins in rest:
            add_entry(i, ins)
            if len(picked) >= max_sel:
                break
        if not picked:
            for i, ins in entries[:max_sel]:
                add_entry(i, ins)
        elif len(picked) < min_sel:
            for i, ins in entries:
                if i not in picked_idx:
                    add_entry(i, ins)
                    if len(picked) >= min_sel:
                        break

    return [_insight_key(i, ins) for i, ins in picked]


def _raw_insight_dicts(result_data: dict[str, Any]) -> list[dict]:
    raw = result_data.get("insight_results") or result_data.get("insights") or []
    if not isinstance(raw, list):
        return []
    return [x for x in raw if isinstance(x, dict)]


def _dataset_context_type(result_data: dict[str, Any]) -> str | None:
    ds = result_data.get("dataset_summary")
    if not isinstance(ds, dict):
        return None
    dc = ds.get("dataset_context")
    if not isinstance(dc, dict):
        return None
    dt = dc.get("dataset_type")
    return str(dt) if isinstance(dt, str) else None


def _is_financial_markets_snapshot_result(result_data: dict[str, Any]) -> bool:
    return _dataset_context_type(result_data) == FINANCIAL_MARKETS_SNAPSHOT


def _is_financial_markets_timeseries_result(result_data: dict[str, Any]) -> bool:
    return _dataset_context_type(result_data) == FINANCIAL_MARKETS_TIMESERIES


def _select_charts_by_priority_titles(
    result_data: dict[str, Any],
    priority_titles: tuple[str, ...],
    *,
    max_sel: int,
) -> list[str | int]:
    charts = _chart_dicts_from_result(result_data)
    if not charts:
        return []

    picked_idx: set[int] = set()
    chosen_keys: set[str | int] = set()
    out: list[str | int] = []

    for wanted_title in priority_titles:
        if len(out) >= max_sel:
            break
        for idx, ch in enumerate(charts):
            if idx in picked_idx:
                continue
            if str(ch.get("title") or "").strip() != wanted_title:
                continue
            key = _chart_key(idx, ch)
            if key in chosen_keys:
                continue
            picked_idx.add(idx)
            chosen_keys.add(key)
            out.append(key)
            break

    return out


def _finance_priority_insight_pick(
    raw_dicts: list[dict],
    *,
    domain: str,
    priority_titles: tuple[str, ...],
    min_sel: int,
    max_sel: int,
) -> list[str | int]:
    entries = list(enumerate(raw_dicts))
    picked: list[tuple[int, dict]] = []
    picked_idx: set[int] = set()

    for title in priority_titles:
        if len(picked) >= max_sel:
            break
        for i, ins in entries:
            if i in picked_idx:
                continue
            if ins.get("domain") != domain:
                continue
            if str(ins.get("title") or "").strip() != title:
                continue
            picked.append((i, ins))
            picked_idx.add(i)
            break

    if len(picked) >= min_sel:
        return [_insight_key(i, ins) for i, ins in picked[:max_sel]]

    out: list[str | int] = [_insight_key(i, ins) for i, ins in picked]
    selected: set[str | int] = set(out)

    for k in select_default_insight_selection(raw_dicts, min_sel=min_sel, max_sel=max_sel):
        if len(out) >= max_sel:
            break
        if k not in selected:
            out.append(k)
            selected.add(k)

    for i, ins in entries:
        if len(out) >= max_sel:
            break
        k = _insight_key(i, ins)
        if k not in selected:
            out.append(k)
            selected.add(k)

    return out[:max_sel]


def select_default_chart_selection_for_result(
    result_data: dict[str, Any],
    *,
    max_sel: int = 4,
) -> list[str | int]:
    """Pick chart keys from stored payloads for finance snapshot / timeseries runs only.

    Reads the first non-empty list among
    ``charts`` / ``chart_results`` / ``suggested_charts`` / ``chart_gallery``.
    Match by exact ``title`` strings in the domain priority tuple;
    emit ``chart_id`` / ``id`` when set, else legacy list index; dedupe keys; cap ``max_sel``.
    """
    if _is_financial_markets_snapshot_result(result_data):
        return _select_charts_by_priority_titles(
            result_data,
            _FINANCE_SNAPSHOT_CHART_PRIORITY_TITLES,
            max_sel=max_sel,
        )
    if _is_financial_markets_timeseries_result(result_data):
        return _select_charts_by_priority_titles(
            result_data,
            _FINANCE_TS_CHART_PRIORITY_TITLES,
            max_sel=max_sel,
        )
    return []


def select_default_insight_selection_for_result(
    result_data: dict[str, Any],
    *,
    min_sel: int = 3,
    max_sel: int = 5,
) -> list[str | int]:
    """Pick 3–5 insight keys; finance snapshot / timeseries runs prefer domain titles in fixed order."""
    raw_dicts = _raw_insight_dicts(result_data)
    if not raw_dicts:
        return []

    if _is_financial_markets_snapshot_result(result_data):
        return _finance_priority_insight_pick(
            raw_dicts,
            domain=FINANCIAL_MARKETS_SNAPSHOT,
            priority_titles=_FINANCE_SNAPSHOT_PRIORITY_TITLES,
            min_sel=min_sel,
            max_sel=max_sel,
        )
    if _is_financial_markets_timeseries_result(result_data):
        return _finance_priority_insight_pick(
            raw_dicts,
            domain=FINANCIAL_MARKETS_TIMESERIES,
            priority_titles=_FINANCE_TS_INSIGHT_PRIORITY_TITLES,
            min_sel=min_sel,
            max_sel=max_sel,
        )

    return select_default_insight_selection(raw_dicts, min_sel=min_sel, max_sel=max_sel)


__all__ = [
    "build_fallback_executive_summary",
    "select_default_chart_selection_for_result",
    "select_default_insight_selection",
    "select_default_insight_selection_for_result",
]
