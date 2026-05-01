"""
Finance-aware chart suggestions for financial_markets_snapshot datasets (Task 74A).

When ``DatasetContext.dataset_type`` is ``financial_markets_snapshot``, chart
payloads use semantic roles (return, volatility, asset labels, etc.) instead of
generic time-series or index-based line charts that mislead on cross-sectional
market snapshots.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from app.services.analysis.domain import snapshot_finance as _sf
from app.services.charting.budget import MAX_SCATTER_POINTS
from app.services.charting.narrator import _narrate_scatter
from app.services.charting.stats import _pearson, _spearman
from app.services.dataset_context.schema import FINANCIAL_MARKETS_SNAPSHOT, DatasetContext

# Minimum valid rows / groups (Task 74A)
_MIN_ROWS_LEADERBOARD = 5
_MIN_ROWS_SCATTER = 5
_MIN_ROWS_GROUP_AVG = 3
_MIN_DISTINCT_GROUPS = 2
_LEADERBOARD_TOP_N = 10


def _cols_for_snapshot_charts(df: pd.DataFrame, ctx: DatasetContext) -> dict[str, str | None]:
    """Resolve role-based columns using the same priority rules as SnapshotFinanceInsightPack."""
    return {
        "return_col": _sf._select_return_column(df, ctx),
        "vol_col": _sf._select_volatility_column(df, ctx),
        "label_col": _sf._select_label_column(df, ctx),
        "asset_class_col": _sf._select_asset_class_column(df, ctx),
        "sector_col": _sf._select_sector_column(df, ctx),
        "analyst_col": _sf._select_analyst_upside_column(df, ctx),
        "pos52_col": _sf._select_52w_position_column(df, ctx),
    }


def _bar_leaderboard(
    df: pd.DataFrame,
    label_col: str,
    value_col: str,
    *,
    title: str,
    description: str,
    insight: str,
    ascending: bool,
    score: float,
) -> dict | None:
    sub = df[[label_col, value_col]].copy()
    sub[value_col] = pd.to_numeric(sub[value_col], errors="coerce")
    sub = sub.dropna(subset=[value_col])
    if len(sub) < _MIN_ROWS_LEADERBOARD:
        return None
    sub = sub.assign(
        _lab=sub[label_col].map(lambda x: str(x).strip() if pd.notna(x) else "")
    )
    sub["_lab"] = sub["_lab"].replace("", np.nan)
    sub = sub.dropna(subset=["_lab"])
    if len(sub) < _MIN_ROWS_LEADERBOARD:
        return None
    sub_sorted = sub.sort_values(value_col, ascending=ascending).head(_LEADERBOARD_TOP_N)
    data: list[dict] = []
    for _, row in sub_sorted.iterrows():
        lab = str(row["_lab"])[:160]
        data.append({"label": lab, "value": round(float(row[value_col]), 8)})
    return {
        "type": "bar",
        "title": title,
        "description": description,
        "insight": insight,
        "x_key": "label",
        "y_key": "value",
        "x_label": label_col,
        "y_label": value_col,
        "data": data,
        "horizontal": True,
        "recommended": not ascending,
        "score": score,
    }


def _avg_numeric_by_category(
    df: pd.DataFrame,
    category_col: str,
    value_col: str,
    *,
    title: str,
    description: str,
    score: float,
) -> dict | None:
    gdf = df[[category_col, value_col]].copy()
    gdf[value_col] = pd.to_numeric(gdf[value_col], errors="coerce")
    gdf = gdf.dropna(subset=[value_col])
    if gdf.empty:
        return None
    gdf[category_col] = gdf[category_col].map(lambda x: str(x).strip() if pd.notna(x) else np.nan)
    gdf = gdf.dropna(subset=[category_col])
    grp = gdf.groupby(category_col, sort=False)[value_col].agg(["count", "mean"])
    qualified = grp[grp["count"] >= _MIN_ROWS_GROUP_AVG]
    if len(qualified) < _MIN_DISTINCT_GROUPS:
        return None
    means = qualified["mean"].sort_values(ascending=False)
    data = [{"label": str(cat), "value": round(float(mn), 8)} for cat, mn in means.items()]
    top = means.index[0]
    top_mean = float(means.iloc[0])
    return {
        "type": "bar",
        "title": title,
        "description": description,
        "insight": (
            f"Across {len(data)} categories with at least {_MIN_ROWS_GROUP_AVG} assets each, "
            f"'{top}' posts the highest mean {value_col} (~{top_mean:.4g})."
        ),
        "x_key": "label",
        "y_key": "value",
        "x_label": category_col,
        "y_label": f"Mean {value_col}",
        "data": data,
        "horizontal": len(data) > 6,
        "recommended": False,
        "score": score,
    }


def _risk_return_scatter(
    df: pd.DataFrame,
    vol_col: str,
    ret_col: str,
    group_col: str | None,
) -> dict | None:
    cols = [vol_col, ret_col]
    if group_col and group_col in df.columns:
        cols.append(group_col)
    work = df[cols].copy()
    work[vol_col] = pd.to_numeric(work[vol_col], errors="coerce")
    work[ret_col] = pd.to_numeric(work[ret_col], errors="coerce")
    clean = work[[vol_col, ret_col]].dropna()
    if len(clean) < _MIN_ROWS_SCATTER:
        return None
    if float(clean[vol_col].std()) < 1e-10 or float(clean[ret_col].std()) < 1e-10:
        return None

    pr, pp = _pearson(clean[vol_col], clean[ret_col])
    sr, sp = _spearman(clean[vol_col], clean[ret_col])

    sample = clean.sample(min(len(clean), MAX_SCATTER_POINTS), random_state=42)
    idx = sample.index
    x = sample[vol_col].to_numpy(dtype=float)
    y = sample[ret_col].to_numpy(dtype=float)

    try:
        coeffs = np.polyfit(clean[vol_col].values, clean[ret_col].values, 1)
        predicted = np.polyval(coeffs, x)
        residuals = y - predicted
        res_std = float(np.std(residuals))
        anomaly = (res_std > 0) & (np.abs(residuals) > 2 * res_std)
        x_min, x_max = float(clean[vol_col].min()), float(clean[vol_col].max())
        regression = [
            {"x": x_min, "y_hat": float(np.polyval(coeffs, x_min))},
            {"x": x_max, "y_hat": float(np.polyval(coeffs, x_max))},
        ]
    except (np.linalg.LinAlgError, Exception):
        anomaly = np.zeros(len(x), dtype=bool)
        regression = []

    narration = _narrate_scatter(vol_col, ret_col, pr, pp, sr)
    significance_badge = "significant" if pp < 0.05 else "not significant"
    best_r = max(abs(pr), abs(sr))

    data: list[dict] = []
    if group_col and group_col in df.columns:
        for xi, yi, ai, ix in zip(x, y, anomaly, idx):
            gv = df.loc[ix, group_col]
            grp = "" if pd.isna(gv) else str(gv).strip()
            data.append({"x": float(xi), "y": float(yi), "is_anomaly": bool(ai), "group": grp})
    else:
        for xi, yi, ai in zip(x, y, anomaly):
            data.append({"x": float(xi), "y": float(yi), "is_anomaly": bool(ai)})

    result: dict = {
        "type": "scatter",
        "title": "Risk vs return",
        "description": f"Cross-section of {vol_col} (risk axis) versus {ret_col} (return axis)",
        "insight": narration,
        "x_key": "x",
        "y_key": "y",
        "x_label": vol_col,
        "y_label": ret_col,
        "data": data,
        "regression": regression,
        "significance_badge": significance_badge,
        "pearson_r": round(pr, 4),
        "pearson_p": round(pp, 6),
        "spearman_rho": round(sr, 4),
        "spearman_p": round(sp, 6),
        "recommended": best_r > 0.35,
        "score": round(8.5 + min(best_r, 1.0) * 0.5, 2),
    }
    if group_col and group_col in df.columns:
        result["color_key"] = group_col
    return result


def build_financial_snapshot_charts(df: pd.DataFrame, ctx: DatasetContext) -> list[dict]:
    """
    Build chart payloads appropriate for a financial market *cross-section* snapshot.

    Caller must ensure ``ctx.dataset_type == FINANCIAL_MARKETS_SNAPSHOT``.
    """
    if ctx.dataset_type != FINANCIAL_MARKETS_SNAPSHOT:
        return []

    c = _cols_for_snapshot_charts(df, ctx)
    ret_col = c["return_col"]
    vol_col = c["vol_col"]
    label_col = c["label_col"]
    asset_class_col = c["asset_class_col"]
    sector_col = c["sector_col"]
    analyst_col = c["analyst_col"]
    pos52_col = c["pos52_col"]

    out: list[dict] = []

    if ret_col and label_col:
        ch = _bar_leaderboard(
            df,
            label_col,
            ret_col,
            title="Top assets by return",
            description=f"Top {_LEADERBOARD_TOP_N} assets by {ret_col}",
            insight=f"Ranked by {ret_col} (higher is better for this metric).",
            ascending=False,
            score=8.85,
        )
        if ch:
            out.append(ch)
        ch = _bar_leaderboard(
            df,
            label_col,
            ret_col,
            title="Largest return laggards",
            description=f"Bottom {_LEADERBOARD_TOP_N} assets by {ret_col}",
            insight=f"Lowest {ret_col} values in the snapshot.",
            ascending=True,
            score=8.75,
        )
        if ch:
            out.append(ch)

    if vol_col and label_col:
        ch = _bar_leaderboard(
            df,
            label_col,
            vol_col,
            title="Highest volatility assets",
            description=f"Top {_LEADERBOARD_TOP_N} assets by {vol_col}",
            insight=f"Ranked by {vol_col} (higher indicates more dispersion).",
            ascending=False,
            score=8.78,
        )
        if ch:
            out.append(ch)

    if vol_col and ret_col:
        grp = asset_class_col if asset_class_col and asset_class_col in df.columns else None
        sc = _risk_return_scatter(df, vol_col, ret_col, grp)
        if sc:
            out.append(sc)

    if ret_col and asset_class_col:
        ch = _avg_numeric_by_category(
            df,
            asset_class_col,
            ret_col,
            title="Average return by asset class",
            description=f"Mean {ret_col} for each asset class (≥{_MIN_ROWS_GROUP_AVG} rows per class)",
            score=8.55,
        )
        if ch:
            out.append(ch)

    if ret_col and sector_col:
        ch = _avg_numeric_by_category(
            df,
            sector_col,
            ret_col,
            title="Average return by sector",
            description=f"Mean {ret_col} for each sector (≥{_MIN_ROWS_GROUP_AVG} rows per sector)",
            score=8.45,
        )
        if ch:
            out.append(ch)

    if analyst_col and label_col:
        ch = _bar_leaderboard(
            df,
            label_col,
            analyst_col,
            title="Highest analyst-implied upside",
            description=f"Top {_LEADERBOARD_TOP_N} assets by {analyst_col}",
            insight=f"Ranked by {analyst_col}.",
            ascending=False,
            score=8.4,
        )
        if ch:
            out.append(ch)

    if pos52_col and label_col:
        ch = _bar_leaderboard(
            df,
            label_col,
            pos52_col,
            title="Assets by 52-week position",
            description=f"{_LEADERBOARD_TOP_N} assets ranked by {pos52_col}",
            insight="Higher values typically sit nearer the trailing 52-week range top.",
            ascending=False,
            score=8.35,
        )
        if ch:
            out.append(ch)

    return out
