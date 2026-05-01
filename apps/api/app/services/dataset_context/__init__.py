"""
Dataset context detection — dataset-awareness layer for Analyst Pro.

Public exports (schema only for now; detector added in the next slice):

    DatasetContext          Frozen dataclass describing the detected domain.
    CONFIDENCE_THRESHOLD    Float; domain pack activates above this score.
    FINANCIAL_MARKETS_SNAPSHOT   Dataset type constant.
    FINANCIAL_MARKETS_TIMESERIES Dataset type constant.
    GENERIC_TABULAR              Dataset type constant.
    generic_tabular_context      Convenience constructor for the fallback context.

    _normalise_col          Normalise a column name for signal matching.
    role_for_column         Return the semantic role for a column name.
"""

from .schema import (
    DatasetContext,
    CONFIDENCE_THRESHOLD,
    FINANCIAL_MARKETS_SNAPSHOT,
    FINANCIAL_MARKETS_TIMESERIES,
    GENERIC_TABULAR,
    generic_tabular_context,
)
from .signals import (
    _normalise_col,
    role_for_column,
    RETURN_NAMES,
    VOLATILITY_NAMES,
    SHARPE_NAMES,
    ASSET_CLASS_NAMES,
    SECTOR_NAMES,
    ANALYST_UPSIDE_NAMES,
    POSITION_52W_NAMES,
    COMPOSITE_SCORE_NAMES,
    OHLC_NAMES,
    ASSET_ID_NAMES,
    ASSET_LABEL_NAMES,
    SIZE_METRIC_NAMES,
)

__all__ = [
    "DatasetContext",
    "CONFIDENCE_THRESHOLD",
    "FINANCIAL_MARKETS_SNAPSHOT",
    "FINANCIAL_MARKETS_TIMESERIES",
    "GENERIC_TABULAR",
    "generic_tabular_context",
    "_normalise_col",
    "role_for_column",
    "RETURN_NAMES",
    "VOLATILITY_NAMES",
    "SHARPE_NAMES",
    "ASSET_CLASS_NAMES",
    "SECTOR_NAMES",
    "ANALYST_UPSIDE_NAMES",
    "POSITION_52W_NAMES",
    "COMPOSITE_SCORE_NAMES",
    "OHLC_NAMES",
    "ASSET_ID_NAMES",
    "ASSET_LABEL_NAMES",
    "SIZE_METRIC_NAMES",
]
