"""
Large-dataset fast path for analysis (Task 77C).

When row counts exceed LARGE_DATASET_ROWS, expensive generic detectors run on a
deterministic sample while summary statistics (shape, symbol cardinality, date
span, missingness in health/profile) still use the full cleaned frame where cheap.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from app.services.dataset_context import detect_dataset_context
from app.services.dataset_context.schema import FINANCIAL_MARKETS_TIMESERIES

# ── Central thresholds (single source of truth for analysis sampling) ─────────

LARGE_DATASET_ROWS = 250_000
LARGE_DATASET_SAMPLE_ROWS = 100_000
LARGE_HEALTH_HEAVY_SAMPLE_ROWS = 100_000

# Peek size for early dataset-context detection (avoid scanning millions of rows twice).
LARGE_CONTEXT_PEEK_ROWS = 100_000

# Floor / cap when dividing the TS sample budget across symbols.
_TS_MIN_ROWS_PER_SYMBOL = 50
_TS_MAX_ROWS_PER_SYMBOL_CAP = 2_500

LARGE_DATASET_NARRATIVE_NOTE = (
    "\n\nLarge dataset mode used: expensive pattern detection ran on a representative sample."
)


def prepare_analysis_frame(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """
    Return (dataframe_for_insight_pipeline, metadata).

    Small datasets pass through unchanged. Large datasets return a deterministic
    sample suitable for correlations, anomalies, trends, and domain packs.
    """
    full_rows = len(df)
    full_cols = len(df.columns)
    base: dict = {
        "large_dataset_mode": False,
        "full_rows": full_rows,
        "full_columns": full_cols,
        "analyzed_rows": full_rows,
        "sample_strategy": "full",
        "symbol_count": None,
        "date_range_start": None,
        "date_range_end": None,
    }
    if full_rows <= LARGE_DATASET_ROWS or df.empty:
        return df, base

    peek_n = min(LARGE_CONTEXT_PEEK_ROWS, full_rows)
    peek = df.iloc[:peek_n]
    ctx = detect_dataset_context(peek)

    if ctx.dataset_type == FINANCIAL_MARKETS_TIMESERIES:
        sampled, meta = _sample_financial_markets_timeseries(df, base)
        return sampled, meta

    n = min(LARGE_DATASET_SAMPLE_ROWS, full_rows)
    out = df.sample(n=n, random_state=42)
    base.update(
        {
            "large_dataset_mode": True,
            "analyzed_rows": len(out),
            "sample_strategy": "random_uniform",
        }
    )
    return out, base


def _iso_ts(ts: pd.Timestamp | None) -> str | None:
    if ts is None or pd.isna(ts):
        return None
    return pd.Timestamp(ts).strftime("%Y-%m-%d")


def _sample_financial_markets_timeseries(df: pd.DataFrame, base: dict) -> tuple[pd.DataFrame, dict]:
    from app.services.analysis.domain.timeseries_finance import resolve_ts_finance_columns

    cols = resolve_ts_finance_columns(df)
    if cols is None:
        n = min(LARGE_DATASET_SAMPLE_ROWS, len(df))
        out = df.sample(n=n, random_state=42)
        base.update(
            {
                "large_dataset_mode": True,
                "analyzed_rows": len(out),
                "sample_strategy": "random_uniform_fallback_non_ts",
            }
        )
        return out, base

    dt = pd.to_datetime(df[cols.date_col], errors="coerce")
    sym = df[cols.symbol_col].map(lambda x: str(x).strip() if pd.notna(x) else "")
    mask = dt.notna() & (sym != "")
    if not bool(mask.any()):
        n = min(LARGE_DATASET_SAMPLE_ROWS, len(df))
        out = df.sample(n=n, random_state=42)
        base.update(
            {
                "large_dataset_mode": True,
                "analyzed_rows": len(out),
                "sample_strategy": "random_uniform_fallback_bad_dates",
            }
        )
        return out, base

    idx_arr = np.flatnonzero(mask.to_numpy())
    tmp = pd.DataFrame(
        {
            "_sym": sym.iloc[idx_arr].to_numpy(),
            "_dt": dt.iloc[idx_arr].to_numpy(),
            "_idx": idx_arr,
        }
    )
    n_syms = int(tmp["_sym"].nunique())
    per_sym = max(
        _TS_MIN_ROWS_PER_SYMBOL,
        min(
            _TS_MAX_ROWS_PER_SYMBOL_CAP,
            LARGE_DATASET_SAMPLE_ROWS // max(n_syms, 1),
        ),
    )
    picked = tmp.sort_values("_dt").groupby("_sym", sort=False).tail(per_sym)["_idx"].to_numpy()
    picked_sorted = np.sort(picked)
    out = df.iloc[picked_sorted].copy()

    dr_start = dt[mask].min()
    dr_end = dt[mask].max()

    base.update(
        {
            "large_dataset_mode": True,
            "analyzed_rows": len(out),
            "sample_strategy": "timeseries_recent_rows_per_symbol",
            "symbol_count": int(sym[mask].nunique()),
            "date_range_start": _iso_ts(dr_start),
            "date_range_end": _iso_ts(dr_end),
        }
    )
    return out, base


def attach_large_dataset_meta(result: dict, meta: dict) -> None:
    """Merge sampling metadata into the canonical analysis API payload."""
    result["large_dataset_mode"] = meta["large_dataset_mode"]
    result["full_rows"] = meta["full_rows"]
    result["full_columns"] = meta["full_columns"]
    result["analyzed_rows"] = meta["analyzed_rows"]
    result["sample_strategy"] = meta["sample_strategy"]
    if meta.get("symbol_count") is not None:
        result["symbol_count"] = meta["symbol_count"]
    if meta.get("date_range_start"):
        result["date_range_start"] = meta["date_range_start"]
    if meta.get("date_range_end"):
        result["date_range_end"] = meta["date_range_end"]
