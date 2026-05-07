"""
Dataset context detector.

detect_dataset_context(df) -> DatasetContext

Classification order (first match wins):
  1. financial_markets_timeseries — trade-date axis (datetime64 or coercible trade-date
     column) + ≥2 OHLC-role columns
  2. financial_markets_snapshot   — snapshot signal score >= CONFIDENCE_THRESHOLD
  3. generic_tabular              — fallback; never raises

All internal exceptions are caught; the function always returns a valid
DatasetContext with dataset_type = GENERIC_TABULAR on failure.
"""
from __future__ import annotations

import logging

import pandas as pd

from .schema import (
    DatasetContext,
    CONFIDENCE_THRESHOLD,
    FINANCIAL_MARKETS_SNAPSHOT,
    FINANCIAL_MARKETS_TIMESERIES,
    GENERIC_TABULAR,
)
from .signals import role_for_column
from .roles import resolve_semantic_roles

logger = logging.getLogger(__name__)

# ── Snapshot signal weights ───────────────────────────────────────────────────
# Weights are chosen so that the three core signals (return + volatility +
# sharpe) sum to exactly CONFIDENCE_THRESHOLD (0.65), and the full
# Yahoo-like signal set sums to 1.00.
#
# Core (0.65 total):
#   return_period  0.25
#   volatility     0.20
#   sharpe_ratio   0.20
#
# Boost (0.35 total):
#   asset_class    0.08
#   sector         0.06
#   analyst_upside 0.05
#   position_52w   0.05
#   asset_id       0.04
#   asset_label    0.03
#   composite_score 0.02
#   size_metric    0.02

_SNAPSHOT_SIGNAL_WEIGHTS: dict[str, float] = {
    "return_period":    0.25,
    "volatility":       0.20,
    "sharpe_ratio":     0.20,
    "asset_class":      0.08,
    "sector":           0.06,
    "analyst_upside":   0.05,
    "position_52w":     0.05,
    "asset_id":         0.04,
    "asset_label":      0.03,
    "composite_score":  0.02,
    "size_metric":      0.02,
}
_SNAPSHOT_MAX_WEIGHT: float = sum(_SNAPSHOT_SIGNAL_WEIGHTS.values())  # 1.00


# ── Internal helpers ──────────────────────────────────────────────────────────

def _has_datetime_column(df: pd.DataFrame) -> bool:
    """Return True if any column has a datetime64 dtype."""
    return any(pd.api.types.is_datetime64_any_dtype(df[c]) for c in df.columns)


def _infer_trade_date_column(df: pd.DataFrame) -> str | None:
    """
    Pick the best time-axis column: prefer native datetime64 columns, otherwise
    attempt coercion on columns whose name matches trade-date signal patterns.
    """
    for c in df.columns:
        if pd.api.types.is_datetime64_any_dtype(df[c]):
            return c
    best_col: str | None = None
    best_rate = 0.0
    for c in df.columns:
        if role_for_column(c) != "trade_date":
            continue
        try:
            coerced = pd.to_datetime(df[c], errors="coerce")
            rate = float(coerced.notna().mean()) if len(df.index) else 0.0
        except Exception:
            rate = 0.0
        if rate > best_rate:
            best_col, best_rate = c, rate
    if best_col is not None and best_rate >= 0.5:
        return best_col
    return None


def _timeseries_axis_ready(df: pd.DataFrame) -> bool:
    """True when a usable calendar/trade-date axis exists."""
    return _has_datetime_column(df) or _infer_trade_date_column(df) is not None


def _ohlc_columns(df: pd.DataFrame) -> list[str]:
    """Return column names whose role is ohlc_price."""
    return [c for c in df.columns if role_for_column(c) == "ohlc_price"]


def _score_snapshot(df: pd.DataFrame) -> tuple[float, list[str]]:
    """
    Score df against the financial_markets_snapshot signal table.

    Returns (confidence, matched_signal_strings).
    confidence is in [0.0, 1.0]; matched_signal_strings are human-readable.
    """
    matched_weight = 0.0
    signals: list[str] = []

    for role, weight in _SNAPSHOT_SIGNAL_WEIGHTS.items():
        matching = [c for c in df.columns if role_for_column(c) == role]
        if matching:
            matched_weight += weight
            col_label = ", ".join(matching[:3])
            if len(matching) > 3:
                col_label += f" (+{len(matching) - 3} more)"
            signals.append(f"{role} column detected ({col_label})")

    # Round before returning so that IEEE-754 imprecision in the weight sums
    # (e.g. 0.25 + 0.20 + 0.20 == 0.6499999... rather than 0.65) doesn't
    # cause a boundary-exact score to fall fractionally below the threshold.
    confidence = round(matched_weight / _SNAPSHOT_MAX_WEIGHT, 4)
    return confidence, signals


def _snapshot_warnings(df: pd.DataFrame, roles: dict[str, str]) -> tuple[str, ...]:
    """
    Build non-fatal warnings for a financial_markets_snapshot context.

    Currently checks: mixed asset classes.
    """
    w: list[str] = []
    asset_class_cols = [c for c, r in roles.items() if r == "asset_class"]
    for col in asset_class_cols:
        try:
            n = df[col].dropna().nunique()
            if n >= 2:
                w.append(
                    "This dataset contains mixed asset classes. "
                    "Risk and return metrics should be interpreted with caution across classes."
                )
                break
        except Exception:
            pass
    return tuple(w)


def _fallback_context(
    roles: dict[str, str],
    extra_signals: list[str] | None = None,
    extra_warnings: list[str] | None = None,
) -> DatasetContext:
    """Return a generic_tabular DatasetContext."""
    signals: tuple[str, ...] = (
        "No supported dataset context confidently detected",
        *(extra_signals or []),
    )
    return DatasetContext(
        dataset_type=GENERIC_TABULAR,
        confidence=1.0,
        matched_signals=signals,
        semantic_roles=roles,
        warnings=tuple(extra_warnings or []),
    )


# ── Public API ────────────────────────────────────────────────────────────────

def detect_dataset_context(df: pd.DataFrame) -> DatasetContext:
    """
    Classify df into one of the supported dataset types.

    Returns a fully populated DatasetContext.  Never raises — any internal
    exception produces a generic_tabular fallback with a warning.

    Classification order:
      1. financial_markets_timeseries: trade-date axis + ≥2 OHLC-role columns
      2. financial_markets_snapshot:   snapshot score >= CONFIDENCE_THRESHOLD
      3. generic_tabular:              fallback
    """
    try:
        return _classify(df)
    except Exception as exc:
        logger.exception("detect_dataset_context failed; returning generic_tabular")
        try:
            roles: dict[str, str] = {c: "unknown" for c in df.columns}
        except Exception:
            roles = {}
        return DatasetContext(
            dataset_type=GENERIC_TABULAR,
            confidence=1.0,
            matched_signals=(),
            semantic_roles=roles,
            warnings=(
                f"Dataset context detection failed unexpectedly ({exc!r}). "
                "Falling back to generic analysis.",
            ),
        )


def _classify(df: pd.DataFrame) -> DatasetContext:
    """Inner classification logic — may raise; caller wraps in try/except."""
    # Empty or column-free DataFrames → generic immediately
    if df.empty or len(df.columns) == 0:
        return _fallback_context(
            roles={},
            extra_signals=["DataFrame has no rows or no columns"],
        )

    ts_axis_col = None
    if _has_datetime_column(df):
        ts_axis_col = next(c for c in df.columns if pd.api.types.is_datetime64_any_dtype(df[c]))
    else:
        ts_axis_col = _infer_trade_date_column(df)

    ohlc_cols = _ohlc_columns(df)

    # ── 1. Timeseries: trade-date axis + ≥2 OHLC columns ───────────────────────
    if ts_axis_col is not None and len(ohlc_cols) >= 2:
        roles = resolve_semantic_roles(df, FINANCIAL_MARKETS_TIMESERIES)
        signals = (
            f"Time axis detected ({ts_axis_col})",
            f"OHLC price columns detected ({', '.join(ohlc_cols[:4])})",
        )
        return DatasetContext(
            dataset_type=FINANCIAL_MARKETS_TIMESERIES,
            confidence=0.90,
            matched_signals=signals,
            semantic_roles=roles,
            warnings=(
                "Financial markets time-series layout detected (OHLC-style prices over dates). "
                "Analysis prioritises per-symbol return, risk, liquidity, and data coverage.",
            ),
        )

    # ── 2. Snapshot: score signals ────────────────────────────────────────────
    snap_conf, snap_signals = _score_snapshot(df)
    if snap_conf >= CONFIDENCE_THRESHOLD:
        roles = resolve_semantic_roles(df, FINANCIAL_MARKETS_SNAPSHOT)
        warnings = _snapshot_warnings(df, roles)
        return DatasetContext(
            dataset_type=FINANCIAL_MARKETS_SNAPSHOT,
            confidence=round(snap_conf, 4),
            matched_signals=tuple(snap_signals),
            semantic_roles=roles,
            warnings=warnings,
        )

    # ── 3. Generic fallback ───────────────────────────────────────────────────
    roles = resolve_semantic_roles(df, GENERIC_TABULAR)
    extra: list[str] = []
    if snap_conf > 0.0:
        extra.append(
            f"Best financial_markets_snapshot match: {snap_conf:.0%} "
            f"(threshold is {CONFIDENCE_THRESHOLD:.0%})"
        )
    return _fallback_context(roles=roles, extra_signals=extra)
