"""
Per-chart-type payload builders.

Each function assembles one complete chart dict ready for the frontend.
Data generation uses vectorized NumPy operations instead of iterrows()
for performance on large datasets.
"""
import numpy as np
import pandas as pd

from .budget import (
    MAX_TIMESERIES_POINTS,
    MAX_SCATTER_POINTS,
    MAX_CAT_BAR_TOP,
    MAX_BOXPLOT_OUTLIERS,
)
from .narrator import (
    _narrate_timeseries,
    _narrate_distribution,
    _narrate_scatter,
    _narrate_categorical,
)
from .stats import _normality_badge


def _histogram_bins(series: pd.Series, n_bins: int = 10) -> list[dict]:
    """Build histogram bin data with density and anomaly flagging."""
    clean = series.dropna()
    if len(clean) == 0:
        return []
    q1, q3  = float(clean.quantile(0.25)), float(clean.quantile(0.75))
    iqr     = q3 - q1
    lo_fence = q1 - 1.5 * iqr
    hi_fence = q3 + 1.5 * iqr

    counts, edges = np.histogram(clean, bins=n_bins)
    total = len(clean)
    result = []
    for i, count in enumerate(counts):
        label      = f"{edges[i]:.2g}–{edges[i+1]:.2g}"
        bin_center = (edges[i] + edges[i + 1]) / 2
        result.append({
            "label":         label,
            "value":         int(count),
            "density":       round(float(count) / total, 4),
            "is_anomaly_bin": bool(bin_center < lo_fence or bin_center > hi_fence),
        })
    return result


# ── Time-series line chart ────────────────────────────────────────────────────

def build_timeseries_payload(df: pd.DataFrame, date_col: str, num_col: str) -> dict | None:
    """
    Return a line chart payload for num_col plotted over date_col.
    Returns None when there are fewer than 4 data points.
    Data points are generated with vectorized operations — no iterrows().
    """
    ts = df[[date_col, num_col]].dropna().sort_values(date_col)
    if len(ts) < 4:
        return None

    values  = ts[num_col].to_numpy(dtype=float)
    dates   = ts[date_col].astype(str).str[:10].to_numpy()
    mean_v  = float(values.mean())
    std_v   = float(values.std())
    anomaly = np.abs(values - mean_v) > 2 * std_v       # vectorized boolean array

    data = [
        {"date": str(d), "value": float(v), "is_anomaly": bool(a)}
        for d, v, a in zip(dates, values, anomaly)
    ][:MAX_TIMESERIES_POINTS]

    narration = _narrate_timeseries(num_col, ts[num_col], date_col)
    return {
        "type":        "line",
        "title":       f"{num_col} over time",
        "description": f"Trend of {num_col} over {date_col}",
        "insight":     narration,
        "x_key":       "date",
        "y_key":       "value",
        "x_label":     date_col,
        "y_label":     num_col,
        "data":        data,
        "reference_lines": [
            {"label": "Mean",   "value": round(mean_v, 4),                        "color": "#6366f1"},
            {"label": "Median", "value": round(float(np.median(values)), 4),      "color": "#a78bfa"},
        ],
        "recommended": True,
        "score":       10,
    }


# ── Numeric histogram ─────────────────────────────────────────────────────────

def build_histogram_payload(
    df: pd.DataFrame, col: str, is_first_chart: bool
) -> dict | None:
    """Return a histogram (bar) payload for col. Returns None when too few values."""
    clean = df[col].dropna()
    if len(clean) < 5:
        return None

    skew   = float(clean.skew())
    n_bins = 15 if len(clean) > 500 else 10
    hist_data = _histogram_bins(clean, n_bins=n_bins)
    if not hist_data:
        return None

    sig_badge, normality_p = _normality_badge(clean)
    narration = _narrate_distribution(col, clean, skew)

    return {
        "type":        "bar",
        "title":       f"Distribution of {col}",
        "description": f"Histogram showing the spread of values in {col}",
        "insight":     narration,
        "x_key":       "label",
        "y_key":       "value",
        "x_label":     col,
        "y_label":     "Count",
        "data":        hist_data,
        "reference_lines": [
            {"label": "Mean",   "value": round(float(clean.mean()),   4), "color": "#6366f1"},
            {"label": "Median", "value": round(float(clean.median()), 4), "color": "#a78bfa"},
        ],
        "significance_badge": sig_badge,
        "normality_p":        round(normality_p, 4) if normality_p is not None else None,
        "recommended":        is_first_chart,
        "score":              8,
    }


# ── Categorical bar chart ─────────────────────────────────────────────────────

def build_cat_bar_payload(df: pd.DataFrame, col: str) -> dict | None:
    """Return a categorical bar chart payload. Returns None when n_unique < 2."""
    n_unique = df[col].nunique()
    if n_unique < 2:
        return None

    counts       = df[col].fillna("(missing)").astype(str).value_counts()
    show_top     = n_unique > 15
    display_counts = counts.head(MAX_CAT_BAR_TOP)
    if len(display_counts) == 0:
        return None

    top_cat = str(display_counts.index[0])
    top_pct = float(display_counts.iloc[0]) / max(len(df), 1) * 100
    data    = [{"label": str(k), "value": int(v)} for k, v in display_counts.items()]
    if show_top and len(counts) > MAX_CAT_BAR_TOP:
        data.append({"label": "Other", "value": int(counts.iloc[MAX_CAT_BAR_TOP:].sum())})

    narration = _narrate_categorical(col, top_cat, top_pct, n_unique)
    n_shown   = f"top {MAX_CAT_BAR_TOP} of {n_unique}" if show_top else str(n_unique)
    return {
        "type":        "bar",
        "title":       f"Top values in {col}" if show_top else f"Distribution of {col}",
        "description": f"Frequency of {n_shown} categories in {col}",
        "insight":     narration,
        "x_key":       "label",
        "y_key":       "value",
        "x_label":     col,
        "y_label":     "Count",
        "data":        data,
        "horizontal":  show_top,
        "recommended": False,
        "score":       6,
    }


# ── Categorical pie chart ─────────────────────────────────────────────────────

def build_pie_payload(df: pd.DataFrame, col: str) -> dict | None:
    """Return a pie chart payload for low-cardinality columns (2–8 unique values)."""
    n_unique = df[col].nunique()
    if n_unique < 2 or n_unique > 8:
        return None

    counts  = df[col].fillna("(missing)").astype(str).value_counts()
    data    = [{"name": str(k), "value": int(v)} for k, v in counts.items()]
    top_pct = float(counts.iloc[0]) / max(len(df), 1) * 100
    return {
        "type":        "pie",
        "title":       f"Breakdown of {col}",
        "description": f"Proportional breakdown of {col} categories",
        "insight":     f"'{counts.index[0]}' accounts for {top_pct:.1f}% of all records.",
        "x_key":       "name",
        "y_key":       "value",
        "x_label":     col,
        "y_label":     "Count",
        "data":        data,
        "recommended": False,
        "score":       5,
    }


# ── Scatter plot ──────────────────────────────────────────────────────────────

def build_scatter_payload(
    df: pd.DataFrame,
    col1: str,
    col2: str,
    pearson_r: float,
    pearson_p: float,
    spearman_rho: float,
    spearman_p: float,
) -> dict | None:
    """
    Return a scatter chart payload for the (col1, col2) pair.

    Includes both Pearson and Spearman metrics.
    Data points are generated with vectorized operations — no iterrows().
    Returns None for degenerate (near-constant) columns.
    """
    clean = df[[col1, col2]].dropna()
    if float(clean[col1].std()) < 1e-10 or float(clean[col2].std()) < 1e-10:
        return None

    sample = clean.sample(min(len(clean), MAX_SCATTER_POINTS), random_state=42)
    x = sample[col1].to_numpy(dtype=float)
    y = sample[col2].to_numpy(dtype=float)

    try:
        coeffs    = np.polyfit(clean[col1].values, clean[col2].values, 1)
        predicted = np.polyval(coeffs, x)
        residuals = y - predicted
        res_std   = float(np.std(residuals))
        anomaly   = (res_std > 0) & (np.abs(residuals) > 2 * res_std)
        x_min, x_max = float(clean[col1].min()), float(clean[col1].max())
        regression = [
            {"x": x_min, "y_hat": float(np.polyval(coeffs, x_min))},
            {"x": x_max, "y_hat": float(np.polyval(coeffs, x_max))},
        ]
    except (np.linalg.LinAlgError, Exception):
        anomaly    = np.zeros(len(x), dtype=bool)
        regression = []

    data = [
        {"x": float(xi), "y": float(yi), "is_anomaly": bool(ai)}
        for xi, yi, ai in zip(x, y, anomaly)
    ]

    narration          = _narrate_scatter(col1, col2, pearson_r, pearson_p, spearman_rho)
    significance_badge = "significant" if pearson_p < 0.05 else "not significant"
    best_r             = max(abs(pearson_r), abs(spearman_rho))

    return {
        "type":               "scatter",
        "title":              f"{col1} vs {col2}",
        "description":        f"Correlation between {col1} and {col2}",
        "insight":            narration,
        "x_key":              "x",
        "y_key":              "y",
        "x_label":            col1,
        "y_label":            col2,
        "data":               data,
        "regression":         regression,
        "significance_badge": significance_badge,
        "pearson_r":          round(pearson_r,   4),
        "pearson_p":          round(pearson_p,   6),
        "spearman_rho":       round(spearman_rho, 4),
        "spearman_p":         round(spearman_p,   6),
        "recommended":        best_r > 0.7,
        "score":              round(best_r * 9, 1),
    }


# ── Boxplot ───────────────────────────────────────────────────────────────────

def build_boxplot_payload(df: pd.DataFrame, cat_col: str, num_col: str) -> dict | None:
    """
    Return a box-whisker chart payload comparing num_col across cat_col groups.
    Returns None when fewer than 2 valid groups are found.
    """
    n_unique = df[cat_col].nunique()
    if n_unique < 2 or n_unique > 12:
        return None

    box_data = []
    for cat_val, grp in df.groupby(cat_col)[num_col]:
        clean_grp = grp.dropna()
        if len(clean_grp) < 4:
            continue
        q1  = float(clean_grp.quantile(0.25))
        q3  = float(clean_grp.quantile(0.75))
        iqr = q3 - q1
        lo  = q1 - 1.5 * iqr
        hi  = q3 + 1.5 * iqr
        outliers = [
            round(float(v), 4)
            for v in clean_grp[(clean_grp < lo) | (clean_grp > hi)].tolist()[:MAX_BOXPLOT_OUTLIERS]
        ]
        box_data.append({
            "name":     str(cat_val),
            "min":      round(float(clean_grp[clean_grp >= lo].min()), 4),
            "q1":       round(q1, 4),
            "median":   round(float(clean_grp.median()), 4),
            "q3":       round(q3, 4),
            "max":      round(float(clean_grp[clean_grp <= hi].max()), 4),
            "outliers": outliers,
            "n":        len(clean_grp),
        })

    if len(box_data) < 2:
        return None

    return {
        "type":        "boxplot",
        "title":       f"{num_col} by {cat_col}",
        "description": f"Distribution of {num_col} split by {cat_col} (IQR box-whisker)",
        "insight": (
            f"Each box shows the interquartile range of '{num_col}' for each '{cat_col}' group. "
            f"Dots beyond the whiskers are outliers."
        ),
        "x_key":       "name",
        "y_key":       "median",
        "x_label":     cat_col,
        "y_label":     num_col,
        "data":        box_data,
        "recommended": False,
        "score":       7,
    }


# ── Correlation heatmap ───────────────────────────────────────────────────────

def build_heatmap_payload(df: pd.DataFrame, numeric_cols: list[str]) -> dict | None:
    """
    Return a Pearson correlation heatmap payload.
    Returns None when fewer than 3 columns or 10 rows are available.
    """
    if len(numeric_cols) < 3:
        return None
    sub = df[numeric_cols].dropna()
    if len(sub) < 10:
        return None

    corr_matrix = sub.corr(method="pearson")
    heatmap_data = []
    for col_x in numeric_cols:
        for col_y in numeric_cols:
            val = corr_matrix.loc[col_x, col_y]
            heatmap_data.append({
                "x":     col_x,
                "y":     col_y,
                "value": round(float(val), 3) if not np.isnan(val) else 0.0,
            })

    return {
        "type":        "heatmap",
        "title":       "Correlation heatmap",
        "description": f"Pearson correlations between {len(numeric_cols)} numeric columns",
        "insight": (
            "Values close to +1 or −1 indicate strong linear relationships. "
            "Focus on off-diagonal cells — diagonal is always 1."
        ),
        "x_key":       "x",
        "y_key":       "y",
        "x_label":     "Column",
        "y_label":     "Column",
        "data":        heatmap_data,
        "columns":     numeric_cols,
        "recommended": False,
        "score":       8,
    }
