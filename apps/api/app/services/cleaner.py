import pandas as pd
import numpy as np
from scipy import stats
from scipy.stats import pointbiserialr


def _classify_missingness(df: pd.DataFrame, col: str) -> tuple[str, float]:
    """
    Classify missing data mechanism for a column:
      - MCAR: missingness uncorrelated with other variables
      - MAR:  missingness correlated with other observed variables
      - MNAR: column's own value predicts its own missingness

    Returns (mechanism, max_correlation).
    """
    missing_indicator = df[col].isnull().astype(float)
    if missing_indicator.sum() < 3:
        return "mcar", 0.0

    numeric_others = df.select_dtypes(include=[np.number]).columns.tolist()
    numeric_others = [c for c in numeric_others if c != col]

    max_corr = 0.0
    for other_col in numeric_others[:15]:
        other_clean = df[other_col].fillna(df[other_col].median())
        try:
            r, _ = pointbiserialr(missing_indicator, other_clean)
            if abs(r) > abs(max_corr):
                max_corr = r
        except Exception:
            pass

    # Check if column's own non-missing values predict missingness (MNAR proxy)
    # Compare distribution of non-missing values vs overall: if mean differs a lot, likely MNAR
    non_missing = df[col].dropna()
    if len(non_missing) >= 10 and pd.api.types.is_numeric_dtype(df[col]):
        # Use a simple heuristic: MNAR if top/bottom 20% values have disproportionate missingness
        # We can't observe missing values directly, but we can check quantile patterns
        # Use "neighboring rows" heuristic — if previous value correlates with current missingness
        shifted = df[col].shift(1).dropna()
        aligned_missing = missing_indicator[shifted.index]
        try:
            r_self, _ = pointbiserialr(aligned_missing, shifted)
            if abs(r_self) > 0.3:
                return "mnar", float(abs(r_self))
        except Exception:
            pass

    if abs(max_corr) > 0.25:
        return "mar", float(abs(max_corr))
    return "mcar", float(abs(max_corr))


def _knn_impute_column(df: pd.DataFrame, col: str, n_neighbors: int = 5) -> pd.Series:
    """KNN imputation using all numeric columns as features."""
    try:
        from sklearn.impute import KNNImputer
    except ImportError:
        return df[col].fillna(df[col].median())

    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    if col not in numeric_cols:
        return df[col].fillna(df[col].median())

    sub = df[numeric_cols].copy()
    imputer = KNNImputer(n_neighbors=n_neighbors, weights="distance")
    imputed = imputer.fit_transform(sub)
    col_idx = numeric_cols.index(col)
    return pd.Series(imputed[:, col_idx], index=df.index)


def _iterative_impute_column(df: pd.DataFrame, col: str) -> pd.Series:
    """MICE-style iterative imputation using BayesianRidge as estimator."""
    try:
        from sklearn.experimental import enable_iterative_imputer  # noqa
        from sklearn.impute import IterativeImputer
        from sklearn.linear_model import BayesianRidge
    except ImportError:
        return _knn_impute_column(df, col)

    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    predictors = [c for c in numeric_cols if c != col and df[c].isnull().mean() < 0.5]

    if len(predictors) < 2:
        # Fall back to KNN when too few predictor columns
        return _knn_impute_column(df, col)

    cols_to_use = [col] + predictors[:9]  # cap at 10 columns for performance
    sub = df[cols_to_use].copy()
    imputer = IterativeImputer(estimator=BayesianRidge(), max_iter=10, random_state=42)
    imputed = imputer.fit_transform(sub)
    return pd.Series(imputed[:, 0], index=df.index)


def _simple_impute_value(series: pd.Series) -> tuple[float, str]:
    """Return (fill_value, method_name). Uses mean for symmetric, median for skewed."""
    clean = series.dropna()
    if len(clean) < 3:
        return float(clean.median()), "median"
    skew = abs(float(clean.skew()))
    if skew > 1.0:
        return float(clean.median()), "median"
    return float(clean.mean()), "mean"


def clean_dataset(df: pd.DataFrame) -> tuple[pd.DataFrame, list[dict], dict]:
    report = []
    df_clean = df.copy()
    original_shape = df_clean.shape

    # 1. Remove fully empty rows and columns
    empty_rows = int(df_clean.isnull().all(axis=1).sum())
    empty_cols = int(df_clean.isnull().all(axis=0).sum())
    df_clean.dropna(how="all", inplace=True)
    df_clean.dropna(axis=1, how="all", inplace=True)
    if empty_rows > 0 or empty_cols > 0:
        report.append({
            "step": "Remove empty rows/columns",
            "detail": f"Dropped {empty_rows} completely empty rows and {empty_cols} empty columns",
            "impact": "high",
        })

    # 2. Remove duplicate rows
    dupes = int(df_clean.duplicated().sum())
    if dupes > 0:
        df_clean.drop_duplicates(inplace=True)
        report.append({
            "step": "Remove duplicate rows",
            "detail": f"Dropped {dupes} exact duplicate rows ({round(dupes / max(len(df), 1) * 100, 1)}% of data)",
            "impact": "high",
        })

    # 3. Standardize column names
    original_cols = df_clean.columns.tolist()
    df_clean.columns = (
        df_clean.columns
        .str.strip()
        .str.lower()
        .str.replace(r"\s+", "_", regex=True)
        .str.replace(r"[^\w]", "_", regex=True)
        .str.replace(r"_+", "_", regex=True)
        .str.strip("_")
    )
    renamed = sum(1 for a, b in zip(original_cols, df_clean.columns) if a != b)
    if renamed > 0:
        report.append({
            "step": "Standardize column names",
            "detail": f"Cleaned {renamed} column names — lowercase, underscores, removed special characters",
            "impact": "medium",
        })

    # 4. Fix data types (numeric + datetime detection)
    for col in list(df_clean.columns):
        if df_clean[col].dtype != object:
            continue
        converted = pd.to_numeric(df_clean[col], errors="coerce")
        non_null_converted = converted.notna().sum()
        non_null_original = df_clean[col].notna().sum()
        if non_null_original > 0 and non_null_converted / non_null_original > 0.9:
            df_clean[col] = converted
            report.append({
                "step": f"Convert to numeric: {col}",
                "detail": f"Converted '{col}' from text to numeric ({non_null_converted} valid numbers detected)",
                "impact": "high",
            })
            continue
        try:
            converted_dt = pd.to_datetime(df_clean[col], errors="coerce", infer_datetime_format=True)
            non_null_dt = converted_dt.notna().sum()
            if non_null_original > 0 and non_null_dt / non_null_original > 0.9:
                df_clean[col] = converted_dt
                report.append({
                    "step": f"Convert to datetime: {col}",
                    "detail": f"Converted '{col}' from text to datetime",
                    "impact": "medium",
                })
        except Exception:
            pass

    # 5. Handle missing values with missingness mechanism awareness
    for col in list(df_clean.columns):
        missing = int(df_clean[col].isnull().sum())
        if missing == 0:
            continue
        missing_pct = missing / max(len(df_clean), 1) * 100

        if missing_pct > 60:
            df_clean.drop(columns=[col], inplace=True)
            report.append({
                "step": f"Drop high-missing column: {col}",
                "detail": f"'{col}' had {missing_pct:.1f}% missing values — too sparse to be useful",
                "impact": "high",
            })
            continue

        if pd.api.types.is_numeric_dtype(df_clean[col]):
            mechanism, max_corr = _classify_missingness(df_clean, col)

            if mechanism == "mnar":
                # MNAR: create binary flag column, then median-fill the original
                flag_col = f"{col}_was_missing"
                df_clean[flag_col] = df_clean[col].isnull().astype(int)
                fill_val, fill_method = _simple_impute_value(df_clean[col])
                df_clean[col] = df_clean[col].fillna(fill_val)
                report.append({
                    "step": f"Impute missing (MNAR): {col}",
                    "detail": (
                        f"Detected MNAR pattern in '{col}' (correlation={max_corr:.2f}). "
                        f"Created binary flag '{flag_col}'. Filled {missing} values with {fill_method} ({fill_val:.4g})."
                    ),
                    "impact": "high",
                })

            elif mechanism == "mar" and missing_pct <= 30:
                # MAR with moderate missingness: use MICE (iterative) or KNN imputation
                try:
                    if len(df_clean.select_dtypes(include=[np.number]).columns) >= 4:
                        imputed = _iterative_impute_column(df_clean, col)
                        method_name = "MICE (iterative)"
                    else:
                        imputed = _knn_impute_column(df_clean, col)
                        method_name = "KNN"
                    df_clean[col] = imputed
                    report.append({
                        "step": f"Impute missing (MAR): {col}",
                        "detail": (
                            f"Detected MAR pattern in '{col}' (correlation with other columns={max_corr:.2f}). "
                            f"Used {method_name} imputation to fill {missing} values."
                        ),
                        "impact": "medium",
                    })
                except Exception:
                    fill_val, fill_method = _simple_impute_value(df_clean[col])
                    df_clean[col] = df_clean[col].fillna(fill_val)
                    report.append({
                        "step": f"Impute missing (MAR fallback): {col}",
                        "detail": (
                            f"MAR detected in '{col}' but advanced imputation failed. "
                            f"Fell back to {fill_method} ({fill_val:.4g}) for {missing} values."
                        ),
                        "impact": "medium",
                    })

            else:
                # MCAR or high missingness MAR: simple mean/median imputation
                fill_val, fill_method = _simple_impute_value(df_clean[col])
                df_clean[col] = df_clean[col].fillna(fill_val)
                mech_label = mechanism.upper()
                report.append({
                    "step": f"Impute missing ({mech_label}): {col}",
                    "detail": (
                        f"Filled {missing} missing values in '{col}' with {fill_method} ({fill_val:.4g}). "
                        f"Mechanism: {mech_label} — data appears to be missing at random."
                    ),
                    "impact": "medium",
                })

        else:
            mode_vals = df_clean[col].mode()
            mode_val = str(mode_vals.iloc[0]) if len(mode_vals) > 0 else "Unknown"
            df_clean[col] = df_clean[col].fillna(mode_val)
            report.append({
                "step": f"Impute missing: {col}",
                "detail": f"Filled {missing} missing values in '{col}' with most common value ('{mode_val}')",
                "impact": "medium",
            })

    # 6. Adaptive winsorization: IQR-based for skewed, sigma-based for normal
    numeric_cols = df_clean.select_dtypes(include=[np.number]).columns.tolist()
    for col in numeric_cols:
        col_data = df_clean[col].dropna()
        if len(col_data) < 20:
            continue
        skew = abs(float(col_data.skew()))
        if skew > 1.0:
            # Heavily skewed: use wider IQR fence (Tukey's outer fence)
            q1, q3 = float(col_data.quantile(0.25)), float(col_data.quantile(0.75))
            iqr = q3 - q1
            lower = q1 - 3.0 * iqr
            upper = q3 + 3.0 * iqr
            outside = int(((col_data < lower) | (col_data > upper)).sum())
            method_desc = "3×IQR fence (skewed distribution)"
        else:
            # Approximately normal: ±4σ clip (less aggressive than 3σ to reduce false positives)
            mean, std = float(col_data.mean()), float(col_data.std())
            lower = mean - 4 * std
            upper = mean + 4 * std
            outside = int(((col_data < lower) | (col_data > upper)).sum())
            method_desc = "±4σ clip (normal distribution)"

        if outside > 0:
            df_clean[col] = df_clean[col].clip(lower=lower, upper=upper)
            report.append({
                "step": f"Winsorize outliers: {col}",
                "detail": (
                    f"Clipped {outside} extreme values in '{col}' using {method_desc} "
                    f"[{lower:.4g}, {upper:.4g}]"
                ),
                "impact": "medium",
            })

    # 7. Strip whitespace from string columns
    str_cols = df_clean.select_dtypes(include="object").columns.tolist()
    total_stripped = 0
    cols_stripped = []
    for col in str_cols:
        before = df_clean[col].copy()
        df_clean[col] = df_clean[col].str.strip()
        n_changed = int((before != df_clean[col]).sum())
        if n_changed > 0:
            total_stripped += n_changed
            cols_stripped.append(col)
    if total_stripped > 0:
        report.append({
            "step": "Strip whitespace",
            "detail": (
                f"Removed leading/trailing spaces from {total_stripped} values "
                f"across {len(cols_stripped)} column(s)"
            ),
            "impact": "low",
        })

    # 8. Normalize string casing (lowercase all-uppercase columns)
    for col in df_clean.select_dtypes(include="object").columns:
        sample = df_clean[col].dropna().head(50)
        if len(sample) > 0:
            upper_ratio = sample.apply(lambda x: str(x).isupper()).mean()
            if upper_ratio > 0.7:
                df_clean[col] = df_clean[col].str.title()
                report.append({
                    "step": f"Normalize casing: {col}",
                    "detail": f"Converted '{col}' from ALL-CAPS to Title Case",
                    "impact": "low",
                })

    final_shape = df_clean.shape
    # Estimate time saved: each step ~ 5 min manual, complex steps (MICE/KNN) ~ 15 min
    complex_steps = sum(1 for r in report if "MICE" in r["detail"] or "KNN" in r["detail"] or "MNAR" in r["detail"])
    simple_steps = len(report) - complex_steps
    time_saved = simple_steps * 5 + complex_steps * 15

    summary = {
        "original_rows": original_shape[0],
        "original_cols": original_shape[1],
        "final_rows": final_shape[0],
        "final_cols": final_shape[1],
        "rows_removed": original_shape[0] - final_shape[0],
        "cols_removed": original_shape[1] - final_shape[1],
        "steps": len(report),
        "time_saved_estimate": f"~{max(1, time_saved)} minutes",
    }

    return df_clean, report, summary
