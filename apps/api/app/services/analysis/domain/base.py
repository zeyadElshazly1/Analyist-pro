"""
Base class for domain insight packs.

A DomainInsightPack encapsulates all domain-specific insight detection
and suppression logic for one dataset_type.  Concrete packs inherit this
class and override run() and/or suppression_keys().

Default behaviour (base class):
  run()              → []         (no insights)
  suppression_keys() → set()      (nothing suppressed)

These defaults mean an unfinished or placeholder pack is always safe to
register and call — it produces no output and suppresses nothing.
"""
from __future__ import annotations

import pandas as pd

from app.services.dataset_context.schema import DatasetContext


class DomainInsightPack:
    """
    Base class for a domain-specific insight pack.

    Subclasses override run() to return domain insights and/or
    suppression_keys() to declare which generic insights should be
    removed before final ranking.

    Attributes
    ----------
    dataset_type
        The DatasetContext.dataset_type string this pack handles.
        Set as a class attribute on each concrete subclass.
    """

    dataset_type: str = ""

    def run(
        self,
        df: pd.DataFrame,
        context: DatasetContext,
    ) -> list[dict]:
        """
        Detect domain-specific insights and return them as raw insight dicts.

        Each dict must match the existing insight dict schema produced by
        the generic detectors (keys: type, title, finding, severity,
        confidence, evidence, action).

        Returns an empty list by default.  Subclass implementations must
        never raise — wrap all logic in try/except and return [] on failure.
        """
        return []

    def suppression_keys(
        self,
        context: DatasetContext,
    ) -> set[tuple]:
        """
        Return a set of insight deduplication keys that should be removed
        from the generic detector output before final ranking.

        Keys use the same (insight_type, frozenset_of_columns) shape as
        ranking._insight_key().  Returns an empty set by default.
        """
        return set()
