"""
Adapter: raw analyze_dataset() insight dicts → canonical InsightResult list.

This is the single mapping layer between the analysis pipeline output and the
V1 schema contract. All downstream consumers (insights screen, trust UI, report
builder, run model) should read InsightResult, not the raw pipeline dicts.

Key normalization applied here:
  - confidence  : 0–100 (pipeline) → 0.0–1.0 (schema)
  - insight_id  : deterministic md5 hash of (category + sorted columns)
  - columns_used: consolidated from col_a/col_b + title-pattern extraction
  - method_used : category → method lookup + evidence string parsing
  - report_safe : severity/confidence/category gate
  - caveats     : per-category lookup table + BH-FDR flag from evidence
  - chart_suggestion: category → chart type map
"""
from __future__ import annotations

import hashlib
import re

from app.schemas.insight import InsightResult

# ── Lookup tables ─────────────────────────────────────────────────────────────

_DEFAULT_METHOD: dict[str, str] = {
    "correlation":       "Pearson / Spearman correlation",
    "anomaly":           "Isolation Forest / IQR fence",
    "distribution":      "Shapiro-Wilk / Jarque-Bera",
    "segment":           "Mann-Whitney U",
    "trend":             "Mann-Kendall",
    "concentration":     "Pareto (80/20 rule)",
    "data_quality":      "Column statistics",
    "multicollinearity": "VIF (Variance Inflation Factor)",
    "simpsons_paradox":  "Subgroup comparison",
    "interaction":       "Interaction effect test",
    "missing_pattern":   "MCAR/MAR/MNAR classification",
    "leading_indicator": "Cross-correlation / lag analysis",
}

_CHART_SUGGESTION: dict[str, str] = {
    "correlation":       "scatter",
    "distribution":      "histogram",
    "segment":           "bar",
    "trend":             "line",
    "concentration":     "bar",
    "anomaly":           "scatter",
    "multicollinearity": "heatmap",
    "data_quality":      "none",
    "simpsons_paradox":  "bar",
    "interaction":       "bar",
    "missing_pattern":   "none",
    "leading_indicator": "line",
}

_CAVEATS_BY_CATEGORY: dict[str, list[str]] = {
    "correlation":       ["Correlation does not imply causation."],
    "anomaly":           ["Anomalies may be data entry errors or legitimate extreme events."],
    "distribution":      ["Significance level α=0.05; large samples may flag trivial skew."],
    "segment":           ["Group differences may reflect confounding variables."],
    "multicollinearity": ["VIF > 5 threshold; review before removing features."],
    "simpsons_paradox":  ["Always verify aggregated trends at the subgroup level."],
    "interaction":       ["Interaction effects require sufficient sample size per cell."],
    "leading_indicator": ["Lagged correlation does not confirm causality."],
    "trend":             ["Statistical trend does not guarantee the pattern will continue."],
    "missing_pattern":   ["Missingness mechanism classification is probabilistic."],
    "concentration":     [],
    "data_quality":      [],
}

_BH_FDR_CAVEAT = "p-values corrected for multiple comparisons (Benjamini-Hochberg FDR)."

# Report-safe: categories excluded regardless of confidence/severity
_UNSAFE_CATEGORIES: frozenset[str] = frozenset({"data_quality"})


# ── Public API ────────────────────────────────────────────────────────────────

def build_insight_results(raw_insights: list[dict]) -> list[InsightResult]:
    """Convert a list of raw pipeline insight dicts to canonical InsightResult objects."""
    return [build_insight_result(ins) for ins in raw_insights]


def build_insight_result(ins: dict) -> InsightResult:
    """
    Map one raw insight dict to a canonical InsightResult.

    Args:
        ins: Raw dict from analyze_dataset() — enriched by _enrich_insight(),
             so why_it_matters and likely_drivers are already present.

    Returns:
        Canonical InsightResult with all trust fields populated.
    """
    category  = ins.get("type", "data_quality")
    severity  = ins.get("severity", "low")
    raw_conf  = float(ins.get("confidence", 50.0))
    confidence = round(raw_conf / 100.0, 4)

    columns_used = _extract_columns(ins)
    insight_id   = _make_id(category, columns_used)
    method_used  = _extract_method(category, ins.get("evidence", ""))
    caveats      = _build_caveats(category, ins.get("evidence", ""))
    chart        = _CHART_SUGGESTION.get(category, "none")
    report_safe  = _is_report_safe(severity, confidence, category)

    return InsightResult(
        insight_id=insight_id,
        title=ins.get("title", ""),
        explanation=ins.get("finding", ""),
        category=category,                    # type: ignore[arg-type]
        severity=severity,                    # type: ignore[arg-type]
        columns_used=columns_used,
        method_used=method_used,
        evidence=ins.get("evidence", ""),
        confidence=confidence,
        report_safe=report_safe,
        caveats=caveats,
        why_it_matters=ins.get("why_it_matters", ""),
        recommendation=ins.get("action", ""),
        chart_suggestion=chart,               # type: ignore[arg-type]
    )


# ── Extraction helpers ────────────────────────────────────────────────────────

def _make_id(category: str, columns_used: list[str]) -> str:
    """Deterministic 12-char hex ID stable across re-runs on the same data."""
    key = f"{category}:{'|'.join(sorted(columns_used))}"
    return hashlib.md5(key.encode()).hexdigest()[:12]


def _extract_columns(ins: dict) -> list[str]:
    """
    Consolidate column references into a stable list.

    Priority:
    1. Explicit col_a / col_b fields (correlations)
    2. "→" separator in title (segments, leading indicators)
    3. "×" separator in title (interactions: "c1 × c2 moderated by mod")
    4. "vs … by" pattern (Simpson's paradox)
    5. "linked to" pattern (missing_pattern: "miss linked to num")
    6. " in " after known prefix (anomalies, concentration, data_quality)
    7. ":" split fallback (most remaining types)
    """
    # 1. Explicit fields
    cols: list[str] = []
    for field in ("col_a", "col_b"):
        v = ins.get(field)
        if v:
            cols.append(str(v))
    if cols:
        return cols

    title = ins.get("title", "")

    # 2. "→" pattern: "Segment gap: cat → num" / "Leading indicator: c1 → c2 (lag 3)"
    if "→" in title:
        parts = title.split("→")
        left  = parts[0].split(":")[-1].strip()
        right = parts[1].strip().split(" (")[0].strip()
        return _nonempty([left, right])

    # 3. "×" pattern: "Interaction effect: c1 × c2 moderated by mod"
    if "×" in title:
        left_part = title.split("moderated by")[0]
        pair_str  = left_part.split(":")[-1].strip()
        parts     = [p.strip() for p in pair_str.split("×")]
        return _nonempty(parts)

    # 4. "vs … by" pattern: "Possible Simpson's Paradox: c1 vs c2 by cat"
    vs_m = re.search(r":\s*(.+?)\s+vs\s+(.+?)\s+by\s+(.+)$", title, re.IGNORECASE)
    if vs_m:
        return _nonempty([vs_m.group(1), vs_m.group(2), vs_m.group(3)])

    # 5. "linked to" pattern: "Structural missing data: miss linked to num"
    lt_m = re.search(r":\s*(.+?)\s+linked to\s+(.+)$", title, re.IGNORECASE)
    if lt_m:
        return _nonempty([lt_m.group(1), lt_m.group(2)])

    # 6. " in " pattern (after a prefix word): "Anomalies in col" / "Concentration risk in col"
    in_m = re.search(r"\bin\s+(\S+)\s*$", title, re.IGNORECASE)
    if in_m:
        return _nonempty([in_m.group(1)])

    # 7. ":" fallback: "High-cardinality column: col" / "Constant column: col"
    if ":" in title:
        col_part = title.split(":")[-1].strip().split(" (")[0].strip()
        return _nonempty([col_part])

    return []


def _nonempty(items: list[str]) -> list[str]:
    """Filter out empty / whitespace-only strings."""
    return [s for s in items if s and s.strip()]


def _extract_method(category: str, evidence: str) -> str:
    """
    Return a human-readable method string.

    For correlations: parse "Pearson" or "Spearman" from the evidence string.
    For anomalies: distinguish Isolation Forest vs IQR from evidence.
    All others: use the default lookup table.
    """
    if category == "correlation":
        if "Pearson" in evidence:
            return "Pearson correlation (BH-FDR corrected)"
        if "Spearman" in evidence:
            return "Spearman correlation (BH-FDR corrected)"
    if category == "anomaly":
        if "Isolation Forest" in evidence:
            return "Isolation Forest"
        if "IQR" in evidence:
            return "IQR fence"
    return _DEFAULT_METHOD.get(category, "Statistical analysis")


def _build_caveats(category: str, evidence: str) -> list[str]:
    """Assemble caveats list from per-category defaults plus BH-FDR flag."""
    base = list(_CAVEATS_BY_CATEGORY.get(category, []))
    if "adjusted p" in evidence.lower():
        if _BH_FDR_CAVEAT not in base:
            base.append(_BH_FDR_CAVEAT)
    return base


def _is_report_safe(severity: str, confidence: float, category: str) -> bool:
    """Gate: true when this insight can go into a client report without manual review."""
    return (
        severity in ("high", "medium")
        and confidence >= 0.6
        and category not in _UNSAFE_CATEGORIES
    )
