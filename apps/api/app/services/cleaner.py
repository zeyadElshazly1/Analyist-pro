import re
import pandas as pd
import numpy as np
from scipy import stats
from scipy.stats import pointbiserialr

# ── Canonical mappings for boolean/truthy categoricals ───────────────────────
_BOOL_TRUE = {"yes", "y", "true", "t", "1", "on", "oui", "si", "ja", "да"}
_BOOL_FALSE = {"no", "n", "false", "f", "0", "off", "non", "nein", "нет"}

# ── Regex patterns for smart type detection ───────────────────────────────────
_CURRENCY_RE = re.compile(r"^[€$£¥₹]?\s*-?[\d,]+\.?\d*\s*[€$£¥₹]?$")
_PERCENT_RE = re.compile(r"^-?\d+\.?\d*\s*%$")
_DATE_FORMATS = [
    "%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y", "%m-%d-%Y",
    "%Y/%m/%d", "%d.%m.%Y", "%m.%d.%Y", "%B %d, %Y", "%d %B %Y",
    "%b %d, %Y", "%d %b %Y", "%Y%m%d",
]


def _classify_missingness(df: pd.DataFrame, col: str) -> tuple[str, float]:
    """Classify missing data mechanism: MCAR / MAR / MNAR."""
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

    # MNAR proxy: previous-row value predicts current missingness
    non_missing = df[col].dropna()
    if len(non_missing) >= 10 and pd.api.types.is_numeric_dtype(df[col]):
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
    return pd.Series(imputed[:, numeric_cols.index(col)], index=df.index)


def _iterative_impute_column(df: pd.DataFrame, col: str) -> pd.Series:
    try:
        from sklearn.experimental import enable_iterative_imputer  # noqa
        from sklearn.impute import IterativeImputer
        from sklearn.linear_model import BayesianRidge
    except ImportError:
        return _knn_impute_column(df, col)
    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    predictors = [c for c in numeric_cols if c != col and df[c].isnull().mean() < 0.5]
    if len(predictors) < 2:
        return _knn_impute_column(df, col)
    cols_to_use = [col] + predictors[:9]
    sub = df[cols_to_use].copy()
    imputer = IterativeImputer(estimator=BayesianRidge(), max_iter=10, random_state=42)
    imputed = imputer.fit_transform(sub)
    return pd.Series(imputed[:, 0], index=df.index)


def _simple_impute_value(series: pd.Series) -> tuple[float, str]:
    clean = series.dropna()
    if len(clean) < 3:
        return float(clean.median()), "median"
    if abs(float(clean.skew())) > 1.0:
        return float(clean.median()), "median"
    return float(clean.mean()), "mean"


def _try_parse_currency(series: pd.Series) -> tuple[pd.Series | None, int]:
    """Try to parse currency strings like '$1,234.56' → 1234.56.
    Returns (parsed_series, n_converted) or (None, 0) if not applicable."""
    sample = series.dropna().head(100).astype(str)
    matches = sample.str.match(_CURRENCY_RE).sum()
    if matches / max(len(sample), 1) < 0.7:
        return None, 0
    cleaned = (
        series.astype(str)
        .str.replace(r"[€$£¥₹,\s]", "", regex=True)
        .str.replace(r"[()]", "", regex=True)
    )
    numeric = pd.to_numeric(cleaned, errors="coerce")
    n_converted = int(numeric.notna().sum())
    return numeric, n_converted


def _try_parse_percentage(series: pd.Series) -> tuple[pd.Series | None, int]:
    """Try to parse percentage strings like '45%' → 45.0 (keeps raw number)."""
    sample = series.dropna().head(100).astype(str)
    matches = sample.str.match(_PERCENT_RE).sum()
    if matches / max(len(sample), 1) < 0.7:
        return None, 0
    cleaned = series.astype(str).str.replace(r"\s*%", "", regex=True)
    numeric = pd.to_numeric(cleaned, errors="coerce")
    n_converted = int(numeric.notna().sum())
    return numeric, n_converted


def _standardize_booleans(series: pd.Series) -> tuple[pd.Series | None, str | None, int]:
    """
    Detect columns where values are synonyms for True/False
    (e.g. yes/YES/y/1/True/on) and unify them.
    Returns (standardized_series, canonical_pair, n_changed) or (None, None, 0).
    """
    clean = series.dropna().astype(str).str.strip().str.lower()
    unique_vals = set(clean.unique())
    is_true = unique_vals.issubset(_BOOL_TRUE | _BOOL_FALSE)
    if not is_true or len(unique_vals) < 2:
        return None, None, 0

    # Already standardized?
    if unique_vals == {"yes", "no"} or unique_vals == {"true", "false"} or unique_vals == {"1", "0"}:
        return None, None, 0

    mapping = {v: "yes" if v in _BOOL_TRUE else "no" for v in unique_vals}
    standardized = series.astype(str).str.strip().str.lower().map(mapping).where(series.notna(), other=None)
    n_changed = int((standardized.fillna("") != series.astype(str).str.strip().str.lower().fillna("")).sum())
    return standardized, "yes/no", n_changed


def _harmonize_date_formats(series: pd.Series) -> tuple[pd.Series | None, int, list[str]]:
    """
    Detect columns with mixed date format strings and standardize to ISO.
    Returns (parsed_series, n_converted, formats_detected).
    """
    clean_str = series.dropna().astype(str).head(200)
    detected_formats = []
    for fmt in _DATE_FORMATS:
        try:
            parsed = pd.to_datetime(clean_str, format=fmt, errors="coerce")
            match_rate = parsed.notna().mean()
            if match_rate > 0.5:
                detected_formats.append(fmt)
        except Exception:
            pass

    if len(detected_formats) <= 1:
        return None, 0, []

    # Multiple formats detected — harmonize with mixed format inference
    result = pd.to_datetime(series, infer_datetime_format=True, errors="coerce")
    n_converted = int(result.notna().sum())
    return result, n_converted, detected_formats


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

    # 4. Smart string type parsing (currency, percentage, datetime, numeric)
    for col in list(df_clean.columns):
        if df_clean[col].dtype != object:
            continue
        non_null_original = df_clean[col].notna().sum()
        if non_null_original == 0:
            continue

        # 4a. Try currency
        parsed, n_conv = _try_parse_currency(df_clean[col])
        if parsed is not None and n_conv / non_null_original > 0.8:
            df_clean[col] = parsed
            report.append({
                "step": f"Parse currency: {col}",
                "detail": f"Converted {n_conv} currency strings in '{col}' to numeric (e.g. '$1,234.56' → 1234.56)",
                "impact": "high",
            })
            continue

        # 4b. Try percentage
        parsed, n_conv = _try_parse_percentage(df_clean[col])
        if parsed is not None and n_conv / non_null_original > 0.8:
            df_clean[col] = parsed
            report.append({
                "step": f"Parse percentage: {col}",
                "detail": f"Converted {n_conv} percentage strings in '{col}' to numeric (e.g. '45%' → 45.0)",
                "impact": "high",
            })
            continue

        # 4c. Try numeric
        converted = pd.to_numeric(df_clean[col], errors="coerce")
        if non_null_original > 0 and converted.notna().sum() / non_null_original > 0.9:
            df_clean[col] = converted
            report.append({
                "step": f"Convert to numeric: {col}",
                "detail": f"Converted '{col}' from text to numeric ({int(converted.notna().sum())} valid numbers detected)",
                "impact": "high",
            })
            continue

        # 4d. Try date format harmonization (mixed formats)
        harmonized, n_conv, formats_found = _harmonize_date_formats(df_clean[col])
        if harmonized is not None and n_conv / non_null_original > 0.8:
            df_clean[col] = harmonized
            fmts = ", ".join(formats_found[:3])
            report.append({
                "step": f"Harmonize date formats: {col}",
                "detail": (
                    f"Standardized {n_conv} values in '{col}' to ISO dates. "
                    f"Mixed formats detected: {fmts}"
                ),
                "impact": "high",
            })
            continue

        # 4e. Try datetime
        try:
            converted_dt = pd.to_datetime(df_clean[col], errors="coerce", infer_datetime_format=True)
            if non_null_original > 0 and converted_dt.notna().sum() / non_null_original > 0.9:
                df_clean[col] = converted_dt
                report.append({
                    "step": f"Convert to datetime: {col}",
                    "detail": f"Converted '{col}' from text to datetime",
                    "impact": "medium",
                })
                continue
        except Exception:
            pass

    # 5. Categorical standardization (yes/YES/y/1/True → yes/no)
    for col in list(df_clean.columns):
        if df_clean[col].dtype != object:
            continue
        standardized, canonical, n_changed = _standardize_booleans(df_clean[col])
        if standardized is not None and n_changed > 0:
            df_clean[col] = standardized
            report.append({
                "step": f"Standardize boolean: {col}",
                "detail": (
                    f"Unified {n_changed} values in '{col}' to canonical '{canonical}' form. "
                    f"Previously had mixed representations (e.g. Yes/YES/y/1/True)."
                ),
                "impact": "medium",
            })

    # 6. Handle missing values with missingness mechanism awareness
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
                try:
                    if len(df_clean.select_dtypes(include=[np.number]).columns) >= 4:
                        imputed = _iterative_impute_column(df_clean, col)
                        method_name = "MICE (iterative regression)"
                    else:
                        imputed = _knn_impute_column(df_clean, col)
                        method_name = "KNN"
                    df_clean[col] = imputed
                    report.append({
                        "step": f"Impute missing (MAR): {col}",
                        "detail": (
                            f"Detected MAR pattern in '{col}' (max cross-column correlation={max_corr:.2f}). "
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
                fill_val, fill_method = _simple_impute_value(df_clean[col])
                df_clean[col] = df_clean[col].fillna(fill_val)
                report.append({
                    "step": f"Impute missing ({mechanism.upper()}): {col}",
                    "detail": (
                        f"Filled {missing} missing values in '{col}' with {fill_method} ({fill_val:.4g}). "
                        f"Mechanism: {mechanism.upper()} — data appears to be missing at random."
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

    # 7. Adaptive winsorization: IQR-based for skewed, sigma-based for normal
    numeric_cols = df_clean.select_dtypes(include=[np.number]).columns.tolist()
    for col in numeric_cols:
        col_data = df_clean[col].dropna()
        if len(col_data) < 20:
            continue
        skew = abs(float(col_data.skew()))
        if skew > 1.0:
            q1, q3 = float(col_data.quantile(0.25)), float(col_data.quantile(0.75))
            iqr = q3 - q1
            lower = q1 - 3.0 * iqr
            upper = q3 + 3.0 * iqr
            outside = int(((col_data < lower) | (col_data > upper)).sum())
            method_desc = "3×IQR fence (skewed distribution)"
        else:
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

    # 8. Strip whitespace from string columns
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

    # 9. Normalize string casing (lowercase all-uppercase columns)
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
    complex_steps = sum(1 for r in report if any(kw in r["detail"] for kw in ["MICE", "KNN", "MNAR", "currency", "percentage", "Harmonize"]))
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
