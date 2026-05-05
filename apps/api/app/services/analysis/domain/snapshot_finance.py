"""
Insight pack for financial markets snapshot datasets (cross-section of assets).

Includes return movers, volatility concentration, risk-adjusted leaders, asset-class and sector contrasts,
plus analyst-implied upside screens and 52-week positioning context.
"""
from __future__ import annotations

import logging

import pandas as pd

from app.services.analysis.domain.base import DomainInsightPack
from app.services.dataset_context import DatasetContext, FINANCIAL_MARKETS_SNAPSHOT, _normalise_col

logger = logging.getLogger(__name__)

# Normalised column-name tokens (via _normalise_col) for return_period priority.
_RETURN_PRIORITY_GROUPS: list[frozenset[str]] = [
    frozenset(
        {
            "return1ypct",
            "oneyearreturn",
            "1yreturn",
            "1yrreturn",
            "ret1y",
            "performance1y",
            "perf1y",
        }
    ),
    frozenset({"ytdreturn", "returnytd", "retytd", "perfytd"}),
    frozenset({"return6mpct", "6mreturn", "ret6m", "perf6m", "performance6m"}),
    frozenset({"return3mpct", "3mreturn", "ret3m", "perf3m", "performance3m"}),
    frozenset({"return1mpct", "1mreturn", "ret1m", "perf1m", "performance1m"}),
]

_VOLATILITY_PRIORITY_GROUPS: list[frozenset[str]] = [
    frozenset({"volatility1yann", "volatility1y", "vol1y"}),
    frozenset({"volatility90dann", "volatility90d", "vol90d"}),
    frozenset({"volatility30dann", "volatility30d", "vol30d"}),
]

_SHARPE_PRIORITY_GROUPS: list[frozenset[str]] = [
    frozenset({"sharpe1y"}),
    frozenset({"sharperatio"}),
    frozenset({"sharpe"}),
]

_ANALYST_UPSIDE_PRIORITY_GROUPS: list[frozenset[str]] = [
    frozenset({"analystupsidepct"}),
    frozenset({"analystupside"}),
    frozenset({"upsidepct"}),
    frozenset({"upside"}),
    frozenset({"targetupside"}),
    frozenset({"impliedupside"}),
]

_POSITION_52W_PRIORITY_GROUPS: list[frozenset[str]] = [
    frozenset({"pctof52whigh"}),
    frozenset({"week52positionpct"}),
    frozenset({"week52position"}),
    frozenset({"52weekposition"}),
    frozenset({"pctfrom52whigh"}),
]


class SnapshotFinanceInsightPack(DomainInsightPack):
    dataset_type = FINANCIAL_MARKETS_SNAPSHOT

    def run(self, df: pd.DataFrame, context: DatasetContext) -> list[dict]:
        insights: list[dict] = []
        for detector in (
            self._detect_return_leaders,
            self._detect_return_laggards,
            self._detect_volatility_leaders,
            self._detect_sharpe_leaders,
            self._detect_asset_class_return_comparison,
            self._detect_sector_return_comparison,
            self._detect_analyst_upside_leaders,
            self._detect_52w_position_extremes,
        ):
            try:
                insights.extend(detector(df, context))
            except Exception:
                logger.exception("Snapshot finance detector %s failed", detector.__name__)
        return insights

    def _detect_return_leaders(self, df: pd.DataFrame, context: DatasetContext) -> list[dict]:
        selected_return_col = _select_return_column(df, context)
        if not selected_return_col:
            return []

        values = pd.to_numeric(df[selected_return_col], errors="coerce")
        valid = values.dropna()
        if valid.shape[0] < 3:
            return []

        scale = _detect_percent_scale(valid)
        label_col = _select_label_column(df, context)
        top_named = _named_extremes(df, valid, label_col, k=3, largest=True)

        finding = "Top 3 outperformance candidates to flag for review: " + ", ".join(
            f"{name} ({_format_percent(value, scale)})" for name, value in top_named
        ) + "."

        columns_used = _columns_used(selected_return_col, label_col)

        return [
            {
                "type": "segment",
                "title": "Top return leaders",
                "finding": finding,
                "severity": "medium",
                "confidence": 85,
                "evidence": {
                    "selected_return_column": selected_return_col,
                    "top_values": [
                        {"asset": name, "return": _format_percent(value, scale)}
                        for name, value in top_named
                    ],
                    "valid_row_count": int(valid.shape[0]),
                },
                "action": (
                    "Review the top performers and compare whether momentum is supported by "
                    "risk-adjusted metrics before making decisions."
                ),
                "why_it_matters": (
                    "Return leaders help screen momentum and relative outperformance candidates "
                    "for deeper risk-aware review."
                ),
                "columns_used": columns_used,
                "domain": FINANCIAL_MARKETS_SNAPSHOT,
            }
        ]

    def _detect_return_laggards(self, df: pd.DataFrame, context: DatasetContext) -> list[dict]:
        selected_return_col = _select_return_column(df, context)
        if not selected_return_col:
            return []

        values = pd.to_numeric(df[selected_return_col], errors="coerce")
        valid = values.dropna()
        if valid.shape[0] < 3:
            return []

        scale = _detect_percent_scale(valid)
        label_col = _select_label_column(df, context)
        bottom_named = _named_extremes(df, valid, label_col, k=3, largest=False)

        finding = "Bottom 3 names showing downside pressure to flag for review: " + ", ".join(
            f"{name} ({_format_percent(value, scale)})" for name, value in bottom_named
        ) + "."

        columns_used = _columns_used(selected_return_col, label_col)

        return [
            {
                "type": "segment",
                "title": "Largest return laggards",
                "finding": finding,
                "severity": "medium",
                "confidence": 85,
                "evidence": {
                    "selected_return_column": selected_return_col,
                    "bottom_values": [
                        {"asset": name, "return": _format_percent(value, scale)}
                        for name, value in bottom_named
                    ],
                    "valid_row_count": int(valid.shape[0]),
                },
                "action": (
                    "Review laggards for drawdown, volatility, or sector-specific pressure "
                    "before interpreting underperformance."
                ),
                "why_it_matters": (
                    "Return laggards surface downside pressure and weak momentum candidates "
                    "that may warrant risk-focused screening."
                ),
                "columns_used": columns_used,
                "domain": FINANCIAL_MARKETS_SNAPSHOT,
            }
        ]

    def _detect_volatility_leaders(self, df: pd.DataFrame, context: DatasetContext) -> list[dict]:
        volatility_col = _select_volatility_column(df, context)
        if not volatility_col:
            return []

        values = pd.to_numeric(df[volatility_col], errors="coerce")
        valid = values.dropna()
        if valid.shape[0] < 3:
            return []

        scale = _detect_percent_scale(valid)
        label_col = _select_label_column(df, context)
        top_named = _named_extremes(df, valid, label_col, k=3, largest=True)

        finding = "Top 3 volatility names to flag for review: " + ", ".join(
            f"{name} ({_format_percent(value, scale)})" for name, value in top_named
        ) + "."

        columns_used = _columns_used(volatility_col, label_col)

        return [
            {
                "type": "concentration",
                "title": "Highest volatility assets",
                "finding": finding,
                "severity": "medium",
                "confidence": 82,
                "evidence": {
                    "selected_volatility_column": volatility_col,
                    "top_values": [
                        {"asset": name, "volatility": _format_percent(value, scale)}
                        for name, value in top_named
                    ],
                    "median_volatility": _format_percent(float(valid.median()), scale),
                    "valid_row_count": int(valid.shape[0]),
                },
                "action": (
                    "Review high-volatility assets separately from lower-risk assets before comparing returns."
                ),
                "why_it_matters": (
                    "Volatility leaders can indicate risk concentration and less stable return profiles "
                    "that deserve separate screening."
                ),
                "columns_used": columns_used,
                "domain": FINANCIAL_MARKETS_SNAPSHOT,
            }
        ]

    def _detect_sharpe_leaders(self, df: pd.DataFrame, context: DatasetContext) -> list[dict]:
        sharpe_col = _select_sharpe_column(df, context)
        if not sharpe_col:
            return []

        values = pd.to_numeric(df[sharpe_col], errors="coerce")
        valid = values.dropna()
        if valid.shape[0] < 3:
            return []

        label_col = _select_label_column(df, context)
        top_named = _named_extremes(df, valid, label_col, k=3, largest=True)

        finding = "Top 3 risk-adjusted performers to flag for review: " + ", ".join(
            f"{name} ({_format_number(value)})" for name, value in top_named
        ) + "."

        columns_used = _columns_used(sharpe_col, label_col)

        return [
            {
                "type": "segment",
                "title": "Best risk-adjusted performers",
                "finding": finding,
                "severity": "medium",
                "confidence": 84,
                "evidence": {
                    "selected_sharpe_column": sharpe_col,
                    "top_values": [
                        {"asset": name, "sharpe": _format_number(value)} for name, value in top_named
                    ],
                    "valid_row_count": int(valid.shape[0]),
                },
                "action": (
                    "Use Sharpe leaders as a starting point, then verify annualisation, volatility, "
                    "and asset-class comparability."
                ),
                "why_it_matters": (
                    "Sharpe helps compare return relative to risk so high-ranked names can be screened "
                    "on a risk-adjusted basis."
                ),
                "columns_used": columns_used,
                "domain": FINANCIAL_MARKETS_SNAPSHOT,
            }
        ]

    def _detect_asset_class_return_comparison(self, df: pd.DataFrame, context: DatasetContext) -> list[dict]:
        selected_return_col = _select_return_column(df, context)
        asset_class_col = _select_asset_class_column(df, context)
        if not selected_return_col or not asset_class_col:
            return []

        work = df[[asset_class_col, selected_return_col]].copy()
        work["_ret"] = pd.to_numeric(work[selected_return_col], errors="coerce")
        work["_cls"] = work[asset_class_col].map(_stringify_asset_class)
        work = work.dropna(subset=["_ret", "_cls"])
        if work.empty:
            return []

        scale = _detect_percent_scale(work["_ret"])

        grp = work.groupby("_cls", sort=False, observed=True)["_ret"]
        agg = grp.agg(count="count", mean="mean", median="median")
        qualified = agg[agg["count"] >= 3].copy()
        if qualified.shape[0] < 2:
            return []

        ranked = qualified.sort_values("mean", ascending=False)
        top_name = ranked.index[0]
        bottom_name = ranked.index[-1]
        top_avg = float(ranked.iloc[0]["mean"])
        bottom_avg = float(ranked.iloc[-1]["mean"])

        metric_label = _readable_return_metric_label(selected_return_col)
        finding = (
            f"Average {metric_label} varies by asset class: {top_name} leads at "
            f"{_format_percent(top_avg, scale)}, while {bottom_name} trails at "
            f"{_format_percent(bottom_avg, scale)}."
        )

        def _group_row(cls_name: object) -> dict:
            row = ranked.loc[cls_name]
            return {
                "asset_class": str(cls_name),
                "count": int(row["count"]),
                "average_return": _format_percent(float(row["mean"]), scale),
                "median_return": _format_percent(float(row["median"]), scale),
            }

        head3 = [_group_row(ix) for ix in ranked.head(3).index]
        bottom_row = _group_row(bottom_name)

        return [
            {
                "type": "segment",
                "title": "Asset classes show different return profiles",
                "finding": finding,
                "severity": "medium",
                "confidence": 83,
                "evidence": {
                    "selected_return_column": selected_return_col,
                    "selected_asset_class_column": asset_class_col,
                    "group_count": int(qualified.shape[0]),
                    "top_groups": head3,
                    "bottom_group": bottom_row,
                    "valid_row_count": int(work.shape[0]),
                },
                "action": "Compare assets within the same asset class before drawing cross-market conclusions.",
                "why_it_matters": (
                    "Mixed asset classes bundle different risk and return regimes, so headline return "
                    "gaps often reflect buckets rather than like-for-like security selection."
                ),
                "columns_used": [selected_return_col, asset_class_col],
                "domain": FINANCIAL_MARKETS_SNAPSHOT,
            }
        ]

    def _detect_sector_return_comparison(self, df: pd.DataFrame, context: DatasetContext) -> list[dict]:
        selected_return_col = _select_return_column(df, context)
        sector_col = _select_sector_column(df, context)
        if not selected_return_col or not sector_col:
            return []

        work = df[[sector_col, selected_return_col]].copy()
        work["_ret"] = pd.to_numeric(work[selected_return_col], errors="coerce")
        work["_sec"] = work[sector_col].map(_stringify_sector)
        work = work.dropna(subset=["_ret", "_sec"])
        if work.empty:
            return []

        scale = _detect_percent_scale(work["_ret"])

        grp = work.groupby("_sec", sort=False, observed=True)["_ret"]
        agg = grp.agg(count="count", mean="mean", median="median")
        qualified = agg[agg["count"] >= 3].copy()
        if qualified.shape[0] < 2:
            return []

        ranked = qualified.sort_values("mean", ascending=False)
        top_name = ranked.index[0]
        bottom_name = ranked.index[-1]
        top_avg = float(ranked.iloc[0]["mean"])
        bottom_avg = float(ranked.iloc[-1]["mean"])

        metric_label = _readable_return_metric_label(selected_return_col)
        finding = (
            f"Average {metric_label} varies by sector: {top_name} leads at "
            f"{_format_percent(top_avg, scale)}, while {bottom_name} trails at "
            f"{_format_percent(bottom_avg, scale)}."
        )

        def _group_row(sec_name: object) -> dict:
            row = ranked.loc[sec_name]
            return {
                "sector": str(sec_name),
                "count": int(row["count"]),
                "average_return": _format_percent(float(row["mean"]), scale),
                "median_return": _format_percent(float(row["median"]), scale),
            }

        head3 = [_group_row(ix) for ix in ranked.head(3).index]
        bottom_row = _group_row(bottom_name)

        return [
            {
                "type": "segment",
                "title": "Sectors show different return profiles",
                "finding": finding,
                "severity": "medium",
                "confidence": 82,
                "evidence": {
                    "selected_return_column": selected_return_col,
                    "selected_sector_column": sector_col,
                    "group_count": int(qualified.shape[0]),
                    "top_groups": head3,
                    "bottom_group": bottom_row,
                    "valid_row_count": int(work.shape[0]),
                },
                "action": (
                    "Compare assets within the same sector before drawing conclusions from broad return differences."
                ),
                "why_it_matters": (
                    "Sector grouping captures shared industry exposures, so return dispersion across sectors "
                    "often reflects structural winners and laggards rather than individual issuer stories alone."
                ),
                "columns_used": [selected_return_col, sector_col],
                "domain": FINANCIAL_MARKETS_SNAPSHOT,
            }
        ]

    def _detect_analyst_upside_leaders(self, df: pd.DataFrame, context: DatasetContext) -> list[dict]:
        upside_col = _select_analyst_upside_column(df, context)
        if not upside_col:
            return []

        values = pd.to_numeric(df[upside_col], errors="coerce")
        valid = values.dropna()
        if valid.shape[0] < 3:
            return []

        label_col = _select_label_column(df, context)
        top_named = _named_extremes(df, valid, label_col, k=3, largest=True)
        if not any(value > 0.0 for _, value in top_named):
            return []

        scale = _detect_percent_scale(valid)
        top_phrase = _finding_three_analyst_upside_assets(top_named, scale)

        columns_used = _columns_used(upside_col, label_col)

        finding = f"Analyst-implied upside is highest for {top_phrase}."

        return [
            {
                "type": "segment",
                "title": "Highest analyst-implied upside",
                "finding": finding,
                "severity": "medium",
                "confidence": 80,
                "evidence": {
                    "selected_analyst_upside_column": upside_col,
                    "top_values": [
                        {"asset": name, "analyst_implied_upside": _format_percent(value, scale)}
                        for name, value in top_named
                    ],
                    "median_analyst_upside": _format_percent(float(valid.median()), scale),
                    "valid_row_count": int(valid.shape[0]),
                },
                "action": (
                    "Use analyst-implied upside as a screening signal, then validate coverage, "
                    "assumptions, and risk before drawing conclusions."
                ),
                "why_it_matters": (
                    "Analyst-implied upside highlights gap-to-target style market expectations that "
                    "can flag names for review, but those figures depend on models, coverage, and "
                    "time horizon and should not be read as a standalone view of fair value."
                ),
                "columns_used": columns_used,
                "domain": FINANCIAL_MARKETS_SNAPSHOT,
            }
        ]

    def _detect_52w_position_extremes(self, df: pd.DataFrame, context: DatasetContext) -> list[dict]:
        pos_col = _select_52w_position_column(df, context)
        if not pos_col:
            return []

        values = pd.to_numeric(df[pos_col], errors="coerce")
        parsed = values.dropna()
        if parsed.shape[0] < 3:
            return []

        scale, low_b, high_b = _infer_52w_position_bounds(parsed)
        in_range = (values >= low_b) & (values <= high_b)
        valid = values.where(in_range).dropna()
        invalid_ct = int(values.notna().sum() - valid.shape[0])

        if valid.shape[0] < 3:
            return []

        label_col = _select_label_column(df, context)
        near_named = _named_extremes(df, valid, label_col, k=3, largest=True)
        low_named = _named_extremes(df, valid, label_col, k=3, largest=False)

        near_pair = near_named[:2]
        low_pair = low_named[:2]
        high_names = near_pair[0][0], near_pair[1][0]
        low_names = low_pair[0][0], low_pair[1][0]

        range_hint = "0–1 fraction of the 52-week range" if scale == "decimal" else "0–100% position in the 52-week range"
        finding = (
            f"52-week positioning is split: {high_names[0]} and {high_names[1]} are closest to their highs, "
            f"while {low_names[0]} and {low_names[1]} sit furthest from their highs."
        )
        if invalid_ct > 0:
            finding += (
                f" ({invalid_ct} row(s) had values outside the expected {range_hint} "
                "and were excluded from this ranking.)"
            )

        columns_used = _columns_used(pos_col, label_col)

        evidence: dict = {
            "selected_52w_position_column": pos_col,
            "near_high_assets": [
                {"asset": name, "position_52w": _format_percent(value, scale)}
                for name, value in near_named
            ],
            "low_position_assets": [
                {"asset": name, "position_52w": _format_percent(value, scale)}
                for name, value in low_named
            ],
            "valid_row_count": int(valid.shape[0]),
            "position_scale": scale,
            "expected_min": low_b,
            "expected_max": high_b,
        }
        if invalid_ct > 0:
            evidence["invalid_position_value_count"] = invalid_ct
            evidence["position_validation_note"] = (
                f"Values outside [{low_b:g}, {high_b:g}] are not valid percent positions for this scale "
                f"({range_hint}) and were excluded from extremes."
            )

        return [
            {
                "type": "segment",
                "title": "Assets cluster at different 52-week positions",
                "finding": finding,
                "severity": "medium",
                "confidence": 79,
                "evidence": evidence,
                "action": (
                    "Use 52-week position as a momentum/context screen, then compare it with return, "
                    "volatility, and asset class."
                ),
                "why_it_matters": (
                    "52-week position summarises where price sits versus its trailing high–low corridor, "
                    "so extremes surface relative momentum context without naming causes or confirming trend quality."
                ),
                "columns_used": columns_used,
                "domain": FINANCIAL_MARKETS_SNAPSHOT,
            }
        ]


def _select_return_column(df: pd.DataFrame, context: DatasetContext) -> str | None:
    return_cols = [
        col
        for col, role in context.semantic_roles.items()
        if role == "return_period" and col in df.columns
    ]
    if not return_cols:
        return None

    normalized = {col: _normalise_col(col) for col in return_cols}
    for priority_group in _RETURN_PRIORITY_GROUPS:
        for col, norm in normalized.items():
            if norm in priority_group:
                return col
    return return_cols[0]


def _select_by_role_with_priority(
    df: pd.DataFrame,
    context: DatasetContext,
    role: str,
    priority_groups: list[frozenset[str]],
) -> str | None:
    cols = [
        col for col, r in context.semantic_roles.items() if r == role and col in df.columns
    ]
    if not cols:
        return None
    normalized = {col: _normalise_col(col) for col in cols}
    for group in priority_groups:
        for col, norm in normalized.items():
            if norm in group:
                return col
    return cols[0]


def _select_volatility_column(df: pd.DataFrame, context: DatasetContext) -> str | None:
    return _select_by_role_with_priority(df, context, "volatility", _VOLATILITY_PRIORITY_GROUPS)


def _select_sharpe_column(df: pd.DataFrame, context: DatasetContext) -> str | None:
    return _select_by_role_with_priority(df, context, "sharpe_ratio", _SHARPE_PRIORITY_GROUPS)


def _select_analyst_upside_column(df: pd.DataFrame, context: DatasetContext) -> str | None:
    return _select_by_role_with_priority(
        df, context, "analyst_upside", _ANALYST_UPSIDE_PRIORITY_GROUPS
    )


def _select_52w_position_column(df: pd.DataFrame, context: DatasetContext) -> str | None:
    return _select_by_role_with_priority(
        df, context, "position_52w", _POSITION_52W_PRIORITY_GROUPS
    )


def _select_asset_class_column(df: pd.DataFrame, context: DatasetContext) -> str | None:
    for col, role in context.semantic_roles.items():
        if role == "asset_class" and col in df.columns:
            return col
    return None


def _select_sector_column(df: pd.DataFrame, context: DatasetContext) -> str | None:
    for col, role in context.semantic_roles.items():
        if role == "sector" and col in df.columns:
            return col
    return None


def _select_label_column(df: pd.DataFrame, context: DatasetContext) -> str | None:
    for col, role in context.semantic_roles.items():
        if role == "asset_label" and col in df.columns:
            return col
    for col, role in context.semantic_roles.items():
        if role == "asset_id" and col in df.columns:
            return col
    return None


def _label_for_row(df: pd.DataFrame, idx: object, label_col: str | None) -> str:
    if label_col is not None:
        try:
            value = df.loc[idx, label_col]
            if isinstance(value, pd.Series):
                value = value.iloc[0]
        except (KeyError, IndexError):
            value = pd.NA
        if pd.notna(value):
            text = str(value).strip()
            if text:
                return text
    return str(idx)


def _stringify_asset_class(value: object) -> str | None:
    """Return a stripped group label, or None when the row should be excluded."""
    if pd.isna(value):
        return None
    text = str(value).strip()
    if not text or text.lower() in {"nan", "none", "<na>"}:
        return None
    return text


def _stringify_sector(value: object) -> str | None:
    """Clean sector bucket labels using the same rules as asset class grouping."""
    return _stringify_asset_class(value)


def _readable_return_metric_label(column_name: str) -> str:
    if column_name.strip() == "return_1y_pct" or _normalise_col(column_name) == "return1ypct":
        return "1Y return"
    return column_name.replace("_", " ").strip() or column_name


def _named_extremes(
    df: pd.DataFrame,
    valid: pd.Series,
    label_col: str | None,
    *,
    k: int,
    largest: bool,
) -> list[tuple[str, float]]:
    ranked = valid.nlargest(k) if largest else valid.nsmallest(k)
    return [(_label_for_row(df, idx, label_col), float(ranked.loc[idx])) for idx in ranked.index]


def _finding_three_analyst_upside_assets(
    top_named: list[tuple[str, float]],
    scale: str,
) -> str:
    parts = [f"{name} ({_format_percent(value, scale)})" for name, value in top_named]
    if len(parts) == 1:
        return parts[0]
    if len(parts) == 2:
        return f"{parts[0]} and {parts[1]}"
    return f"{parts[0]}, {parts[1]}, and {parts[2]}"


def _columns_used(primary_col: str, label_col: str | None) -> list[str]:
    out = [primary_col]
    if label_col is not None:
        out.append(label_col)
    return out


def _detect_percent_scale(valid: pd.Series) -> str:
    if valid.empty:
        return "decimal"
    abs_max = float(valid.abs().max())
    # Treat [-1, 1] magnitude as fractional returns; larger magnitudes as already in percent units.
    return "decimal" if abs_max <= 1.0 else "unit"


def _infer_52w_position_bounds(parsed: pd.Series) -> tuple[str, float, float]:
    """
    Decide whether a 52-week position column is stored as a 0–1 range fraction or 0–100 percent points.

    Uses a majority rule so a few stray percent-scale points do not re-label an otherwise fractional column.
    """
    if parsed.empty:
        return "decimal", 0.0, 1.0
    abs_max = float(parsed.abs().max())
    in_01_ratio = float(((parsed >= 0.0) & (parsed <= 1.0)).mean())
    if in_01_ratio >= 0.85 or abs_max <= 1.001:
        return "decimal", 0.0, 1.0
    return "unit", 0.0, 100.0


def _format_percent(value: float, scale: str) -> str:
    pct = value * 100.0 if scale == "decimal" else value
    return f"{pct:.1f}%"


def _format_number(value: float) -> str:
    return f"{value:.2f}"

