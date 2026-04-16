"""
Data quality detectors.

Three simple checks that run in O(n) time:
  - High-cardinality string/category columns (possible identifiers / free-text)
  - Columns with > 5% missing values
  - Constant numeric columns (zero variance)
"""
import pandas as pd


def detect_high_cardinality(df: pd.DataFrame) -> list[dict]:
    """Flag object/category columns where > 80% of values are unique."""
    insights: list[dict] = []
    n_rows = len(df)
    for col in df.select_dtypes(include=["object", "category"]).columns:
        n_unique = df[col].nunique()
        ratio = n_unique / n_rows
        if ratio > 0.8 and n_unique > 50:
            insights.append({
                "type": "data_quality",
                "severity": "low",
                "confidence": 90.0,
                "title": f"High-cardinality column: {col}",
                "finding": (
                    f"'{col}' has {n_unique} unique values ({ratio:.0%} of rows). "
                    f"May be an identifier or free-text field."
                ),
                "evidence": f"{n_unique} unique values out of {n_rows} rows",
                "action": (
                    f"Consider whether '{col}' should be excluded from analysis "
                    f"or bucketed/encoded."
                ),
            })
    return insights


def detect_missing_columns(df: pd.DataFrame) -> list[dict]:
    """Report columns where > 5% of values are missing."""
    insights: list[dict] = []
    n_rows = len(df)
    for col, count in df.isnull().sum().items():
        if count == 0:
            continue
        pct = round(count / n_rows * 100, 1)
        if pct <= 5:
            continue
        insights.append({
            "type": "data_quality",
            "severity": "high" if pct > 30 else "medium",
            "confidence": 99.0,
            "title": f"Missing data in {col}",
            "finding": (
                f"{count} records ({pct}% of data) are missing values in '{col}'."
            ),
            "evidence": f"{count}/{n_rows} rows missing ({pct}%)",
            "action": (
                "Drop this column or impute carefully."
                if pct > 40
                else "Impute with median/mode or model-based imputation."
            ),
        })
    return insights


def detect_constant_columns(df: pd.DataFrame, numeric_cols: list[str]) -> list[dict]:
    """Flag numeric columns with zero variance."""
    insights: list[dict] = []
    for col in numeric_cols:
        col_data = df[col].dropna()
        if len(col_data) < 5 or col_data.std() >= 1e-6:
            continue
        insights.append({
            "type": "data_quality",
            "severity": "medium",
            "confidence": 100.0,
            "title": f"Constant column: {col}",
            "finding": (
                f"'{col}' has zero variance — all values are identical "
                f"({col_data.iloc[0]})."
            ),
            "evidence": f"Std={col_data.std():.2e}, unique values={col_data.nunique()}",
            "action": (
                f"Remove '{col}' from any model or analysis — it carries no information."
            ),
        })
    return insights
