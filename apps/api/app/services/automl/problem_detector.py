"""
Problem type detector.

detect_problem_type(df, target_col) → "classification" | "regression"

Replaces the original single-rule heuristic (nunique <= 20 → classification)
with a multi-signal approach that correctly handles:
  - Satisfaction scores / ratings / NPS (1–10 integer → classification)
  - Revenue / price / salary columns (float → regression)
  - High-cardinality numeric columns (→ regression)
  - String / object targets (→ always classification)
"""
from __future__ import annotations

import pandas as pd

# Keywords strongly suggesting a continuous numeric target
_REGRESSION_NAMES: frozenset[str] = frozenset({
    "amount", "price", "revenue", "cost", "qty", "quantity",
    "total", "age", "salary", "income", "weight", "height",
    "size", "count", "duration", "distance", "temperature",
})

# Keywords for ordinal/discrete targets that look numeric but are categorical
_SCORE_NAMES: frozenset[str] = frozenset({
    "score", "rating", "rank", "satisfaction", "risk",
    "rate", "index", "nps", "grade",
})


def detect_problem_type(df: pd.DataFrame, target_col: str) -> str:
    """
    Infer whether target_col is a regression or classification target.

    Decision order (first matching rule wins):
    1. Object/string dtype          → classification
    2. Semantic regression keyword  → regression
    3. Score/rating keyword + ≤15 unique values → classification
    4. Integer values + ≤15 unique  → classification
    5. High cardinality (ratio>0.05 or nunique>20) → regression
    6. Default                      → classification
    """
    col = df[target_col].dropna()
    col_lower = target_col.lower()

    if col.dtype == object:
        return "classification"

    n_unique = col.nunique()
    n_rows   = max(len(col), 1)
    cardinality_ratio = n_unique / n_rows

    if any(kw in col_lower for kw in _REGRESSION_NAMES):
        return "regression"

    if any(kw in col_lower for kw in _SCORE_NAMES) and n_unique <= 15:
        return "classification"

    has_decimals = bool((col % 1 != 0).any())
    if not has_decimals and n_unique <= 15:
        return "classification"

    if cardinality_ratio > 0.05 or n_unique > 20:
        return "regression"

    return "classification"
