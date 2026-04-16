"""
Semantic column detection.

Identifies columns that should be protected from auto-mutation:
IDs, phone numbers, postal codes, SKUs, emails, account numbers, revenue columns.
"""
import re

import pandas as pd

# ── Name-pattern keyword sets ─────────────────────────────────────────────────
_ID_KEYWORDS = {"id", "uuid", "guid", "key", "pk", "_id", "ref", "identifier"}
_PHONE_KEYWORDS = {"phone", "mobile", "tel", "fax", "cell", "contact"}
_POSTAL_KEYWORDS = {"zip", "postal", "postcode", "zipcode", "post_code"}
_SKU_KEYWORDS = {"sku", "upc", "barcode", "item_no", "product_code", "part_no", "item_code"}
_ACCOUNT_KEYWORDS = {"account", "acct", "member", "customer_id", "user_id", "employee_id"}
_EMAIL_KEYWORDS = {"email", "e_mail", "mail"}
_REVENUE_KEYWORDS = {
    "revenue", "price", "amount", "value", "cost", "salary",
    "income", "sales", "profit", "spend", "fee", "charge", "wage",
}

# ── Value-level regex patterns ────────────────────────────────────────────────
_EMAIL_RE = re.compile(r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$")
# Phone regex: requires digit-dense sequences but NOT ISO-date-like (NNNN-NN-NN).
# Must contain at least 7 digit characters, not purely a YYYY-MM-DD pattern.
_PHONE_RE = re.compile(
    r"^(?!(?:19|20)\d{2}-\d{2}-\d{2}$)"   # exclude ISO dates like 2023-01-15
    r"\+?[\d\s\-().]{7,20}$"
)
_ZIP_RE = re.compile(r"^\d{5}(-\d{4})?$|^[A-Z]\d[A-Z]\s?\d[A-Z]\d$", re.IGNORECASE)
_IP_RE = re.compile(
    r"^(?:(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\.){3}(?:25[0-5]|2[0-4]\d|[01]?\d\d?)$"
)

# Semantic types that block type coercion, title-casing, and winsorization
PROTECTED_TYPES = {"id", "phone", "postal", "sku", "account_number", "email", "ip_address"}


def _has_keyword(col_lower: str, keywords: set[str]) -> bool:
    """Return True if any keyword appears as a word-boundary match in col_lower."""
    for kw in keywords:
        if kw in col_lower:
            return True
    return False


def _value_match_rate(series: pd.Series, pattern: re.Pattern, n: int = 200) -> float:
    """Return fraction of non-null string values matching pattern in first n rows."""
    sample = series.dropna().astype(str).head(n)
    if len(sample) == 0:
        return 0.0
    return sample.str.match(pattern).mean()


def _is_id_column(col_lower: str, series: pd.Series) -> bool:
    """True if column name contains an ID keyword AND values have high uniqueness."""
    if not _has_keyword(col_lower, _ID_KEYWORDS):
        return False
    non_null = series.dropna()
    if len(non_null) < 5:
        return False
    unique_ratio = series.nunique() / max(len(series), 1)
    return unique_ratio > 0.85


def detect_semantic_columns(df: pd.DataFrame) -> dict[str, str]:
    """
    Analyse each column's name and value sample to assign a semantic type.

    Returns a dict mapping column_name → semantic_type for columns that
    should receive special treatment during cleaning. Columns not in the
    returned dict are treated as ordinary data.

    Semantic types:
        "id"             — Identifiers (never coerce, never title-case, never winsorize)
        "phone"          — Phone numbers (never coerce or title-case)
        "postal"         — Postal / ZIP codes (never coerce leading zeros away)
        "sku"            — Product codes / SKUs (never coerce or title-case)
        "account_number" — Account / member IDs (never coerce or winsorize)
        "email"          — Email addresses (never coerce or title-case)
        "ip_address"     — IP addresses (never coerce)
        "revenue"        — Financial value columns (still convert currency strings,
                           but never winsorize — preserve extreme values)
    """
    result: dict[str, str] = {}

    for col in df.columns:
        col_lower = col.lower()
        series = df[col]

        # ── 1. Fast name-pattern check (O(1)) ────────────────────────────────
        if _has_keyword(col_lower, _EMAIL_KEYWORDS):
            result[col] = "email"
            continue
        if _has_keyword(col_lower, _PHONE_KEYWORDS):
            result[col] = "phone"
            continue
        if _has_keyword(col_lower, _POSTAL_KEYWORDS):
            result[col] = "postal"
            continue
        if _has_keyword(col_lower, _SKU_KEYWORDS):
            result[col] = "sku"
            continue
        if _has_keyword(col_lower, _ACCOUNT_KEYWORDS):
            result[col] = "account_number"
            continue
        if _is_id_column(col_lower, series):
            result[col] = "id"
            continue
        if _has_keyword(col_lower, _REVENUE_KEYWORDS):
            result[col] = "revenue"
            continue

        # ── 2. Value-sample check for string columns (O(200)) ─────────────
        if pd.api.types.is_string_dtype(series) or series.dtype == object:
            sample_str = series.dropna().head(200).astype(str)

            # Guard: skip value-based semantic detection for datetime-like columns.
            # Date strings (e.g. "2023-01-15") can superficially match phone/postal
            # regexes, so if the column looks like dates we leave it for type inference.
            try:
                dt_parsed = pd.to_datetime(sample_str, format="mixed", errors="coerce")
                if len(dt_parsed) > 0 and dt_parsed.notna().mean() >= 0.80:
                    continue  # Datetime column — no semantic type assigned here
            except Exception:
                pass

            if _value_match_rate(series, _EMAIL_RE) >= 0.70:
                result[col] = "email"
                continue
            if _value_match_rate(series, _PHONE_RE) >= 0.70:
                result[col] = "phone"
                continue
            if _value_match_rate(series, _ZIP_RE) >= 0.70:
                result[col] = "postal"
                continue
            if _value_match_rate(series, _IP_RE) >= 0.80:
                result[col] = "ip_address"
                continue

    return result
