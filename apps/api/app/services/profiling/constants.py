"""
Regex constants for the profiling package.

All patterns used by _detect_pattern are kept here so they can be imported
consistently by patterns.py and any future sub-module.
"""
import re

# ── Value-level regex patterns ────────────────────────────────────────────────
_EMAIL_RE    = re.compile(r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$")
_PHONE_RE    = re.compile(r"^[\+]?[(]?[0-9]{3}[)]?[\-\s\.]?[0-9]{3}[\-\s\.]?[0-9]{4,6}$")
_URL_RE      = re.compile(r"^(https?://|www\.)\S+")
_ZIP_US_RE   = re.compile(r"^\d{5}(-\d{4})?$")
_IP_RE       = re.compile(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$")
_CURRENCY_RE = re.compile(r"^[€$£¥₹]?\s*-?[\d,]+\.?\d*\s*[€$£¥₹]?$")
_PERCENT_RE  = re.compile(r"^-?\d+\.?\d*\s*%$")

# Ordered list: first matching pattern wins
_PATTERN_CHECKS = [
    ("email",      _EMAIL_RE),
    ("phone",      _PHONE_RE),
    ("url",        _URL_RE),
    ("zip_code",   _ZIP_US_RE),
    ("ip_address", _IP_RE),
    ("currency",   _CURRENCY_RE),
    ("percentage", _PERCENT_RE),
]

# ── Large dataset thresholds ──────────────────────────────────────────────────
LARGE_THRESHOLD   = 100_000   # rows above which sampling is used for inference
LARGE_SAMPLE_SIZE = 20_000    # sample size for per-column inference on large data
