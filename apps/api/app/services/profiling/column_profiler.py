"""
Per-column profiling helpers.

_normality_test        — Shapiro-Wilk / Jarque-Bera, returns (is_normal, p_value)
                         NOTE: this variant returns a tuple[bool, float] to expose
                         the p-value for display; it is intentionally different from
                         analysis.stats_helpers._normality_test which returns bool only.
_iqr_outliers          — 1.5×IQR fence outlier count
_recommended_chart     — simple chart type selector
_profile_numeric_col   — full numeric column stats
_profile_datetime_col  — full datetime column stats
_profile_categorical_col — top values, pattern, format issues
_build_flags           — derive quality flag strings from a completed profile dict
"""
import numpy as np
import pandas as pd
from scipy import stats

from .distributions import _fit_distribution
from .datetime_analysis import _detect_gaps
from .patterns import _detect_pattern, _check_format_consistency


# ── Statistical helpers ───────────────────────────────────────────────────────

def _normality_test(series: pd.Series) -> tuple[bool, float]:
    """Return (is_normal, p_value) using Shapiro-Wilk or normaltest."""
    clean = series.dropna()
    if len(clean) < 8:
        return True, 1.0
    try:
        sample = clean.sample(min(len(clean), 2000), random_state=42)
        if len(sample) <= 5000:
            _, p = stats.shapiro(sample)
        else:
            _, p = stats.normaltest(sample)
        return bool(p > 0.05), round(float(p), 4)
    except Exception:
        return True, 1.0


def _iqr_outliers(series: pd.Series) -> int:
    """Return the count of values outside the 1.5×IQR fence."""
    clean = series.dropna()
    if len(clean) < 4:
        return 0
    q1, q3 = float(clean.quantile(0.25)), float(clean.quantile(0.75))
    iqr = q3 - q1
    return int(((clean < q1 - 1.5 * iqr) | (clean > q3 + 1.5 * iqr)).sum())


def _recommended_chart(col_type: str, n_unique: int, n_rows: int) -> str:
    """Return a simple chart type recommendation for a column."""
    if col_type == "datetime":
        return "line"
    if col_type == "numeric":
        return "bar" if n_unique <= 10 else "histogram"
    if col_type == "categorical":
        return "bar" if n_unique <= 12 else "bar_top10"
    return "bar"


# ── Per-type profiling functions ──────────────────────────────────────────────

def _profile_numeric_col(
    col_data: pd.Series,
    sample: pd.Series,
    unique: int,
    n_rows: int,
) -> dict:
    """
    Build the numeric-specific portion of a column profile.

    ``sample`` is used for expensive inference (normality, distribution fit,
    outlier count on large data); ``col_data`` is used for exact aggregates.
    """
    clean = col_data.dropna()
    clean_sample = sample.dropna()

    skewness = round(float(clean.skew()), 3) if len(clean) > 2 else 0.0
    kurtosis = round(float(clean.kurtosis()), 3) if len(clean) > 3 else 0.0
    is_normal, normality_p = _normality_test(clean_sample)
    iqr_out = _iqr_outliers(clean_sample)
    z_out = int((np.abs(stats.zscore(clean_sample)) > 3).sum()) if len(clean_sample) >= 3 else 0
    dist_fit = _fit_distribution(clean_sample)

    n_unique = clean.nunique()
    if n_unique <= 5 and len(clean) > 20:
        dtype_confidence, dtype_note = "low", "possibly encoded categorical"
    elif n_unique <= 15 and len(clean) > 50:
        dtype_confidence, dtype_note = "medium", "may be ordinal"
    else:
        dtype_confidence, dtype_note = "high", "continuous numeric"

    return {
        "type": "numeric",
        "mean":    round(float(clean.mean()), 4)           if len(clean) > 0 else None,
        "median":  round(float(clean.median()), 4)         if len(clean) > 0 else None,
        "std":     round(float(clean.std()), 4)            if len(clean) > 1 else None,
        "min":     round(float(clean.min()), 4)            if len(clean) > 0 else None,
        "max":     round(float(clean.max()), 4)            if len(clean) > 0 else None,
        "q25":     round(float(clean.quantile(0.25)), 4)   if len(clean) > 0 else None,
        "q75":     round(float(clean.quantile(0.75)), 4)   if len(clean) > 0 else None,
        "skewness":        skewness,
        "kurtosis":        kurtosis,
        "is_normal":       is_normal,
        "normality_p":     normality_p,
        "outliers_zscore": z_out,
        "outliers_iqr":    iqr_out,
        "zeros":           int((clean == 0).sum()),
        "dtype_confidence": dtype_confidence,
        "dtype_note":       dtype_note,
        "distribution_fit": dist_fit,
        "recommended_chart": _recommended_chart("numeric", unique, n_rows),
    }


def _profile_datetime_col(col_data: pd.Series) -> dict:
    """Build the datetime-specific portion of a column profile."""
    clean = col_data.dropna()
    freq_guess = "unknown"
    if len(clean) >= 3:
        diffs = clean.sort_values().diff().dropna()
        med_days = diffs.median().days if len(diffs) > 0 else 0
        if med_days <= 1:
            freq_guess = "daily"
        elif med_days <= 8:
            freq_guess = "weekly"
        elif med_days <= 32:
            freq_guess = "monthly"
        elif med_days <= 95:
            freq_guess = "quarterly"
        else:
            freq_guess = "yearly"

    gaps = _detect_gaps(clean, freq_guess)
    return {
        "type": "datetime",
        "min": str(clean.min())  if len(clean) > 0 else None,
        "max": str(clean.max())  if len(clean) > 0 else None,
        "range_days": int((clean.max() - clean.min()).days) if len(clean) > 1 else 0,
        "inferred_frequency": freq_guess,
        "gap_count":          gaps["gap_count"],
        "largest_gap_days":   gaps["largest_gap_days"],
        "gaps":               gaps["gaps"],
        "data_freshness":     gaps.get("data_freshness"),
        "most_recent_days_ago": gaps.get("most_recent_days_ago"),
        "recommended_chart":  "line",
        "dtype_confidence":   "high",
        "dtype_note":         "datetime",
    }


def _profile_categorical_col(
    col_data: pd.Series,
    sample: pd.Series,
    unique: int,
    n_rows: int,
) -> dict:
    """Build the categorical-specific portion of a column profile."""
    top_values_raw = col_data.value_counts().head(10)
    top_values = {str(k): int(v) for k, v in top_values_raw.items()}
    vc = col_data.value_counts()
    other_count = int(vc.iloc[10:].sum()) if len(vc) > 10 else 0
    most_common = str(col_data.mode().iloc[0]) if len(col_data.mode()) > 0 else "N/A"
    most_common_pct = (
        round(float(vc.iloc[0]) / max(n_rows, 1) * 100, 1) if len(vc) > 0 else 0.0
    )

    pattern_info  = _detect_pattern(sample)
    format_issue  = _check_format_consistency(sample)

    avg_word_count = None
    if unique / max(n_rows, 1) > 0.3 and len(col_data.dropna()) > 0:
        try:
            avg_word_count = round(
                float(col_data.dropna().astype(str).str.split().str.len().mean()), 1
            )
        except Exception:
            pass

    return {
        "type": "categorical",
        "top_values":      top_values,
        "other_count":     other_count,
        "most_common":     most_common,
        "most_common_pct": most_common_pct,
        "pattern":         pattern_info,
        "format_issue":    format_issue,
        "avg_word_count":  avg_word_count,
        "recommended_chart": _recommended_chart("categorical", unique, n_rows),
        "dtype_confidence": "high",
        "dtype_note":       "categorical",
    }


# ── Flag builder ──────────────────────────────────────────────────────────────

def _build_flags(col_profile: dict, col_data: pd.Series) -> list[str]:
    """Derive data quality flag strings from a completed column profile dict."""
    flags: list[str] = []
    missing_pct = col_profile.get("missing_pct", 0)
    unique_pct  = col_profile.get("unique_pct", 0)

    if missing_pct > 30:
        flags.append("high missing data")
    if missing_pct > 0:
        flags.append(f"{missing_pct}% missing")
    if unique_pct > 95 and col_data.dtype == object:
        flags.append("possible ID column")
    if col_profile.get("type") == "numeric":
        if col_profile.get("outliers_iqr", 0) > 0:
            flags.append(f"{col_profile['outliers_iqr']} IQR outliers")
        if abs(col_profile.get("skewness", 0)) > 2:
            flags.append("highly skewed")
        if not col_profile.get("is_normal", True):
            flags.append("non-normal distribution")
    if col_profile.get("unique", 1) == 1:
        flags.append("constant column")
    pattern = col_profile.get("pattern")
    if pattern and pattern.get("compliance_pct", 100) < 95:
        flags.append(
            f"{100 - pattern['compliance_pct']:.0f}% malformed {pattern['pattern']}s"
        )
    if col_profile.get("format_issue"):
        flags.append("mixed formats detected")
    if col_profile.get("type") == "datetime" and col_profile.get("gap_count", 0) > 0:
        flags.append(f"{col_profile['gap_count']} time gaps detected")

    return flags
