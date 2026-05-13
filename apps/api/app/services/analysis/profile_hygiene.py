"""
90J — Profile-aware hygiene helper (disabled by default).

Applies conservative confidence penalties derived from V2 pre_analysis_profile
risks (date-part artifacts, high-cardinality dims, leakage, constant columns).

IMPORTANT: enabled=False by default.
No pipeline path calls this yet.  It is wired in only after the 90I regression
baseline is explicitly updated to reflect the new expected ordering.
"""
from __future__ import annotations

import re
from typing import Any

from app.services.analysis.confidence import safe_confidence_from_insight

# ── Column-name normalization (local, mirrors column_matching.py) ────────────

def _norm(name: str) -> str:
    """Lowercase + spaces/hyphens → underscores."""
    return re.sub(r"[\s\-]+", "_", name.strip().lower())


def _norm_blob(blob: str) -> str:
    """Normalize a prose blob so boundary-safe scanning works."""
    s = _norm(blob)
    s = re.sub(r"[^a-z0-9_]+", "_", s)
    return re.sub(r"_+", "_", s).strip("_")


# ── Insight text fields to scan (same list as column_matching.py) ────────────

_TEXT_FIELDS = (
    "title", "finding", "explanation", "description",
    "evidence", "recommendation", "action",
)

# Categories that represent segment/distribution comparisons.
_SEGMENT_CATEGORIES = frozenset({
    "segment", "segment_comparison", "comparison", "distribution",
})


# ── Column extraction ─────────────────────────────────────────────────────────

def _cols_from_structured(ins: dict) -> set[str]:
    """Return normalized column names from structured insight fields."""
    found: set[str] = set()
    for field in ("col_a", "col_b", "column"):
        v = ins.get(field)
        if v and isinstance(v, str):
            found.add(_norm(v))
    cols_list = ins.get("columns")
    if cols_list and isinstance(cols_list, list):
        for c in cols_list:
            if c and isinstance(c, str):
                found.add(_norm(c))
    return found


def _cols_from_text(ins: dict, known_columns: set[str]) -> set[str]:
    """Return normalized known column names that appear in insight text fields."""
    chunks = []
    for f in _TEXT_FIELDS:
        v = ins.get(f)
        if v:
            chunks.append(str(v))
    if not chunks:
        return set()
    blob = _norm_blob(" ".join(chunks))
    found: set[str] = set()
    for col in known_columns:
        pattern = rf"(?:^|_){re.escape(col)}(?:_|$)"
        if re.search(pattern, blob):
            found.add(col)
    return found


def _insight_columns(ins: dict, known_columns: set[str]) -> set[str]:
    """All normalized column names referenced by an insight."""
    return _cols_from_structured(ins) | _cols_from_text(ins, known_columns)


# ── Penalty helper ────────────────────────────────────────────────────────────

def _penalise(ins: dict, factor: float, reason: str) -> dict:
    """Return a shallow copy of *ins* with confidence scaled by *factor*."""
    new_conf = safe_confidence_from_insight(ins) * factor
    return {
        **ins,
        "confidence": new_conf,
        "suppressed_by_profile": True,
        "profile_penalty_reason": reason,
    }


# ── Risk index builder ────────────────────────────────────────────────────────

def _index_risks(
    profile: dict,
) -> tuple[set[str], dict[str, set[str]]]:
    """Return (set_of_risk_names, mapping_of_risk_name → affected_cols).

    Affected columns are normalized.
    """
    risk_names: set[str] = set()
    affected: dict[str, set[str]] = {}
    for risk in profile.get("risks") or []:
        name = risk.get("risk_name", "")
        if not name:
            continue
        risk_names.add(name)
        affected[name] = {
            _norm(c) for c in (risk.get("affected_columns") or []) if c
        }
    return risk_names, affected


# ── Public entry point ────────────────────────────────────────────────────────

def apply_pre_analysis_profile_hygiene(
    insights: list[dict],
    pre_analysis_profile: dict | None,
    *,
    enabled: bool = False,
) -> list[dict]:
    """Apply V2 profile-aware confidence penalties to *insights*.

    Parameters
    ----------
    insights:
        List of insight dicts from the analysis pipeline.
    pre_analysis_profile:
        Serialised :class:`PreAnalysisProfile` dict (or None for legacy runs).
    enabled:
        Master gate — defaults to False.  When False the function is a no-op
        and insights are returned unchanged (same object, not a copy).

    Returns
    -------
    list[dict]
        New list (or the original list when no-op).  Individual dicts are
        shallow-copied only when penalised; unpenalised dicts are the same
        objects as in the input.
    """
    if not enabled:
        return insights
    if not pre_analysis_profile or not isinstance(pre_analysis_profile, dict):
        return insights
    if not insights:
        return insights

    # Build known-column set from column_roles (used for text scanning).
    known_columns: set[str] = {
        _norm(r["column_name"])
        for r in (pre_analysis_profile.get("column_roles") or [])
        if r.get("column_name")
    }

    risk_names, affected = _index_risks(pre_analysis_profile)

    result: list[dict] = []
    for ins in insights:
        penalised = ins
        ins_cols = _insight_columns(ins, known_columns)
        ins_category = (ins.get("category") or "").lower()

        # ── Rule 1: date_part_artifacts ───────────────────────────────────────
        if "date_part_artifacts" in risk_names:
            artifact_cols = affected.get("date_part_artifacts", set())
            if ins_cols & artifact_cols:
                penalised = _penalise(penalised, 0.35, "profile_date_part_artifact")

        # ── Rule 2: high_cardinality_dimensions (segment insights only) ───────
        if "high_cardinality_dimensions" in risk_names and ins_category in _SEGMENT_CATEGORIES:
            hcd_cols = affected.get("high_cardinality_dimensions", set())
            if ins_cols & hcd_cols:
                penalised = _penalise(penalised, 0.50, "profile_high_cardinality_dimension")

        # ── Rule 3: leakage candidates ────────────────────────────────────────
        leakage_risk_names = {"possible_leakage", "target_leakage_risk"}
        active_leakage = risk_names & leakage_risk_names
        if active_leakage:
            leakage_cols: set[str] = set()
            for lrn in active_leakage:
                leakage_cols |= affected.get(lrn, set())
            if ins_cols & leakage_cols:
                penalised = _penalise(penalised, 0.25, "profile_leakage_candidate")

        # ── Rule 4: constant_columns ──────────────────────────────────────────
        if "constant_columns" in risk_names:
            const_cols = affected.get("constant_columns", set())
            if ins_cols & const_cols:
                penalised = _penalise(penalised, 0.30, "profile_constant_column")

        result.append(penalised)

    return result
