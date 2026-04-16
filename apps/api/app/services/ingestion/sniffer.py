"""
CSV raw-text reconnaissance.

Reads up to 500 lines without any pandas involvement to classify the file
structure and locate the actual data region.
"""
from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass, field
from pathlib import Path

# Markers that indicate a section label or preamble line (all-caps short line)
_SECTION_RE = re.compile(r'^[A-Z][A-Z0-9 _\-]{2,}$')
_KNOWN_SECTION_LABELS = frozenset([
    "DATA", "OBSERVATIONS", "SERIES", "SECTION", "TABLE", "NOTES",
    "HEADER", "METADATA", "FIELDS", "COLUMNS", "RECORDS",
])

FOOTER_MARKERS = frozenset([
    "notes", "note:", "footnote", "source:", "sources:", "source",
    "terms", "definitions", "disclaimer", "contact:", "data source",
    "metadata", "description:", "updated:", "downloaded from",
    "* ", "† ", "[1]", "[2]", "[source]",
])


@dataclass
class SniffResult:
    delimiter: str = ","
    file_kind: str = "flat_table"
    table_start_row: int = 0
    header_row: int = 0
    footer_start_row: int | None = None
    n_columns: int = 0
    blank_blocks: list[tuple[int, int]] = field(default_factory=list)
    confidence: float = 0.97
    has_section_labels: bool = False


def sniff_csv(path: Path, max_lines: int = 500) -> SniffResult:
    """Read the first *max_lines* raw lines and classify the file structure."""
    raw_lines = _read_raw_lines(path, max_lines)
    if not raw_lines:
        return SniffResult()

    delimiter = _detect_delimiter(raw_lines)
    rows = [_split_line(line, delimiter) for line in raw_lines]
    field_counts = [len(r) for r in rows]
    blank_blocks = _find_blank_blocks(raw_lines)

    table_start, table_end = _find_stable_window(field_counts)
    n_cols = field_counts[table_start] if table_start < len(field_counts) else 0

    header_row = _find_header_row(rows, table_start)

    # Detect footer after the stable data window
    footer_row = _find_footer_row(raw_lines, table_end + 1)

    # Section labels before table_start?
    has_sections = any(_is_section_label(rows[i]) for i in range(table_start))

    file_kind, confidence = _classify(table_start, rows, blank_blocks, has_sections)

    return SniffResult(
        delimiter=delimiter,
        file_kind=file_kind,
        table_start_row=table_start,
        header_row=header_row,
        footer_start_row=footer_row,
        n_columns=n_cols,
        blank_blocks=blank_blocks,
        confidence=confidence,
        has_section_labels=has_sections,
    )


# ── Internal helpers ──────────────────────────────────────────────────────────

def _read_raw_lines(path: Path, max_lines: int) -> list[str]:
    encodings = ["utf-8-sig", "utf-8", "latin-1", "cp1252"]
    for enc in encodings:
        try:
            text = path.read_text(encoding=enc, errors="replace")
            return text.splitlines()[:max_lines]
        except Exception:
            continue
    return []


def _detect_delimiter(lines: list[str]) -> str:
    """Return the most consistent delimiter in the first 20 non-blank lines."""
    sample = [l for l in lines[:30] if l.strip()][:20]
    if not sample:
        return ","
    counts: dict[str, list[int]] = {",": [], "\t": [], ";": [], "|": []}
    for line in sample:
        try:
            dialect = csv.Sniffer().sniff(line, delimiters=",\t;|")
            for d in counts:
                counts[d].append(line.count(d))
        except Exception:
            for d in counts:
                counts[d].append(line.count(d))

    # Choose delimiter with highest mean count, preferring comma on tie
    best = ","
    best_mean = -1.0
    for d, cnts in counts.items():
        if not cnts:
            continue
        mean = sum(cnts) / len(cnts)
        if mean > best_mean:
            best_mean = mean
            best = d
    return best


def _split_line(line: str, delimiter: str) -> list[str]:
    """Split a raw line respecting basic quoting."""
    try:
        return next(csv.reader(io.StringIO(line), delimiter=delimiter))
    except Exception:
        return line.split(delimiter)


def _find_stable_window(field_counts: list[int]) -> tuple[int, int]:
    """
    Return (start, end) of the longest run of equal, non-zero field counts.
    On ties prefer higher column count (more informative).
    """
    if not field_counts:
        return 0, 0

    best_start, best_end, best_run, best_cols = 0, len(field_counts) - 1, 0, 0
    i = 0
    while i < len(field_counts):
        if field_counts[i] == 0:
            i += 1
            continue
        j = i
        while j < len(field_counts) and field_counts[j] == field_counts[i]:
            j += 1
        run_len = j - i
        cols = field_counts[i]
        if run_len > best_run or (run_len == best_run and cols > best_cols):
            best_start, best_end, best_run, best_cols = i, j - 1, run_len, cols
        i = j

    return best_start, best_end


def _find_blank_blocks(lines: list[str]) -> list[tuple[int, int]]:
    """Return list of (start, end) index ranges for consecutive blank lines."""
    blocks: list[tuple[int, int]] = []
    start = None
    for i, line in enumerate(lines):
        if not line.strip():
            if start is None:
                start = i
        else:
            if start is not None:
                blocks.append((start, i - 1))
                start = None
    if start is not None:
        blocks.append((start, len(lines) - 1))
    return blocks


def _is_section_label(row: list[str]) -> bool:
    non_empty = [c.strip() for c in row if c.strip()]
    if len(non_empty) != 1:
        return False
    cell = non_empty[0]
    return cell.upper() in _KNOWN_SECTION_LABELS or bool(_SECTION_RE.match(cell))


def _find_header_row(rows: list[list[str]], table_start: int) -> int:
    """
    The header row is the row at `table_start - 1` if it scores well as a header,
    otherwise `table_start` itself (pandas default — header is first row of stable window).
    """
    from .header_inference import score_header_candidate

    if table_start == 0:
        return 0

    # Check the row just before the stable window
    candidate_idx = table_start - 1
    # Skip blank rows going backwards
    while candidate_idx > 0 and not any(c.strip() for c in rows[candidate_idx]):
        candidate_idx -= 1

    next_data = rows[table_start: table_start + 6]
    score = score_header_candidate(rows[candidate_idx], next_data)
    if score >= 0.5:
        return candidate_idx

    # Fall back: first row of stable window is the header
    return table_start


def _find_footer_row(lines: list[str], search_from: int) -> int | None:
    """Return index of first line that looks like a footer/note, or None."""
    for i in range(search_from, len(lines)):
        stripped = lines[i].strip().lower()
        if not stripped:
            continue
        if any(stripped.startswith(m) for m in FOOTER_MARKERS):
            return i
    return None


def _classify(
    table_start: int,
    rows: list[list[str]],
    blank_blocks: list[tuple[int, int]],
    has_sections: bool,
) -> tuple[str, float]:
    if table_start == 0:
        return "flat_table", 0.97
    if table_start <= 5:
        return "preamble_csv", 0.88
    if has_sections:
        return "sectioned_csv", 0.85
    if table_start > 5:
        return "preamble_csv", 0.82
    return "flat_table", 0.90
