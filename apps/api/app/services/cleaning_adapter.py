"""
Adapter: raw clean_dataset() output → canonical CleaningResult.

This is the single mapping layer between the cleaning pipeline's tuple output
and the V1 schema contract. All downstream consumers should use CleaningResult,
not the raw (report, summary) pair.
"""
from __future__ import annotations

import re

from app.schemas.cleaning import (
    CleaningResult,
    CleaningSummary,
    ColumnRename,
    DuplicateNote,
    MissingnessNote,
    SuspiciousColumn,
    TypeFix,
)

# ── Step pattern tables ───────────────────────────────────────────────────────

# (lowercased step fragment after stripping "[SUGGESTION] ", to_dtype)
_TYPE_FIX_PATTERNS: list[tuple[str, str]] = [
    ("parse currency:",       "currency"),
    ("parse percentage:",     "percentage"),
    ("convert to numeric:",   "numeric"),
    ("harmonize date formats:", "datetime"),
    ("convert to datetime:",  "datetime"),
    ("standardize boolean:",  "boolean"),
]

# Matches: "Impute missing (MNAR): col" / "[SUGGESTION] Impute missing: col" /
#          "Drop high-missing column: col"
_IMPUTE_RE = re.compile(
    r"^(?:\[SUGGESTION\] )?"
    r"(?:Impute missing|Drop high-missing column)"
    r"(?:\s*\(([^)]+)\))?:\s*(.+)$",
    re.IGNORECASE,
)

_MECHANISM_MAP: dict[str, str] = {
    "mnar":         "MNAR",
    "mar":          "MAR",
    "mar fallback": "MAR",
    "mcar":         "MCAR",
}

# Extracts the leading count from detail strings like "Dropped 42 exact duplicate rows"
_DUPE_ROW_RE = re.compile(r"(?:Dropped|Found)\s+(\d+)\s+exact duplicate rows", re.IGNORECASE)

# Extracts leading count from type-fix details like "Converted 318 currency strings"
_N_VALUES_RE = re.compile(r"(?:Converted|Found|Would convert|Standardized|Would standardize)\s+(\d+)", re.IGNORECASE)

# Extracts missing count from imputation details like "Filled 23 missing values"
_MISSING_COUNT_RE = re.compile(r"(?:fill|filled|impute[sd]?)\s+(\d+)\s+missing values?", re.IGNORECASE)
_MISSING_PCT_RE   = re.compile(r"\((\d+(?:\.\d+)?)%\)")


# ── Public API ────────────────────────────────────────────────────────────────

def build_cleaning_result(
    original_cols: list[str],
    clean_cols: list[str],
    report: list[dict],
    summary: dict,
) -> CleaningResult:
    """
    Convert raw clean_dataset() output into a canonical CleaningResult.

    Args:
        original_cols: df.columns.tolist() BEFORE cleaning (from the input df).
        clean_cols:    df_clean.columns.tolist() AFTER cleaning.
        report:        list[{"step", "detail", "impact"}] from clean_dataset().
        summary:       summary dict from clean_dataset().

    Returns:
        Fully-populated CleaningResult ready for serialisation.
    """
    return CleaningResult(
        renamed_columns=_extract_renamed(original_cols, clean_cols),
        dropped_columns=_extract_dropped(report),
        type_fixes=_extract_type_fixes(report),
        missingness_notes=_extract_missingness(report),
        duplicate_notes=_extract_duplicate_notes(report, summary),
        suspicious_columns=_extract_suspicious(summary),
        assumptions_made=[],   # not emitted by pipeline in V1
        cleaning_summary=CleaningSummary(
            original_rows=summary["original_rows"],
            original_cols=summary["original_cols"],
            final_rows=summary["final_rows"],
            final_cols=summary["final_cols"],
            rows_removed=summary["rows_removed"],
            cols_removed=summary["cols_removed"],
            steps_applied=summary.get("steps", 0),
            confidence_score=float(summary.get("confidence_score", 0.0)),
            confidence_grade=str(summary.get("confidence_grade", "F")),
            time_saved_estimate=str(summary.get("time_saved_estimate", "~1 minutes")),
            mode=summary.get("mode", "aggressive"),   # type: ignore[arg-type]
        ),
    )


# ── Extraction helpers ────────────────────────────────────────────────────────

def _strip_suggestion(step: str) -> str:
    """Remove the '[SUGGESTION] ' prefix if present (exact substring, not lstrip)."""
    prefix = "[SUGGESTION] "
    return step[len(prefix):] if step.startswith(prefix) else step


def _extract_renamed(original_cols: list[str], clean_cols: list[str]) -> list[ColumnRename]:
    """Zip pre/post column lists and emit a ColumnRename for each pair that changed."""
    return [
        ColumnRename(original=orig, cleaned=clean)
        for orig, clean in zip(original_cols, clean_cols)
        if orig != clean
    ]


def _extract_dropped(report: list[dict]) -> list[str]:
    """Extract column names from high-missing drop step strings."""
    dropped: list[str] = []
    for item in report:
        step = _strip_suggestion(item.get("step", ""))
        if step.lower().startswith("drop high-missing column:"):
            col = step.split(":", 1)[-1].strip()
            if col:
                dropped.append(col)
    return dropped


def _extract_type_fixes(report: list[dict]) -> list[TypeFix]:
    """Parse type-conversion steps into TypeFix records."""
    fixes: list[TypeFix] = []
    for item in report:
        raw_step = item.get("step", "")
        normalized = _strip_suggestion(raw_step).lower()
        for fragment, to_dtype in _TYPE_FIX_PATTERNS:
            if normalized.startswith(fragment):
                col = raw_step.split(":", 1)[-1].strip()
                detail = item.get("detail", "")
                m = _N_VALUES_RE.search(detail)
                fixes.append(TypeFix(
                    column=col,
                    to_dtype=to_dtype,
                    n_values_converted=int(m.group(1)) if m else 0,
                ))
                break
    return fixes


def _extract_missingness(report: list[dict]) -> list[MissingnessNote]:
    """Parse imputation and drop-high-missing steps into MissingnessNote records."""
    notes: list[MissingnessNote] = []
    for item in report:
        step = item.get("step", "")
        detail = item.get("detail", "")
        m = _IMPUTE_RE.match(step)
        if not m:
            continue

        raw_mech = (m.group(1) or "").strip().lower()
        col = m.group(2).strip()

        is_drop = _strip_suggestion(step).lower().startswith("drop high-missing column")
        is_safe = step.startswith("[SUGGESTION]")

        mechanism = _MECHANISM_MAP.get(raw_mech, "unknown")

        if is_drop:
            strategy = "dropped"
        elif is_safe:
            strategy = "safe_suggestion"
        elif raw_mech == "mnar":
            strategy = "flag_and_fill"
        elif raw_mech in ("mar", "mar fallback"):
            # Pipeline uses MICE or KNN but doesn't distinguish in step string
            strategy = "knn"
        elif "most common value" in detail:
            strategy = "mode"
        else:
            strategy = "mean"

        count_m = _MISSING_COUNT_RE.search(detail)
        pct_m = _MISSING_PCT_RE.search(detail)
        notes.append(MissingnessNote(
            column=col,
            missing_count=int(count_m.group(1)) if count_m else 0,
            missing_pct=round(float(pct_m.group(1)), 2) if pct_m else 0.0,
            mechanism=mechanism,        # type: ignore[arg-type]
            strategy_applied=strategy,  # type: ignore[arg-type]
        ))
    return notes


def _extract_duplicate_notes(report: list[dict], summary: dict) -> DuplicateNote:
    """Build DuplicateNote from the 'Remove duplicate rows' step and summary."""
    rows_found = 0
    rows_removed = 0
    for item in report:
        step = item.get("step", "")
        if _strip_suggestion(step).lower() == "remove duplicate rows":
            m = _DUPE_ROW_RE.search(item.get("detail", ""))
            if m:
                rows_found = int(m.group(1))
            if not step.startswith("[SUGGESTION]"):
                rows_removed = rows_found
            break

    return DuplicateNote(
        duplicate_rows_found=rows_found,
        duplicate_rows_removed=rows_removed,
        duplicate_columns=list(summary.get("duplicate_col_names", [])),
    )


def _extract_suspicious(summary: dict) -> list[SuspiciousColumn]:
    """Convert suspicious_issues_remaining entries to SuspiciousColumn records."""
    result: list[SuspiciousColumn] = []
    for issue in summary.get("suspicious_issues_remaining", []):
        col = issue.get("column", "")
        if col:
            result.append(SuspiciousColumn(
                column=col,
                issue_type=issue.get("type", "unknown"),
                detail=issue.get("detail", ""),
            ))
    return result
