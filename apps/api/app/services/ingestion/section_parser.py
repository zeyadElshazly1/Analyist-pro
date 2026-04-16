"""Preamble / footer metadata extraction."""
from __future__ import annotations

from .sniffer import FOOTER_MARKERS


def extract_preamble_metadata(raw_lines: list[str], header_row: int) -> dict:
    """
    Parse lines *before* the header row for title, source, and notes.

    Rules:
    - First non-empty line → title
    - Line starting with "source" → source
    - Line starting with "note" / "description" → notes list
    """
    meta: dict = {}
    for line in raw_lines[:header_row]:
        stripped = line.strip()
        if not stripped:
            continue
        low = stripped.lower()
        if low.startswith("source"):
            meta["source"] = stripped.split(":", 1)[-1].strip()
        elif low.startswith("note") or low.startswith("description"):
            meta.setdefault("notes", []).append(stripped.split(":", 1)[-1].strip())
        elif "title" not in meta and len(stripped) > 5:
            meta["title"] = stripped   # first substantive line
    return meta


def find_footer_row(raw_lines: list[str], search_from: int) -> int | None:
    """
    Return the 0-based index of the first line that looks like footer/notes,
    searching from *search_from* onward. Returns None if not found.
    """
    for i in range(search_from, len(raw_lines)):
        stripped = raw_lines[i].strip().lower()
        if not stripped:
            continue
        if any(stripped.startswith(m) for m in FOOTER_MARKERS):
            return i
    return None
