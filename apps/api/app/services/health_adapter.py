"""
Adapter: raw calculate_health_score() + profile_dataset() output → canonical HealthResult.

This is the single mapping layer between the health/profiling pipeline outputs
and the V1 schema contract. All downstream consumers should use HealthResult.

Inputs:
    df      — the post-cleaning DataFrame (needed for missingness cell counts)
    health  — dict returned by calculate_health_score(df)
    profile — list[dict] returned by profile_dataset(df)
"""
from __future__ import annotations

import pandas as pd

from app.schemas.health import (
    ColumnHealthEntry,
    ColumnMissingness,
    DuplicateStats,
    HealthResult,
    HealthScore,
    HealthWarning,
    MissingnessStats,
    SemanticColumnType,
)

# ── Deduction string → (dimension, severity) lookup ──────────────────────────
# Ordered from most specific to least so the first match wins.
_DEDUCTION_RULES: list[tuple[str, str, str]] = [
    # (prefix, dimension, severity)
    ("Missing data:",         "completeness", "high"),
    ("Duplicate rows:",       "uniqueness",   "medium"),
    ("Whitespace issues in",  "consistency",  "low"),
    ("Mixed types in",        "consistency",  "medium"),
    ("IQR outliers in",       "validity",     "medium"),
    ("Highly skewed in",      "validity",     "low"),
    ("Constant columns:",     "structure",    "high"),
    ("Very highly skewed:",   "structure",    "low"),
]

# Semantic types that mark a column as an identifier / key column
_PROTECTED_TYPES: frozenset[str] = frozenset({
    "id", "phone", "postal", "sku", "account_number", "email", "ip_address",
})


# ── Public API ────────────────────────────────────────────────────────────────

def build_health_result(
    df: pd.DataFrame,
    health: dict,
    profile: list[dict],
) -> HealthResult:
    """
    Convert raw health/profile pipeline output into a canonical HealthResult.

    Args:
        df:      Post-cleaning DataFrame (used for missingness cell stats).
        health:  Dict from calculate_health_score(df).
        profile: List[dict] from profile_dataset(df); each item has a
                 'semantic_type' field used to build semantic_column_types.

    Returns:
        Fully-populated HealthResult ready for serialisation.
    """
    row_count    = len(df)
    column_count = len(df.columns)

    semantic_types = _build_semantic_types(profile)
    key_cols       = [s.column for s in semantic_types if s.semantic_type in _PROTECTED_TYPES]

    return HealthResult(
        row_count=row_count,
        column_count=column_count,
        missingness_stats=_build_missingness_stats(df, health),
        duplicate_stats=_build_duplicate_stats(health, row_count),
        semantic_column_types=semantic_types,
        key_columns=key_cols,
        health_score=_build_health_score(health),
        health_warnings=_build_warnings(health),
        column_health=_build_column_health(health),
    )


# ── Sub-builders ──────────────────────────────────────────────────────────────

def _build_health_score(health: dict) -> HealthScore:
    return HealthScore(
        total_score=float(health["total"]),          # "total" → "total_score" rename
        grade=health["grade"],
        label=health["label"],
        breakdown=dict(health["breakdown"]),
        dataset_type=health["dataset_type"],
        dataset_type_confidence=float(health.get("dataset_type_confidence", 1.0)),
    )


def _build_missingness_stats(df: pd.DataFrame, health: dict) -> MissingnessStats:
    total_cells    = len(df) * len(df.columns)
    missing_cells  = int(df.isnull().sum().sum())
    missing_pct    = round(missing_cells / max(total_cells, 1) * 100, 2)
    bi             = health.get("business_impact", {})

    per_column: list[ColumnMissingness] = []
    for col, count in df.isnull().sum().items():
        if count > 0:
            per_column.append(ColumnMissingness(
                column=str(col),
                missing_count=int(count),
                missing_pct=round(int(count) / max(len(df), 1) * 100, 2),
            ))

    return MissingnessStats(
        total_missing_cells=missing_cells,
        missing_cell_pct=missing_pct,
        rows_with_any_missing=int(bi.get("unreliable_rows", 0)),
        rows_with_any_missing_pct=float(bi.get("unreliable_pct", 0.0)),
        columns_with_missing=per_column,
    )


def _build_duplicate_stats(health: dict, row_count: int) -> DuplicateStats:
    bi         = health.get("business_impact", {})
    dupe_count = int(bi.get("duplicate_rows", 0))
    dupe_pct   = round(dupe_count / max(row_count, 1) * 100, 2)
    return DuplicateStats(
        duplicate_row_count=dupe_count,
        duplicate_row_pct=dupe_pct,
    )


def _build_semantic_types(profile: list[dict]) -> list[SemanticColumnType]:
    result: list[SemanticColumnType] = []
    for col_profile in profile:
        sem = col_profile.get("semantic_type")
        if sem:
            result.append(SemanticColumnType(
                column=str(col_profile["column"]),
                semantic_type=str(sem),
            ))
    return result


def _build_warnings(health: dict) -> list[HealthWarning]:
    """Parse deduction strings into structured HealthWarning records."""
    warnings: list[HealthWarning] = []
    for deduction in health.get("deductions", []):
        dimension, severity = _classify_deduction(deduction)
        warnings.append(HealthWarning(
            dimension=dimension,
            message=deduction,
            severity=severity,      # type: ignore[arg-type]
        ))
    return warnings


def _classify_deduction(text: str) -> tuple[str, str]:
    """Return (dimension, severity) for a deduction string using prefix matching."""
    for prefix, dimension, severity in _DEDUCTION_RULES:
        if text.startswith(prefix):
            return dimension, severity
    # Fallback: unknown issue → structure / low
    return "structure", "low"


def _build_column_health(health: dict) -> list[ColumnHealthEntry]:
    """Convert column_health dict (keyed by name) to a sorted list."""
    raw: dict[str, dict] = health.get("column_health", {})
    entries: list[ColumnHealthEntry] = []
    for col, data in raw.items():
        entries.append(ColumnHealthEntry(
            column=str(col),
            score=float(data.get("score", 0.0)),
            issues=list(data.get("issues", [])),
        ))
    # Sort by score ascending so worst columns appear first
    entries.sort(key=lambda e: e.score)
    return entries
