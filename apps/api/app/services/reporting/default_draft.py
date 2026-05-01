"""
Default Report Builder draft materialisation.

When a project has a finished analysis but no persisted ``ReportDraft`` yet,
``GET /reports/draft/{project_id}`` auto-creates a sensible starting draft:
executive summary text derived from ``result_json``, and 3–5 recommended
findings (report-safe first, then severity- and category-aware fallbacks).
"""
from __future__ import annotations

from typing import Any

from app.services.dataset_context.schema import FINANCIAL_MARKETS_SNAPSHOT
from app.services.reporting.executive_summary_draft import build_fallback_executive_summary

# Priority order for default Report Builder selection on ``financial_markets_snapshot`` runs.
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


def _is_financial_markets_snapshot_result(result_data: dict[str, Any]) -> bool:
    ds = result_data.get("dataset_summary")
    if not isinstance(ds, dict):
        return False
    dc = ds.get("dataset_context")
    return isinstance(dc, dict) and dc.get("dataset_type") == FINANCIAL_MARKETS_SNAPSHOT


def select_default_insight_selection_for_result(
    result_data: dict[str, Any],
    *,
    min_sel: int = 3,
    max_sel: int = 5,
) -> list[str | int]:
    """Pick 3–5 insight keys; finance snapshot runs prefer domain finance titles in fixed order."""
    raw_dicts = _raw_insight_dicts(result_data)
    if not raw_dicts:
        return []

    if not _is_financial_markets_snapshot_result(result_data):
        return select_default_insight_selection(raw_dicts, min_sel=min_sel, max_sel=max_sel)

    entries = list(enumerate(raw_dicts))
    picked: list[tuple[int, dict]] = []
    picked_idx: set[int] = set()

    for title in _FINANCE_SNAPSHOT_PRIORITY_TITLES:
        if len(picked) >= max_sel:
            break
        for i, ins in entries:
            if i in picked_idx:
                continue
            if ins.get("domain") != FINANCIAL_MARKETS_SNAPSHOT:
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


__all__ = [
    "build_fallback_executive_summary",
    "select_default_insight_selection",
    "select_default_insight_selection_for_result",
]
