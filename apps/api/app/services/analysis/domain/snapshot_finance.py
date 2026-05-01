from __future__ import annotations

import logging

import pandas as pd

from app.services.analysis.domain.base import DomainInsightPack
from app.services.dataset_context import (
    DatasetContext,
    FINANCIAL_MARKETS_SNAPSHOT,
    _normalise_col,
)

logger = logging.getLogger(__name__)


class SnapshotFinanceInsightPack(DomainInsightPack):
    dataset_type = FINANCIAL_MARKETS_SNAPSHOT

    def run(self, df: pd.DataFrame, context: DatasetContext) -> list[dict]:
        insights: list[dict] = []
        detectors = (
            self._detect_return_leaders,
            self._detect_return_laggards,
            self._detect_volatility_leaders,
            self._detect_sharpe_leaders,
        )
        for detector in detectors:
            try:
                insights.extend(detector(df, context))
            except Exception:
                logger.exception("Snapshot finance detector %s failed", detector.__name__)
        return insights

    def _detect_return_leaders(self, df: pd.DataFrame, context: DatasetContext) -> list[dict]:
        selected_return_col = _select_return_column(df, context)
        if not selected_return_col:
            return []
        valid = pd.to_numeric(df[selected_return_col], errors="coerce").dropna()
        if valid.shape[0] < 3:
            return []
        scale = _detect_percent_scale(valid)
        label_col = _select_label_column(df, context)
        top_named = _top_named(df, valid, label_col)
        columns_used = _columns_used(selected_return_col, label_col)
        return [{
            "type": "segment",
            "title": "Top return leaders",
            "finding": "Top 3 outperformance candidates to flag for review: " + ", ".join(
                f"{name} ({_format_percent(value, scale)})" for name, value in top_named
            ) + ".",
            "severity": "medium",
            "confidence": 85,
            "evidence": {
                "selected_return_column": selected_return_col,
                "top_values": [{"asset": n, "return": _format_percent(v, scale)} for n, v in top_named],
                "valid_row_count": int(valid.shape[0]),
            },
            "action": "Review the top performers and compare whether momentum is supported by risk-adjusted metrics before making decisions.",
            "why_it_matters": "Return leaders help screen momentum and relative outperformance candidates for deeper risk-aware review.",
            "columns_used": columns_used,
            "domain": FINANCIAL_MARKETS_SNAPSHOT,
        }]

    def _detect_return_laggards(self, df: pd.DataFrame, context: DatasetContext) -> list[dict]:
        selected_return_col = _select_return_column(df, context)
        if not selected_return_col:
            return []
        valid = pd.to_numeric(df[selected_return_col], errors="coerce").dropna()
        if valid.shape[0] < 3:
            return []
        scale = _detect_percent_scale(valid)
        label_col = _select_label_column(df, context)
        bottom_named = _bottom_named(df, valid, label_col)
        columns_used = _columns_used(selected_return_col, label_col)
        return [{
            "type": "segment",
            "title": "Largest return laggards",
            "finding": "Bottom 3 names showing downside pressure to flag for review: " + ", ".join(
                f"{name} ({_format_percent(value, scale)})" for name, value in bottom_named
            ) + ".",
            "severity": "medium",
            "confidence": 85,
            "evidence": {
                "selected_return_column": selected_return_col,
                "bottom_values": [{"asset": n, "return": _format_percent(v, scale)} for n, v in bottom_named],
                "valid_row_count": int(valid.shape[0]),
            },
            "action": "Review laggards for drawdown, volatility, or sector-specific pressure before interpreting underperformance.",
            "why_it_matters": "Return laggards surface downside pressure and weak momentum candidates that may warrant risk-focused screening.",
            "columns_used": columns_used,
            "domain": FINANCIAL_MARKETS_SNAPSHOT,
        }]

    def _detect_volatility_leaders(self, df: pd.DataFrame, context: DatasetContext) -> list[dict]:
        volatility_col = _select_volatility_column(df, context)
        if not volatility_col:
            return []
        valid = pd.to_numeric(df[volatility_col], errors="coerce").dropna()
        if valid.shape[0] < 3:
            return []
        scale = _detect_percent_scale(valid)
        label_col = _select_label_column(df, context)
        top_named = _top_named(df, valid, label_col)
        columns_used = _columns_used(volatility_col, label_col)
        return [{
            "type": "concentration",
            "title": "Highest volatility assets",
            "finding": "Top 3 volatility names to flag for review: " + ", ".join(
                f"{name} ({_format_percent(value, scale)})" for name, value in top_named
            ) + ".",
            "severity": "medium",
            "confidence": 82,
            "evidence": {
                "selected_volatility_column": volatility_col,
                "top_values": [{"asset": n, "volatility": _format_percent(v, scale)} for n, v in top_named],
                "median_volatility": _format_percent(float(valid.median()), scale),
                "valid_row_count": int(valid.shape[0]),
            },
            "action": "Review high-volatility assets separately from lower-risk assets before comparing returns.",
            "why_it_matters": "Volatility leaders can indicate risk concentration and less stable return profiles that deserve separate screening.",
            "columns_used": columns_used,
            "domain": FINANCIAL_MARKETS_SNAPSHOT,
        }]

    def _detect_sharpe_leaders(self, df: pd.DataFrame, context: DatasetContext) -> list[dict]:
        sharpe_col = _select_sharpe_column(df, context)
        if not sharpe_col:
            return []
        valid = pd.to_numeric(df[sharpe_col], errors="coerce").dropna()
        if valid.shape[0] < 3:
            return []
        label_col = _select_label_column(df, context)
        top_named = _top_named(df, valid, label_col)
        columns_used = _columns_used(sharpe_col, label_col)
        return [{
            "type": "segment",
            "title": "Best risk-adjusted performers",
            "finding": "Top 3 risk-adjusted performers to flag for review: " + ", ".join(
                f"{name} ({_format_number(value)})" for name, value in top_named
            ) + ".",
            "severity": "medium",
            "confidence": 84,
            "evidence": {
                "selected_sharpe_column": sharpe_col,
                "top_values": [{"asset": n, "sharpe": _format_number(v)} for n, v in top_named],
                "valid_row_count": int(valid.shape[0]),
            },
            "action": "Use Sharpe leaders as a starting point, then verify annualisation, volatility, and asset-class comparability.",
            "why_it_matters": "Sharpe helps compare return relative to risk so high-ranked names can be screened on a risk-adjusted basis.",
            "columns_used": columns_used,
            "domain": FINANCIAL_MARKETS_SNAPSHOT,
        }]


def _select_by_role_with_priority(df: pd.DataFrame, context: DatasetContext, role: str, priorities: list[set[str]]) -> str | None:
    cols = [col for col, r in context.semantic_roles.items() if r == role and col in df.columns]
    if not cols:
        return None
    normalized = {col: _normalise_col(col) for col in cols}
    for group in priorities:
        for col, norm in normalized.items():
            if norm in group:
                return col
    return cols[0]


def _select_return_column(df: pd.DataFrame, context: DatasetContext) -> str | None:
    return _select_by_role_with_priority(df, context, "return_period", [
        {"return1ypct", "oneyearreturn", "1yreturn", "1yrreturn", "ret1y", "performance1y", "perf1y"},
        {"ytdreturn", "returnytd", "retytd", "perfytd"},
        {"return6mpct", "6mreturn", "ret6m", "perf6m", "performance6m"},
        {"return3mpct", "3mreturn", "ret3m", "perf3m", "performance3m"},
        {"return1mpct", "1mreturn", "ret1m", "perf1m", "performance1m"},
    ])


def _select_volatility_column(df: pd.DataFrame, context: DatasetContext) -> str | None:
    return _select_by_role_with_priority(df, context, "volatility", [
        {"volatility1yann", "volatility1y", "vol1y"},
        {"volatility90dann", "volatility90d"},
        {"volatility30dann", "volatility30d"},
    ])


def _select_sharpe_column(df: pd.DataFrame, context: DatasetContext) -> str | None:
    return _select_by_role_with_priority(df, context, "sharpe_ratio", [
        {"sharpe1y"},
        {"sharperatio"},
        {"sharpe"},
    ])


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
        value = df.at[idx, label_col]
        if pd.notna(value):
            text = str(value).strip()
            if text:
                return text
    return str(idx)


def _top_named(df: pd.DataFrame, valid: pd.Series, label_col: str | None) -> list[tuple[str, float]]:
    return [(_label_for_row(df, idx, label_col), float(valid.loc[idx])) for idx in valid.nlargest(3).index]


def _bottom_named(df: pd.DataFrame, valid: pd.Series, label_col: str | None) -> list[tuple[str, float]]:
    return [(_label_for_row(df, idx, label_col), float(valid.loc[idx])) for idx in valid.nsmallest(3).index]


def _columns_used(primary_col: str, label_col: str | None) -> list[str]:
    columns = [primary_col]
    if label_col is not None:
        columns.append(label_col)
    return columns


def _detect_percent_scale(valid: pd.Series) -> str:
    absmax = float(valid.abs().max()) if not valid.empty else 0.0
    return "decimal" if absmax <= 1.0 else "unit"


def _format_percent(value: float, scale: str) -> str:
    pct = value * 100.0 if scale == "decimal" else value
    return f"{pct:.1f}%"


def _format_number(value: float) -> str:
    return f"{value:.2f}"
