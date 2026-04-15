import pandas as pd
import numpy as np
from scipy import stats
from itertools import combinations


def _histogram_bins(series: pd.Series, n_bins: int = 10) -> list[dict]:
    """Build histogram bin data with density and anomaly flagging."""
    clean = series.dropna()
    if len(clean) == 0:
        return []
    q1, q3 = float(clean.quantile(0.25)), float(clean.quantile(0.75))
    iqr = q3 - q1
    lower_fence = q1 - 1.5 * iqr
    upper_fence = q3 + 1.5 * iqr

    counts, edges = np.histogram(clean, bins=n_bins)
    total = len(clean)
    result = []
    for i, count in enumerate(counts):
        label = f"{edges[i]:.2g}–{edges[i+1]:.2g}"
        bin_center = (edges[i] + edges[i + 1]) / 2
        result.append({
            "label": label,
            "value": int(count),
            "density": round(float(count) / total, 4),
            "is_anomaly_bin": bool(bin_center < lower_fence or bin_center > upper_fence),
        })
    return result


def _narrate_distribution(col: str, clean: pd.Series, skew: float) -> str:
    """Template-based 2–3 sentence narration for distribution charts."""
    mean = float(clean.mean())
    median = float(clean.median())
    std = float(clean.std())
    n = len(clean)

    if abs(skew) > 1.5:
        direction = "right" if skew > 0 else "left"
        tail_note = "high outliers pull the mean up" if skew > 0 else "low outliers pull the mean down"
        return (
            f"'{col}' is {direction}-skewed (skew={skew:.2f}), meaning {tail_note}. "
            f"The median ({median:.3g}) is a more reliable central estimate than the mean ({mean:.3g}). "
            f"Consider a log transform before using this column in linear models."
        )
    elif abs(mean - median) / (std + 1e-10) < 0.1:
        return (
            f"'{col}' follows an approximately normal distribution (n={n:,}). "
            f"Values are centered around {mean:.3g} with a spread of ±{std:.3g}. "
            f"Standard parametric tests are safe to use on this column."
        )
    else:
        return (
            f"'{col}' has mean={mean:.3g} and median={median:.3g} with std={std:.3g} (n={n:,}). "
            f"The slight difference between mean and median suggests mild asymmetry. "
            f"Review outlier values before applying statistical tests."
        )


def _narrate_timeseries(col: str, values: pd.Series, date_col: str) -> str:
    """Template-based narration for time series charts."""
    pct_change = float((values.iloc[-1] - values.iloc[0]) / (abs(values.iloc[0]) + 1e-10) * 100)
    direction = "increased" if pct_change > 0 else "decreased"
    volatility = round(float(values.std() / (abs(values.mean()) + 1e-10) * 100), 1)
    return (
        f"'{col}' has {direction} by {abs(pct_change):.1f}% over the observed period. "
        f"Volatility is {volatility:.1f}% (coefficient of variation). "
        f"Examine the trend line for structural breaks or seasonality."
    )


def _narrate_scatter(col1: str, col2: str, corr: float, pval: float) -> str:
    """Template-based narration for scatter/correlation charts."""
    strength = (
        "very strong" if abs(corr) > 0.9
        else "strong" if abs(corr) > 0.7
        else "moderate" if abs(corr) > 0.5
        else "weak"
    )
    direction = "positive" if corr > 0 else "negative"
    sig_note = f"statistically significant (p={pval:.4f})" if pval < 0.05 else f"not statistically significant (p={pval:.4f})"
    return (
        f"'{col1}' and '{col2}' show a {strength} {direction} relationship (r={corr:.2f}). "
        f"This correlation is {sig_note}. "
        f"{'Consider whether this is a causal relationship or driven by a confounding variable.' if abs(corr) > 0.5 else 'The relationship is too weak to be actionable on its own.'}"
    )


def _narrate_categorical(col: str, top_cat: str, top_pct: float, n_unique: int) -> str:
    """Template-based narration for categorical bar charts."""
    if top_pct > 50:
        return (
            f"'{top_cat}' dominates '{col}' with {top_pct:.1f}% of records. "
            f"This heavy concentration may introduce class imbalance in models. "
            f"Consider whether the minority categories carry meaningful signal."
        )
    else:
        return (
            f"'{col}' has {n_unique} categories; '{top_cat}' is the most frequent at {top_pct:.1f}%. "
            f"The distribution appears relatively balanced, which is favorable for analysis. "
            f"Review low-frequency categories for potential grouping or removal."
        )


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
                values = ts[num_col]
                mean_val = float(values.mean())
                data = [
                    {
                        "date": str(row[date_col])[:10],
                        "value": float(row[num_col]),
                        "is_anomaly": bool(abs(float(row[num_col]) - mean_val) > 2 * float(values.std())),
                    }
                    for _, row in ts.iterrows()
                ]
                narration = _narrate_timeseries(num_col, values, date_col)
                charts.append({
                    "type": "line",
                    "title": f"{num_col} over time",
                    "description": f"Trend of {num_col} over {date_col}",
                    "insight": narration,
                    "x_key": "date",
                    "y_key": "value",
                    "x_label": date_col,
                    "y_label": num_col,
                    "data": data[:200],
                    "reference_lines": [
                        {"label": "Mean", "value": round(mean_val, 4), "color": "#6366f1"},
                        {"label": "Median", "value": round(float(values.median()), 4), "color": "#a78bfa"},
                    ],
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

        # Significance badge: test if distribution departs from normality
        try:
            if len(clean) >= 8:
                sample = clean.sample(min(len(clean), 2000), random_state=42)
                _, normality_p = stats.shapiro(sample) if len(sample) <= 5000 else stats.normaltest(sample)
                sig_badge = "non-normal" if normality_p < 0.05 else "normal"
            else:
                sig_badge = None
                normality_p = None
        except Exception:
            sig_badge = None
            normality_p = None

        narration = _narrate_distribution(col, clean, skew)
        charts.append({
            "type": "bar",
            "title": f"Distribution of {col}",
            "description": f"Histogram showing the spread of values in {col}",
            "insight": narration,
            "x_key": "label",
            "y_key": "value",
            "x_label": col,
            "y_label": "Count",
            "data": hist_data,
            "reference_lines": [
                {"label": "Mean", "value": round(float(clean.mean()), 4), "color": "#6366f1"},
                {"label": "Median", "value": round(float(clean.median()), 4), "color": "#a78bfa"},
            ],
            "significance_badge": sig_badge,
            "normality_p": round(float(normality_p), 4) if normality_p is not None else None,
            "recommended": len(charts) == 0,
            "score": 8,
        })

    # ── 3. Categorical bar charts ─────────────────────────────────────────────
    for col in categorical_cols[:3]:
        n_unique = df[col].nunique()
        if n_unique < 2:
            continue

        # Smart chart type: >15 unique values → horizontal bar (top 10)
        counts = df[col].fillna("(missing)").astype(str).value_counts()
        show_top = n_unique > 15
        display_counts = counts.head(10)

        if len(display_counts) == 0:
            continue

        top_cat = str(display_counts.index[0])
        top_pct = float(display_counts.iloc[0]) / max(len(df), 1) * 100
        data = [{"label": str(k), "value": int(v)} for k, v in display_counts.items()]
        if show_top and len(counts) > 10:
            other_total = int(counts.iloc[10:].sum())
            data.append({"label": "Other", "value": other_total})

        narration = _narrate_categorical(col, top_cat, top_pct, n_unique)
        charts.append({
            "type": "bar",
            "title": f"Top values in {col}" if show_top else f"Distribution of {col}",
            "description": f"Frequency of {'top 10 of ' + str(n_unique) if show_top else str(n_unique)} categories in {col}",
            "insight": narration,
            "x_key": "label",
            "y_key": "value",
            "x_label": col,
            "y_label": "Count",
            "data": data,
            "horizontal": show_top,  # hint for frontend to render horizontally
            "recommended": False,
            "score": 6,
        })

    # ── 4. Categorical pie charts (low-cardinality) ───────────────────────────
    for col in categorical_cols[:2]:
        n_unique = df[col].nunique()
        if n_unique < 2 or n_unique > 8:
            continue
        counts = df[col].fillna("(missing)").astype(str).value_counts()
        data = [{"name": str(k), "value": int(v)} for k, v in counts.items()]
        top_pct = float(counts.iloc[0]) / len(df) * 100
        charts.append({
            "type": "pie",
            "title": f"Breakdown of {col}",
            "description": f"Proportional breakdown of {col} categories",
            "insight": f"'{counts.index[0]}' accounts for {top_pct:.1f}% of all records.",
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
                corr, pval = stats.pearsonr(clean[col1], clean[col2])
                pair_corrs.append((col1, col2, float(corr), float(pval), clean))
            except Exception:
                pass
        pair_corrs.sort(key=lambda x: abs(x[2]), reverse=True)

        for col1, col2, corr, pval, clean in pair_corrs[:2]:
            # Skip degenerate pairs (near-constant columns cause SVD failures in polyfit)
            if float(clean[col1].std()) < 1e-10 or float(clean[col2].std()) < 1e-10:
                continue

            sample = clean.sample(min(len(clean), 300), random_state=42)

            # Regression + anomaly flagging — guarded against LinAlgError
            try:
                coeffs = np.polyfit(clean[col1].values, clean[col2].values, 1)
                predicted = np.polyval(coeffs, sample[col1].values)
                residuals = sample[col2].values - predicted
                residual_std = float(np.std(residuals))
                data = [
                    {
                        "x": float(row[col1]),
                        "y": float(row[col2]),
                        "is_anomaly": bool(residual_std > 0 and abs(residuals[i]) > 2 * residual_std),
                    }
                    for i, (_, row) in enumerate(sample.iterrows())
                ]
                x_min, x_max = float(clean[col1].min()), float(clean[col1].max())
                regression = [
                    {"x": x_min, "y_hat": float(np.polyval(coeffs, x_min))},
                    {"x": x_max, "y_hat": float(np.polyval(coeffs, x_max))},
                ]
            except (np.linalg.LinAlgError, Exception):
                data = [
                    {"x": float(row[col1]), "y": float(row[col2]), "is_anomaly": False}
                    for _, row in sample.iterrows()
                ]
                regression = []

            narration = _narrate_scatter(col1, col2, corr, pval)
            significance_badge = "significant" if pval < 0.05 else "not significant"

            charts.append({
                "type": "scatter",
                "title": f"{col1} vs {col2}",
                "description": f"Correlation between {col1} and {col2}",
                "insight": narration,
                "x_key": "x",
                "y_key": "y",
                "x_label": col1,
                "y_label": col2,
                "data": data,
                "regression": regression,
                "significance_badge": significance_badge,
                "pearson_r": round(corr, 4),
                "pearson_p": round(pval, 6),
                "recommended": abs(corr) > 0.7,
                "score": round(abs(corr) * 9, 1),
            })

    # ── 6. Boxplot — distribution comparison across a category ───────────────
    if categorical_cols and numeric_cols:
        cat_col = categorical_cols[0]
        n_unique = df[cat_col].nunique()
        for num_col in numeric_cols[:2]:
            if n_unique < 2 or n_unique > 12:
                continue
            box_data = []
            for cat_val, grp in df.groupby(cat_col)[num_col]:
                clean_grp = grp.dropna()
                if len(clean_grp) < 4:
                    continue
                q1 = float(clean_grp.quantile(0.25))
                q3 = float(clean_grp.quantile(0.75))
                iqr = q3 - q1
                fence_lo = q1 - 1.5 * iqr
                fence_hi = q3 + 1.5 * iqr
                outliers = [round(float(v), 4) for v in clean_grp[(clean_grp < fence_lo) | (clean_grp > fence_hi)].tolist()[:20]]
                box_data.append({
                    "name": str(cat_val),
                    "min": round(float(clean_grp[clean_grp >= fence_lo].min()), 4),
                    "q1": round(q1, 4),
                    "median": round(float(clean_grp.median()), 4),
                    "q3": round(q3, 4),
                    "max": round(float(clean_grp[clean_grp <= fence_hi].max()), 4),
                    "outliers": outliers,
                    "n": len(clean_grp),
                })
            if len(box_data) >= 2:
                charts.append({
                    "type": "boxplot",
                    "title": f"{num_col} by {cat_col}",
                    "description": f"Distribution of {num_col} split by {cat_col} (IQR box-whisker)",
                    "insight": (
                        f"Each box shows the interquartile range of '{num_col}' for each '{cat_col}' group. "
                        f"Dots beyond the whiskers are outliers."
                    ),
                    "x_key": "name",
                    "y_key": "median",
                    "x_label": cat_col,
                    "y_label": num_col,
                    "data": box_data,
                    "recommended": False,
                    "score": 7,
                })
            break  # one boxplot is enough

    # ── 7. Correlation heatmap ────────────────────────────────────────────────
    if len(numeric_cols) >= 3:
        heatmap_cols = numeric_cols[:8]
        sub = df[heatmap_cols].dropna()
        if len(sub) >= 10:
            corr_matrix = sub.corr(method="pearson")
            heatmap_data = []
            for col_x in heatmap_cols:
                for col_y in heatmap_cols:
                    val = corr_matrix.loc[col_x, col_y]
                    heatmap_data.append({
                        "x": col_x,
                        "y": col_y,
                        "value": round(float(val), 3) if not np.isnan(val) else 0.0,
                    })
            charts.append({
                "type": "heatmap",
                "title": "Correlation heatmap",
                "description": f"Pearson correlations between {len(heatmap_cols)} numeric columns",
                "insight": (
                    "Values close to +1 or −1 indicate strong linear relationships. "
                    "Focus on off-diagonal cells — diagonal is always 1."
                ),
                "x_key": "x",
                "y_key": "y",
                "x_label": "Column",
                "y_label": "Column",
                "data": heatmap_data,
                "columns": heatmap_cols,
                "recommended": False,
                "score": 8,
            })

    # Sort by score descending, cap at 10 charts
    charts.sort(key=lambda c: c.get("score", 0), reverse=True)
    return charts[:10]
