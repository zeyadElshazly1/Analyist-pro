"""
Health score engine.

_HEALTH_WEIGHTS         — dimension weights by dataset type
_column_health_score    — 0–100 score for a single column
calculate_health_score  — overall dataset health with grade, deductions,
                          business impact, fix suggestions, and per-column breakdown

New field added (backward-compat): "dataset_type_confidence"
"""
import pandas as pd

from .dataset_classifier import _detect_dataset_type


# ── Weights by dataset type ───────────────────────────────────────────────────

_HEALTH_WEIGHTS: dict[str, dict[str, int]] = {
    "timeseries":    {"completeness": 35, "uniqueness": 15, "consistency": 20, "validity": 15, "structure": 15},
    "transactional": {"completeness": 25, "uniqueness": 30, "consistency": 20, "validity": 15, "structure": 10},
    "survey":        {"completeness": 30, "uniqueness": 10, "consistency": 25, "validity": 20, "structure": 15},
    "general":       {"completeness": 30, "uniqueness": 20, "consistency": 20, "validity": 15, "structure": 15},
}


def _column_health_score(col_data: pd.Series, df_len: int) -> dict:
    """Return a 0–100 quality score for a single column."""
    score = 100.0
    issues: list[str] = []

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
                outlier_pct = float(
                    ((clean < q1 - 1.5 * iqr) | (clean > q3 + 1.5 * iqr)).mean() * 100
                )
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
    """
    Return an overall health score dict for the dataset.

    Keys (all existing keys preserved + new 'dataset_type_confidence'):
        total, grade, label, color, dataset_type, dataset_type_confidence,
        breakdown, deductions, max_scores, column_health,
        business_impact, fix_suggestions
    """
    dataset_type, dataset_type_confidence = _detect_dataset_type(df)
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
        deductions.append(
            f"Duplicate rows: -{round(w_u - uniqueness, 1)} pts ({dupe_pct:.1f}% duplicates)"
        )

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
        if df[col].dtype == object
        and 0.1 < pd.to_numeric(df[col], errors="coerce").notna().mean() < 0.9
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
    skewed_cols = [
        col for col in numeric_cols
        if len(df[col].dropna()) > 10 and abs(float(df[col].skew())) > 2
    ]
    if skewed_cols:
        skew_pen = min(float(w_v) * 0.3, len(skewed_cols) * 1.0)
        validity -= skew_pen
        deductions.append(
            f"Highly skewed in {len(skewed_cols)} columns: -{skew_pen:.1f} pts"
        )
    scores["validity"] = round(max(0.0, validity), 1)

    # 5. Structure
    w_s = weights["structure"]
    structure = float(w_s)
    constant_cols = [col for col in df.columns if df[col].nunique() <= 1]
    if constant_cols:
        deduction = min(float(w_s) * 0.6, len(constant_cols) * 2.0)
        structure -= deduction
        deductions.append(
            f"Constant columns: -{deduction:.1f} pts "
            f"({len(constant_cols)} columns with ≤1 unique value)"
        )
    very_skewed = [
        col for col in numeric_cols
        if len(df[col].dropna()) > 10 and abs(float(df[col].skew())) > 3
    ]
    if very_skewed:
        deduction = min(float(w_s) * 0.4, len(very_skewed) * 1.5)
        structure -= deduction
        deductions.append(
            f"Very highly skewed: -{deduction:.1f} pts ({len(very_skewed)} columns)"
        )
    scores["structure"] = round(max(0.0, structure), 1)

    total = round(sum(scores.values()), 1)

    if total >= 85:
        grade, label, color = "A", "Excellent", "#68d391"
    elif total >= 70:
        grade, label, color = "B", "Good",      "#90cdf4"
    elif total >= 55:
        grade, label, color = "C", "Fair",      "#f6ad55"
    elif total >= 40:
        grade, label, color = "D", "Poor",      "#fc8181"
    else:
        grade, label, color = "F", "Critical",  "#e53e3e"

    # Per-column health breakdown
    column_health = {col: _column_health_score(df[col], len(df)) for col in df.columns}

    # Business impact summary
    total_rows   = len(df)
    missing_rows = int(df.isnull().any(axis=1).sum())
    dupe_rows    = int(df.duplicated().sum())
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
        "unreliable_rows":      missing_rows,
        "unreliable_pct":       round(missing_rows / max(total_rows, 1) * 100, 1),
        "duplicate_rows":       dupe_rows,
        "outlier_rows_estimate": outlier_rows_approx,
        "summary": (
            f"~{missing_rows:,} rows ({missing_rows / max(total_rows, 1) * 100:.1f}%) "
            f"have at least one missing value and may produce unreliable analysis results. "
            + (f"{dupe_rows:,} duplicate rows inflate counts and skew averages. " if dupe_rows > 0 else "")
            + (
                f"~{outlier_rows_approx:,} rows contain outliers that may distort statistical tests."
                if outlier_rows_approx > 0 else ""
            )
        ),
    }

    # Actionable fix suggestions
    fix_suggestions: list[dict] = []
    if missing_rows > 0:
        fix_suggestions.append({
            "issue": "Missing data",
            "options": [
                {"action": "Fill with median",  "effect": "Safe for skewed numeric columns — preserves distribution shape",                   "risk": "Low"},
                {"action": "Fill with mean",    "effect": "Good for symmetric distributions — may be pulled by outliers",                     "risk": "Low"},
                {"action": "KNN imputation",    "effect": "Uses similar rows — preserves relationships between columns",                      "risk": "Medium"},
                {"action": "Drop column",       "effect": "Eliminates missing data issue but loses all information in that column",            "risk": "High"},
            ],
        })
    if dupe_rows > 0:
        fix_suggestions.append({
            "issue": "Duplicate rows",
            "options": [
                {"action": "Remove all exact duplicates", "effect": f"Reduces dataset by {dupe_rows} rows, eliminates double-counting", "risk": "Low"},
                {"action": "Keep first occurrence",       "effect": "Deterministic — keeps earliest record when duplicates appear",    "risk": "Low"},
            ],
        })

    return {
        "total":                   total,
        "grade":                   grade,
        "label":                   label,
        "color":                   color,
        "dataset_type":            dataset_type,
        "dataset_type_confidence": dataset_type_confidence,   # NEW — backward-compat addition
        "breakdown":               scores,
        "deductions":              deductions,
        "max_scores":              weights,
        "column_health":           column_health,
        "business_impact":         business_impact,
        "fix_suggestions":         fix_suggestions,
    }
