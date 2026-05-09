"""
Analysis Plan–aware finding hygiene (86E).

Applies two targeted penalties to raw insight dicts before ranking:

1. Date-part penalty — down-weights findings whose columns are derived
   date features (month/quarter/year/week/day/weekend) from a column
   listed in analysis_plan.time_columns.  Real date-trend findings
   (e.g. revenue over order_date) are preserved.

2. Ignored-column penalty — down-weights findings where all involved
   columns are in analysis_plan.columns_to_ignore (IDs, artifact cols).

Penalties work by lowering the insight's "confidence" field (which feeds
_composite_score) and setting suppressed_by_plan / plan_penalty_reason
metadata.  No insight is deleted — ranking decides the final order.
"""
from __future__ import annotations

import re

from app.schemas.analysis_plan import AnalysisPlan

# ── Constants ─────────────────────────────────────────────────────────────────

# Confidence multiplier for date-part noise findings (0-100 scale, same as
# raw pipeline output).  Reduces but does not zero; the finding remains
# available if no better findings exist.
_DATE_PART_PENALTY  = 0.35   # ×35% — strong suppression
_IGNORED_COL_PENALTY = 0.40  # ×40% — moderate suppression

# Suffixes that mark a column as a date-derived feature (not a real date col).
_DATE_PART_SUFFIXES = re.compile(
    r"_(month|quarter|year|week|weekday|day|dayofweek|weekend|is_weekend|wday)$",
    re.IGNORECASE,
)

# These column name fragments indicate the column IS a real date column,
# not a derived part.  Findings involving them should not be penalised.
_REAL_DATE_FRAGMENTS = re.compile(
    r"(date|time|timestamp|_at$|_on$)",
    re.IGNORECASE,
)

# Suffixes appended to plan time_columns to form known noisy date-part features.
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

# Free-text insight fields scanned for verbatim known column identifiers.
_INSIGHT_TEXT_COLUMN_FIELDS: tuple[str, ...] = (
    "title",
    "finding",
    "explanation",
    "description",
    "evidence",
    "recommendation",
    "action",
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _norm_col_name(value: str) -> str:
    """Normalize a column-ish token: spaces/hyphens → underscores; lowercased."""
    return re.sub(r"[\s\-]+", "_", value.strip().lower())


def _norm_text_blob_for_column_scan(blob: str) -> str:
    """Normalize prose so (^|_)known_column(_|$) matches token boundaries."""
    s = _norm_col_name(blob)
    s = re.sub(r"[^a-z0-9_]+", "_", s)
    return re.sub(r"_+", "_", s).strip("_")


def _known_columns_from_plan(analysis_plan: AnalysisPlan) -> set[str]:
    """All normalized plan columns plus derived date-part variants for time columns."""
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


def _cols_from_insight(
    ins: dict,
    known_columns: set[str] | None = None,
) -> list[str]:
    """Collect column names referenced by an insight dict (normalized, deduped, stable).

    Structured fields are processed first (col_a, col_b, column, columns).
    When ``known_columns`` is provided, prose fields are scanned for exact
    normalized identifiers present in that set—no fuzzy or invented columns.
    """
    cols: list[str] = []
    seen_norm: set[str] = set()

    def add_name(raw: str) -> None:
        n = _norm_col_name(raw)
        if not n or n in seen_norm:
            return
        seen_norm.add(n)
        cols.append(n)

    for field in ("col_a", "col_b", "column", "columns"):
        val = ins.get(field)
        if isinstance(val, str) and val:
            add_name(val)
        elif isinstance(val, (list, tuple)):
            for c in val:
                if c:
                    add_name(str(c))

    if known_columns:
        chunks: list[str] = []
        for f in _INSIGHT_TEXT_COLUMN_FIELDS:
            v = ins.get(f)
            if v:
                chunks.append(str(v))
        norm_text = _norm_text_blob_for_column_scan(" ".join(chunks))
        if norm_text:
            for known in sorted(known_columns):
                if known in seen_norm:
                    continue
                pattern = rf"(?:^|_){re.escape(known)}(?:_|$)"
                if re.search(pattern, norm_text):
                    seen_norm.add(known)
                    cols.append(known)

    return cols


def _is_date_part_derived(col: str, time_column_bases: set[str]) -> bool:
    """Return True if col looks like a derived date-part feature.

    A column like 'order_date_month' is date-part derived when:
      - Its suffix matches _DATE_PART_SUFFIXES, AND
      - The base name (before the suffix) matches a known time column.

    A column like 'order_date' (real date) or 'monthly_revenue' (happens to
    contain "month" mid-name) is NOT date-part derived.
    """
    m = _DATE_PART_SUFFIXES.search(col)
    if not m:
        return False
    # Extract base: everything before the matched suffix
    base = col[: m.start()].rstrip("_").lower()
    return base in time_column_bases


def _penalise(ins: dict, factor: float, reason: str) -> dict:
    """Return a shallow copy of ins with confidence multiplied by factor."""
    new_conf = float(ins.get("confidence", 50.0)) * factor
    return {
        **ins,
        "confidence": new_conf,
        "suppressed_by_plan": True,
        "plan_penalty_reason": reason,
    }


# ── Public API ────────────────────────────────────────────────────────────────

def apply_analysis_plan_hygiene(
    insights: list[dict],
    analysis_plan: AnalysisPlan | None,
) -> list[dict]:
    """Apply plan-aware hygiene penalties to raw insight dicts.

    Safe to call with analysis_plan=None — returns insights unchanged.
    Does not mutate input list or dicts.
    """
    if not analysis_plan:
        return insights

    known_columns = _known_columns_from_plan(analysis_plan)
    ignore_set = {_norm_col_name(c) for c in analysis_plan.columns_to_ignore}
    time_bases = {_norm_col_name(c) for c in analysis_plan.time_columns}

    out: list[dict] = []
    for ins in insights:
        cols = _cols_from_insight(ins, known_columns)

        # ── Ignored-column penalty ────────────────────────────────────────────
        # Only penalise if ALL columns involved are ignored cols.
        # (A finding mixing an ID with a real metric should survive.)
        if cols and all(c in ignore_set for c in cols):
            out.append(_penalise(ins, _IGNORED_COL_PENALTY, "ignored_column"))
            continue

        # ── Date-part derived column penalty ─────────────────────────────────
        # Penalise if ANY column is a date-derived feature from a time column.
        # Exception: if the insight type is "trend" and involves a real date
        # column, it is a genuine time-series finding — do not penalise.
        date_part_cols = [c for c in cols if _is_date_part_derived(c, time_bases)]
        if date_part_cols:
            # Preserve genuine trend findings on real date columns
            real_date_cols = [c for c in cols if _REAL_DATE_FRAGMENTS.search(c) and c not in date_part_cols]
            if ins.get("type") == "trend" and real_date_cols:
                out.append(ins)
                continue
            out.append(_penalise(ins, _DATE_PART_PENALTY, "date_part_feature"))
            continue

        out.append(ins)

    return out
