"""
Domain pack registry.

Maps dataset_type strings to DomainInsightPack instances and provides
three public helpers used by the analysis orchestrator:

  get_domain_pack(dataset_type)      → DomainInsightPack | None
  run_domain_pack(df, context)       → list[dict]
  get_suppression_keys(context)      → set[tuple]

V1 registrations
----------------
  financial_markets_snapshot   → SnapshotFinanceInsightPack
  financial_markets_timeseries → (not registered — V1.5)
  generic_tabular              → (not registered — uses generic pipeline)

Safety
------
All three public functions handle unknown dataset_type, generic_tabular,
and empty DataFrames without raising.
"""
from __future__ import annotations

import logging

import pandas as pd

from app.services.dataset_context.schema import (
    DatasetContext,
    FINANCIAL_MARKETS_SNAPSHOT,
    GENERIC_TABULAR,
)
from .base import DomainInsightPack
from .snapshot_finance import SnapshotFinanceInsightPack

logger = logging.getLogger(__name__)


# ── Placeholder pack ──────────────────────────────────────────────────────────



# ── Registry ──────────────────────────────────────────────────────────────────

# Map dataset_type → instantiated pack.
# financial_markets_timeseries is intentionally absent in V1.
# generic_tabular is intentionally absent — it uses the generic pipeline.
DOMAIN_PACKS: dict[str, DomainInsightPack] = {
    FINANCIAL_MARKETS_SNAPSHOT: SnapshotFinanceInsightPack(),
}


# ── Public API ────────────────────────────────────────────────────────────────

def get_domain_pack(dataset_type: str) -> DomainInsightPack | None:
    """
    Return the registered DomainInsightPack for dataset_type, or None.

    Returns None for generic_tabular, financial_markets_timeseries (V1),
    and any unrecognised type.
    """
    return DOMAIN_PACKS.get(dataset_type)


def run_domain_pack(
    df: pd.DataFrame,
    context: DatasetContext,
) -> list[dict]:
    """
    Run the domain pack for context.dataset_type and return its insights.

    Returns an empty list when:
      - no pack is registered for the dataset_type
      - the pack's run() raises (logged, never re-raised)
      - df is empty
    """
    pack = get_domain_pack(context.dataset_type)
    if pack is None:
        return []
    try:
        return pack.run(df, context)
    except Exception:
        logger.exception(
            "Domain pack %s raised during run(); returning empty list",
            type(pack).__name__,
        )
        return []


def get_suppression_keys(context: DatasetContext) -> set[tuple]:
    """
    Return the suppression key set for context.dataset_type.

    Returns an empty set when no pack is registered or the pack raises.
    """
    pack = get_domain_pack(context.dataset_type)
    if pack is None:
        return set()
    try:
        return pack.suppression_keys(context)
    except Exception:
        logger.exception(
            "Domain pack %s raised during suppression_keys(); returning empty set",
            type(pack).__name__,
        )
        return set()
