"""Messy file ingestion engine — pre-processing layer before pandas."""
from .excel_region import find_data_region  # noqa: F401
from .header_inference import score_header_candidate  # noqa: F401
from .report import ParseReport  # noqa: F401
from .schema_normalizer import normalize_schema  # noqa: F401
from .section_parser import extract_preamble_metadata, find_footer_row  # noqa: F401
from .sniffer import sniff_csv  # noqa: F401

__all__ = [
    "ParseReport",
    "sniff_csv",
    "score_header_candidate",
    "extract_preamble_metadata",
    "find_footer_row",
    "find_data_region",
    "normalize_schema",
]
