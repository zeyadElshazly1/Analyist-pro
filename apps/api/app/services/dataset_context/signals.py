"""
Signal name sets and column-role resolver for dataset context detection.

All matching is done against normalised column names produced by
_normalise_col(): lowercase, no spaces/underscores/hyphens/punctuation.
This lets "YTD Return", "ytd_return", "ytdReturn", and "ytd-return" all
match the same frozenset entry.

Public API
----------
_normalise_col(col)      Normalise a raw column name for matching.
role_for_column(col)     Return the semantic role label for a column name.
RETURN_NAMES             frozenset of normalised return-column name patterns.
... (one frozenset per role)
"""
from __future__ import annotations

import re

# ── Normaliser ────────────────────────────────────────────────────────────────

_STRIP_RE = re.compile(r"[\s_\-\.%#@!()\[\]{}]")


def _normalise_col(col: str) -> str:
    """
    Lowercase and strip spaces, underscores, hyphens, dots, and common
    punctuation so that "YTD Return", "ytd_return", "ytdReturn", and
    "ytd-return" all collapse to the same comparison string.

    camelCase is NOT split — the intent is maximum recall, not tokenisation.
    "currentPrice" stays "currentprice"; it will still match "currentprice"
    in the frozenset.
    """
    return _STRIP_RE.sub("", col.lower())


# ── Signal frozensets ─────────────────────────────────────────────────────────
# Every entry is a normalised column name (already passed through
# _normalise_col so the matching loop is a simple set lookup).

RETURN_NAMES: frozenset[str] = frozenset({
    # Generic return terms
    "return", "returns", "ret",
    # Period-specific
    "ytdreturn", "ytdreturns", "ytdret",
    "1yreturn", "1yearreturn", "oneyearreturn",
    "3yreturn", "3yearreturn", "threeyearreturn",
    "5yreturn", "5yearreturn", "fiveyearreturn",
    "return1y", "return3y", "return5y",
    "return1yr", "return3yr", "return5yr",
    "returnytd",
    # pct / percentage suffix variants
    "return1ypct", "return3ypct", "return5ypct",
    "returnytdpct", "returnpct",
    "1yrreturnpct", "3yrreturnpct", "5yrreturnpct",
    "ytdreturnpct",
    # Yahoo Finance typical column names
    "ytd", "1yrtotalreturn", "3yrtotalreturn", "5yrtotalreturn",
    "totalreturn", "pricereturn", "totalreturns",
    "annualizedreturn", "annualisedreturn",
    "cumulativereturn",
    "trailingreturn", "trailingreturns",
    # Short codes seen in market data exports
    "ret1y", "ret3y", "ret5y", "retytd",
    "r1y", "r3y", "r5y",
    "perf1y", "perf3y", "perf5y", "perfytd",
    "performance1y", "performance3y", "performance5y",
})

VOLATILITY_NAMES: frozenset[str] = frozenset({
    "volatility", "vol", "stddev", "standarddeviation",
    "annualisedvol", "annualizedvol",
    "volatility1y", "volatility3y", "volatility5y",
    "vol1y", "vol3y", "vol5y",
    "historicalvol", "historicalvolatility",
    "impliedvol", "impliedvolatility",
    "realizedvol", "realisedvolatility",
    "dailyvol", "weeklyvol", "monthlyvol",
    "annualvol", "annualvolatility",
    "volatility1yann", "vol1yann",
    "voldaily", "volmonthly", "volannual",
    "stddevannual", "stddev1y",
    "risk",  # sometimes used as a volatility proxy column header
})

SHARPE_NAMES: frozenset[str] = frozenset({
    "sharpe", "sharperatio", "sharperatios",
    "sharpe1y", "sharpe3y", "sharpe5y",
    "sharpe1yr", "sharpe3yr", "sharpe5yr",
    "sharpescaled", "excessreturn",
    "riskadjustedreturn", "riskadjustedreturns",
    "sortinoreturn", "sortino", "sortinoratio",
    "calmarratio", "calmar",
    "informationratio",
    "treynorratio", "treynor",
})

ASSET_CLASS_NAMES: frozenset[str] = frozenset({
    "assetclass", "assettype", "instrumenttype", "instrumentclass",
    "type", "category", "assetcategory",
    "class", "securitytype", "secclass",
    "fundtype", "producttype", "productclass",
})

SECTOR_NAMES: frozenset[str] = frozenset({
    "sector", "sectors",
    "industrysector", "gicssector", "gics",
    "industry", "industrygroup",
    "businesssector", "marketsector",
    "sectorname",
})

ANALYST_UPSIDE_NAMES: frozenset[str] = frozenset({
    "analystupside", "consensusupside", "pricetargetupside",
    "upside", "upsidepotential", "upsidepct",
    "analystupside", "analystconsensusupside",
    "targetupside", "priceupside",
    "analystupside", "upsidetotarget",
    "upsidetoconsensustarget",
    "analystupsidepct",
    "consensustargetupside",
    "impliedupside",
})

POSITION_52W_NAMES: frozenset[str] = frozenset({
    # 52-week high/low position
    "pctof52whigh", "week52positionpct",
    "week52position", "52weekposition",
    "52whighpct", "52wlowpct",
    "pctfrom52whigh", "pctfrom52wlow",
    "52weekhighpct", "52weeklowpct",
    "positionin52weekrange",
    "week52range", "52wrange",
    "nearweek52high", "nearweek52low",
    "week52highposition", "week52lowposition",
    # Yahoo Finance column labels
    "fiftytwoweekrange", "52wkrange",
    "fiftytwoweekposition",
    "fiftytwoweekpositionpct",
    "pctof52wkhigh",
})

COMPOSITE_SCORE_NAMES: frozenset[str] = frozenset({
    "compositescore", "overallscore", "totalscore",
    "score", "rating", "compositerating",
    "overallrating", "finalrating",
    "rankscore", "rankingscore",
    "quantilescore",
    "alphascoring", "alphascore",
    "zscore",  # only when used as a composite / ranking column
    "compositerank", "overallrank",
    "combinedrating", "combinedscore",
    "aggregatescore",
})

OHLC_NAMES: frozenset[str] = frozenset({
    "open", "openprice", "openingprice",
    "high", "highprice", "dailyhigh", "sessionhigh",
    "low", "lowprice", "dailylow", "sessionlow",
    "close", "closeprice", "closingprice",
    "adjclose", "adjustedclose", "adjustedcloseprice",
    "lastprice", "last",
    "settle", "settlementprice",
    "bid", "ask", "midprice",
    "vwap",  # volume-weighted average price — price column
})

ASSET_ID_NAMES: frozenset[str] = frozenset({
    "ticker", "tickers",
    "symbol", "symbols",
    "isin", "cusip", "sedol",
    "tickersymbol", "stockticker",
    "bbgticker", "bloombergticker",
    "ric",  # Reuters Instrument Code
    "code", "seccode",
})

ASSET_LABEL_NAMES: frozenset[str] = frozenset({
    "name", "companyname", "stockname", "assetname",
    "shortname", "longname",
    "fullname", "issuername",
    "fundname", "etfname",
    "securityname", "instrumentname",
    "description", "assetdescription",
    "label",  # generic display label
})

SIZE_METRIC_NAMES: frozenset[str] = frozenset({
    "marketcap", "mktcap", "marketcapitalization",
    "aum", "assetsundermanagement",
    "fundsize", "totalassets",
    "enterprisevalue", "ev",
    "netassets",
})

# ── Ordered role resolution table ─────────────────────────────────────────────
# Checked in priority order; first match wins.
# Roles are defined before asset_class/sector so that a column literally named
# "type" or "category" is not confused with return or volatility columns.

_ROLE_TABLE: list[tuple[str, frozenset[str]]] = [
    ("asset_id",        ASSET_ID_NAMES),
    ("asset_label",     ASSET_LABEL_NAMES),
    ("ohlc_price",      OHLC_NAMES),
    ("return_period",   RETURN_NAMES),
    ("volatility",      VOLATILITY_NAMES),
    ("sharpe_ratio",    SHARPE_NAMES),
    ("asset_class",     ASSET_CLASS_NAMES),
    ("sector",          SECTOR_NAMES),
    ("analyst_upside",  ANALYST_UPSIDE_NAMES),
    ("position_52w",    POSITION_52W_NAMES),
    ("composite_score", COMPOSITE_SCORE_NAMES),
    ("size_metric",     SIZE_METRIC_NAMES),
]


def role_for_column(col: str) -> str:
    """
    Return the semantic role label for a column name.

    The column name is normalised before lookup so casing, spaces,
    underscores, and hyphens are irrelevant.

    Returns one of:
        "asset_id", "asset_label", "ohlc_price",
        "return_period", "volatility", "sharpe_ratio",
        "asset_class", "sector", "analyst_upside",
        "position_52w", "composite_score", "size_metric",
        "unknown"
    """
    key = _normalise_col(col)
    for role, names in _ROLE_TABLE:
        if key in names:
            return role
    return "unknown"
