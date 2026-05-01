"""
Semantic role resolver.

resolve_semantic_roles(df, dataset_type) -> dict[str, str]

Maps every column in df to a semantic role string using role_for_column()
from signals.py.  Every column in df is guaranteed to appear as a key in
the returned dict; columns not matched to any known role receive "unknown".

The dataset_type parameter is accepted for forward-compatibility (future
domain types may need different resolution logic) but is not used in V1 —
role_for_column() is domain-agnostic and covers all current domains.
"""
from __future__ import annotations

import pandas as pd

from .signals import role_for_column


def resolve_semantic_roles(
    df: pd.DataFrame,
    dataset_type: str | None,
) -> dict[str, str]:
    """
    Return a dict mapping every column name in df to its semantic role.

    Guarantees:
      - Every column in df.columns appears exactly once as a key.
      - No value is None or empty string; unrecognised columns get "unknown".
      - The dataset_type argument is reserved for future per-domain overrides.
    """
    return {col: role_for_column(col) for col in df.columns}
