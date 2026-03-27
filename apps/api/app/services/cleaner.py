import pandas as pd
import numpy as np
from scipy import stats

def clean_dataset(df):
    report = []
    df_clean = df.copy()
    original_shape = df_clean.shape

    # 1. Remove fully empty rows and columns
    empty_rows = df_clean.isnull().all(axis=1).sum()
    empty_cols = df_clean.isnull().all(axis=0).sum()
    df_clean.dropna(how='all', inplace=True)
    df_clean.dropna(axis=1, how='all', inplace=True)
    if empty_rows > 0 or empty_cols > 0:
        report.append({
            "step": "Removed empty rows/columns",
            "detail": f"Dropped {empty_rows} empty rows and {empty_cols} empty columns",
            "impact": "high"
        })

    # 2. Remove duplicate rows
    dupes = df_clean.duplicated().sum()
    if dupes > 0:
        df_clean.drop_duplicates(inplace=True)
        report.append({
            "step": "Removed duplicates",
            "detail": f"Dropped {dupes} duplicate rows ({round(dupes/len(df)*100,1)}% of data)",
            "impact": "high"
        })

    # 3. Fix column names
    original_cols = df_clean.columns.tolist()
    df_clean.columns = (
        df_clean.columns
        .str.strip()
        .str.lower()
        .str.replace(' ', '_')
        .str.replace(r'[^\w]', '_', regex=True)
    )
    renamed = sum(1 for a, b in zip(original_cols, df_clean.columns) if a != b)
    if renamed > 0:
        report.append({
            "step": "Standardized column names",
            "detail": f"Cleaned {renamed} column names — removed spaces and special characters",
            "impact": "medium"
        })

    # 4. Fix data types
    for col in df_clean.columns:
        # Try converting to numeric
        if df_clean[col].dtype == object:
            converted = pd.to_numeric(df_clean[col], errors='coerce')
            non_null_converted = converted.dropna()
            non_null_original = df_clean[col].dropna()
            if len(non_null_converted) / max(len(non_null_original), 1) > 0.9:
                df_clean[col] = converted
                report.append({
                    "step": f"Fixed data type: {col}",
                    "detail": f"Converted '{col}' from text to numeric",
                    "impact": "high"
                })
                continue

        # Try converting to datetime
        if df_clean[col].dtype == object:
            try:
                converted = pd.to_datetime(df_clean[col], errors='coerce')
                non_null_converted = converted.dropna()
                non_null_original = df_clean[col].dropna()
                if len(non_null_converted) / max(len(non_null_original), 1) > 0.9:
                    df_clean[col] = converted
                    report.append({
                        "step": f"Fixed data type: {col}",
                        "detail": f"Converted '{col}' from text to datetime",
                        "impact": "medium"
                    })
            except:
                pass

    # 5. Handle missing values
    for col in df_clean.columns:
        missing = df_clean[col].isnull().sum()
        if missing == 0:
            continue
        missing_pct = missing / len(df_clean) * 100

        if missing_pct > 60:
            df_clean.drop(columns=[col], inplace=True)
            report.append({
                "step": f"Dropped column: {col}",
                "detail": f"'{col}' was {missing_pct:.1f}% empty — too much missing data to be useful",
                "impact": "high"
            })
        elif df_clean[col].dtype in [np.float64, np.int64, float, int]:
            median_val = df_clean[col].median()
            df_clean[col].fillna(median_val, inplace=True)
            report.append({
                "step": f"Filled missing values: {col}",
                "detail": f"Filled {missing} missing values in '{col}' with median ({median_val:.2f})",
                "impact": "medium"
            })
        else:
            mode_val = df_clean[col].mode()[0] if len(df_clean[col].mode()) > 0 else "Unknown"
            df_clean[col].fillna(mode_val, inplace=True)
            report.append({
                "step": f"Filled missing values: {col}",
                "detail": f"Filled {missing} missing values in '{col}' with most common value ('{mode_val}')",
                "impact": "medium"
            })

    # 6. Fix outliers in numeric columns (cap at 3 std)
    numeric_cols = df_clean.select_dtypes(include=[np.number]).columns
    for col in numeric_cols:
        col_data = df_clean[col].dropna()
        if len(col_data) < 10:
            continue
        z_scores = np.abs(stats.zscore(col_data))
        outlier_count = (z_scores > 3).sum()
        if outlier_count > 0:
            mean = col_data.mean()
            std = col_data.std()
            lower = mean - 3 * std
            upper = mean + 3 * std
            df_clean[col] = df_clean[col].clip(lower=lower, upper=upper)
            report.append({
                "step": f"Capped outliers: {col}",
                "detail": f"Capped {outlier_count} outliers in '{col}' to 3 standard deviations",
                "impact": "medium"
            })

    # 7. Strip whitespace from string columns
    str_cols = df_clean.select_dtypes(include='object').columns
    stripped = 0
    for col in str_cols:
        original = df_clean[col].copy()
        df_clean[col] = df_clean[col].str.strip()
        stripped += (original != df_clean[col]).sum()
    if stripped > 0:
        report.append({
            "step": "Stripped whitespace",
            "detail": f"Removed leading/trailing spaces from {stripped} values",
            "impact": "low"
        })

    final_shape = df_clean.shape
    summary = {
        "original_rows": original_shape[0],
        "original_cols": original_shape[1],
        "final_rows": final_shape[0],
        "final_cols": final_shape[1],
        "rows_removed": original_shape[0] - final_shape[0],
        "cols_removed": original_shape[1] - final_shape[1],
        "steps": len(report)
    }

    return df_clean, report, summary