"""
Shared constants for the cleaning pipeline.
Regex patterns, lookup sets, and date format lists.
"""
import re

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

# ── Column name patterns for high-value / preserve-outlier columns ────────────
_PRESERVE_OUTLIER_RE = re.compile(
    r"(revenue|price|amount|value|cost|salary|income|sales|profit|spend|fee|charge)",
    re.IGNORECASE,
)

# ── Large dataset threshold for sampling-based inference ─────────────────────
LARGE_DATASET_THRESHOLD = 100_000
LARGE_DATASET_SAMPLE_SIZE = 10_000
