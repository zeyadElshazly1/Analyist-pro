"""
Data quality scoring and grading.

Computes a 0-100 confidence score with letter grades (A+/A/B/C/D).
"""

_GRADE_THRESHOLDS = [
    (90, "A+", "Analyst Ready"),
    (80, "A",  "High Quality"),
    (65, "B",  "Good"),
    (50, "C",  "Needs Review"),
    (0,  "D",  "Significant Issues"),
]


def _compute_confidence_score(
    original_rows: int,
    original_cols: int,
    missing_pct_original: float,
    placeholders_replaced: int,
    suspicious_issues_count: int,
    total_outliers_winsorized: int,
    duplicate_cols_removed: int,
) -> int:
    """
    Compute a 0–100 data confidence score.

    Penalises:
    - High original missingness      → up to −30 pts
    - Placeholder pollution          → up to −20 pts
    - Suspicious issues remaining    → up to −20 pts  (5 pts each, max 4)
    - High outlier / winsorization rate → up to −15 pts
    - Duplicate columns              → up to −10 pts
    """
    score = 100.0
    total_cells = max(original_rows * original_cols, 1)

    # Missing data penalty
    score -= min(30.0, missing_pct_original * 0.5)

    # Placeholder penalty (as % of total cells)
    placeholder_rate = placeholders_replaced / total_cells * 100
    score -= min(20.0, placeholder_rate * 0.4)

    # Suspicious zero issues penalty
    score -= min(20.0, suspicious_issues_count * 5.0)

    # Outlier winsorization penalty (as % of total numeric cells)
    outlier_rate = total_outliers_winsorized / max(total_cells, 1) * 100
    score -= min(15.0, outlier_rate * 0.3)

    # Duplicate columns penalty
    score -= min(10.0, duplicate_cols_removed * 2.0)

    return max(0, min(100, round(score)))


def score_to_grade(score: int) -> dict:
    """Convert a numeric confidence score to a grade dict.

    Returns {"score": int, "grade": str, "label": str}

    Example: score_to_grade(87) → {"score": 87, "grade": "A", "label": "High Quality"}
    """
    for threshold, grade, label in _GRADE_THRESHOLDS:
        if score >= threshold:
            return {"score": score, "grade": grade, "label": label}
    return {"score": score, "grade": "D", "label": "Significant Issues"}
