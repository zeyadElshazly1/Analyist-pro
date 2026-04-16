"""
Main cleaning pipeline orchestrator.

Public entry point: clean_dataset(df, mode="aggressive")

mode="aggressive" — applies all cleaning operations (default, backward compatible)
mode="safe"       — detects issues and suggests fixes without mutating data
"""
import numpy as np
import pandas as pd

from .constants import LARGE_DATASET_THRESHOLD, LARGE_DATASET_SAMPLE_SIZE
from .feature_engineering import _extract_date_features
from .missingness import (
    _classify_missingness,
    _iterative_impute_column,
    _knn_impute_column,
    _simple_impute_value,
)
from .outliers import (
    _detect_outlier_bounds,
    _flag_suspicious_zeros,
    _handle_outliers,
    choose_outlier_strategy,
)
from .quality_score import _compute_confidence_score, score_to_grade
from .semantic import detect_semantic_columns, PROTECTED_TYPES
from .text_cleaning import _replace_placeholders, normalize_casing, strip_whitespace
from .type_inference import (
    _harmonize_date_formats,
    _standardize_booleans,
    _try_parse_currency,
    _try_parse_percentage,
)


def _get_inference_sample(df: pd.DataFrame) -> pd.DataFrame:
    """Return a representative sample for type/missingness inference on large datasets.

    For datasets ≤ LARGE_DATASET_THRESHOLD rows: returns df unchanged.
    For larger datasets: returns a deterministic sample so heavy inference
    (skewness tests, correlation checks) runs in bounded time.
    Cleaning strategies are detected on the sample but applied to the full df.
    """
    if len(df) <= LARGE_DATASET_THRESHOLD:
        return df
    return df.sample(n=LARGE_DATASET_SAMPLE_SIZE, random_state=42)


def _remove_duplicate_columns(df: pd.DataFrame) -> tuple[pd.DataFrame, int, list[str]]:
    """Remove columns whose values are identical to a preceding column.

    Uses direct value equality (.equals()) instead of hash-sum comparison
    to eliminate false positives from hash collisions.
    Returns the cleaned DataFrame, count removed, and list of removed column names.
    """
    seen: list[str] = []   # column names already kept
    to_drop: list[str] = []
    for col in df.columns:
        duplicate_of = None
        for kept_col in seen:
            if df[col].equals(df[kept_col]):
                duplicate_of = kept_col
                break
        if duplicate_of is not None:
            to_drop.append(col)
        else:
            seen.append(col)
    if to_drop:
        df = df.drop(columns=to_drop)
    return df, len(to_drop), to_drop


def clean_dataset(
    df: pd.DataFrame,
    mode: str = "aggressive",
) -> tuple[pd.DataFrame, list[dict], dict]:
    """Clean a DataFrame using the full Analyst Pro cleaning pipeline.

    Parameters
    ----------
    df   : Input DataFrame. Not mutated — a copy is returned.
    mode : "aggressive" (default) applies all cleaning operations.
           "safe" detects and reports issues but does not mutate the data.

    Returns
    -------
    tuple[pd.DataFrame, list[dict], dict]
        - df_clean  : Cleaned DataFrame (or unchanged copy in safe mode)
        - report    : List of step dicts {"step", "detail", "impact"}
        - summary   : Metrics and metadata dict including confidence_grade
    """
    report: list[dict] = []
    df_clean = df.copy()
    original_shape = df_clean.shape

    # Track summary fields
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
            "confidence_grade": score_to_grade(0),
            "placeholders_replaced": 0,
            "duplicate_cols_removed": 0,
            "date_features_created": [],
            "suspicious_issues_remaining": [],
            "semantic_columns": {},
            "mode": mode,
        }

    # ── Step 0: Replace placeholder strings with NaN ─────────────────────────
    if mode == "aggressive":
        df_clean, placeholders_replaced = _replace_placeholders(df_clean)
    else:
        # Safe mode: count but do not write
        tmp, placeholders_replaced = _replace_placeholders(df_clean.copy())
        del tmp
    if placeholders_replaced > 0:
        prefix = "" if mode == "aggressive" else "[SUGGESTION] "
        report.append({
            "step": f"{prefix}Replace placeholder values",
            "detail": (
                f"{'Replaced' if mode == 'aggressive' else 'Found'} {placeholders_replaced} placeholder strings "
                f"(N/A, None, null, -, ?, unknown, …) with NaN across string columns"
            ),
            "impact": "high" if mode == "aggressive" else "warning",
        })

    # ── Step 1: Remove fully empty rows and columns ───────────────────────────
    empty_rows = int(df_clean.isnull().all(axis=1).sum())
    empty_cols = int(df_clean.isnull().all(axis=0).sum())
    if mode == "aggressive":
        df_clean.dropna(how="all", inplace=True)
        df_clean.dropna(axis=1, how="all", inplace=True)
    if empty_rows > 0 or empty_cols > 0:
        prefix = "" if mode == "aggressive" else "[SUGGESTION] "
        report.append({
            "step": f"{prefix}Remove empty rows/columns",
            "detail": f"{'Dropped' if mode == 'aggressive' else 'Found'} {empty_rows} completely empty rows and {empty_cols} empty columns",
            "impact": "high" if mode == "aggressive" else "warning",
        })

    # ── Step 2: Remove duplicate rows ────────────────────────────────────────
    dupes = int(df_clean.duplicated().sum())
    if dupes > 0:
        if mode == "aggressive":
            df_clean.drop_duplicates(inplace=True)
        prefix = "" if mode == "aggressive" else "[SUGGESTION] "
        report.append({
            "step": f"{prefix}Remove duplicate rows",
            "detail": f"{'Dropped' if mode == 'aggressive' else 'Found'} {dupes} exact duplicate rows ({round(dupes / max(len(df), 1) * 100, 1)}% of data)",
            "impact": "high" if mode == "aggressive" else "warning",
        })

    # ── Step 2b: Remove duplicate columns ────────────────────────────────────
    if mode == "aggressive":
        df_clean, duplicate_cols_removed, duplicate_col_names = _remove_duplicate_columns(df_clean)
    else:
        _, duplicate_cols_removed, duplicate_col_names = _remove_duplicate_columns(df_clean.copy())
    if duplicate_cols_removed > 0:
        names_str = ", ".join(f"'{c}'" for c in duplicate_col_names[:5])
        prefix = "" if mode == "aggressive" else "[SUGGESTION] "
        report.append({
            "step": f"{prefix}Remove duplicate columns",
            "detail": (
                f"{'Dropped' if mode == 'aggressive' else 'Found'} {duplicate_cols_removed} column(s) with identical content: "
                f"{names_str}"
            ),
            "impact": "medium" if mode == "aggressive" else "warning",
        })

    # ── Step 3: Standardize column names ─────────────────────────────────────
    original_cols = df_clean.columns.tolist()
    if mode == "aggressive":
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
        prefix = "" if mode == "aggressive" else "[SUGGESTION] "
        report.append({
            "step": f"{prefix}Standardize column names",
            "detail": f"{'Cleaned' if mode == 'aggressive' else 'Would clean'} {renamed} column names — lowercase, underscores, removed special characters",
            "impact": "medium" if mode == "aggressive" else "warning",
        })

    # ── Detect semantic columns (after name standardization) ─────────────────
    semantic_map = detect_semantic_columns(df_clean)
    protected_cols = {
        col for col, typ in semantic_map.items()
        if typ in PROTECTED_TYPES
    }

    # ── Step 4: Smart string type parsing (currency, %, datetime, numeric) ───
    _sample = _get_inference_sample(df_clean)
    for col in list(df_clean.columns):
        if not pd.api.types.is_string_dtype(df_clean[col]):
            continue
        if col in protected_cols:
            continue  # never auto-convert IDs, phone numbers, postal codes, SKUs
        non_null_original = df_clean[col].notna().sum()
        if non_null_original == 0:
            continue

        # 4a. Currency
        parsed, n_conv = _try_parse_currency(df_clean[col])
        if parsed is not None and n_conv / non_null_original > 0.95:
            if mode == "aggressive":
                df_clean[col] = parsed
            report.append({
                "step": f"{'Parse' if mode == 'aggressive' else '[SUGGESTION] Parse'} currency: {col}",
                "detail": f"{'Converted' if mode == 'aggressive' else 'Found'} {n_conv} currency strings in '{col}' to numeric (e.g. '$1,234.56' → 1234.56)",
                "impact": "high" if mode == "aggressive" else "warning",
            })
            continue

        # 4b. Percentage
        parsed, n_conv = _try_parse_percentage(df_clean[col])
        if parsed is not None and n_conv / non_null_original > 0.90:
            if mode == "aggressive":
                df_clean[col] = parsed
            report.append({
                "step": f"{'Parse' if mode == 'aggressive' else '[SUGGESTION] Parse'} percentage: {col}",
                "detail": f"{'Converted' if mode == 'aggressive' else 'Found'} {n_conv} percentage strings in '{col}' to numeric (e.g. '45%' → 45.0)",
                "impact": "high" if mode == "aggressive" else "warning",
            })
            continue

        # 4c. Numeric
        converted = pd.to_numeric(df_clean[col], errors="coerce")
        if non_null_original > 0 and converted.notna().sum() / non_null_original > 0.9:
            if mode == "aggressive":
                df_clean[col] = converted
            report.append({
                "step": f"{'Convert' if mode == 'aggressive' else '[SUGGESTION] Convert'} to numeric: {col}",
                "detail": f"{'Converted' if mode == 'aggressive' else 'Would convert'} '{col}' from text to numeric ({int(converted.notna().sum())} valid numbers detected)",
                "impact": "high" if mode == "aggressive" else "warning",
            })
            continue

        # 4d. Harmonize mixed date formats (use sample for detection)
        sample_col = _sample[col] if col in _sample.columns else df_clean[col]
        harmonized, n_conv, formats_found = _harmonize_date_formats(sample_col)
        if harmonized is not None and n_conv / max(sample_col.notna().sum(), 1) > 0.8:
            if mode == "aggressive":
                # Apply to full column using the same mixed-format parser
                df_clean[col] = pd.to_datetime(df_clean[col], format="mixed", errors="coerce")
                n_conv_full = int(df_clean[col].notna().sum())
            else:
                n_conv_full = n_conv
            fmts = ", ".join(formats_found[:3])
            report.append({
                "step": f"{'Harmonize' if mode == 'aggressive' else '[SUGGESTION] Harmonize'} date formats: {col}",
                "detail": (
                    f"{'Standardized' if mode == 'aggressive' else 'Would standardize'} {n_conv_full} values in '{col}' to ISO dates. "
                    f"Mixed formats detected: {fmts}"
                ),
                "impact": "high" if mode == "aggressive" else "warning",
            })
            continue

        # 4e. Datetime
        try:
            converted_dt = pd.to_datetime(df_clean[col], errors="coerce")
            if non_null_original > 0 and converted_dt.notna().sum() / non_null_original > 0.9:
                if mode == "aggressive":
                    df_clean[col] = converted_dt
                report.append({
                    "step": f"{'Convert' if mode == 'aggressive' else '[SUGGESTION] Convert'} to datetime: {col}",
                    "detail": f"{'Converted' if mode == 'aggressive' else 'Would convert'} '{col}' from text to datetime",
                    "impact": "medium" if mode == "aggressive" else "warning",
                })
                continue
        except Exception:
            pass

    # ── Step 5: Categorical standardization (yes/YES/y/1/True → yes/no) ──────
    for col in list(df_clean.columns):
        if not pd.api.types.is_string_dtype(df_clean[col]):
            continue
        if col in protected_cols:
            continue
        standardized, canonical, n_changed = _standardize_booleans(df_clean[col])
        if standardized is not None and n_changed > 0:
            if mode == "aggressive":
                df_clean[col] = standardized
            report.append({
                "step": f"{'Standardize' if mode == 'aggressive' else '[SUGGESTION] Standardize'} boolean: {col}",
                "detail": (
                    f"{'Unified' if mode == 'aggressive' else 'Would unify'} {n_changed} values in '{col}' to canonical '{canonical}' form. "
                    f"Previously had mixed representations (e.g. Yes/YES/y/1/True)."
                ),
                "impact": "medium" if mode == "aggressive" else "warning",
            })

    # ── Step 6: Handle missing values with missingness mechanism awareness ────
    sample_for_miss = _get_inference_sample(df_clean)
    for col in list(df_clean.columns):
        missing = int(df_clean[col].isnull().sum())
        if missing == 0:
            continue
        missing_pct = missing / max(len(df_clean), 1) * 100

        if missing_pct > 60:
            if mode == "aggressive":
                df_clean.drop(columns=[col], inplace=True)
            report.append({
                "step": f"{'Drop' if mode == 'aggressive' else '[SUGGESTION] Drop'} high-missing column: {col}",
                "detail": f"'{col}' had {missing_pct:.1f}% missing values — too sparse to be useful",
                "impact": "high" if mode == "aggressive" else "warning",
            })
            continue

        if mode == "safe":
            report.append({
                "step": f"[SUGGESTION] Impute missing: {col}",
                "detail": f"'{col}' has {missing} missing values ({missing_pct:.1f}%). Would apply imputation.",
                "impact": "warning",
            })
            continue

        if pd.api.types.is_numeric_dtype(df_clean[col]):
            # Use sample for mechanism classification on large datasets
            sample_col_df = sample_for_miss if col in sample_for_miss.columns else df_clean
            mechanism, max_corr = _classify_missingness(sample_col_df, col)

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

    # ── Step 7: Adaptive outlier treatment (strategy-aware) ──────────────────
    # Use sample for skewness detection on large datasets; apply to full column.
    _sample_for_outliers = _get_inference_sample(df_clean)
    numeric_cols = df_clean.select_dtypes(include=[np.number]).columns.tolist()
    for col in numeric_cols:
        col_data = df_clean[col].dropna()
        if len(col_data) < 20:
            continue

        semantic_type = semantic_map.get(col)
        strategy = choose_outlier_strategy(col, semantic_type)

        if mode == "safe":
            strategy = "flag_only"

        # Use sample for bound calculation on large datasets
        sample_data = _sample_for_outliers[col].dropna() if col in _sample_for_outliers.columns else col_data
        if len(sample_data) < 20:
            sample_data = col_data

        result_series, n_affected, desc = _handle_outliers(sample_data, strategy)
        # Re-apply the same bounds computed from sample to the full column
        if strategy in ("winsorize", "cap") and n_affected > 0:
            lower, upper, method_desc = _detect_outlier_bounds(sample_data)
            outside = int(((col_data < lower) | (col_data > upper)).sum())
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
        elif strategy == "preserve" and n_affected == 0:
            # Check if there actually are outliers to mention
            lower, upper, method_desc = _detect_outlier_bounds(col_data)
            outside = int(((col_data < lower) | (col_data > upper)).sum())
            if outside > 0:
                report.append({
                    "step": f"Preserve outliers: {col}",
                    "detail": (
                        f"'{col}' has {outside} extreme values. Preserved — column may contain "
                        f"legitimately high values (e.g. revenue, price, salary)."
                    ),
                    "impact": "warning",
                })
        elif strategy == "flag_only":
            lower, upper, method_desc = _detect_outlier_bounds(col_data)
            outside = int(((col_data < lower) | (col_data > upper)).sum())
            if outside > 0:
                report.append({
                    "step": f"[SUGGESTION] Winsorize outliers: {col}",
                    "detail": (
                        f"Detected {outside} extreme values in '{col}' using {method_desc} "
                        f"[{lower:.4g}, {upper:.4g}]. Switch to aggressive mode to clip."
                    ),
                    "impact": "warning",
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
    if mode == "aggressive":
        df_clean, total_stripped, cols_stripped = strip_whitespace(df_clean, protected_cols=set())
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
    df_clean, cols_cased = normalize_casing(df_clean, protected_cols=protected_cols, mode=mode)
    for col in cols_cased:
        prefix = "" if mode == "aggressive" else "[SUGGESTION] "
        report.append({
            "step": f"{prefix}Normalize casing: {col}",
            "detail": f"{'Converted' if mode == 'aggressive' else 'Would convert'} '{col}' from ALL-CAPS to Title Case",
            "impact": "low" if mode == "aggressive" else "warning",
        })

    # ── Step 9: Date feature extraction (after all cleaning) ─────────────────
    if mode == "aggressive":
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
        "confidence_score": confidence_score,
        "confidence_grade": score_to_grade(confidence_score),
        "placeholders_replaced": placeholders_replaced,
        "duplicate_cols_removed": duplicate_cols_removed,
        "date_features_created": date_features_created,
        "suspicious_issues_remaining": suspicious_issues,
        "semantic_columns": semantic_map,
        "mode": mode,
    }

    return df_clean, report, summary
