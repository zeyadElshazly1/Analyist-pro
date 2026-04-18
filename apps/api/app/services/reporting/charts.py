"""
Chart.js configuration builder for embedded report charts.

build_chart_configs(analysis_result) → dict

Returns a dict with optional keys:
  health_chart  — horizontal bar showing each quality dimension score
  missing_chart — horizontal bar showing top columns by missing %
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
