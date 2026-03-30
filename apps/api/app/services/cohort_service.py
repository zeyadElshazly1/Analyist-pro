from __future__ import annotations

from datetime import datetime

import numpy as np
import pandas as pd


def rfm_segmentation(
    df: pd.DataFrame,
    customer_col: str,
    date_col: str,
    revenue_col: str,
) -> dict:
    df = df.copy()
    df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
    df = df.dropna(subset=[date_col, customer_col, revenue_col])
    df[revenue_col] = pd.to_numeric(df[revenue_col], errors="coerce").fillna(0)

    analysis_date = df[date_col].max()

    rfm = df.groupby(customer_col).agg(
        last_date=(date_col, "max"),
        frequency=(date_col, "count"),
        monetary=(revenue_col, "sum"),
    ).reset_index()

    rfm["recency_days"] = (analysis_date - rfm["last_date"]).dt.days

    def _score(series: pd.Series, ascending: bool = True) -> pd.Series:
        try:
            labels = [5, 4, 3, 2, 1] if ascending else [1, 2, 3, 4, 5]
            return pd.qcut(series, q=5, labels=labels, duplicates="drop").astype(int)
        except Exception:
            # fallback if too few unique values
            return pd.Series([3] * len(series), index=series.index)

    # lower recency = more recent = better score
    rfm["r_score"] = _score(rfm["recency_days"], ascending=True)
    rfm["f_score"] = _score(rfm["frequency"], ascending=False)
    rfm["m_score"] = _score(rfm["monetary"], ascending=False)
    rfm["rfm_score"] = rfm["r_score"] + rfm["f_score"] + rfm["m_score"]

    def _segment(row: pd.Series) -> str:
        r, f, m = row["r_score"], row["f_score"], row["m_score"]
        if r >= 4 and f >= 4:
            return "Champions"
        if f >= 4 and r >= 3:
            return "Loyal"
        if r >= 4 and f == 1:
            return "New Customer"
        if r >= 4 and f <= 3:
            return "Potential Loyalist"
        if r <= 2 and f >= 3:
            return "At Risk"
        if r <= 2 and f <= 2:
            return "Lost"
        return "Promising"

    rfm["segment"] = rfm.apply(_segment, axis=1)

    customers = []
    for _, row in rfm.iterrows():
        customers.append({
            "customer_id": str(row[customer_col]),
            "recency_days": int(row["recency_days"]),
            "frequency": int(row["frequency"]),
            "monetary": round(float(row["monetary"]), 2),
            "r_score": int(row["r_score"]),
            "f_score": int(row["f_score"]),
            "m_score": int(row["m_score"]),
            "rfm_score": int(row["rfm_score"]),
            "segment": row["segment"],
        })

    segment_counts = rfm["segment"].value_counts().to_dict()

    segment_stats = {}
    for seg in rfm["segment"].unique():
        seg_df = rfm[rfm["segment"] == seg]
        segment_stats[seg] = {
            "count": int(len(seg_df)),
            "avg_monetary": round(float(seg_df["monetary"].mean()), 2),
            "avg_frequency": round(float(seg_df["frequency"].mean()), 2),
            "avg_recency_days": round(float(seg_df["recency_days"].mean()), 1),
            "total_revenue": round(float(seg_df["monetary"].sum()), 2),
        }

    return {
        "customers": customers[:500],  # cap for response size
        "segment_counts": segment_counts,
        "segment_stats": segment_stats,
        "total_customers": int(len(rfm)),
        "analysis_date": str(analysis_date.date()) if pd.notna(analysis_date) else None,
        "total_revenue": round(float(rfm["monetary"].sum()), 2),
    }


def retention_matrix(
    df: pd.DataFrame,
    cohort_col: str,
    period_col: str,
    user_col: str,
) -> dict:
    df = df.copy()
    df = df.dropna(subset=[cohort_col, period_col, user_col])

    # cohort sizes
    cohort_sizes = df.groupby(cohort_col)[user_col].nunique()
    cohorts = sorted(cohort_sizes.index.tolist())

    # all periods (sorted)
    periods = sorted(df[period_col].unique().tolist())
    period_index = {p: i for i, p in enumerate(periods)}

    matrix: list[list[float | None]] = []
    row_labels = []

    for cohort in cohorts:
        cohort_df = df[df[cohort_col] == cohort]
        cohort_users = set(cohort_df[user_col].unique())
        cohort_size = len(cohort_users)
        if cohort_size == 0:
            continue

        row: list[float | None] = [None] * len(periods)
        for _, period_df in cohort_df.groupby(period_col):
            p = period_df[period_col].iloc[0]
            idx = period_index.get(p)
            if idx is not None:
                active = len(set(period_df[user_col].unique()) & cohort_users)
                row[idx] = round(active / cohort_size, 4)

        matrix.append(row)
        row_labels.append(str(cohort))

    return {
        "matrix": matrix,
        "row_labels": row_labels,
        "col_labels": [str(p) for p in periods],
        "cohort_sizes": [int(cohort_sizes[c]) for c in cohorts if cohort_sizes.get(c, 0) > 0],
    }
