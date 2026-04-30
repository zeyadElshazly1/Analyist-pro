"""
Chart data orchestrator.

build_chart_data(df) → list[dict]

Generates up to MAX_CHARTS chart payloads from a cleaned DataFrame:
  1. Time-series line charts  (highest priority, score=10)
  2. Numeric histograms        (score=8)
  3. Correlation heatmap       (score=8)
  4. Boxplot                   (score=7)
  5. Categorical bar charts    (score=6)
  6. Categorical pie charts    (score=5)
  7. Scatter plots             (score based on max(|pearson_r|, |spearman_rho|)×9)

Scatter pairs are ranked by the stronger of Pearson r and Spearman rho so
nonlinear relationships surface alongside linear ones.

Data generation is vectorized (no iterrows()) for performance on large datasets.
"""
import pandas as pd
from itertools import combinations

from .budget import (
    MAX_TIMESERIES_DATES,
    MAX_TIMESERIES_NUMS,
    MAX_HIST_COLS,
    MAX_CAT_BAR_COLS,
    MAX_CAT_PIE_COLS,
    MAX_SCATTER_COLS,
    MAX_HEATMAP_COLS,
)
from .stats import _pearson, _spearman
from .payloads import (
    build_timeseries_payload,
    build_histogram_payload,
    build_cat_bar_payload,
    build_pie_payload,
    build_scatter_payload,
    build_boxplot_payload,
    build_heatmap_payload,
)
from .ranker import rank_and_cap


def _is_id_col(col: str, df: pd.DataFrame) -> bool:
    """True when a column is effectively an identifier and should not be charted."""
    n_rows = max(len(df), 1)
    return df[col].nunique() / n_rows > 0.8 and df[col].nunique() > 50


def build_chart_data(df: pd.DataFrame) -> list[dict]:
    """
    Return a list of chart payload dicts (up to MAX_CHARTS) sorted by score.

    Each dict contains at minimum:
        type, title, description, insight, x_key, y_key,
        x_label, y_label, data, recommended, score
    Plus chart-type-specific fields.

    ID and high-cardinality columns (> 80% unique values AND > 50 distinct values)
    are excluded from categorical charts — they produce useless per-value bars.

    Binary numeric columns (nunique <= 2) are excluded from histogram generation
    because a 2-bin histogram carries no distributional insight; they are added
    to the categorical column list instead so they get bar/pie treatment.
    """
    charts: list[dict] = []

    all_numeric      = df.select_dtypes(include=["number"]).columns.tolist()
    categorical_cols = [
        col for col in df.select_dtypes(include=["object", "category"]).columns
        if not _is_id_col(col, df)
    ]
    datetime_cols    = df.select_dtypes(include=["datetime64"]).columns.tolist()

    # Binary numeric columns (0/1 flags, encoded categoricals) → treat as categorical
    binary_numeric = [
        col for col in all_numeric
        if df[col].nunique() <= 2 and len(df[col].dropna()) >= 5
    ]
    # Numeric columns for histograms/scatter/heatmap — exclude binary flags
    numeric_cols = [col for col in all_numeric if col not in binary_numeric]

    # Merge binary numerics into categorical list (deduplicated, binary flags first
    # so they appear in the more informative bar/pie position)
    categorical_cols = list(dict.fromkeys(binary_numeric + categorical_cols))

    # ── 1. Time-series line charts ────────────────────────────────────────────
    for date_col in datetime_cols[:MAX_TIMESERIES_DATES]:
        for num_col in numeric_cols[:MAX_TIMESERIES_NUMS]:
            try:
                payload = build_timeseries_payload(df, date_col, num_col)
                if payload is not None:
                    charts.append(payload)
            except Exception:
                pass

    # ── 2. Numeric histograms ─────────────────────────────────────────────────
    for col in numeric_cols[:MAX_HIST_COLS]:
        try:
            payload = build_histogram_payload(df, col, is_first_chart=(len(charts) == 0))
            if payload is not None:
                charts.append(payload)
        except Exception:
            pass

    # ── 3. Categorical bar charts ─────────────────────────────────────────────
    for col in categorical_cols[:MAX_CAT_BAR_COLS]:
        try:
            payload = build_cat_bar_payload(df, col)
            if payload is not None:
                charts.append(payload)
        except Exception:
            pass

    # ── 4. Categorical pie charts ─────────────────────────────────────────────
    for col in categorical_cols[:MAX_CAT_PIE_COLS]:
        try:
            payload = build_pie_payload(df, col)
            if payload is not None:
                charts.append(payload)
        except Exception:
            pass

    # ── 5. Scatter plots (Pearson + Spearman, ranked by stronger correlation) ─
    if len(numeric_cols) >= 2:
        pair_corrs: list[tuple] = []
        for col1, col2 in combinations(numeric_cols[:MAX_SCATTER_COLS], 2):
            clean = df[[col1, col2]].dropna()
            if len(clean) < 10:
                continue
            try:
                pr, pp = _pearson(clean[col1], clean[col2])
                sr, sp = _spearman(clean[col1], clean[col2])
                pair_corrs.append((col1, col2, pr, pp, sr, sp, clean))
            except Exception:
                pass

        # Rank by the stronger of the two correlations
        pair_corrs.sort(key=lambda x: max(abs(x[2]), abs(x[4])), reverse=True)

        for col1, col2, pr, pp, sr, sp, _ in pair_corrs[:2]:
            try:
                payload = build_scatter_payload(df, col1, col2, pr, pp, sr, sp)
                if payload is not None:
                    charts.append(payload)
            except Exception:
                pass

    # ── 6. Boxplot ────────────────────────────────────────────────────────────
    if categorical_cols and numeric_cols:
        cat_col = categorical_cols[0]
        for num_col in numeric_cols[:2]:
            try:
                payload = build_boxplot_payload(df, cat_col, num_col)
                if payload is not None:
                    charts.append(payload)
                    break   # one boxplot is enough
            except Exception:
                pass

    # ── 7. Correlation heatmap ────────────────────────────────────────────────
    if len(numeric_cols) >= 3:
        try:
            payload = build_heatmap_payload(df, numeric_cols[:MAX_HEATMAP_COLS])
            if payload is not None:
                charts.append(payload)
        except Exception:
            pass

    return rank_and_cap(charts)
