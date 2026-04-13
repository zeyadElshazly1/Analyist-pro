import re
import pandas as pd
import numpy as np
from scipy import stats

# ── Pattern regexes ───────────────────────────────────────────────────────────
_EMAIL_RE = re.compile(r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$")
_PHONE_RE = re.compile(r"^[\+]?[(]?[0-9]{3}[)]?[\-\s\.]?[0-9]{3}[\-\s\.]?[0-9]{4,6}$")
_URL_RE = re.compile(r"^(https?://|www\.)\S+")
_ZIP_US_RE = re.compile(r"^\d{5}(-\d{4})?$")
_IP_RE = re.compile(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$")
_CURRENCY_RE = re.compile(r"^[€$£¥₹]?\s*-?[\d,]+\.?\d*\s*[€$£¥₹]?$")
_PERCENT_RE = re.compile(r"^-?\d+\.?\d*\s*%$")

_PATTERN_CHECKS = [
    ("email", _EMAIL_RE),
    ("phone", _PHONE_RE),
    ("url", _URL_RE),
    ("zip_code", _ZIP_US_RE),
    ("ip_address", _IP_RE),
    ("currency", _CURRENCY_RE),
    ("percentage", _PERCENT_RE),
]


def _normality_test(series: pd.Series) -> tuple[bool, float]:
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
    clean = series.dropna()
    if len(clean) < 4:
        return 0
    q1, q3 = float(clean.quantile(0.25)), float(clean.quantile(0.75))
    iqr = q3 - q1
    return int(((clean < q1 - 1.5 * iqr) | (clean > q3 + 1.5 * iqr)).sum())


def _recommended_chart(col_type: str, n_unique: int, n_rows: int) -> str:
    if col_type == "datetime":
        return "line"
    if col_type == "numeric":
        return "bar" if n_unique <= 10 else "histogram"
    if col_type == "categorical":
        return "bar" if n_unique <= 12 else "bar_top10"
    return "bar"


def _detect_pattern(series: pd.Series) -> dict | None:
    """Detect if a string column matches a known pattern (email, phone, URL, etc.).

    Returns a result with ``pattern_strength`` of "strong" (≥85% compliance)
    or "weak" (50–84%) so consumers can differentiate reliable detections from
    ambiguous ones.  Returns None if compliance < 50%.
    """
    sample = series.dropna().astype(str).head(300)
    if len(sample) == 0:
        return None
    for pattern_name, pattern_re in _PATTERN_CHECKS:
        matches = sample.str.match(pattern_re).sum()
        compliance = round(float(matches) / len(sample) * 100, 1)
        if compliance >= 50:
            pattern_strength = "strong" if compliance >= 85 else "weak"
            return {
                "pattern": pattern_name,
                "pattern_strength": pattern_strength,
                "compliance_pct": compliance,
                "malformed_count": int(len(sample) * (1 - matches / len(sample))),
                "note": (
                    f"{compliance:.0f}% of values match {pattern_name} format"
                    + (f" ({100 - compliance:.0f}% are malformed)" if compliance < 100 else "")
                ),
            }
    return None


def _check_format_consistency(series: pd.Series) -> dict | None:
    """Detect mixed value formats within a string column."""
    sample = series.dropna().astype(str).head(200)
    if len(sample) < 10:
        return None

    # Detect multiple date-like format clusters
    date_formats_found = []
    import datetime
    _QUICK_DATE_FORMATS = [
        ("%Y-%m-%d", r"^\d{4}-\d{2}-\d{2}$"),
        ("%d/%m/%Y", r"^\d{2}/\d{2}/\d{4}$"),
        ("%m/%d/%Y", r"^\d{2}/\d{2}/\d{4}$"),
        ("%d.%m.%Y", r"^\d{2}\.\d{2}\.\d{4}$"),
        ("%Y%m%d", r"^\d{8}$"),
    ]
    for fmt, pat in _QUICK_DATE_FORMATS:
        count = int(sample.str.match(pat).sum())
        if count > 0:
            date_formats_found.append((fmt, count))

    if len(date_formats_found) >= 2:
        format_desc = ", ".join(f"{fmt} ({n} values)" for fmt, n in date_formats_found)
        return {
            "issue": "mixed_date_formats",
            "formats_found": [f for f, _ in date_formats_found],
            "detail": f"Mixed date formats detected: {format_desc}. Standardize to ISO 8601 (YYYY-MM-DD).",
        }

    # Detect mixed length / structure patterns (e.g. phone formats)
    lengths = sample.str.len().value_counts()
    if len(lengths) >= 3 and lengths.iloc[0] / len(sample) < 0.7:
        top_lengths = lengths.head(3).to_dict()
        return {
            "issue": "inconsistent_length",
            "detail": f"Values have inconsistent lengths: {top_lengths}. May indicate mixed formatting.",
        }

    return None


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
            "fresh" if recency_days <= 7
            else "recent" if recency_days <= 30
            else "stale" if recency_days <= 180
            else "outdated"
        ),
    }


def _detect_dataset_type(df: pd.DataFrame) -> str:
    datetime_cols = df.select_dtypes(include=["datetime64"]).columns.tolist()
    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    object_cols = df.select_dtypes(include=["object", "category"]).columns.tolist()

    if datetime_cols and numeric_cols:
        return "timeseries"

    for col in df.columns:
        unique_ratio = df[col].nunique() / max(len(df), 1)
        col_lower = col.lower()
        if unique_ratio > 0.9 and any(kw in col_lower for kw in ["id", "order", "transaction", "invoice", "customer"]):
            return "transactional"

    if object_cols:
        low_cardinality = sum(1 for col in object_cols if df[col].nunique() <= 10)
        if low_cardinality / max(len(object_cols), 1) > 0.5:
            return "survey"

    return "general"


def profile_dataset(df: pd.DataFrame) -> list[dict]:
    profile = []

    for col in df.columns:
        col_data = df[col]
        missing = int(col_data.isnull().sum())
        missing_pct = round(missing / max(len(df), 1) * 100, 1)
        unique = int(col_data.nunique())
        unique_pct = round(unique / max(len(df), 1) * 100, 1)
        dtype = str(col_data.dtype)

        col_profile: dict = {
            "column": col,
            "dtype": dtype,
            "missing": missing,
            "missing_pct": missing_pct,
            "unique": unique,
            "unique_pct": unique_pct,
        }

        is_numeric = pd.api.types.is_numeric_dtype(col_data)
        is_datetime = pd.api.types.is_datetime64_any_dtype(col_data)

        if is_numeric:
            clean = col_data.dropna()
            skewness = round(float(clean.skew()), 3) if len(clean) > 2 else 0.0
            kurtosis = round(float(clean.kurtosis()), 3) if len(clean) > 3 else 0.0
            is_normal, normality_p = _normality_test(clean)
            iqr_outliers = _iqr_outliers(clean)
            z_outliers = int((np.abs(stats.zscore(clean)) > 3).sum()) if len(clean) >= 3 else 0

            n_unique = clean.nunique()
            if n_unique <= 5 and len(clean) > 20:
                dtype_confidence, dtype_note = "low", "possibly encoded categorical"
            elif n_unique <= 15 and len(clean) > 50:
                dtype_confidence, dtype_note = "medium", "may be ordinal"
            else:
                dtype_confidence, dtype_note = "high", "continuous numeric"

            col_profile.update({
                "type": "numeric",
                "mean": round(float(clean.mean()), 4) if len(clean) > 0 else None,
                "median": round(float(clean.median()), 4) if len(clean) > 0 else None,
                "std": round(float(clean.std()), 4) if len(clean) > 1 else None,
                "min": round(float(clean.min()), 4) if len(clean) > 0 else None,
                "max": round(float(clean.max()), 4) if len(clean) > 0 else None,
                "q25": round(float(clean.quantile(0.25)), 4) if len(clean) > 0 else None,
                "q75": round(float(clean.quantile(0.75)), 4) if len(clean) > 0 else None,
                "skewness": skewness,
                "kurtosis": kurtosis,
                "is_normal": is_normal,
                "normality_p": normality_p,
                "outliers_zscore": z_outliers,
                "outliers_iqr": iqr_outliers,
                "zeros": int((clean == 0).sum()),
                "dtype_confidence": dtype_confidence,
                "dtype_note": dtype_note,
                "recommended_chart": _recommended_chart("numeric", unique, len(df)),
            })

        elif is_datetime:
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
            col_profile.update({
                "type": "datetime",
                "min": str(clean.min()) if len(clean) > 0 else None,
                "max": str(clean.max()) if len(clean) > 0 else None,
                "range_days": int((clean.max() - clean.min()).days) if len(clean) > 1 else 0,
                "inferred_frequency": freq_guess,
                "gap_count": gaps["gap_count"],
                "largest_gap_days": gaps["largest_gap_days"],
                "gaps": gaps["gaps"],
                "data_freshness": gaps.get("data_freshness"),
                "most_recent_days_ago": gaps.get("most_recent_days_ago"),
                "recommended_chart": "line",
                "dtype_confidence": "high",
                "dtype_note": "datetime",
            })

        else:
            top_values_raw = col_data.value_counts().head(10)
            top_values = {str(k): int(v) for k, v in top_values_raw.items()}
            other_count = int(col_data.value_counts().iloc[10:].sum()) if len(col_data.value_counts()) > 10 else 0
            most_common = str(col_data.mode().iloc[0]) if len(col_data.mode()) > 0 else "N/A"
            most_common_pct = (
                round(float(col_data.value_counts().iloc[0]) / max(len(df), 1) * 100, 1)
                if len(col_data.value_counts()) > 0 else 0.0
            )

            # Pattern detection + format consistency
            pattern_info = _detect_pattern(col_data)
            format_issue = _check_format_consistency(col_data)

            # Average word count for free-text columns (high cardinality)
            avg_word_count = None
            if unique / max(len(df), 1) > 0.3 and len(col_data.dropna()) > 0:
                try:
                    avg_word_count = round(
                        float(col_data.dropna().astype(str).str.split().str.len().mean()), 1
                    )
                except Exception:
                    pass

            col_profile.update({
                "type": "categorical",
                "top_values": top_values,
                "other_count": other_count,
                "most_common": most_common,
                "most_common_pct": most_common_pct,
                "pattern": pattern_info,
                "format_issue": format_issue,
                "avg_word_count": avg_word_count,
                "recommended_chart": _recommended_chart("categorical", unique, len(df)),
                "dtype_confidence": "high",
                "dtype_note": "categorical",
            })

        # Data quality flags
        flags: list[str] = []
        if missing_pct > 30:
            flags.append("high missing data")
        if missing_pct > 0:
            flags.append(f"{missing_pct}% missing")
        if unique_pct > 95 and col_data.dtype == object:
            flags.append("possible ID column")
        if is_numeric:
            if col_profile.get("outliers_iqr", 0) > 0:
                flags.append(f"{col_profile['outliers_iqr']} IQR outliers")
            if abs(col_profile.get("skewness", 0)) > 2:
                flags.append("highly skewed")
            if not col_profile.get("is_normal", True):
                flags.append("non-normal distribution")
        if unique == 1:
            flags.append("constant column")
        if col_profile.get("pattern") and col_profile["pattern"].get("compliance_pct", 100) < 95:
            flags.append(f"{100 - col_profile['pattern']['compliance_pct']:.0f}% malformed {col_profile['pattern']['pattern']}s")
        if col_profile.get("format_issue"):
            flags.append("mixed formats detected")
        if is_datetime and col_profile.get("gap_count", 0) > 0:
            flags.append(f"{col_profile['gap_count']} time gaps detected")

        col_profile["flags"] = flags
        profile.append(col_profile)

    return profile


# ── Health score weights by dataset type ─────────────────────────────────────
_HEALTH_WEIGHTS = {
    "timeseries":    {"completeness": 35, "uniqueness": 15, "consistency": 20, "validity": 15, "structure": 15},
    "transactional": {"completeness": 25, "uniqueness": 30, "consistency": 20, "validity": 15, "structure": 10},
    "survey":        {"completeness": 30, "uniqueness": 10, "consistency": 25, "validity": 20, "structure": 15},
    "general":       {"completeness": 30, "uniqueness": 20, "consistency": 20, "validity": 15, "structure": 15},
}


def _column_health_score(col_data: pd.Series, df_len: int) -> dict:
    """Return a 0–100 quality score for a single column."""
    score = 100.0
    issues = []

    missing_pct = col_data.isnull().mean() * 100
    if missing_pct > 0:
        deduct = min(40.0, missing_pct * 1.5)
        score -= deduct
        issues.append(f"{missing_pct:.1f}% missing (-{deduct:.0f})")

    is_numeric = pd.api.types.is_numeric_dtype(col_data)
    if is_numeric:
        clean = col_data.dropna()
        if len(clean) >= 4:
            q1, q3 = clean.quantile(0.25), clean.quantile(0.75)
            iqr = q3 - q1
            if iqr > 0:
                outlier_pct = float(((clean < q1 - 1.5 * iqr) | (clean > q3 + 1.5 * iqr)).mean() * 100)
                if outlier_pct > 0:
                    deduct = min(20.0, outlier_pct * 2)
                    score -= deduct
                    issues.append(f"{outlier_pct:.1f}% outliers (-{deduct:.0f})")

        if len(clean) > 2 and abs(float(clean.skew())) > 3:
            score -= 5
            issues.append("severe skew (-5)")

        if col_data.nunique() <= 1:
            score -= 20
            issues.append("constant value (-20)")

    return {
        "score": round(max(0.0, score), 1),
        "issues": issues,
    }


def calculate_health_score(df: pd.DataFrame) -> dict:
    dataset_type = _detect_dataset_type(df)
    weights = _HEALTH_WEIGHTS[dataset_type]
    scores: dict[str, float] = {}
    deductions: list[str] = []

    # 1. Completeness
    w_c = weights["completeness"]
    total_cells = max(len(df) * len(df.columns), 1)
    missing_pct = df.isnull().sum().sum() / total_cells * 100
    completeness = max(0.0, w_c - missing_pct * (w_c / 20))
    scores["completeness"] = round(completeness, 1)
    if missing_pct > 0:
        affected_rows = int(df.isnull().any(axis=1).sum())
        deductions.append(
            f"Missing data: -{round(w_c - completeness, 1)} pts "
            f"({missing_pct:.1f}% of cells; ~{affected_rows:,} rows will produce unreliable results)"
        )

    # 2. Uniqueness
    w_u = weights["uniqueness"]
    dupe_pct = df.duplicated().sum() / max(len(df), 1) * 100
    uniqueness = max(0.0, w_u - dupe_pct * (w_u / 10))
    scores["uniqueness"] = round(uniqueness, 1)
    if dupe_pct > 0:
        deductions.append(f"Duplicate rows: -{round(w_u - uniqueness, 1)} pts ({dupe_pct:.1f}% duplicates)")

    # 3. Consistency
    w_con = weights["consistency"]
    consistency = float(w_con)
    for col in df.select_dtypes(include="object").columns:
        try:
            if df[col].dropna().astype(str).str.strip().ne(df[col].dropna().astype(str)).any():
                consistency -= 2
                deductions.append(f"Whitespace issues in '{col}': -2 pts")
                break
        except Exception:
            pass
    mixed_type_cols = sum(
        1 for col in df.columns
        if df[col].dtype == object and 0.1 < pd.to_numeric(df[col], errors="coerce").notna().mean() < 0.9
    )
    if mixed_type_cols > 0:
        deduction = min(float(w_con) * 0.5, mixed_type_cols * 3.0)
        consistency -= deduction
        deductions.append(f"Mixed types in {mixed_type_cols} columns: -{deduction:.1f} pts")
    scores["consistency"] = round(max(0.0, consistency), 1)

    # 4. Validity
    w_v = weights["validity"]
    validity = float(w_v)
    numeric_cols = df.select_dtypes(include="number").columns
    outlier_cols = 0
    for col in numeric_cols:
        clean = df[col].dropna()
        if len(clean) < 4:
            continue
        q1, q3 = clean.quantile(0.25), clean.quantile(0.75)
        iqr = q3 - q1
        if iqr > 0 and ((clean < q1 - 1.5 * iqr) | (clean > q3 + 1.5 * iqr)).any():
            outlier_cols += 1
    if outlier_cols > 0:
        deduction = min(float(w_v) * 0.7, outlier_cols * 2.0)
        validity -= deduction
        deductions.append(f"IQR outliers in {outlier_cols} columns: -{deduction:.1f} pts")
    skewed_cols = [col for col in numeric_cols if len(df[col].dropna()) > 10 and abs(float(df[col].skew())) > 2]
    if skewed_cols:
        skew_pen = min(float(w_v) * 0.3, len(skewed_cols) * 1.0)
        validity -= skew_pen
        deductions.append(f"Highly skewed in {len(skewed_cols)} columns: -{skew_pen:.1f} pts")
    scores["validity"] = round(max(0.0, validity), 1)

    # 5. Structure
    w_s = weights["structure"]
    structure = float(w_s)
    constant_cols = [col for col in df.columns if df[col].nunique() <= 1]
    if constant_cols:
        deduction = min(float(w_s) * 0.6, len(constant_cols) * 2.0)
        structure -= deduction
        deductions.append(f"Constant columns: -{deduction:.1f} pts ({len(constant_cols)} columns with ≤1 unique value)")
    very_skewed = [col for col in numeric_cols if len(df[col].dropna()) > 10 and abs(float(df[col].skew())) > 3]
    if very_skewed:
        deduction = min(float(w_s) * 0.4, len(very_skewed) * 1.5)
        structure -= deduction
        deductions.append(f"Very highly skewed: -{deduction:.1f} pts ({len(very_skewed)} columns)")
    scores["structure"] = round(max(0.0, structure), 1)

    total = round(sum(scores.values()), 1)

    if total >= 85:
        grade, label, color = "A", "Excellent", "#68d391"
    elif total >= 70:
        grade, label, color = "B", "Good", "#90cdf4"
    elif total >= 55:
        grade, label, color = "C", "Fair", "#f6ad55"
    elif total >= 40:
        grade, label, color = "D", "Poor", "#fc8181"
    else:
        grade, label, color = "F", "Critical", "#e53e3e"

    # Per-column health breakdown
    column_health = {}
    for col in df.columns:
        ch = _column_health_score(df[col], len(df))
        column_health[col] = ch

    # Business impact summary
    total_rows = len(df)
    missing_rows = int(df.isnull().any(axis=1).sum())
    dupe_rows = int(df.duplicated().sum())
    outlier_rows_approx = 0
    for col in numeric_cols:
        clean = df[col].dropna()
        if len(clean) >= 4:
            q1, q3 = clean.quantile(0.25), clean.quantile(0.75)
            iqr = q3 - q1
            if iqr > 0:
                outlier_rows_approx = max(
                    outlier_rows_approx,
                    int(((clean < q1 - 1.5 * iqr) | (clean > q3 + 1.5 * iqr)).sum())
                )

    business_impact = {
        "unreliable_rows": missing_rows,
        "unreliable_pct": round(missing_rows / max(total_rows, 1) * 100, 1),
        "duplicate_rows": dupe_rows,
        "outlier_rows_estimate": outlier_rows_approx,
        "summary": (
            f"~{missing_rows:,} rows ({missing_rows / max(total_rows, 1) * 100:.1f}%) have at least one missing value "
            f"and may produce unreliable analysis results. "
            + (f"{dupe_rows:,} duplicate rows inflate counts and skew averages. " if dupe_rows > 0 else "")
            + (f"~{outlier_rows_approx:,} rows contain outliers that may distort statistical tests." if outlier_rows_approx > 0 else "")
        ),
    }

    # Actionable fix suggestions per deduction
    fix_suggestions = []
    if missing_rows > 0:
        fix_suggestions.append({
            "issue": "Missing data",
            "options": [
                {"action": "Fill with median", "effect": "Safe for skewed numeric columns — preserves distribution shape", "risk": "Low"},
                {"action": "Fill with mean", "effect": "Good for symmetric distributions — may be pulled by outliers", "risk": "Low"},
                {"action": "KNN imputation", "effect": "Uses similar rows — preserves relationships between columns", "risk": "Medium"},
                {"action": "Drop column", "effect": "Eliminates missing data issue but loses all information in that column", "risk": "High"},
            ],
        })
    if dupe_rows > 0:
        fix_suggestions.append({
            "issue": "Duplicate rows",
            "options": [
                {"action": "Remove all exact duplicates", "effect": f"Reduces dataset by {dupe_rows} rows, eliminates double-counting", "risk": "Low"},
                {"action": "Keep first occurrence", "effect": "Deterministic — keeps earliest record when duplicates appear", "risk": "Low"},
            ],
        })

    return {
        "total": total,
        "grade": grade,
        "label": label,
        "color": color,
        "dataset_type": dataset_type,
        "breakdown": scores,
        "deductions": deductions,
        "max_scores": weights,
        "column_health": column_health,
        "business_impact": business_impact,
        "fix_suggestions": fix_suggestions,
    }
