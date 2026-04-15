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

# ── Placeholder strings treated as missing ────────────────────────────────────
_PLACEHOLDER_STRINGS: set[str] = {
    "n/a", "na", "n.a.", "n.a", "none", "null", "nil", "nan", "nat",
    "-", "--", "---", "?", "??", "unknown", "undefined", "missing",
    "not available", "not applicable", "not provided", "not specified",
    "#n/a", "#null!", "empty", "blank", ".", "..", "...",
}


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
    """Try to parse currency strings like '$1,234.56' → 1234.56."""
    if pd.api.types.is_numeric_dtype(series):
        return None, 0
    sample = series.dropna().head(100).astype(str)
    matches = sample.str.match(_CURRENCY_RE).sum()
    if matches / max(len(sample), 1) < 0.95:
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
    """Try to parse percentage strings like '45%' → 45.0."""
    if pd.api.types.is_numeric_dtype(series):
        return None, 0
    sample = series.dropna().head(100).astype(str)
    matches = sample.str.match(_PERCENT_RE).sum()
    if matches / max(len(sample), 1) < 0.90:
        return None, 0
    cleaned = series.astype(str).str.replace(r"\s*%", "", regex=True)
    numeric = pd.to_numeric(cleaned, errors="coerce")
    n_converted = int(numeric.notna().sum())
    return numeric, n_converted


def _standardize_booleans(series: pd.Series) -> tuple[pd.Series | None, str | None, int]:
    """Detect and unify boolean-synonym columns (yes/YES/y/1/True/on → yes/no)."""
    clean = series.dropna().astype(str).str.strip().str.lower()
    unique_vals = set(clean.unique())
    is_true = unique_vals.issubset(_BOOL_TRUE | _BOOL_FALSE)
    if not is_true or len(unique_vals) < 2:
        return None, None, 0
    if unique_vals == {"yes", "no"} or unique_vals == {"true", "false"} or unique_vals == {"1", "0"}:
        return None, None, 0
    mapping = {v: "yes" if v in _BOOL_TRUE else "no" for v in unique_vals}
    standardized = series.astype(str).str.strip().str.lower().map(mapping).where(series.notna(), other=None)
    n_changed = int((standardized.fillna("") != series.astype(str).str.strip().str.lower().fillna("")).sum())
    return standardized, "yes/no", n_changed


def _harmonize_date_formats(series: pd.Series) -> tuple[pd.Series | None, int, list[str]]:
    """Detect mixed date format strings and standardize to ISO."""
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
    result = pd.to_datetime(series, infer_datetime_format=True, errors="coerce")
    n_converted = int(result.notna().sum())
    return result, n_converted, detected_formats


def _replace_placeholders(df: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    """
    Replace known placeholder strings (N/A, None, null, -, ?, unknown, …)
    with NaN across all object/string columns.
    Returns the modified DataFrame and the total count of replacements.
    """
    total_replaced = 0
    for col in df.select_dtypes(include=["object"]).columns:
        # Normalise to lowercase for matching, preserve original NaN positions
        lower = df[col].astype(str).str.strip().str.lower()
        mask = lower.isin(_PLACEHOLDER_STRINGS) & df[col].notna()
        n = int(mask.sum())
        if n > 0:
            df[col] = df[col].where(~mask, other=np.nan)
            total_replaced += n
    return df, total_replaced


def _remove_duplicate_columns(df: pd.DataFrame) -> tuple[pd.DataFrame, int, list[str]]:
    """
    Remove columns whose values are identical to a preceding column.
    Returns the cleaned DataFrame, count removed, and list of removed column names.
    """
    seen: dict[str, str] = {}   # hash → first column name
    to_drop: list[str] = []
    for col in df.columns:
        col_hash = pd.util.hash_pandas_object(df[col].fillna("__NA__"), index=False).sum()
        key = str(col_hash)
        if key in seen:
            to_drop.append(col)
        else:
            seen[key] = col
    if to_drop:
        df = df.drop(columns=to_drop)
    return df, len(to_drop), to_drop


def _flag_suspicious_zeros(
    df: pd.DataFrame,
    threshold: float = 0.10,
) -> list[dict]:
    """
    Flag numeric columns where a suspiciously high fraction of non-missing values
    are exactly zero — which often signals that 0 was used to encode missingness
    rather than a true measurement.

    No mutation — only returns a list of warning dicts.
    threshold: minimum zero-fraction to trigger a warning (default 10%).
    """
    warnings: list[dict] = []
    for col in df.select_dtypes(include=[np.number]).columns:
        non_null = df[col].dropna()
        if len(non_null) < 20:
            continue
        zero_count = int((non_null == 0).sum())
        zero_pct = zero_count / len(non_null)
        if zero_pct < threshold:
            continue
        # Additional heuristic: zero_pct spike is suspicious when the column has
        # a non-trivial range (i.e. it's not a binary or count-of-zero column).
        col_range = float(non_null.max() - non_null.min())
        if col_range == 0:
            continue  # constant column — zeros expected
        if non_null.nunique() <= 2:
            continue  # binary column — zeros are legitimate
        warnings.append({
            "column": col,
            "zero_count": zero_count,
            "zero_pct": round(zero_pct * 100, 1),
            "message": (
                f"'{col}' has {zero_count} exact zeros ({zero_pct * 100:.1f}% of non-null values). "
                f"Zeros may encode missing data rather than a true measurement. "
                f"Verify with the data source before modeling."
            ),
        })
    return warnings


def _extract_date_features(df: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    """
    For each datetime column, extract calendar features as new numeric columns:
    year, month, day, day_of_week (0=Mon … 6=Sun), quarter, is_weekend.

    Returns the augmented DataFrame and a list of newly created column names.
    """
    created: list[str] = []
    datetime_cols = df.select_dtypes(include=["datetime64"]).columns.tolist()
    for col in datetime_cols:
        series = df[col]
        base = col  # already snake_case after step 3
        features = {
            f"{base}_year":         series.dt.year,
            f"{base}_month":        series.dt.month,
            f"{base}_day":          series.dt.day,
            f"{base}_day_of_week":  series.dt.dayofweek,
            f"{base}_quarter":      series.dt.quarter,
            f"{base}_is_weekend":   series.dt.dayofweek.isin([5, 6]).astype(int),
        }
        for feat_name, feat_series in features.items():
            if feat_name not in df.columns:
                df[feat_name] = feat_series
                created.append(feat_name)
    return df, created


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


def clean_dataset(df: pd.DataFrame) -> tuple[pd.DataFrame, list[dict], dict]:
    report: list[dict] = []
    df_clean = df.copy()
    original_shape = df_clean.shape

    # Track new summary fields
    placeholders_replaced = 0
    duplicate_cols_removed = 0
    duplicate_col_names: list[str] = []
    date_features_created: list[str] = []
    total_outliers_winsorized = 0
    suspicious_issues: list[dict] = []

    # Snapshot original missing % before any changes
    missing_pct_original = round(
        df_clean.isnull().sum().sum() / max(original_shape[0] * original_shape[1], 1) * 100, 1
    )

    # Early return for empty DataFrames
    if df_clean.empty and len(df_clean.columns) == 0:
        return df_clean, report, {
            "original_rows": 0, "original_cols": 0, "final_rows": 0, "final_cols": 0,
            "rows_removed": 0, "cols_removed": 0, "steps": 0,
            "time_saved_estimate": "~1 minutes",
            "confidence_score": 0,
            "placeholders_replaced": 0,
            "duplicate_cols_removed": 0,
            "date_features_created": [],
            "suspicious_issues_remaining": [],
        }

    # ── Step 0: Replace placeholder strings with NaN ─────────────────────────
    df_clean, placeholders_replaced = _replace_placeholders(df_clean)
    if placeholders_replaced > 0:
        report.append({
            "step": "Replace placeholder values",
            "detail": (
                f"Replaced {placeholders_replaced} placeholder strings "
                f"(N/A, None, null, -, ?, unknown, …) with NaN across string columns"
            ),
            "impact": "high",
        })

    # ── Step 1: Remove fully empty rows and columns ───────────────────────────
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

    # ── Step 2: Remove duplicate rows ────────────────────────────────────────
    dupes = int(df_clean.duplicated().sum())
    if dupes > 0:
        df_clean.drop_duplicates(inplace=True)
        report.append({
            "step": "Remove duplicate rows",
            "detail": f"Dropped {dupes} exact duplicate rows ({round(dupes / max(len(df), 1) * 100, 1)}% of data)",
            "impact": "high",
        })

    # ── Step 2b: Remove duplicate columns ────────────────────────────────────
    df_clean, duplicate_cols_removed, duplicate_col_names = _remove_duplicate_columns(df_clean)
    if duplicate_cols_removed > 0:
        names_str = ", ".join(f"'{c}'" for c in duplicate_col_names[:5])
        report.append({
            "step": "Remove duplicate columns",
            "detail": (
                f"Dropped {duplicate_cols_removed} column(s) with identical content to a preceding column: "
                f"{names_str}"
            ),
            "impact": "medium",
        })

    # ── Step 3: Standardize column names ─────────────────────────────────────
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

    # ── Step 4: Smart string type parsing (currency, %, datetime, numeric) ───
    for col in list(df_clean.columns):
        if not pd.api.types.is_string_dtype(df_clean[col]):
            continue
        non_null_original = df_clean[col].notna().sum()
        if non_null_original == 0:
            continue

        # 4a. Currency
        parsed, n_conv = _try_parse_currency(df_clean[col])
        if parsed is not None and n_conv / non_null_original > 0.95:
            df_clean[col] = parsed
            report.append({
                "step": f"Parse currency: {col}",
                "detail": f"Converted {n_conv} currency strings in '{col}' to numeric (e.g. '$1,234.56' → 1234.56)",
                "impact": "high",
            })
            continue

        # 4b. Percentage
        parsed, n_conv = _try_parse_percentage(df_clean[col])
        if parsed is not None and n_conv / non_null_original > 0.90:
            df_clean[col] = parsed
            report.append({
                "step": f"Parse percentage: {col}",
                "detail": f"Converted {n_conv} percentage strings in '{col}' to numeric (e.g. '45%' → 45.0)",
                "impact": "high",
            })
            continue

        # 4c. Numeric
        converted = pd.to_numeric(df_clean[col], errors="coerce")
        if non_null_original > 0 and converted.notna().sum() / non_null_original > 0.9:
            df_clean[col] = converted
            report.append({
                "step": f"Convert to numeric: {col}",
                "detail": f"Converted '{col}' from text to numeric ({int(converted.notna().sum())} valid numbers detected)",
                "impact": "high",
            })
            continue

        # 4d. Harmonize mixed date formats
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

        # 4e. Datetime
        try:
            converted_dt = pd.to_datetime(df_clean[col], errors="coerce")
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

    # ── Step 5: Categorical standardization (yes/YES/y/1/True → yes/no) ──────
    for col in list(df_clean.columns):
        if not pd.api.types.is_string_dtype(df_clean[col]):
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

    # ── Step 6: Handle missing values with missingness mechanism awareness ────
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

    # ── Step 7: Adaptive winsorization (IQR for skewed, sigma for normal) ─────
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
            total_outliers_winsorized += outside
            report.append({
                "step": f"Winsorize outliers: {col}",
                "detail": (
                    f"Clipped {outside} extreme values in '{col}' using {method_desc} "
                    f"[{lower:.4g}, {upper:.4g}]"
                ),
                "impact": "medium",
            })

    # ── Step 7b: Suspicious zero flagging (warning only — no mutation) ────────
    suspicious_zeros = _flag_suspicious_zeros(df_clean)
    for sz in suspicious_zeros:
        suspicious_issues.append({
            "type": "suspicious_zeros",
            "column": sz["column"],
            "detail": sz["message"],
        })
        report.append({
            "step": f"Suspicious zeros detected: {sz['column']}",
            "detail": sz["message"],
            "impact": "warning",
        })

    # ── Step 8: Strip whitespace from string columns ──────────────────────────
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

    # ── Step 8b: Normalize string casing (lowercase all-uppercase columns) ────
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

    # ── Step 9: Date feature extraction (after all cleaning) ─────────────────
    df_clean, date_features_created = _extract_date_features(df_clean)
    if date_features_created:
        feat_list = ", ".join(date_features_created[:8])
        report.append({
            "step": "Extract date features",
            "detail": (
                f"Created {len(date_features_created)} calendar feature(s) from datetime column(s): "
                f"{feat_list}"
            ),
            "impact": "medium",
        })

    # ── Build summary ─────────────────────────────────────────────────────────
    final_shape = df_clean.shape
    complex_steps = sum(
        1 for r in report
        if any(kw in r["detail"] for kw in ["MICE", "KNN", "MNAR", "currency", "percentage", "Harmonize"])
    )
    simple_steps = len(report) - complex_steps
    time_saved = simple_steps * 5 + complex_steps * 15

    confidence_score = _compute_confidence_score(
        original_rows=original_shape[0],
        original_cols=original_shape[1],
        missing_pct_original=missing_pct_original,
        placeholders_replaced=placeholders_replaced,
        suspicious_issues_count=len(suspicious_issues),
        total_outliers_winsorized=total_outliers_winsorized,
        duplicate_cols_removed=duplicate_cols_removed,
    )

    summary = {
        "original_rows": original_shape[0],
        "original_cols": original_shape[1],
        "final_rows": final_shape[0],
        "final_cols": final_shape[1],
        "rows_removed": original_shape[0] - final_shape[0],
        "cols_removed": original_shape[1] - final_shape[1],
        "steps": len(report),
        "time_saved_estimate": f"~{max(1, time_saved)} minutes",
        # ── New fields ──
        "confidence_score": confidence_score,
        "placeholders_replaced": placeholders_replaced,
        "duplicate_cols_removed": duplicate_cols_removed,
        "date_features_created": date_features_created,
        "suspicious_issues_remaining": suspicious_issues,
    }

    return df_clean, report, summary
