"""
Enhanced rule-based fallback engine.

_fallback_answer(df, message, intent) → str

Answers common data questions locally without any LLM call.
Handles ~12 distinct intent categories — much broader than the original 5.
"""
from __future__ import annotations

import pandas as pd


def _fallback_answer(df: pd.DataFrame, message: str, intent: str = "general") -> str:
    msg      = message.lower()
    n_rows, n_cols = df.shape
    numeric  = df.select_dtypes(include="number")
    cat_cols = df.select_dtypes(include=["object", "category"]).columns.tolist()
    dt_cols  = df.select_dtypes(include=["datetime64"]).columns.tolist()

    # ── Shape ─────────────────────────────────────────────────────────────────
    if intent == "shape" or any(
        w in msg for w in ("how many rows", "row count", "how big", "size", "shape")
    ):
        return f"The dataset has **{n_rows:,} rows** and **{n_cols} columns**."

    # ── Schema ────────────────────────────────────────────────────────────────
    if intent == "schema" or any(
        w in msg for w in ("column", "field", "variable", "what column")
    ):
        cols = ", ".join(f"`{c}`" for c in df.columns[:20])
        suffix = f"… and {n_cols - 20} more" if n_cols > 20 else ""
        return f"The dataset has **{n_cols} columns**: {cols}{suffix}."

    # ── Missing values ────────────────────────────────────────────────────────
    if intent == "missing" or any(
        w in msg for w in ("missing", "null", "nan", "empty", "incomplete")
    ):
        missing = df.isnull().sum()
        top_missing = missing[missing > 0].sort_values(ascending=False).head(5)
        if top_missing.empty:
            return "There are **no missing values** in the dataset. ✓"
        lines = [
            f"- **{col}**: {int(cnt):,} missing ({cnt / n_rows * 100:.1f}%)"
            for col, cnt in top_missing.items()
        ]
        return "Columns with missing values:\n" + "\n".join(lines)

    # ── Summary statistics ────────────────────────────────────────────────────
    if intent == "summary" or any(
        w in msg for w in ("summary", "describe", "overview", "statistic", "stat")
    ):
        if not numeric.empty:
            desc = numeric.describe().round(2)
            return f"Summary statistics:\n```\n{desc.to_string()}\n```"
        return f"No numeric columns found. Categorical columns: {', '.join(cat_cols[:10])}."

    # ── Mean / median ─────────────────────────────────────────────────────────
    if intent == "mean" or any(w in msg for w in ("average", "mean", "median")):
        if not numeric.empty:
            # Try to find the specific column mentioned in the message
            col_name = next(
                (c for c in numeric.columns if c.lower() in msg),
                numeric.columns[0],
            )
            mean_v   = numeric[col_name].mean()
            median_v = numeric[col_name].median()
            std_v    = numeric[col_name].std()
            return (
                f"**{col_name}**:\n"
                f"- Mean: {mean_v:.4f}\n"
                f"- Median: {median_v:.4f}\n"
                f"- Std: {std_v:.4f}"
            )
        return "No numeric columns found."

    # ── Top-N / ranking ───────────────────────────────────────────────────────
    if intent == "top" or any(
        w in msg for w in ("top ", "bottom ", "most ", "least ", "highest", "lowest", "rank")
    ):
        if cat_cols:
            col = cat_cols[0]
            counts = df[col].value_counts().head(10)
            lines  = [f"- **{k}**: {v:,}" for k, v in counts.items()]
            return f"Top values in **{col}**:\n" + "\n".join(lines)
        if not numeric.empty:
            col = numeric.columns[0]
            top = df[col].nlargest(10)
            return f"Top 10 values in **{col}**: {top.tolist()}"
        return "No columns suitable for ranking found."

    # ── Groupby / breakdown ───────────────────────────────────────────────────
    if intent == "group" or any(
        w in msg for w in ("group", "segment", "breakdown", "by ", "per ")
    ):
        if cat_cols and not numeric.empty:
            cat_col = cat_cols[0]
            num_col = numeric.columns[0]
            grp     = df.groupby(cat_col)[num_col].agg(["mean", "count"]).round(2)
            grp.columns = ["mean", "count"]
            grp = grp.sort_values("count", ascending=False).head(10)
            lines = [
                f"- **{idx}**: mean={row['mean']:.2f}, n={int(row['count']):,}"
                for idx, row in grp.iterrows()
            ]
            return (
                f"**{num_col}** grouped by **{cat_col}** (top 10 groups):\n"
                + "\n".join(lines)
            )
        return "Need at least one categorical and one numeric column to group."

    # ── Correlation ───────────────────────────────────────────────────────────
    if intent == "corr" or any(
        w in msg for w in ("correlat", "relationship", "related", "depend")
    ):
        if numeric.shape[1] >= 2:
            corr_mat = numeric.corr().abs()
            # Extract upper triangle pairs
            pairs = []
            cols  = corr_mat.columns.tolist()
            for i in range(len(cols)):
                for j in range(i + 1, len(cols)):
                    pairs.append((cols[i], cols[j], float(corr_mat.iloc[i, j])))
            pairs.sort(key=lambda x: x[2], reverse=True)
            lines = [
                f"- **{a}** ↔ **{b}**: r={r:.3f}"
                for a, b, r in pairs[:5]
            ]
            return "Top correlations (Pearson |r|):\n" + "\n".join(lines)
        return "Need at least 2 numeric columns to compute correlations."

    # ── Outliers / anomalies ──────────────────────────────────────────────────
    if intent == "anomaly" or any(
        w in msg for w in ("outlier", "anomal", "unusual", "weird", "spike")
    ):
        if not numeric.empty:
            lines = []
            for col in numeric.columns[:8]:
                clean = numeric[col].dropna()
                if len(clean) < 4:
                    continue
                q1, q3 = clean.quantile(0.25), clean.quantile(0.75)
                iqr    = q3 - q1
                if iqr == 0:
                    continue
                n_out  = int(((clean < q1 - 1.5 * iqr) | (clean > q3 + 1.5 * iqr)).sum())
                if n_out > 0:
                    lines.append(f"- **{col}**: {n_out:,} IQR outliers ({n_out / n_rows * 100:.1f}%)")
            if lines:
                return "Outliers by column (IQR method):\n" + "\n".join(lines)
            return "No IQR outliers detected in numeric columns."
        return "No numeric columns to check for outliers."

    # ── Trend / date range ────────────────────────────────────────────────────
    if intent == "trend" or any(
        w in msg for w in ("trend", "over time", "date range", "when", "time period")
    ):
        if dt_cols:
            col    = dt_cols[0]
            dmin   = df[col].min()
            dmax   = df[col].max()
            return (
                f"**{col}** spans from **{dmin}** to **{dmax}**. "
                f"Set the ANTHROPIC_API_KEY to get trend analysis."
            )
        return "No datetime columns found. Set ANTHROPIC_API_KEY for trend analysis."

    # ── Default ───────────────────────────────────────────────────────────────
    return (
        f"This dataset has {n_rows:,} rows and {n_cols} columns. "
        f"Set the ANTHROPIC_API_KEY environment variable to enable AI-powered analysis. "
        f"Available columns: {', '.join(df.columns[:10].tolist())}."
    )
