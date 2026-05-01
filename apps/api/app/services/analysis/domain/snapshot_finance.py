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

        values = pd.to_numeric(df[selected_return_col], errors="coerce")
        valid = values.dropna()
        if valid.shape[0] < 3:
            return []

        scale = _detect_percent_scale(valid)
        label_col = _select_label_column(df, context)

        top_idx = valid.nlargest(3).index
        top_rows = [(idx, valid.loc[idx]) for idx in top_idx]
        top_named = [(_label_for_row(df, idx, label_col), value) for idx, value in top_rows]

        finding = "Top 3 outperformance candidates to flag for review: " + ", ".join(
            f"{name} ({_format_percent(value, scale)})" for name, value in top_named
        ) + "."

        columns_used = [selected_return_col]
        if label_col is not None:
            columns_used.append(label_col)

        return [{
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
            "action": "Review the top performers and compare whether momentum is supported by risk-adjusted metrics before making decisions.",
            "why_it_matters": "Return leaders help screen momentum and relative outperformance candidates for deeper risk-aware review.",
            "columns_used": columns_used,
            "domain": FINANCIAL_MARKETS_SNAPSHOT,
        }]

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

        bottom_idx = valid.nsmallest(3).index
        bottom_rows = [(idx, valid.loc[idx]) for idx in bottom_idx]
        bottom_named = [(_label_for_row(df, idx, label_col), value) for idx, value in bottom_rows]

        finding = "Bottom 3 names showing downside pressure to flag for review: " + ", ".join(
            f"{name} ({_format_percent(value, scale)})" for name, value in bottom_named
        ) + "."

        columns_used = [selected_return_col]
        if label_col is not None:
            columns_used.append(label_col)

        return [{
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
            "action": "Review laggards for drawdown, volatility, or sector-specific pressure before interpreting underperformance.",
            "why_it_matters": "Return laggards surface downside pressure and weak momentum candidates that may warrant risk-focused screening.",
            "columns_used": columns_used,
            "domain": FINANCIAL_MARKETS_SNAPSHOT,
        }]


def _select_return_column(df: pd.DataFrame, context: DatasetContext) -> str | None:
    return_cols = [
        col for col, role in context.semantic_roles.items()
        if role == "return_period" and col in df.columns
    ]
    if not return_cols:
        return None

    priorities = [
        {"return1ypct", "oneyearreturn", "1yreturn", "1yrreturn", "ret1y", "performance1y", "perf1y"},
        {"ytdreturn", "returnytd", "retytd", "perfytd"},
        {"return6mpct", "6mreturn", "ret6m", "perf6m", "performance6m"},
        {"return3mpct", "3mreturn", "ret3m", "perf3m", "performance3m"},
        {"return1mpct", "1mreturn", "ret1m", "perf1m", "performance1m"},
    ]

    normalized = {col: _normalise_col(col) for col in return_cols}
    for priority_group in priorities:
        for col, norm in normalized.items():
            if norm in priority_group:
                return col
    return return_cols[0]


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


def _detect_percent_scale(valid: pd.Series) -> str:
    absmax = float(valid.abs().max()) if not valid.empty else 0.0
    return "decimal" if absmax <= 1.0 else "unit"


def _format_percent(value: float, scale: str) -> str:
    pct = value * 100.0 if scale == "decimal" else value
    return f"{pct:.1f}%"
