"""
Canonical InsightResult schema — V1.

Represents one finding from the analysis pipeline: a statistically
supported observation about the data, with enough evidence to be
defensible and enough context to include safely in a client report.

Consumers:
  - Insights screen (title, explanation, severity badge, evidence chip)
  - Trust UI (confidence bar, caveats, report_safe gate)
  - Add-to-report action (title, explanation, recommendation, chart_suggestion)
  - Report assembly (report_safe filter, then full record)
  - Run model (list[InsightResult] stored in result_json)

Main producer:
  - services/analysis/orchestrator.py → analyze_dataset(df)
    which chains all detectors → rank_insights() → _enrich_insight()

See ADAPTER_NOTES at the bottom for the field-by-field mapping.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

# ── Sub-types ─────────────────────────────────────────────────────────────────

InsightCategory = Literal[
    "correlation",
    "anomaly",
    "segment",
    "distribution",
    "data_quality",
    "concentration",
    "interaction",
    "simpsons_paradox",
    "missing_pattern",
    "multicollinearity",
    "leading_indicator",
    "trend",
]

InsightSeverity = Literal["high", "medium", "low"]

ChartSuggestion = Literal[
    "scatter",
    "bar",
    "histogram",
    "line",
    "heatmap",
    "boxplot",
    "pie",
    "none",
]


# ── Canonical schema ──────────────────────────────────────────────────────────

class InsightResult(BaseModel):
    """
    V1 insight — one statistically supported finding from the analysis pipeline.

    Each instance represents a single insight. Collections and ordering belong
    in the caller; rank is not stored here.

    confidence is normalised to 0.0–1.0. The legacy pipeline emits 0–100;
    the adapter must divide by 100 before constructing this model.
    """

    # ── Identity ──────────────────────────────────────────────────────────────
    insight_id: str = Field(
        description=(
            "Deterministic identifier: hex digest of (category + sorted columns_used). "
            "Stable across re-runs on the same data so the frontend can track "
            "which insights are new vs. persistent."
        ),
    )

    # ── Display ───────────────────────────────────────────────────────────────
    title: str = Field(
        description="Short headline suitable for a card header or report section title.",
    )
    explanation: str = Field(
        description=(
            "Full human-readable finding. Maps from 'finding' in the current "
            "insight dict. Should be one to three sentences."
        ),
    )
    category: InsightCategory = Field(
        description="Machine label for the type of finding. Maps from 'type'.",
    )
    severity: InsightSeverity = Field(
        description=(
            "'high' — requires attention before client delivery. "
            "'medium' — worth noting in the report. "
            "'low' — informational only."
        ),
    )

    # ── Evidence ──────────────────────────────────────────────────────────────
    columns_used: list[str] = Field(
        default_factory=list,
        description=(
            "All column names involved in this insight. "
            "Normalises the current scattered pattern of col_a / col_b / "
            "columns embedded in title strings."
        ),
    )
    method_used: str = Field(
        description=(
            "Statistical method or detector that produced this finding, "
            "e.g. 'Pearson correlation', 'Spearman correlation', "
            "'IQR fence', 'Isolation Forest', 'Shapiro-Wilk', "
            "'Benjamini-Hochberg FDR correction'."
        ),
    )
    evidence: str = Field(
        description=(
            "Compact statistical evidence string for the evidence chip in the UI, "
            "e.g. 'Pearson r=0.84, adjusted p=0.0003, n=412'."
        ),
    )
    confidence: float = Field(
        ge=0.0, le=1.0,
        description=(
            "Confidence in this finding, normalised to 0.0–1.0. "
            "The current pipeline emits 0–100; divide by 100 in the adapter."
        ),
    )

    # ── Trust signals ─────────────────────────────────────────────────────────
    report_safe: bool = Field(
        description=(
            "True when this insight is suitable for inclusion in a client-facing "
            "report without manual review. "
            "Rule: severity in ('high', 'medium') AND confidence >= 0.6 "
            "AND category not in ('data_quality',). "
            "Currently not emitted by the pipeline — computed in the adapter."
        ),
    )
    caveats: list[str] = Field(
        default_factory=list,
        description=(
            "Standard caveats to display alongside this insight. "
            "E.g. 'Correlation does not imply causation', "
            "'Based on a 20k-row sample of a larger dataset', "
            "'p-value corrected for multiple comparisons (BH-FDR)'. "
            "Currently not emitted — populated by a caveat lookup table in the adapter."
        ),
    )

    # ── Context ───────────────────────────────────────────────────────────────
    why_it_matters: str = Field(
        default="",
        description=(
            "One-sentence business context for this insight category. "
            "Added by _enrich_insight() in services/analysis/narrative.py."
        ),
    )
    recommendation: str = Field(
        default="",
        description=(
            "Suggested action for the analyst. Maps from 'action' in the current dict."
        ),
    )

    # ── Chart ─────────────────────────────────────────────────────────────────
    chart_suggestion: ChartSuggestion = Field(
        default="none",
        description=(
            "Best chart type for visualising this insight. "
            "Not currently emitted by the insight pipeline — "
            "determined by a (category, columns) → chart_type lookup in the adapter."
        ),
    )


# ── Adapter notes ─────────────────────────────────────────────────────────────
#
# CURRENT PRODUCER
#   services/analysis/orchestrator.py  analyze_dataset(df) → (list[dict], narrative)
#   Each dict is produced by one of the detector sub-modules, then enriched
#   by _enrich_insight() which adds why_it_matters / likely_drivers.
#
# CLEAN MAPPINGS — direct or rename-only:
#   title              ← ins["title"]           (no change)
#   explanation        ← ins["finding"]          (rename)
#   category           ← ins["type"]             (rename)
#   severity           ← ins["severity"]         (no change, already "high"/"medium"/"low")
#   evidence           ← ins["evidence"]         (no change)
#   why_it_matters     ← ins.get("why_it_matters", "")   (no change, may be absent)
#   recommendation     ← ins.get("action", "")   (rename)
#
# FIELDS NEEDING ADAPTERS — data partially exists but needs extraction or logic:
#
#   insight_id:
#     Not generated by any detector. Adapter: hashlib.md5 or sha1 of
#     f"{category}:{'|'.join(sorted(columns_used))}".encode()).hexdigest()[:12]
#     This mirrors the (itype, frozenset_of_columns) key in ranking.py._insight_key().
#
#   confidence:
#     ins["confidence"] is 0–100 (e.g. 84.0 for r=0.84).
#     Adapter: round(ins["confidence"] / 100.0, 4)
#     This is the known schema bug flagged in RESULT_SCHEMA_IMPLEMENTATION_SPEC.md.
#
#   columns_used:
#     Scattered across the dict in multiple shapes:
#       - Correlation: col_a, col_b (two explicit fields)
#       - Segment:     title contains "cat → num" pattern
#       - Trend:       title contains "Trend detected: col"
#       - Anomaly:     title contains "Anomalies in col"
#       - Data quality: title contains "column: col"
#     Adapter: consolidate col_a/col_b first; fall back to the same title-parsing
#     logic already in ranking.py._insight_key() for non-correlation types.
#
#   method_used:
#     Partially embedded in evidence strings ("Pearson r=", "Spearman r=",
#     "Isolation Forest", "Shapiro-Wilk", etc.) but not as a standalone field.
#     Adapter: (category → default_method) lookup table:
#       "correlation"        → parse "Pearson"/"Spearman" from evidence string
#       "anomaly"            → "Isolation Forest" (multivariate) / "IQR fence" (univariate)
#       "distribution"       → "Shapiro-Wilk / Jarque-Bera"
#       "segment"            → "Mann-Whitney U"
#       "trend"              → "Mann-Kendall"
#       "concentration"      → "Pareto (80/20 rule)"
#       "data_quality"       → "Column statistics"
#       "multicollinearity"  → "VIF (Variance Inflation Factor)"
#       "simpsons_paradox"   → "Subgroup comparison"
#       "interaction"        → "Interaction effect test"
#       "missing_pattern"    → "MCAR/MAR/MNAR classification"
#       "leading_indicator"  → "Cross-correlation / lag analysis"
#
#   report_safe:
#     Not emitted. Adapter rule:
#       report_safe = (
#           severity in ("high", "medium")
#           and confidence >= 0.6
#           and category not in ("data_quality",)
#       )
#     data_quality insights should always be flagged for human review before
#     inclusion — they report problems in the client's data.
#
#   caveats:
#     Not emitted. Adapter: category → list[str] lookup:
#       "correlation"       → ["Correlation does not imply causation."]
#       "anomaly"           → ["Anomalies may be data entry errors or legitimate extremes."]
#       "distribution"      → ["Significance level α=0.05; large samples may flag trivial skew."]
#       "segment"           → ["Group differences may reflect confounding variables."]
#       "multicollinearity" → ["VIF > 5 threshold; review before removing features."]
#       "simpsons_paradox"  → ["Always verify aggregated trends at the subgroup level."]
#       (most types also get: "p-values corrected for multiple comparisons (BH-FDR)."
#        when Benjamini-Hochberg was applied — check evidence string for "adjusted p".)
#
#   chart_suggestion:
#     Not emitted by insight detectors. Adapter lookup by category:
#       "correlation"       → "scatter"
#       "distribution"      → "histogram"
#       "segment"           → "bar" or "boxplot"
#       "trend"             → "line"
#       "concentration"     → "bar"
#       "anomaly"           → "scatter" (with anomaly points highlighted)
#       "multicollinearity" → "heatmap"
#       "data_quality"      → "none"
#       "simpsons_paradox"  → "bar"
#       "interaction"       → "bar"
#       "missing_pattern"   → "none"
#       "leading_indicator" → "line"
