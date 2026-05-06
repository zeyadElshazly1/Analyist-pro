"""
Domain insight pack for financial markets time-series (panel OHLC history).

Per-symbol summaries: total return, realised volatility, drawdowns, volume,
trend strength, coverage gaps, and extreme daily moves.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np
import pandas as pd

from app.services.analysis.domain.base import DomainInsightPack
from app.services.dataset_context import _normalise_col
from app.services.dataset_context.schema import DatasetContext, FINANCIAL_MARKETS_TIMESERIES
from app.services.dataset_context.signals import role_for_column

logger = logging.getLogger(__name__)

# ── Public ordering contract (ranking.py mirrors this tuple exactly) ──────────

FINANCE_TS_PREMIUM_TITLE_ORDER: tuple[str, ...] = (
    "Top performers by total return",
    "Worst performers by total return",
    "Highest volatility symbols",
    "Largest drawdowns",
    "Highest volume symbols",
    "Strongest trend symbols",
    "Symbols with incomplete histories",
    "Unusual price movement days",
)

_MIN_SYMBOLS_FOR_RANKING = 3
_MIN_OBS_PER_SYMBOL = 8
_TOP_K = 3
_TRADING_DAYS_PER_YEAR = 252.0


_PRICES_PREF_KEYS: tuple[str, ...] = (
    "adjustedclose",
    "adjclose",
    "close",
    "closingprice",
    "lastprice",
    "last",
    "open",
)


@dataclass(frozen=True)
class TsFinanceColumns:
    symbol_col: str
    date_col: str
    price_col: str
    volume_col: str | None


def pick_price_column(df: pd.DataFrame) -> str | None:
    """Prefer adjusted close, then close / last / open among OHLC-role columns."""
    ohlc = [c for c in df.columns if role_for_column(c) == "ohlc_price"]
    if not ohlc:
        return None

    def rank_col(c: str) -> tuple[int, str]:
        k = _normalise_col(c)
        for i, pk in enumerate(_PRICES_PREF_KEYS):
            if k == pk or k.endswith(pk):
                return (i, k)
        return (len(_PRICES_PREF_KEYS), k)

    return sorted(ohlc, key=rank_col)[0]


def pick_symbol_column(df: pd.DataFrame) -> str | None:
    for c in df.columns:
        if role_for_column(c) == "asset_id":
            return c
    return None


def pick_volume_column(df: pd.DataFrame) -> str | None:
    for c in df.columns:
        if role_for_column(c) == "trade_volume":
            return c
    return None


def resolve_ts_finance_columns(df: pd.DataFrame) -> TsFinanceColumns | None:
    sym = pick_symbol_column(df)
    if sym is None:
        return None
    dcol = None
    for c in df.columns:
        if pd.api.types.is_datetime64_any_dtype(df[c]):
            dcol = c
            break
    if dcol is None:
        for c in df.columns:
            if role_for_column(c) != "trade_date":
                continue
            coerced = pd.to_datetime(df[c], errors="coerce")
            if len(df.index) and float(coerced.notna().mean()) >= 0.5:
                dcol = c
                break
    if dcol is None:
        return None
    px = pick_price_column(df)
    if px is None:
        return None
    vol = pick_volume_column(df)
    return TsFinanceColumns(symbol_col=sym, date_col=dcol, price_col=px, volume_col=vol)


def build_ts_workframe(df: pd.DataFrame, cols: TsFinanceColumns) -> pd.DataFrame | None:
    use_cols = [cols.symbol_col, cols.date_col, cols.price_col]
    if cols.volume_col and cols.volume_col in df.columns:
        use_cols.append(cols.volume_col)
    w = df[use_cols].copy()
    w["_sym"] = w[cols.symbol_col].map(lambda x: str(x).strip() if pd.notna(x) else "")
    w["_dt"] = pd.to_datetime(w[cols.date_col], errors="coerce")
    w["_px"] = pd.to_numeric(w[cols.price_col], errors="coerce")
    if cols.volume_col and cols.volume_col in w.columns:
        w["_vol"] = pd.to_numeric(w[cols.volume_col], errors="coerce")
    else:
        w["_vol"] = np.nan
    w = w[(w["_sym"] != "") & w["_dt"].notna() & w["_px"].notna()]
    if w.empty:
        return None
    return w


def per_symbol_metrics(w: pd.DataFrame) -> pd.DataFrame:
    """One row per symbol with core risk/return stats."""
    rows: list[dict] = []
    for sym, g in w.groupby("_sym", sort=False):
        g = g.sort_values("_dt")
        px = g["_px"].to_numpy(dtype=float)
        n = int(px.shape[0])
        if n < 2:
            continue
        span_days = int(max(0, (g["_dt"].max() - g["_dt"].min()).days))

        total_ret = float(px[-1] / px[0] - 1.0)

        rets = np.diff(px) / np.clip(px[:-1], 1e-12, None)
        rets = rets[np.isfinite(rets)]
        vol_ann = float(np.std(rets, ddof=1) * np.sqrt(_TRADING_DAYS_PER_YEAR)) if rets.size > 1 else float("nan")

        wealth = np.cumprod(np.concatenate([[1.0], 1.0 + rets]))
        peak = np.maximum.accumulate(wealth)
        max_dd = float(np.min(wealth / np.clip(peak, 1e-12, None) - 1.0)) if wealth.size > 1 else float("nan")

        vol_sum = float(np.nansum(g["_vol"].to_numpy(dtype=float)))

        logp = np.log(np.clip(px, 1e-12, None))
        x = np.arange(len(logp), dtype=float)
        try:
            slope = float(np.polyfit(x, logp, 1)[0])
        except Exception:
            slope = float("nan")

        rows.append({
            "symbol": sym,
            "n_obs": n,
            "span_days": span_days,
            "total_return": total_ret,
            "vol_ann": vol_ann,
            "max_drawdown": max_dd,
            "volume_sum": vol_sum,
            "trend_slope_log": slope,
        })
    return pd.DataFrame(rows)


def collect_daily_returns(w: pd.DataFrame) -> pd.DataFrame:
    """Long frame of symbol, date, daily return."""
    pieces: list[pd.DataFrame] = []
    for sym, g in w.groupby("_sym", sort=False):
        g = g.sort_values("_dt")
        px = g["_px"].to_numpy(dtype=float)
        if px.shape[0] < 2:
            continue
        r = np.diff(px) / np.clip(px[:-1], 1e-12, None)
        dt = g["_dt"].iloc[1:].to_numpy()
        pieces.append(pd.DataFrame({"symbol": sym, "date": dt, "ret": r}))
    if not pieces:
        return pd.DataFrame(columns=["symbol", "date", "ret"])
    return pd.concat(pieces, ignore_index=True)


class TimeseriesFinanceInsightPack(DomainInsightPack):
    dataset_type = FINANCIAL_MARKETS_TIMESERIES

    def run(self, df: pd.DataFrame, context: DatasetContext) -> list[dict]:
        insights: list[dict] = []
        cols = resolve_ts_finance_columns(df)
        if cols is None:
            return []
        w = build_ts_workframe(df, cols)
        if w is None:
            return []

        metrics = per_symbol_metrics(w)
        if metrics.empty or metrics.shape[0] < _MIN_SYMBOLS_FOR_RANKING:
            return []

        qualified = metrics[metrics["n_obs"] >= _MIN_OBS_PER_SYMBOL].copy()
        if qualified.shape[0] < _MIN_SYMBOLS_FOR_RANKING:
            return []

        base_cols = [cols.symbol_col, cols.date_col, cols.price_col]
        if cols.volume_col:
            base_cols.append(cols.volume_col)

        for detector in (
            self._top_total_return,
            self._worst_total_return,
            self._highest_vol,
            self._largest_drawdowns,
            self._highest_volume,
            self._strongest_trend,
            self._incomplete_histories,
            self._unusual_day,
        ):
            try:
                insights.extend(detector(qualified, w, cols, base_cols))
            except Exception:
                logger.exception("Timeseries finance detector %s failed", detector.__name__)

        return insights

    def _top_total_return(
        self,
        qualified: pd.DataFrame,
        w: pd.DataFrame,
        cols: TsFinanceColumns,
        base_cols: list[str],
    ) -> list[dict]:
        top = qualified.nlargest(_TOP_K, "total_return")
        names = ", ".join(f"{r.symbol} ({r.total_return:+.1%})" for r in top.itertuples())
        return [{
            "type": "segment",
            "title": "Top performers by total return",
            "finding": f"Strongest total-return names over the window: {names}.",
            "severity": "medium",
            "confidence": 84,
            "evidence": {
                "metric": "total_return",
                "window": "first_to_last_observation_per_symbol",
                "top": [{"symbol": r.symbol, "total_return": round(float(r.total_return), 6)} for r in top.itertuples()],
            },
            "action": "Validate corporate actions and dividends — prefer adjusted prices when available.",
            "why_it_matters": "Total return ranks symbols on cumulative price performance over the shared calendar.",
            "columns_used": base_cols,
            "domain": FINANCIAL_MARKETS_TIMESERIES,
        }]

    def _worst_total_return(
        self,
        qualified: pd.DataFrame,
        w: pd.DataFrame,
        cols: TsFinanceColumns,
        base_cols: list[str],
    ) -> list[dict]:
        bot = qualified.nsmallest(_TOP_K, "total_return")
        names = ", ".join(f"{r.symbol} ({r.total_return:+.1%})" for r in bot.itertuples())
        return [{
            "type": "segment",
            "title": "Worst performers by total return",
            "finding": f"Weakest cumulative performers vs start-of-window prices: {names}.",
            "severity": "medium",
            "confidence": 84,
            "evidence": {
                "metric": "total_return",
                "bottom": [{"symbol": r.symbol, "total_return": round(float(r.total_return), 6)} for r in bot.itertuples()],
            },
            "action": "Review whether weakness is idiosyncratic or shared across peers in the same sleeve.",
            "why_it_matters": "Bottom total-return names highlight sustained weakness over the observation window.",
            "columns_used": base_cols,
            "domain": FINANCIAL_MARKETS_TIMESERIES,
        }]

    def _highest_vol(
        self,
        qualified: pd.DataFrame,
        w: pd.DataFrame,
        cols: TsFinanceColumns,
        base_cols: list[str],
    ) -> list[dict]:
        sub = qualified.dropna(subset=["vol_ann"])
        if sub.shape[0] < _MIN_SYMBOLS_FOR_RANKING:
            return []
        top = sub.nlargest(_TOP_K, "vol_ann")
        names = ", ".join(f"{r.symbol} ({r.vol_ann:.1%} ann.)" for r in top.itertuples())
        return [{
            "type": "concentration",
            "title": "Highest volatility symbols",
            "finding": f"Largest realised volatility (annualised from daily changes): {names}.",
            "severity": "medium",
            "confidence": 82,
            "evidence": {
                "metric": "annualised_realised_vol",
                "top": [{"symbol": r.symbol, "vol_ann": round(float(r.vol_ann), 6)} for r in top.itertuples()],
            },
            "action": "Treat high-volatility names as distinct risk buckets when sizing or comparing returns.",
            "why_it_matters": "Volatility ranking surfaces symbols with the widest day-to-day price swings.",
            "columns_used": base_cols,
            "domain": FINANCIAL_MARKETS_TIMESERIES,
        }]

    def _largest_drawdowns(
        self,
        qualified: pd.DataFrame,
        w: pd.DataFrame,
        cols: TsFinanceColumns,
        base_cols: list[str],
    ) -> list[dict]:
        sub = qualified.dropna(subset=["max_drawdown"])
        if sub.shape[0] < _MIN_SYMBOLS_FOR_RANKING:
            return []
        bot = sub.nsmallest(_TOP_K, "max_drawdown")
        names = ", ".join(f"{r.symbol} ({r.max_drawdown:.1%})" for r in bot.itertuples())
        return [{
            "type": "concentration",
            "title": "Largest drawdowns",
            "finding": f"Largest peak-to-trough drawdowns on cumulative intra-sample wealth: {names}.",
            "severity": "medium",
            "confidence": 82,
            "evidence": {
                "metric": "max_drawdown",
                "worst": [{"symbol": r.symbol, "max_drawdown": round(float(r.max_drawdown), 6)} for r in bot.itertuples()],
            },
            "action": "Relate drawdown depth to liquidity needs and horizon before leaning on historical averages.",
            "why_it_matters": "Drawdown extremes flag symbols that experienced severe intra-sample erosion.",
            "columns_used": base_cols,
            "domain": FINANCIAL_MARKETS_TIMESERIES,
        }]

    def _highest_volume(
        self,
        qualified: pd.DataFrame,
        w: pd.DataFrame,
        cols: TsFinanceColumns,
        base_cols: list[str],
    ) -> list[dict]:
        if cols.volume_col is None:
            return []
        sub = qualified.dropna(subset=["volume_sum"])
        sub = sub[sub["volume_sum"] > 0]
        if sub.shape[0] < _MIN_SYMBOLS_FOR_RANKING:
            return []
        top = sub.nlargest(_TOP_K, "volume_sum")
        names = ", ".join(f"{r.symbol} ({r.volume_sum:,.0f} shares)" for r in top.itertuples())
        return [{
            "type": "concentration",
            "title": "Highest volume symbols",
            "finding": f"Largest cumulative volume traded over the window: {names}.",
            "severity": "low",
            "confidence": 80,
            "evidence": {
                "metric": "volume_sum",
                "top": [{"symbol": r.symbol, "volume_sum": round(float(r.volume_sum), 2)} for r in top.itertuples()],
            },
            "action": "Use volume leaders as liquidity anchors when interpreting price moves or trade feasibility.",
            "why_it_matters": "Volume concentration highlights where market activity clustered in this slice.",
            "columns_used": base_cols,
            "domain": FINANCIAL_MARKETS_TIMESERIES,
        }]

    def _strongest_trend(
        self,
        qualified: pd.DataFrame,
        w: pd.DataFrame,
        cols: TsFinanceColumns,
        base_cols: list[str],
    ) -> list[dict]:
        sub = qualified.dropna(subset=["trend_slope_log"])
        if sub.shape[0] < _MIN_SYMBOLS_FOR_RANKING:
            return []
        top = sub.nlargest(_TOP_K, "trend_slope_log")
        names = ", ".join(f"{r.symbol} (slope={r.trend_slope_log:.4g})" for r in top.itertuples())
        return [{
            "type": "segment",
            "title": "Strongest trend symbols",
            "finding": f"Steepest positive log-price trends vs trading-day index: {names}.",
            "severity": "low",
            "confidence": 78,
            "evidence": {
                "metric": "ols_slope_log_price_vs_time_index",
                "top": [{"symbol": r.symbol, "slope": round(float(r.trend_slope_log), 8)} for r in top.itertuples()],
            },
            "action": "Treat trends as descriptive — confirm with fundamentals or regime tests before acting.",
            "why_it_matters": "Trend slopes summarise sustained directional drift after logging prices.",
            "columns_used": base_cols,
            "domain": FINANCIAL_MARKETS_TIMESERIES,
        }]

    def _incomplete_histories(
        self,
        qualified: pd.DataFrame,
        w: pd.DataFrame,
        cols: TsFinanceColumns,
        base_cols: list[str],
    ) -> list[dict]:
        med_obs = float(qualified["n_obs"].median())
        med_span = float(qualified["span_days"].median())
        if med_obs <= 0 or med_span <= 0:
            return []
        thresh_obs = max(float(_MIN_OBS_PER_SYMBOL), 0.72 * med_obs)
        thresh_span = max(1.0, 0.72 * med_span)
        weak = qualified[
            (qualified["n_obs"] < thresh_obs) | (qualified["span_days"] < thresh_span)
        ]
        if weak.empty:
            return []
        picked = weak.nsmallest(min(_TOP_K, len(weak)), "n_obs")
        names = ", ".join(f"{r.symbol} (n={int(r.n_obs)}, span={int(r.span_days)}d)" for r in picked.itertuples())
        return [{
            "type": "data_quality",
            "title": "Symbols with incomplete histories",
            "finding": (
                f"Some symbols fall below ~72% of the peer median row-count or calendar span — examples: {names}."
            ),
            "severity": "low",
            "confidence": 76,
            "evidence": {
                "median_obs_peers": med_obs,
                "median_span_days_peers": med_span,
                "threshold_obs": thresh_obs,
                "threshold_span_days": thresh_span,
                "examples": [
                    {"symbol": r.symbol, "n_obs": int(r.n_obs), "span_days": int(r.span_days)}
                    for r in picked.itertuples()
                ],
            },
            "action": "Align coverage via shared calendars or exclude thin symbols from like-for-like rankings.",
            "why_it_matters": "Unequal histories skew cross-sectional comparisons of return and risk metrics.",
            "columns_used": base_cols,
            "domain": FINANCIAL_MARKETS_TIMESERIES,
        }]

    def _unusual_day(
        self,
        qualified: pd.DataFrame,
        w: pd.DataFrame,
        cols: TsFinanceColumns,
        base_cols: list[str],
    ) -> list[dict]:
        dr = collect_daily_returns(w)
        if dr.shape[0] < 5:
            return []
        dr["abs_ret"] = dr["ret"].abs()
        i = int(dr["abs_ret"].idxmax())
        row = dr.iloc[i]
        sym = str(row["symbol"])
        dt = pd.Timestamp(row["date"]).strftime("%Y-%m-%d")
        ret = float(row["ret"])
        return [{
            "type": "anomaly",
            "title": "Unusual price movement days",
            "finding": f"Largest absolute daily move in the panel: {sym} on {dt} ({ret:+.2%}).",
            "severity": "medium",
            "confidence": 80,
            "evidence": {
                "symbol": sym,
                "date": dt,
                "daily_return": round(ret, 8),
            },
            "action": "Verify headlines, splits/dividends, or stale prints around that session.",
            "why_it_matters": "Extreme single-day moves often dominate risk dashboards and deserve contextual review.",
            "columns_used": base_cols,
            "domain": FINANCIAL_MARKETS_TIMESERIES,
        }]
