"""
Canonical IntakeResult schema — V1.

Represents the output of file ingestion: what the parser found, how confident
it was, and a preview of the data. This is the first record in the analysis
pipeline; downstream steps (cleaning, health, report) receive this as context.

Actual production of this schema is handled by the upload route (routes/upload.py)
which calls load_dataset_with_report() and must be adapted to populate all fields.
See ADAPTER_NOTES at the bottom of this module.
"""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

# ── Sub-types ─────────────────────────────────────────────────────────────────

ParseStatus = Literal["ok", "parsed_with_warnings", "fallback"]

FileKind = Literal["flat_table", "preamble_csv", "sectioned_csv", "excel"]


# ── Canonical schema ──────────────────────────────────────────────────────────

class IntakeResult(BaseModel):
    """
    V1 intake result — the structured output of one file parse attempt.

    All row indices are 0-based and refer to the raw source file, not the
    loaded DataFrame. Fields that cannot be determined are None or empty.
    """

    # ── Identity ──────────────────────────────────────────────────────────────
    file_id: int = Field(
        description="ProjectFile.id for the file that was parsed."
    )
    file_name: str = Field(
        description="Original filename as uploaded."
    )

    # ── Parse outcome ─────────────────────────────────────────────────────────
    parse_status: ParseStatus = Field(
        description=(
            "'ok' — clean parse. "
            "'parsed_with_warnings' — loaded with corrections applied. "
            "'fallback' — smart parse failed; basic loader was used."
        )
    )
    confidence: float = Field(
        ge=0.0, le=1.0,
        description="Parser confidence in the detected structure (0.0–1.0).",
    )

    # ── Structure detection ───────────────────────────────────────────────────
    file_kind: FileKind = Field(
        description=(
            "'flat_table' — standard header-then-data CSV/Excel. "
            "'preamble_csv' — rows of metadata above the table. "
            "'sectioned_csv' — multiple named sections. "
            "'excel' — Excel workbook."
        )
    )
    detected_header_row: int = Field(
        ge=0,
        description="0-based raw row index that contains the column names.",
    )
    preamble_rows: list[int] = Field(
        default_factory=list,
        description="0-based indices of raw rows skipped before the header.",
    )
    footer_rows: list[int] = Field(
        default_factory=list,
        description=(
            "0-based indices of raw rows trimmed from the bottom "
            "(notes, sources, disclaimers)."
        ),
    )
    delimiter: str = Field(
        default=",",
        description="Field separator detected in CSV files. Empty string for Excel.",
    )
    encoding: str = Field(
        default="utf-8",
        description="Character encoding used to read the file.",
    )
    n_columns: int = Field(
        ge=0,
        description="Number of columns in the parsed (post-cleanup) table.",
    )

    # ── Diagnostics ───────────────────────────────────────────────────────────
    warnings: list[str] = Field(
        default_factory=list,
        description="Human-readable warnings produced during ingestion.",
    )
    parsing_decisions: list[str] = Field(
        default_factory=list,
        description="Machine-readable log of structural decisions made by the parser.",
    )
    file_metadata: dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "Key/value pairs extracted from preamble rows "
            "(e.g. title, source, notes)."
        ),
    )

    # ── Preview ───────────────────────────────────────────────────────────────
    preview_sample: list[dict[str, Any]] = Field(
        default_factory=list,
        description=(
            "First N rows of the parsed table as column→value dicts, "
            "suitable for rendering a preview table in the UI."
        ),
    )


# ── Adapter notes ─────────────────────────────────────────────────────────────
#
# CURRENT PRODUCER
#   routes/upload.py  (lines 163–180) builds a free-form dict from ParseReport
#   after calling load_dataset_with_report().
#
# CLEAN MAPPINGS — no transformation needed, just rename:
#   report.status           → parse_status
#   report.confidence       → confidence        (already 0.0–1.0)
#   report.file_kind        → file_kind
#   report.header_row       → detected_header_row
#   report.metadata_rows    → preamble_rows     (already list[int])
#   report.warnings         → warnings
#   report.parsing_decisions → parsing_decisions
#   report.metadata         → file_metadata
#   ProjectFile.id          → file_id           (available in upload route)
#   filename (upload param) → file_name         (available in upload route)
#
# FIELDS NEEDING ADAPTERS — not yet preserved through the pipeline:
#   delimiter     → SniffResult.delimiter is computed in _smart_load_csv()
#                   but not stored on ParseReport; needs a new field on
#                   ParseReport or extraction from parsing_decisions log.
#
#   encoding      → _detect_encoding() is called in _smart_load_csv() but the
#                   result is never stored on ParseReport.
#
#   n_columns     → SniffResult.n_columns is computed but not forwarded to
#                   ParseReport; can alternatively be computed from df.shape[1]
#                   after load and stored on ParseReport.
#
#   footer_rows   → report.footer_start_row is a single int | None (first
#                   footer line). Adapter: None → [], int → [int] as a
#                   minimal conversion; a full footer index list would require
#                   more pipeline work.
#
#   preview_sample → not computed during upload at all. Adapter: after loading
#                   the DataFrame, take df.head(10).to_dict("records") and
#                   serialise with str() fallback for non-JSON-safe types.
