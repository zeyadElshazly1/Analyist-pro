"""
Pattern detection for string columns.

_detect_pattern: classify a series as email / phone / URL / zip / IP /
    currency / percentage with compliance percentage and strength label.

_check_format_consistency: detect mixed date formats or inconsistent value
    lengths within a string column.
"""
import pandas as pd

from .constants import _PATTERN_CHECKS


def _detect_pattern(series: pd.Series) -> dict | None:
    """Detect if a string column matches a known pattern (email, phone, URL, etc.).

    Returns a result with ``pattern_strength`` of "strong" (≥85% compliance)
    or "weak" (50–84%) so consumers can differentiate reliable detections from
    ambiguous ones.  Returns None if compliance < 50%.
    """
    sample = series.dropna().astype(str).head(300)
    if len(sample) == 0:
        return None
    for pattern_name, pattern_re in _PATTERN_CHECKS:
        matches = sample.str.match(pattern_re).sum()
        compliance = round(float(matches) / len(sample) * 100, 1)
        if compliance >= 50:
            pattern_strength = "strong" if compliance >= 85 else "weak"
            return {
                "pattern": pattern_name,
                "pattern_strength": pattern_strength,
                "compliance_pct": compliance,
                "malformed_count": len(sample) - int(matches),
                "note": (
                    f"{compliance:.0f}% of values match {pattern_name} format"
                    + (
                        f" ({100 - compliance:.0f}% are malformed)"
                        if compliance < 100
                        else ""
                    )
                ),
            }
    return None


def _check_format_consistency(series: pd.Series) -> dict | None:
    """Detect mixed value formats within a string column."""
    sample = series.dropna().astype(str).head(200)
    if len(sample) < 10:
        return None

    # Detect multiple date-like format clusters
    _QUICK_DATE_FORMATS = [
        ("%Y-%m-%d", r"^\d{4}-\d{2}-\d{2}$"),
        ("%d/%m/%Y", r"^\d{2}/\d{2}/\d{4}$"),
        ("%m/%d/%Y", r"^\d{2}/\d{2}/\d{4}$"),
        ("%d.%m.%Y", r"^\d{2}\.\d{2}\.\d{4}$"),
        ("%Y%m%d",   r"^\d{8}$"),
    ]
    date_formats_found = []
    for fmt, pat in _QUICK_DATE_FORMATS:
        count = int(sample.str.match(pat).sum())
        if count > 0:
            date_formats_found.append((fmt, count))

    if len(date_formats_found) >= 2:
        format_desc = ", ".join(f"{fmt} ({n} values)" for fmt, n in date_formats_found)
        return {
            "issue": "mixed_date_formats",
            "formats_found": [f for f, _ in date_formats_found],
            "detail": (
                f"Mixed date formats detected: {format_desc}. "
                f"Standardize to ISO 8601 (YYYY-MM-DD)."
            ),
        }

    # Detect mixed length / structure patterns (e.g. phone formats)
    lengths = sample.str.len().value_counts()
    if len(lengths) >= 3 and lengths.iloc[0] / len(sample) < 0.7:
        top_lengths = lengths.head(3).to_dict()
        return {
            "issue": "inconsistent_length",
            "detail": (
                f"Values have inconsistent lengths: {top_lengths}. "
                f"May indicate mixed formatting."
            ),
        }

    return None
