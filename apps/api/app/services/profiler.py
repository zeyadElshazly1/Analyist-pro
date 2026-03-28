import pandas as pd
import numpy as np
from scipy import stats


def _normality_test(series: pd.Series) -> tuple[bool, float]:
    """Returns (is_normal, p_value)."""
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
    """Count outliers using IQR method."""
    clean = series.dropna()
    if len(clean) < 4:
        return 0
    q1, q3 = float(clean.quantile(0.25)), float(clean.quantile(0.75))
    iqr = q3 - q1
    lower, upper = q1 - 1.5 * iqr, q3 + 1.5 * iqr
    return int(((clean < lower) | (clean > upper)).sum())


def _recommended_chart(col_type: str, n_unique: int, n_rows: int) -> str:
    if col_type == "datetime":
        return "line"
    if col_type == "numeric":
        if n_unique <= 10:
            return "bar"
        return "histogram"
    if col_type == "categorical":
        if n_unique <= 12:
            return "bar"
        return "bar_top10"
    return "bar"


def _detect_dataset_type(df: pd.DataFrame) -> str:
    """
    Classify the dataset into one of:
      - 'timeseries'    : has a datetime column + at least one numeric
      - 'transactional' : high unique-ID column (e.g. order/customer IDs)
      - 'survey'        : many low-cardinality categoricals (Likert-like)
      - 'general'       : everything else
    """
    datetime_cols = df.select_dtypes(include=["datetime64"]).columns.tolist()
    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    object_cols = df.select_dtypes(include=["object", "category"]).columns.tolist()

    if datetime_cols and numeric_cols:
        return "timeseries"

    # Transactional: has a likely ID column (very high cardinality, numeric or string)
    for col in df.columns:
        unique_ratio = df[col].nunique() / max(len(df), 1)
        col_lower = col.lower()
        if unique_ratio > 0.9 and any(kw in col_lower for kw in ["id", "order", "transaction", "invoice", "customer"]):
            return "transactional"

    # Survey: >50% of columns are object/category with ≤10 unique values
    if object_cols:
        low_cardinality = sum(
            1 for col in object_cols
            if df[col].nunique() <= 10
        )
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

            # Data type confidence: numeric columns with very few unique values are
            # likely encoded categoricals
            n_unique = clean.nunique()
            if n_unique <= 5 and len(clean) > 20:
                dtype_confidence = "low"
                dtype_note = "possibly encoded categorical"
            elif n_unique <= 15 and len(clean) > 50:
                dtype_confidence = "medium"
                dtype_note = "may be ordinal"
            else:
                dtype_confidence = "high"
                dtype_note = "continuous numeric"

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
            col_profile.update({
                "type": "datetime",
                "min": str(clean.min()) if len(clean) > 0 else None,
                "max": str(clean.max()) if len(clean) > 0 else None,
                "range_days": int((clean.max() - clean.min()).days) if len(clean) > 1 else 0,
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
            col_profile.update({
                "type": "categorical",
                "top_values": top_values,
                "other_count": other_count,
                "most_common": most_common,
                "most_common_pct": most_common_pct,
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

        col_profile["flags"] = flags
        profile.append(col_profile)

    return profile


# ── Health score weights by dataset type ────────────────────────────────────
_HEALTH_WEIGHTS = {
    # (completeness, uniqueness, consistency, validity, structure) — must sum to 100
    "timeseries":    {"completeness": 35, "uniqueness": 15, "consistency": 20, "validity": 15, "structure": 15},
    "transactional": {"completeness": 25, "uniqueness": 30, "consistency": 20, "validity": 15, "structure": 10},
    "survey":        {"completeness": 30, "uniqueness": 10, "consistency": 25, "validity": 20, "structure": 15},
    "general":       {"completeness": 30, "uniqueness": 20, "consistency": 20, "validity": 15, "structure": 15},
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
        deductions.append(f"Missing data: -{round(w_c - completeness, 1)} pts ({missing_pct:.1f}% of cells missing)")

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

    # 4. Validity — IQR-based outlier penalty
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

    # Extra validity penalty for highly skewed distributions
    skewed_cols = [
        col for col in numeric_cols
        if len(df[col].dropna()) > 10 and abs(float(df[col].skew())) > 2
    ]
    if skewed_cols:
        skew_penalty = min(float(w_v) * 0.3, len(skewed_cols) * 1.0)
        validity -= skew_penalty
        deductions.append(f"Highly skewed distributions in {len(skewed_cols)} columns: -{skew_penalty:.1f} pts")
    scores["validity"] = round(max(0.0, validity), 1)

    # 5. Structure
    w_s = weights["structure"]
    structure = float(w_s)
    constant_cols = [col for col in df.columns if df[col].nunique() <= 1]
    if constant_cols:
        deduction = min(float(w_s) * 0.6, len(constant_cols) * 2.0)
        structure -= deduction
        deductions.append(f"Constant columns: -{deduction:.1f} pts ({len(constant_cols)} columns with ≤1 unique value)")
    very_skewed_cols = [
        col for col in numeric_cols
        if len(df[col].dropna()) > 10 and abs(float(df[col].skew())) > 3
    ]
    if very_skewed_cols:
        deduction = min(float(w_s) * 0.4, len(very_skewed_cols) * 1.5)
        structure -= deduction
        deductions.append(f"Very highly skewed columns: -{deduction:.1f} pts ({len(very_skewed_cols)} columns with skew > 3)")
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

    return {
        "total": total,
        "grade": grade,
        "label": label,
        "color": color,
        "dataset_type": dataset_type,
        "breakdown": scores,
        "deductions": deductions,
        "max_scores": weights,
    }
