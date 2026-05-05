"""
Chart.js configuration builder for embedded report charts.

build_chart_configs(analysis_result) → dict

Returns a dict with optional keys:
  health_chart  — horizontal bar showing each quality dimension score
  missing_chart — horizontal bar showing top columns by missing %

resolve_selected_chart_payloads(analysis_result) → list[dict]

Returns the ordered list of stored chart payload dicts for chart IDs
recorded under ``analysis_result["selected_chart_ids"]`` (set by
apply_draft_to_result).  Unresolvable IDs are silently skipped.
"""
from __future__ import annotations


def _score_color(v: float) -> str:
    if v >= 80:
        return "#10b981"
    if v >= 60:
        return "#f59e0b"
    return "#ef4444"


def build_chart_configs(analysis_result: dict) -> dict:
    configs: dict = {}

    # Health breakdown horizontal bar
    hs = analysis_result.get("health_score", {})
    breakdown = hs.get("breakdown", {}) if isinstance(hs, dict) else {}
    if not breakdown:
        breakdown = analysis_result.get("health_breakdown", {})
    if breakdown:
        labels = list(breakdown.keys())
        data   = [float(v) if isinstance(v, (int, float)) else 0.0 for v in breakdown.values()]
        configs["health_chart"] = {
            "type": "bar",
            "data": {
                "labels": labels,
                "datasets": [{
                    "label":           "Score /100",
                    "data":            data,
                    "backgroundColor": [_score_color(v) for v in data],
                    "borderRadius":    4,
                }],
            },
            "options": {
                "indexAxis": "y",
                "responsive": True,
                "maintainAspectRatio": False,
                "scales": {
                    "x": {
                        "max": 100,
                        "grid": {"color": "#1e293b"},
                        "ticks": {"color": "#94a3b8"},
                    },
                    "y": {"ticks": {"color": "#cbd5e1"}},
                },
                "plugins": {
                    "legend": {"display": False},
                    "tooltip": {"callbacks": {}},
                },
            },
        }

    # Top-10 columns by missing % horizontal bar (only columns with any missing)
    profile = analysis_result.get("profile", [])
    if isinstance(profile, dict):
        cols = profile.get("columns", [])
    else:
        cols = profile if isinstance(profile, list) else []
    missing_pairs = sorted(
        [(c.get("name") or c.get("column", ""), float(c.get("missing_pct", 0) or 0)) for c in cols],
        key=lambda x: x[1],
        reverse=True,
    )[:10]
    missing_pairs = [(n, pct) for n, pct in missing_pairs if pct > 0]

    if missing_pairs:
        labels, data = zip(*missing_pairs)
        configs["missing_chart"] = {
            "type": "bar",
            "data": {
                "labels": list(labels),
                "datasets": [{
                    "label":           "Missing %",
                    "data":            list(data),
                    "backgroundColor": [_score_color(100 - v) for v in data],
                    "borderRadius":    4,
                }],
            },
            "options": {
                "indexAxis": "y",
                "responsive": True,
                "maintainAspectRatio": False,
                "scales": {
                    "x": {
                        "max": 100,
                        "grid": {"color": "#1e293b"},
                        "ticks": {"color": "#94a3b8"},
                    },
                    "y": {"ticks": {"color": "#cbd5e1"}},
                },
                "plugins": {"legend": {"display": False}},
            },
        }

    return configs


# ── Selected chart payload resolution ─────────────────────────────────────────


def _resolve_chart_catalog(
    analysis_result: dict,
) -> tuple[dict[str, dict], list[dict]]:
    """Read the first non-empty chart block and build (by_id_index, ordered_list).

    Checks the keys ``charts``, ``chart_results``, ``suggested_charts``,
    ``chart_gallery`` in that order; uses the first non-empty list.
    """
    ordered: list[dict] = []
    for key in ("charts", "chart_results", "suggested_charts", "chart_gallery"):
        blk = analysis_result.get(key)
        if isinstance(blk, list):
            vals = [c for c in blk if isinstance(c, dict)]
            if vals:
                ordered = vals
                break

    by_id: dict[str, dict] = {}
    for ch in ordered:
        for field in ("chart_id", "id"):
            cid = ch.get(field)
            if isinstance(cid, str) and cid.strip():
                k = cid.strip()
                if k not in by_id:
                    by_id[k] = ch
                break

    return by_id, ordered


def resolve_selected_chart_payloads(analysis_result: dict) -> list[dict]:
    """Return ordered, deduplicated chart payload dicts for selected chart IDs.

    Reads ``analysis_result["selected_chart_ids"]`` (set by
    ``apply_draft_to_result``).  Each entry may be:

    * a string ``chart_id`` / ``id``
    * an integer legacy list index into the stored chart block
    * a dict containing a ``chart_id`` or ``id`` key (or an integer in those)

    Payloads preserve all stored fields and always expose normalised
    ``chart_id``, ``title``, and ``chart_type`` keys.  Entries that cannot
    be resolved to a stored payload are silently skipped (we cannot render
    a chart without its data).  Returns ``[]`` when no IDs are present.
    """
    selected_ids = analysis_result.get("selected_chart_ids")
    if not isinstance(selected_ids, list) or not selected_ids:
        return []

    by_id, ordered = _resolve_chart_catalog(analysis_result)

    out: list[dict] = []
    seen: set[str] = set()

    for item in selected_ids:
        if isinstance(item, bool):
            continue

        cid: str | None = None
        source: dict | None = None

        if isinstance(item, dict):
            # Dict slot: extract chart_id/id, resolve payload from catalog.
            for field in ("chart_id", "id"):
                v = item.get(field)
                if isinstance(v, bool):
                    continue
                if isinstance(v, str) and v.strip():
                    cid = v.strip()
                    source = by_id.get(cid)
                    break
                if isinstance(v, int) and 0 <= v < len(ordered):
                    ch = ordered[v]
                    for f2 in ("chart_id", "id"):
                        inner = ch.get(f2)
                        if isinstance(inner, str) and inner.strip():
                            cid = inner.strip()
                            break
                    if cid is None:
                        cid = f"idx_{v}"
                    source = ch
                    break

        elif isinstance(item, str) and item.strip():
            cid = item.strip()
            source = by_id.get(cid)

        elif isinstance(item, int) and 0 <= item < len(ordered):
            ch = ordered[item]
            for field in ("chart_id", "id"):
                v = ch.get(field)
                if isinstance(v, str) and v.strip():
                    cid = v.strip()
                    break
            if cid is None:
                cid = f"idx_{item}"
            source = ch

        # Skip if unresolvable or already emitted.
        if cid is None or source is None:
            continue
        if cid in seen:
            continue
        seen.add(cid)

        # Build output entry preserving all stored fields.
        entry: dict = {"chart_id": cid}
        for k, v in source.items():
            if k not in entry:
                entry[k] = v

        # Ensure normalised chart_type (prefer chart_type over type).
        if "chart_type" not in entry:
            ct = source.get("chart_type") or source.get("type")
            entry["chart_type"] = ct.strip() if isinstance(ct, str) and ct.strip() else "unknown"

        # Ensure normalised title.
        if "title" not in entry:
            t = source.get("title") or source.get("chart_title")
            entry["title"] = t.strip() if isinstance(t, str) and t.strip() else cid

        out.append(entry)

    return out
