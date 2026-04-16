"""
Type inference and conversion helpers.

Handles: currency, percentage, boolean, and date format parsing/harmonization.
"""
import pandas as pd

from .constants import _BOOL_TRUE, _BOOL_FALSE, _CURRENCY_RE, _PERCENT_RE, _DATE_FORMATS


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
    """Detect mixed date format strings and standardize to ISO.

    Fixes deprecated infer_datetime_format=True (removed in pandas 3.0).
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
    result = pd.to_datetime(series, format="mixed", errors="coerce")
    n_converted = int(result.notna().sum())
    return result, n_converted, detected_formats
