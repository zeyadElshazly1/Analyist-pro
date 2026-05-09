"""
Shared plan-aware column name normalization and text scanning (88A / 88B).

Used by analysis_plan_hygiene and insight_adapter so penalties and canonical
columns_used agree on what counts as a known column reference.
"""
from __future__ import annotations

import re

from app.schemas.analysis_plan import AnalysisPlan

# ── Insight dict fields scanned for verbatim known identifiers ───────────────

_INSIGHT_TEXT_COLUMN_FIELDS: tuple[str, ...] = (
    "title",
    "finding",
    "explanation",
    "description",
    "evidence",
    "recommendation",
    "action",
)

# Suffixes for derived date-part features built from ``AnalysisPlan.time_columns``.
_DATE_PART_VARIANT_SUFFIXES: tuple[str, ...] = (
    "month",
    "quarter",
    "year",
    "week",
    "weekday",
    "day",
    "dayofweek",
    "weekend",
    "is_weekend",
    "wday",
)


def _norm_col_name(value: str) -> str:
    """Normalize a column-ish token: spaces/hyphens → underscores; lowercased."""
    return re.sub(r"[\s\-]+", "_", value.strip().lower())


def _norm_text_blob_for_column_scan(blob: str) -> str:
    """Normalize prose so (^|_)known_column(_|$) matches token boundaries."""
    s = _norm_col_name(blob)
    s = re.sub(r"[^a-z0-9_]+", "_", s)
    return re.sub(r"_+", "_", s).strip("_")


def _known_columns_from_plan(analysis_plan: AnalysisPlan) -> set[str]:
    """Normalized plan columns plus derived date-part variants for time columns."""
    out: set[str] = set()
    for key in (
        "target_metrics",
        "important_dimensions",
        "time_columns",
        "columns_to_ignore",
    ):
        for x in getattr(analysis_plan, key, None) or []:
            if x:
                out.add(_norm_col_name(str(x)))
    bases = {_norm_col_name(str(tc)) for tc in (analysis_plan.time_columns or []) if tc}
    bases.discard("")
    for base in bases:
        for suf in _DATE_PART_VARIANT_SUFFIXES:
            out.add(f"{base}_{suf}")
    return out


def _extract_known_columns_from_text_fields(
    ins: dict,
    known_columns: set[str],
    exclude_normalized: set[str] | None = None,
) -> list[str]:
    """Return normalized known column names appearing in insight text fields.

    Matches are exact boundary-safe substrings against the normalized text blob only;
    identifiers must appear in ``known_columns``.
    """
    excluded = exclude_normalized or set()
    seen: set[str] = set(excluded)
    cols: list[str] = []
    chunks: list[str] = []
    for f in _INSIGHT_TEXT_COLUMN_FIELDS:
        v = ins.get(f)
        if v:
            chunks.append(str(v))
    norm_text = _norm_text_blob_for_column_scan(" ".join(chunks))
    if not norm_text:
        return []
    for known in sorted(known_columns):
        if known in seen:
            continue
        pattern = rf"(?:^|_){re.escape(known)}(?:_|$)"
        if re.search(pattern, norm_text):
            seen.add(known)
            cols.append(known)
    return cols
