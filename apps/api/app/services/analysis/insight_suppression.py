"""
Finance-aware insight suppression before ranking.

Removes repetitive generic findings that add little value on cross-sectional
financial market snapshots while leaving domain-pack insights untouched.
"""
from __future__ import annotations

from app.services.dataset_context import FINANCIAL_MARKETS_SNAPSHOT, _normalise_col
from app.services.dataset_context.schema import DatasetContext

_PRICE_FAMILY_COLUMNS: frozenset[str] = frozenset(
    _normalise_col(c)
    for c in (
        "open",
        "dayLow",
        "dayHigh",
        "currentPrice",
        "previousClose",
        "regularMarketPrice",
        "fiftyTwoWeekLow",
        "fiftyTwoWeekHigh",
    )
)


_ASSET_IDENTIFIER_COLUMNS: frozenset[str] = frozenset(
    _normalise_col(c)
    for c in (
        "ticker",
        "symbol",
        "shortName",
        "longName",
        "name",
    )
)


_PRICE_OVERLAP_FINDING_TITLE = "Price fields are highly overlapping"


def _is_price_family_column(column_name: str) -> bool:
    return _normalise_col(column_name) in _PRICE_FAMILY_COLUMNS


def _is_asset_identifier_column(column_name: str) -> bool:
    return _normalise_col(column_name) in _ASSET_IDENTIFIER_COLUMNS


def _extract_high_cardinality_column(title: str) -> str | None:
    prefix = "High-cardinality column: "
    if not title.startswith(prefix):
        return None
    return title[len(prefix) :].strip() or None


def _vif_columns_from_evidence(evidence: str) -> list[str]:
    """
    Parse column names from multicollinearity evidence:
    ``VIF scores: col_a (VIF=1.0), col_b (VIF=2.0)``
    """
    marker = "VIF scores:"
    if marker not in evidence:
        return []
    _, _, rest = evidence.partition(marker)
    rest = rest.strip()
    if not rest:
        return []
    cols: list[str] = []
    for part in rest.split(", "):
        if " (VIF=" not in part:
            continue
        name = part.split(" (VIF=", 1)[0].strip()
        if name:
            cols.append(name)
    return cols


def _multicollinearity_mostly_price_family(ins: dict) -> bool:
    cols = _vif_columns_from_evidence(str(ins.get("evidence", "")))
    if not cols:
        return False
    price_hits = sum(1 for c in cols if _is_price_family_column(c))
    return price_hits > len(cols) / 2.0


def suppress_for_dataset_context(
    insights: list[dict],
    context: DatasetContext,
) -> list[dict]:
    """
    Return a filtered insight list for ranking.

    Non-financial snapshot contexts leave ``insights`` unchanged (same object).
    For ``financial_markets_snapshot``, drop selected generic detectors; domain
    insights ``domain == financial_markets_snapshot`` are never removed.

    May append a single caveat insight when ≥2 qualifying price-structure
    findings were removed.
    """
    if context.dataset_type != FINANCIAL_MARKETS_SNAPSHOT:
        return insights

    out: list[dict] = []
    removed_price_noise = 0
    affected_price_columns: list[str] = []
    affected_seen: set[str] = set()

    def note_price_cols(columns: object) -> None:
        if not isinstance(columns, (list, tuple)):
            columns = []
        for c in columns:
            if isinstance(c, str) and _is_price_family_column(c):
                if c not in affected_seen:
                    affected_seen.add(c)
                    affected_price_columns.append(c)

    for ins in insights:
        if ins.get("domain") == FINANCIAL_MARKETS_SNAPSHOT:
            out.append(ins)
            continue

        itype = ins.get("type", "")

        if itype == "correlation":
            ca, cb = ins.get("col_a"), ins.get("col_b")
            if isinstance(ca, str) and isinstance(cb, str):
                if _is_price_family_column(ca) and _is_price_family_column(cb):
                    removed_price_noise += 1
                    note_price_cols((ca, cb))
                    continue
            out.append(ins)
            continue

        if itype == "multicollinearity":
            if _multicollinearity_mostly_price_family(ins):
                removed_price_noise += 1
                note_price_cols(_vif_columns_from_evidence(str(ins.get("evidence", ""))))
                continue
            out.append(ins)
            continue

        if itype == "trend":
            continue

        if itype == "data_quality":
            col = _extract_high_cardinality_column(str(ins.get("title", "")))
            if col and _is_asset_identifier_column(col):
                continue

        out.append(ins)

    if removed_price_noise >= 2:
        out.append(
            {
                "type": "multicollinearity",
                "severity": "medium",
                "confidence": 85,
                "title": _PRICE_OVERLAP_FINDING_TITLE,
                "finding": (
                    "Open, high, low, close, and current price style fields often move "
                    "together in market snapshot data, so they should not be interpreted "
                    "as independent drivers."
                ),
                "evidence": (
                    f"Affected overlapping price-series columns ({len(affected_price_columns)}): "
                    + ", ".join(affected_price_columns[:12])
                    + ("…" if len(affected_price_columns) > 12 else "")
                    if affected_price_columns
                    else "Multiple redundant price-series correlations removed."
                ),
                "action": (
                    "Use one representative price field or derived return/risk metrics when "
                    "building reports or models."
                ),
                "why_it_matters": (
                    "Suppressing repeated price-field correlations keeps the analysis focused "
                    "on return, risk, asset class, sector, and analyst context."
                ),
                "domain": FINANCIAL_MARKETS_SNAPSHOT,
                "columns_used": list(affected_price_columns),
            }
        )

    return out
