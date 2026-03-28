import pandas as pd
import numpy as np
from scipy import stats


def _choose_imputation(series: pd.Series) -> tuple[float, str]:
    """Choose mean vs median based on skewness. Returns (value, method_name)."""
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
    df_clean.dropna(how='all', inplace=True)
    df_clean.dropna(axis=1, how='all', inplace=True)
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
        .str.replace(r'\s+', '_', regex=True)
        .str.replace(r'[^\w]', '_', regex=True)
        .str.replace(r'_+', '_', regex=True)
        .str.strip('_')
    )
    renamed = sum(1 for a, b in zip(original_cols, df_clean.columns) if a != b)
    if renamed > 0:
        report.append({
            "step": "Standardize column names",
            "detail": f"Cleaned {renamed} column names — lowercase, underscores, removed special characters",
            "impact": "medium",
        })

    # 4. Fix data types (numeric detection)
    for col in list(df_clean.columns):
        if df_clean[col].dtype != object:
            continue
        # Try numeric first
        converted = pd.to_numeric(df_clean[col], errors='coerce')
        non_null_converted = converted.notna().sum()
        non_null_original = df_clean[col].notna().sum()
        if non_null_original > 0 and non_null_converted / non_null_original > 0.9:
            df_clean[col] = converted
            report.append({
                "step": f"Convert to numeric: {col}",
                "detail": f"Converted '{col}' from text to numeric (detected {non_null_converted} valid numbers)",
                "impact": "high",
            })
            continue
        # Try datetime
        try:
            converted_dt = pd.to_datetime(df_clean[col], errors='coerce', infer_datetime_format=True)
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

    # 5. Handle missing values
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
        elif pd.api.types.is_numeric_dtype(df_clean[col]):
            fill_val, method = _choose_imputation(df_clean[col])
            df_clean[col] = df_clean[col].fillna(fill_val)
            report.append({
                "step": f"Impute missing: {col}",
                "detail": (
                    f"Filled {missing} missing values in '{col}' with {method} "
                    f"({fill_val:.4g}) — chose {method} due to "
                    f"{'skewed' if method == 'median' else 'symmetric'} distribution"
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

    # 6. Winsorize outliers in numeric columns (1st/99th percentile clip)
    numeric_cols = df_clean.select_dtypes(include=[np.number]).columns.tolist()
    for col in numeric_cols:
        col_data = df_clean[col].dropna()
        if len(col_data) < 20:
            continue
        z_scores = np.abs(stats.zscore(col_data))
        outlier_count = int((z_scores > 3).sum())
        if outlier_count > 0:
            lower = float(col_data.quantile(0.01))
            upper = float(col_data.quantile(0.99))
            df_clean[col] = df_clean[col].clip(lower=lower, upper=upper)
            report.append({
                "step": f"Winsorize outliers: {col}",
                "detail": (
                    f"Clipped {outlier_count} extreme values in '{col}' to 1st–99th percentile "
                    f"range [{lower:.4g}, {upper:.4g}]"
                ),
                "impact": "medium",
            })

    # 7. Strip whitespace from string columns
    str_cols = df_clean.select_dtypes(include='object').columns.tolist()
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
    for col in df_clean.select_dtypes(include='object').columns:
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
    summary = {
        "original_rows": original_shape[0],
        "original_cols": original_shape[1],
        "final_rows": final_shape[0],
        "final_cols": final_shape[1],
        "rows_removed": original_shape[0] - final_shape[0],
        "cols_removed": original_shape[1] - final_shape[1],
        "steps": len(report),
        "time_saved_estimate": f"~{max(1, len(report) * 5)} minutes",
    }

    return df_clean, report, summary
