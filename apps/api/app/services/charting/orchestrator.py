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
from .payloads import build_binary_bar_payload  # noqa: F401 (re-export for tests)
from .ranker import rank_and_cap

# Semantic types that identify a column as an identifier/key field.
# Columns with these types are excluded from all chart generation.
_ID_SEMANTIC_TYPES: frozenset[str] = frozenset({
    "id", "account_number", "email", "ip_address", "phone", "postal", "sku",
})


def _is_id_col(
    col: str,
    df: pd.DataFrame,
    semantic_map: dict[str, str] | None = None,
) -> bool:
    """Return True when a column should be excluded from chart generation.

    A column is treated as an identifier when ANY of the following hold:

    1. Its semantic type (from ``detect_semantic_columns``) is in the ID set.
    2. unique_ratio >= 0.9  AND  unique_count > 20
       (catches high-cardinality string/numeric IDs without a recognised name)
    3. unique_count == len(df)
       (every row is distinct — categorical charts would be one bar per row)

    The minimum unique_count of 20 prevents very small datasets (e.g. 3 rows,
    2 unique) from having their columns incorrectly suppressed.
    """
    if semantic_map and col in semantic_map:
        if semantic_map[col] in _ID_SEMANTIC_TYPES:
            return True

    n_rows       = max(len(df), 1)
    unique_count = int(df[col].nunique())

    # Every row is a distinct value → definitely an ID
    if unique_count == n_rows and unique_count > 20:
        return True

    # ≥ 90 % unique AND more than 20 distinct values
    return unique_count / n_rows >= 0.9 and unique_count > 20


def build_chart_data(df: pd.DataFrame) -> list[dict]:
    """
    Return a list of chart payload dicts (up to MAX_CHARTS) sorted by score.

    Each dict contains at minimum:
        type, title, description, insight, x_key, y_key,
        x_label, y_label, data, recommended, score
    Plus chart-type-specific fields.

    Column handling:
    • ID / high-cardinality columns (unique_ratio ≥ 0.9, unique_count == n_rows,
      or recognised semantic type) are excluded from all chart types.
    • Binary numeric columns (exactly 2 distinct values, e.g. SeniorCitizen 0/1)
      get a dedicated binary bar chart via build_binary_bar_payload.  They are
      NOT routed through the continuous-histogram path so they never receive
      normality badges or skewness language.
    • Continuous numeric columns go through the histogram / scatter / heatmap path.
    • String/category columns go through the categorical bar / pie path.
    """
    charts: list[dict] = []

    # ── Semantic type map (best-effort; silently ignored if unavailable) ──────
    semantic_map: dict[str, str] = {}
    try:
        from app.services.cleaning.semantic import detect_semantic_columns
        semantic_map = detect_semantic_columns(df)
    except Exception:
        pass

    # ── Column classification ─────────────────────────────────────────────────
    all_numeric   = df.select_dtypes(include=["number"]).columns.tolist()
    all_cat_str   = df.select_dtypes(include=["object", "category"]).columns.tolist()
    datetime_cols = df.select_dtypes(include=["datetime64"]).columns.tolist()

    # Binary numeric: exactly 2 distinct values (e.g. SeniorCitizen 0/1)
    binary_numeric = [
        col for col in all_numeric
        if df[col].nunique() == 2
        and len(df[col].dropna()) >= 5
        and not _is_id_col(col, df, semantic_map)
    ]

    # Continuous numeric: non-binary, non-ID numeric columns
    numeric_cols = [
        col for col in all_numeric
        if col not in binary_numeric
        and not _is_id_col(col, df, semantic_map)
    ]

    # String/category: exclude ID-like columns
    categorical_cols = [
        col for col in all_cat_str
        if not _is_id_col(col, df, semantic_map)
    ]

    # ── 1. Time-series line charts ────────────────────────────────────────────
    for date_col in datetime_cols[:MAX_TIMESERIES_DATES]:
        for num_col in numeric_cols[:MAX_TIMESERIES_NUMS]:
            try:
                payload = build_timeseries_payload(df, date_col, num_col)
                if payload is not None:
                    charts.append(payload)
            except Exception:
                pass

    # ── 2. Continuous numeric histograms (binary columns excluded) ────────────
    for col in numeric_cols[:MAX_HIST_COLS]:
        try:
            payload = build_histogram_payload(df, col, is_first_chart=(len(charts) == 0))
            if payload is not None:
                charts.append(payload)
        except Exception:
            pass

    # ── 3. Binary flag bar charts ─────────────────────────────────────────────
    # These use binary-specific narration — no normality badges or skewness text.
    for col in binary_numeric:
        try:
            payload = build_binary_bar_payload(df, col)
            if payload is not None:
                charts.append(payload)
        except Exception:
            pass

    # ── 4. String/category bar charts ────────────────────────────────────────
    for col in categorical_cols[:MAX_CAT_BAR_COLS]:
        try:
            payload = build_cat_bar_payload(df, col)
            if payload is not None:
                charts.append(payload)
        except Exception:
            pass

    # ── 5. Categorical pie charts ─────────────────────────────────────────────
    for col in categorical_cols[:MAX_CAT_PIE_COLS]:
        try:
            payload = build_pie_payload(df, col)
            if payload is not None:
                charts.append(payload)
        except Exception:
            pass

    # ── 6. Scatter plots (Pearson + Spearman, ranked by stronger correlation) ─
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

    # ── 7. Boxplot ────────────────────────────────────────────────────────────
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

    # ── 8. Correlation heatmap ────────────────────────────────────────────────
    if len(numeric_cols) >= 3:
        try:
            payload = build_heatmap_payload(df, numeric_cols[:MAX_HEATMAP_COLS])
            if payload is not None:
                charts.append(payload)
        except Exception:
            pass

    return rank_and_cap(charts)
