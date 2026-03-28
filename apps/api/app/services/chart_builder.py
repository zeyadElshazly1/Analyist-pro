import pandas as pd
import numpy as np
from itertools import combinations


def _histogram_bins(series: pd.Series, n_bins: int = 10) -> list[dict]:
    """Build histogram bin data with density."""
    clean = series.dropna()
    if len(clean) == 0:
        return []
    counts, edges = np.histogram(clean, bins=n_bins)
    total = len(clean)
    result = []
    for i, count in enumerate(counts):
        label = f"{edges[i]:.2g}–{edges[i+1]:.2g}"
        result.append({
            "label": label,
            "value": int(count),
            "density": round(float(count) / total, 4),
        })
    return result


def build_chart_data(df: pd.DataFrame) -> list[dict]:
    charts = []
    numeric_cols = df.select_dtypes(include=["number"]).columns.tolist()
    categorical_cols = df.select_dtypes(include=["object", "category"]).columns.tolist()
    datetime_cols = df.select_dtypes(include=["datetime64"]).columns.tolist()

    # ── 1. Time series line charts (highest priority) ─────────────────────────
    for date_col in datetime_cols[:2]:
        for num_col in numeric_cols[:3]:
            try:
                ts = df[[date_col, num_col]].dropna().sort_values(date_col)
                if len(ts) < 4:
                    continue
                data = [
                    {"date": str(row[date_col])[:10], "value": float(row[num_col])}
                    for _, row in ts.iterrows()
                ]
                charts.append({
                    "type": "line",
                    "title": f"{num_col} over time",
                    "description": f"Trend of {num_col} grouped by {date_col}",
                    "insight": f"Track how {num_col} changes over {date_col}",
                    "x_key": "date",
                    "y_key": "value",
                    "x_label": date_col,
                    "y_label": num_col,
                    "data": data[:200],
                    "recommended": True,
                    "score": 10,
                })
            except Exception:
                pass

    # ── 2. Numeric histograms ─────────────────────────────────────────────────
    for col in numeric_cols[:4]:
        clean = df[col].dropna()
        if len(clean) < 5:
            continue
        skew = float(clean.skew())
        n_bins = 15 if len(clean) > 500 else 10
        hist_data = _histogram_bins(clean, n_bins=n_bins)
        if not hist_data:
            continue
        insight_text = (
            f"Distribution is {'right-skewed' if skew > 1 else 'left-skewed' if skew < -1 else 'approximately normal'} "
            f"(skew={skew:.2f})"
        )
        charts.append({
            "type": "bar",
            "title": f"Distribution of {col}",
            "description": f"Histogram showing the spread of values in {col}",
            "insight": insight_text,
            "x_key": "label",
            "y_key": "value",
            "x_label": col,
            "y_label": "Count",
            "data": hist_data,
            "recommended": len(charts) == 0,
            "score": 8,
        })

    # ── 3. Categorical bar charts (top 10 values) ─────────────────────────────
    for col in categorical_cols[:3]:
        n_unique = df[col].nunique()
        if n_unique < 2:
            continue
        counts = df[col].fillna("(missing)").astype(str).value_counts().head(10)
        if len(counts) == 0:
            continue
        data = [{"label": str(k), "value": int(v)} for k, v in counts.items()]
        insight_text = f"'{counts.index[0]}' is the most common value ({counts.iloc[0]} records)"
        charts.append({
            "type": "bar",
            "title": f"Top values in {col}",
            "description": f"Frequency of top {min(n_unique, 10)} categories in {col}",
            "insight": insight_text,
            "x_key": "label",
            "y_key": "value",
            "x_label": col,
            "y_label": "Count",
            "data": data,
            "recommended": False,
            "score": 6,
        })

    # ── 4. Categorical pie charts (for low-cardinality columns) ───────────────
    for col in categorical_cols[:2]:
        n_unique = df[col].nunique()
        if n_unique < 2 or n_unique > 8:
            continue
        counts = df[col].fillna("(missing)").astype(str).value_counts()
        data = [{"name": str(k), "value": int(v)} for k, v in counts.items()]
        charts.append({
            "type": "pie",
            "title": f"Breakdown of {col}",
            "description": f"Proportional breakdown of {col} categories",
            "insight": f"'{counts.index[0]}' makes up {counts.iloc[0] / len(df) * 100:.1f}% of records",
            "x_key": "name",
            "y_key": "value",
            "x_label": col,
            "y_label": "Count",
            "data": data,
            "recommended": False,
            "score": 5,
        })

    # ── 5. Scatter plots for correlated numeric pairs ─────────────────────────
    if len(numeric_cols) >= 2:
        pair_corrs = []
        for col1, col2 in combinations(numeric_cols[:6], 2):
            clean = df[[col1, col2]].dropna()
            if len(clean) < 10:
                continue
            try:
                corr = float(clean[col1].corr(clean[col2]))
                pair_corrs.append((col1, col2, corr, clean))
            except Exception:
                pass
        # Sort by abs(corr) descending, take top 2
        pair_corrs.sort(key=lambda x: abs(x[2]), reverse=True)
        for col1, col2, corr, clean in pair_corrs[:2]:
            # Sample for performance
            sample = clean.sample(min(len(clean), 300), random_state=42)
            data = [
                {"x": float(row[col1]), "y": float(row[col2])}
                for _, row in sample.iterrows()
            ]
            # Regression line
            coeffs = np.polyfit(clean[col1], clean[col2], 1)
            x_min, x_max = float(clean[col1].min()), float(clean[col1].max())
            regression = [
                {"x": x_min, "y_hat": float(np.polyval(coeffs, x_min))},
                {"x": x_max, "y_hat": float(np.polyval(coeffs, x_max))},
            ]
            charts.append({
                "type": "scatter",
                "title": f"{col1} vs {col2}",
                "description": f"Correlation between {col1} and {col2}",
                "insight": f"r={corr:.2f} — {'strong' if abs(corr) > 0.7 else 'moderate' if abs(corr) > 0.4 else 'weak'} {'positive' if corr > 0 else 'negative'} correlation",
                "x_key": "x",
                "y_key": "y",
                "x_label": col1,
                "y_label": col2,
                "data": data,
                "regression": regression,
                "recommended": abs(corr) > 0.7,
                "score": round(abs(corr) * 9, 1),
            })

    # Sort by score descending, cap at 8 charts
    charts.sort(key=lambda c: c.get("score", 0), reverse=True)
    return charts[:8]
