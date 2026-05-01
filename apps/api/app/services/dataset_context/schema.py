"""
DatasetContext schema — dataset-awareness layer for Analyst Pro.

A frozen dataclass that travels through the analysis pipeline describing
what kind of dataset has been detected and how confidently.  Immutable
by design: callers may read it; no stage of the pipeline should mutate it.
"""
from __future__ import annotations

from dataclasses import dataclass, field

# ── Dataset type labels ───────────────────────────────────────────────────────

FINANCIAL_MARKETS_SNAPSHOT   = "financial_markets_snapshot"
FINANCIAL_MARKETS_TIMESERIES = "financial_markets_timeseries"
GENERIC_TABULAR              = "generic_tabular"

# ── Activation threshold ──────────────────────────────────────────────────────

# Domain pack fires only when detected confidence reaches this level.
# Below it the pipeline falls back to generic_tabular behaviour unchanged.
CONFIDENCE_THRESHOLD: float = 0.65


# ── Core dataclass ────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class DatasetContext:
    """
    Immutable description of a detected dataset domain.

    Fields
    ------
    dataset_type
        One of the FINANCIAL_MARKETS_* or GENERIC_TABULAR constants.
        Default: GENERIC_TABULAR.

    confidence
        Normalised signal-match score in [0.0, 1.0].
        confidence = matched_signal_weight / max_possible_weight.
        For GENERIC_TABULAR this is always 1.0 (it is the fallback, not
        a scored detection).

    matched_signals
        Human-readable list of the signals that fired during detection.
        Empty for GENERIC_TABULAR.  Used in the debug panel and in tests.

    semantic_roles
        Maps every column name in the source DataFrame to a role label
        (e.g. "return_period", "volatility", "asset_id").
        Columns not matched to any role receive role "unknown".
        Guaranteed to cover all columns; never contains None values.

    warnings
        Non-fatal issues the user should know about, e.g.:
          "Mixed asset classes detected — risk metrics not directly comparable."
        Injected into the report header, narrative, and InsightResult caveats.
    """

    dataset_type:    str             = GENERIC_TABULAR
    confidence:      float           = 1.0
    matched_signals: tuple[str, ...] = field(default_factory=tuple)
    # hash=False: dicts are unhashable; exclude from __hash__ while keeping
    # the field in __eq__ so two contexts with the same roles compare equal.
    semantic_roles:  dict[str, str]  = field(default_factory=dict, hash=False)
    warnings:        tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not (0.0 <= self.confidence <= 1.0):
            raise ValueError(
                f"DatasetContext.confidence must be in [0.0, 1.0], got {self.confidence}"
            )


# ── Convenience constructors ──────────────────────────────────────────────────

def generic_tabular_context(semantic_roles: dict[str, str] | None = None) -> DatasetContext:
    """Return the safe generic fallback context."""
    return DatasetContext(
        dataset_type=GENERIC_TABULAR,
        confidence=1.0,
        matched_signals=(),
        semantic_roles=semantic_roles or {},
        warnings=(),
    )
