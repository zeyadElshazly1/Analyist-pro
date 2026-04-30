"""
Missing value classification and imputation.

Handles: MCAR/MAR/MNAR detection, KNN imputation, MICE imputation, simple imputation.
"""
import numpy as np
import pandas as pd
from scipy.stats import pointbiserialr


def _classify_missingness(df: pd.DataFrame, col: str) -> tuple[str, float]:
    """Classify missing data mechanism: MCAR / MAR / MNAR.

    Threshold for MNAR detection raised from 0.3 → 0.4 to reduce
    false positives on structured time-series data.
    """
    missing_indicator = df[col].isnull().astype(float)
    if missing_indicator.sum() < 3:
        return "mcar", 0.0

    numeric_others = [c for c in df.select_dtypes(include=[np.number]).columns if c != col]
    max_corr = 0.0
    for other_col in numeric_others[:15]:
        other_clean = df[other_col].fillna(df[other_col].median())
        try:
            r, _ = pointbiserialr(missing_indicator, other_clean)
            if abs(r) > abs(max_corr):
                max_corr = r
        except Exception:
            pass

    # MNAR proxy: previous-row value predicts current missingness.
    # Threshold raised from 0.3 to 0.4 to reduce false MNAR classifications.
    non_missing = df[col].dropna()
    if len(non_missing) >= 10 and pd.api.types.is_numeric_dtype(df[col]):
        shifted = df[col].shift(1).dropna()
        aligned_missing = missing_indicator[shifted.index]
        try:
            r_self, _ = pointbiserialr(aligned_missing, shifted)
            if abs(r_self) > 0.4:
                return "mnar", float(abs(r_self))
        except Exception:
            pass

    if abs(max_corr) > 0.25:
        return "mar", float(abs(max_corr))
    return "mcar", float(abs(max_corr))


def _safe_knn_k(df: pd.DataFrame, col: str, default_k: int = 5) -> int:
    """Return a safe n_neighbors value that won't exceed the number of complete rows."""
    complete_rows = int(df[col].notna().sum())
    return max(1, min(default_k, complete_rows - 1))


def _knn_impute_column(df: pd.DataFrame, col: str, n_neighbors: int = 5) -> pd.Series:
    try:
        from sklearn.impute import KNNImputer
    except ImportError:
        return df[col].fillna(df[col].median())
    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    if col not in numeric_cols:
        return df[col].fillna(df[col].median())
    safe_k = _safe_knn_k(df, col, n_neighbors)
    sub = df[numeric_cols].copy()
    imputer = KNNImputer(n_neighbors=safe_k, weights="distance")
    imputed = imputer.fit_transform(sub)
    return pd.Series(imputed[:, numeric_cols.index(col)], index=df.index)


def _iterative_impute_column(
    df: pd.DataFrame, col: str
) -> tuple[pd.Series, str | None]:
    """Impute *col* using MICE / IterativeImputer.

    Returns ``(imputed_series, convergence_caveat_or_None)``.  The caveat is
    a human-readable string that the caller should append to the cleaning
    report when it is not None; it means imputation completed but the
    iterative solver did not fully converge, so values are estimates.
    """
    import warnings

    try:
        from sklearn.experimental import enable_iterative_imputer  # noqa: F401
        from sklearn.impute import IterativeImputer
        from sklearn.linear_model import BayesianRidge
        from sklearn.exceptions import ConvergenceWarning
    except ImportError:
        return _knn_impute_column(df, col), None

    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    predictors = [c for c in numeric_cols if c != col and df[c].isnull().mean() < 0.5]
    if len(predictors) < 2:
        return _knn_impute_column(df, col), None

    cols_to_use = [col] + predictors[:9]
    sub = df[cols_to_use].copy()
    # max_iter=15 reduces convergence failures vs the old 10 without
    # materially increasing runtime on the datasets we see in practice.
    imputer = IterativeImputer(estimator=BayesianRidge(), max_iter=15, random_state=42)

    with warnings.catch_warnings(record=True) as caught_warnings:
        warnings.simplefilter("always", ConvergenceWarning)
        imputed = imputer.fit_transform(sub)

    caveat: str | None = None
    if any(issubclass(w.category, ConvergenceWarning) for w in caught_warnings):
        caveat = (
            f"Iterative imputation for '{col}' completed but the solver did not fully "
            f"converge (max_iter=15). Imputed values are reasonable estimates — consider "
            f"reviewing this column manually if precision matters."
        )

    return pd.Series(imputed[:, 0], index=df.index), caveat


def _simple_impute_value(series: pd.Series) -> tuple[float, str]:
    clean = series.dropna()
    if len(clean) < 3:
        return float(clean.median()), "median"
    if abs(float(clean.skew())) > 1.0:
        return float(clean.median()), "median"
    return float(clean.mean()), "mean"
