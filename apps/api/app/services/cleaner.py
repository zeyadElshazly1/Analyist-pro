"""
Backward-compatibility shim for app.services.cleaner.

All production callers do:
    from app.services.cleaner import clean_dataset   # 18+ callers

test_cleaner_edge_cases.py also imports private helpers directly:
    from app.services.cleaner import _safe_knn_k, _try_parse_currency, _try_parse_percentage

All symbols are re-exported from the cleaning sub-package.
Do not add logic to this file — all logic lives in app.services.cleaning.
"""
from app.services.cleaning import (  # noqa: F401
    clean_dataset,
    _safe_knn_k,
    _try_parse_currency,
    _try_parse_percentage,
)

__all__ = [
    "clean_dataset",
    "_safe_knn_k",
    "_try_parse_currency",
    "_try_parse_percentage",
]
