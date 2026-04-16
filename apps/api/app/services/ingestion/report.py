"""ParseReport dataclass — carries all decisions made during ingestion."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ParseReport:
    file_kind: str = "flat_table"
    table_start_row: int | None = None
    header_row: int | None = None
    footer_start_row: int | None = None
    metadata_rows: list[int] = field(default_factory=list)
    confidence: float = 1.0
    warnings: list[str] = field(default_factory=list)
    status: str = "ok"           # "ok" | "parsed_with_warnings" | "fallback"
    metadata: dict = field(default_factory=dict)   # title, source, notes
    tables_found: int = 1
    selected_table: int = 0
    parsing_decisions: list[str] = field(default_factory=list)
