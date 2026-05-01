"""
Domain insight pack registry — dataset-aware analysis layer for Analyst Pro.

Public API
----------
get_domain_pack(dataset_type)     Return the registered pack, or None.
run_domain_pack(df, context)      Run the pack and return insight dicts.
get_suppression_keys(context)     Return ranking suppression keys.

DomainInsightPack                 Base class for all domain packs.
DOMAIN_PACKS                      Registry dict (dataset_type → pack instance).
SnapshotFinancePlaceholderPack    V1 placeholder for financial_markets_snapshot.
"""

from .base import DomainInsightPack
from .registry import (
    DOMAIN_PACKS,
    SnapshotFinancePlaceholderPack,
    get_domain_pack,
    get_suppression_keys,
    run_domain_pack,
)

__all__ = [
    "DomainInsightPack",
    "DOMAIN_PACKS",
    "SnapshotFinancePlaceholderPack",
    "get_domain_pack",
    "get_suppression_keys",
    "run_domain_pack",
]
