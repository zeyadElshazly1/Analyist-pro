"""Column candidate ranking for correlation analysis."""
from __future__ import annotations

import pandas as pd


def _rank_numeric_candidates(
    df: pd.DataFrame, cols: list[str], max_n: int = 20
) -> list[str]:
    """Rank numeric columns by variance × completeness × uniqueness. Best first."""
    scores: dict[str, float] = {}
    for col in cols:
        completeness = float(df[col].notna().mean())
        n_unique = int(df[col].nunique())
        std = float(df[col].std())
        mean = abs(float(df[col].mean()))
        cv = std / mean if mean > 1e-10 else std
        uniqueness = min(n_unique / max(len(df), 1), 1.0)
        scores[col] = completeness * uniqueness * min(cv, 10.0)
    return sorted(cols, key=lambda c: scores.get(c, 0.0), reverse=True)[:max_n]


def _rank_categorical_candidates(
    df: pd.DataFrame, cols: list[str], max_n: int = 10
) -> list[str]:
    """Rank categorical columns by completeness × cardinality score. Best first."""
    scores: dict[str, float] = {}
    for col in cols:
        completeness = float(df[col].notna().mean())
        n_unique = int(df[col].nunique())
        # Prefer moderate cardinality (5-20 unique values)
        if 5 <= n_unique <= 20:
            cardinality_score = 1.0
        elif 2 <= n_unique <= 30:
            cardinality_score = 0.6
        else:
            cardinality_score = 0.0
        scores[col] = completeness * cardinality_score
    return sorted(cols, key=lambda c: scores.get(c, 0.0), reverse=True)[:max_n]
