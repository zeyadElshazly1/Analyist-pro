"""Header row scoring and inference."""
from __future__ import annotations

HEADER_KEYWORDS = frozenset([
    "date", "time", "id", "name", "value", "amount", "count", "year", "month",
    "type", "category", "region", "country", "code", "status", "description",
    "total", "rate", "price", "revenue", "cost", "qty", "quantity", "period",
    "label", "key", "group", "segment", "flag", "gender", "age", "score",
    "index", "rank", "number", "no", "num", "col", "column", "field",
])


def _is_numeric_cell(s: str) -> bool:
    try:
        float(s.replace(",", "").replace("$", "").replace("%", "").strip())
        return True
    except (ValueError, AttributeError):
        return False


def score_header_candidate(row: list[str], next_rows: list[list[str]]) -> float:
    """
    Score how likely *row* is a header row (0.0–1.0).

    Weights:
      0.35 — text ratio   (headers should be mostly text, not numbers)
      0.25 — uniqueness   (column names should be distinct)
      0.20 — keyword hit  (known column-name tokens)
      0.20 — consistency  (next 5 rows should have same column count)
    """
    cells = [c.strip() for c in row if c.strip()]
    if not cells or len(cells) < 2:
        return 0.0

    text_ratio = sum(1 for c in cells if not _is_numeric_cell(c)) / len(cells)
    uniqueness = len({c.lower() for c in cells}) / len(cells)
    keyword_hit = sum(
        1 for c in cells if any(kw in c.lower() for kw in HEADER_KEYWORDS)
    )
    keyword_score = min(keyword_hit / len(cells), 1.0)
    consistency = (
        sum(1 for r in next_rows[:5] if len(r) == len(row))
        / max(len(next_rows[:5]), 1)
    )

    return round(
        0.35 * text_ratio
        + 0.25 * uniqueness
        + 0.20 * keyword_score
        + 0.20 * consistency,
        3,
    )
