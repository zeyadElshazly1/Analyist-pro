"""
Datetime column analysis.

_detect_gaps: find gaps in a datetime series that exceed 2.5× the median
interval, report recency, and classify data freshness.
"""
import pandas as pd


def _detect_gaps(date_series: pd.Series, freq: str) -> dict:
    """Detect gaps in a datetime series based on expected frequency."""
    sorted_dates = date_series.dropna().sort_values().drop_duplicates()
    if len(sorted_dates) < 3:
        return {"gap_count": 0, "gaps": [], "largest_gap_days": 0}

    diffs = sorted_dates.diff().dropna()
    median_diff = diffs.median()
    threshold = median_diff * 2.5

    gaps = []
    for i in range(1, len(sorted_dates)):
        diff = sorted_dates.iloc[i] - sorted_dates.iloc[i - 1]
        if diff > threshold:
            gaps.append({
                "from": str(sorted_dates.iloc[i - 1])[:10],
                "to": str(sorted_dates.iloc[i])[:10],
                "gap_days": int(diff.days),
            })

    largest_gap = max((g["gap_days"] for g in gaps), default=0)
    recency_days = int((pd.Timestamp.now() - sorted_dates.max()).days)

    return {
        "gap_count": len(gaps),
        "gaps": gaps[:5],
        "largest_gap_days": largest_gap,
        "most_recent_days_ago": recency_days,
        "data_freshness": (
            "fresh"    if recency_days <= 7
            else "recent"  if recency_days <= 30
            else "stale"   if recency_days <= 180
            else "outdated"
        ),
    }
