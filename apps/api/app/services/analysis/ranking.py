"""
Insight deduplication and ranking.

BUG FIX: The original analyzer.py deduplicated by insight["title"][:40].lower()
— a fragile prefix match that could:
  (a) discard distinct insights whose titles happen to share a prefix
  (b) miss duplicate insights expressed with different titles

This module uses a semantic key: (insight_type, frozenset_of_involved_columns).
For insights without explicit column references, it falls back to a normalised
title prefix so the behaviour degrades gracefully rather than failing.

For confidently detected ``financial_markets_snapshot`` datasets (above the context
threshold), premium finance tiles are emitted in a fixed analyst narrative order,
then other domain insights, the price-overlap caveat, generic non-correlations, and
correlations last.

``financial_markets_timeseries`` datasets use the same correlation placement pattern
with a dedicated premium-title block for panel OHLC histories.

Outside those modes, tier-based composite sorting applies.

rank_insights: composite sort — severity 50%, confidence 25%, target-driver 25%,
plus optional financial snapshot domain boosts (Task 73C).

Target-driver bonus
-------------------
Insights where ``is_target_driver=True`` (i.e. rate-gap findings that link a
predictor column to a known binary outcome like Churn/Fraud/Default) receive a
0.30-point bonus in the composite score.  Without this, a weak multivariate
anomaly insight with "high" severity could outrank a "medium"-severity finding
that Contract drives churn by 40 percentage points — a clearly worse outcome
for users who need actionable business intelligence first.
"""
from __future__ import annotations

from app.services.analysis.domain.timeseries_finance import FINANCE_TS_PREMIUM_TITLE_ORDER
from app.services.dataset_context.schema import (
    CONFIDENCE_THRESHOLD,
    DatasetContext,
    FINANCIAL_MARKETS_SNAPSHOT,
    FINANCIAL_MARKETS_TIMESERIES,
)
from app.config import MAX_INSIGHTS


_SEV_WEIGHT = {"high": 1.0, "medium": 0.6, "low": 0.2}

# ── Snapshot domain boosts (additive on composite, ~0–1 scale) ────────────────
_PRICE_OVERLAP_CAVEAT_TITLE = "Price fields are highly overlapping"

# Domain-first ordering for headline tiles (must match SnapshotFinanceInsightPack titles).
_FINANCE_SNAPSHOT_TITLE_ORDER: tuple[str, ...] = (
    "Top return leaders",
    "Largest return laggards",
    "Highest volatility assets",
    "Best risk-adjusted performers",
    "Asset classes show different return profiles",
    "Sectors show different return profiles",
    "Highest analyst-implied upside",
    "Assets cluster at different 52-week positions",
)

# Headline SnapshotFinanceInsightPack tiles — strongest boost (~+17 composite).
_SNAPSHOT_FINANCE_PREMIUM_TITLES: frozenset[str] = frozenset(_FINANCE_SNAPSHOT_TITLE_ORDER)

_BOOST_FINANCE_DEFAULT = 0.11       # modest lift for other domain-labelled insights
_BOOST_FINANCE_PREMIUM = 0.17        # headline finance tiles (+12–18pt-style lift)
_BOOST_FINANCE_CAVEAT = 0.035        # keep caveat below headline domain insights


_TS_FINANCE_PREMIUM_TITLES: frozenset[str] = frozenset(FINANCE_TS_PREMIUM_TITLE_ORDER)


def _financial_domain_rank_bonus(ins: dict, ctx: DatasetContext | None) -> float:
    """
    Ranking bonus for domain-tagged financial snapshot / time-series insights.

    Snapshot mode with ctx requires confidence ≥ CONFIDENCE_THRESHOLD; panel
    time-series mode triggers whenever ``financial_markets_timeseries`` is the
    active ctx.dataset_type.

    When ``ctx`` is omitted (legacy callers / tests), bonuses fall back to
    inspecting insight ``domain`` alone — matching pre–multi-domain behaviour
    for snapshot tiles.
    """
    dom_ins = ins.get("domain")
    title = str(ins.get("title", "") or "").strip()

    if ctx is None:
        if dom_ins == FINANCIAL_MARKETS_SNAPSHOT:
            if title == _PRICE_OVERLAP_CAVEAT_TITLE:
                return _BOOST_FINANCE_CAVEAT
            if title in _SNAPSHOT_FINANCE_PREMIUM_TITLES:
                return _BOOST_FINANCE_PREMIUM
            return _BOOST_FINANCE_DEFAULT
        if dom_ins == FINANCIAL_MARKETS_TIMESERIES:
            if title == _PRICE_OVERLAP_CAVEAT_TITLE:
                return _BOOST_FINANCE_CAVEAT
            if title in _TS_FINANCE_PREMIUM_TITLES:
                return _BOOST_FINANCE_PREMIUM
            return _BOOST_FINANCE_DEFAULT
        return 0.0

    if ctx.dataset_type == FINANCIAL_MARKETS_SNAPSHOT and ctx.confidence >= CONFIDENCE_THRESHOLD:
        if dom_ins != FINANCIAL_MARKETS_SNAPSHOT:
            return 0.0
        if title == _PRICE_OVERLAP_CAVEAT_TITLE:
            return _BOOST_FINANCE_CAVEAT
        if title in _SNAPSHOT_FINANCE_PREMIUM_TITLES:
            return _BOOST_FINANCE_PREMIUM
        return _BOOST_FINANCE_DEFAULT

    if ctx.dataset_type == FINANCIAL_MARKETS_TIMESERIES:
        if dom_ins != FINANCIAL_MARKETS_TIMESERIES:
            return 0.0
        if title == _PRICE_OVERLAP_CAVEAT_TITLE:
            return _BOOST_FINANCE_CAVEAT
        if title in _TS_FINANCE_PREMIUM_TITLES:
            return _BOOST_FINANCE_PREMIUM
        return _BOOST_FINANCE_DEFAULT

    return 0.0


# How much weight a "target-driver" insight receives in the composite score.
# Raised above zero so that rate-gap insights linking predictors to binary
# business outcomes (churn, fraud, conversion) are ranked above unrelated
# pattern-detection findings of equivalent severity.
_TARGET_DRIVER_BONUS = 0.30

# Pull generic correlations down when ranking mixed pools for market snapshots.
_CORRELATION_SNAPSHOT_DEMOTE = 0.52


def _snapshot_rank_active(ctx: DatasetContext | None) -> bool:
    return (
        ctx is not None
        and ctx.dataset_type == FINANCIAL_MARKETS_SNAPSHOT
        and ctx.confidence >= CONFIDENCE_THRESHOLD
    )


def _timeseries_rank_active(ctx: DatasetContext | None) -> bool:
    return ctx is not None and ctx.dataset_type == FINANCIAL_MARKETS_TIMESERIES


def _finance_snapshot_ordered_list(insights: list[dict], ctx: DatasetContext | None) -> list:
    """
    Fixed narrative order for confident market snapshots:

    1–8  Premium finance tiles (only titles present in ``insights``)
    9+   Other domain insights (composite order)
         Single price-overlap caveat
         Generic non-correlation insights (composite order)
         Correlations last (composite order)
    """
    premium_by_title: dict[str, dict] = {}
    for ins in insights:
        if ins.get("domain") != FINANCIAL_MARKETS_SNAPSHOT:
            continue
        t = str(ins.get("title", "") or "").strip()
        if t in _FINANCE_SNAPSHOT_TITLE_ORDER and t not in premium_by_title:
            premium_by_title[t] = ins

    premium_block = [premium_by_title[t] for t in _FINANCE_SNAPSHOT_TITLE_ORDER if t in premium_by_title]
    used = {id(x) for x in premium_block}

    caveat_block: list[dict] = []
    other_domain: list[dict] = []
    generic_non_corr: list[dict] = []
    correlations: list[dict] = []

    for ins in insights:
        if id(ins) in used:
            continue
        t = str(ins.get("title", "") or "").strip()
        dom = ins.get("domain")
        itype = ins.get("type", "")
        if dom == FINANCIAL_MARKETS_SNAPSHOT and t == _PRICE_OVERLAP_CAVEAT_TITLE:
            caveat_block.append(ins)
        elif dom == FINANCIAL_MARKETS_SNAPSHOT:
            other_domain.append(ins)
        elif itype == "correlation":
            correlations.append(ins)
        else:
            generic_non_corr.append(ins)

    caveat_pick = sorted(caveat_block, key=lambda x: -_composite_score(x, ctx))[:1]
    other_domain.sort(key=lambda x: -_composite_score(x, ctx))
    generic_non_corr.sort(key=lambda x: -_composite_score(x, ctx))
    correlations.sort(key=lambda x: -_composite_score(x, ctx))

    return premium_block + other_domain + caveat_pick + generic_non_corr + correlations


def _finance_timeseries_ordered_list(insights: list[dict], ctx: DatasetContext | None) -> list:
    """Same placement pattern as snapshots, for panel OHLC histories."""
    premium_by_title: dict[str, dict] = {}
    for ins in insights:
        if ins.get("domain") != FINANCIAL_MARKETS_TIMESERIES:
            continue
        t = str(ins.get("title", "") or "").strip()
        if t in FINANCE_TS_PREMIUM_TITLE_ORDER and t not in premium_by_title:
            premium_by_title[t] = ins

    premium_block = [premium_by_title[t] for t in FINANCE_TS_PREMIUM_TITLE_ORDER if t in premium_by_title]
    used = {id(x) for x in premium_block}

    caveat_block: list[dict] = []
    other_domain: list[dict] = []
    generic_non_corr: list[dict] = []
    correlations: list[dict] = []

    for ins in insights:
        if id(ins) in used:
            continue
        t = str(ins.get("title", "") or "").strip()
        dom = ins.get("domain")
        itype = ins.get("type", "")
        if dom == FINANCIAL_MARKETS_TIMESERIES and t == _PRICE_OVERLAP_CAVEAT_TITLE:
            caveat_block.append(ins)
        elif dom == FINANCIAL_MARKETS_TIMESERIES:
            other_domain.append(ins)
        elif itype == "correlation":
            correlations.append(ins)
        else:
            generic_non_corr.append(ins)

    caveat_pick = sorted(caveat_block, key=lambda x: -_composite_score(x, ctx))[:1]
    other_domain.sort(key=lambda x: -_composite_score(x, ctx))
    generic_non_corr.sort(key=lambda x: -_composite_score(x, ctx))
    correlations.sort(key=lambda x: -_composite_score(x, ctx))

    return premium_block + other_domain + caveat_pick + generic_non_corr + correlations


def _snapshot_rank_sort_tuple(ins: dict, ctx: DatasetContext | None) -> tuple[int | float, ...]:
    """Tier financial headline tiles first when analysing a confident snapshot context."""
    score = _composite_score(ins, ctx)
    if ctx is None or ctx.dataset_type != FINANCIAL_MARKETS_SNAPSHOT:
        return (0, 0, -score)
    if ctx.confidence < CONFIDENCE_THRESHOLD:
        return (0, 0, -score)

    title = str(ins.get("title", "") or "").strip()
    dom = ins.get("domain")

    if dom == FINANCIAL_MARKETS_SNAPSHOT and title in _FINANCE_SNAPSHOT_TITLE_ORDER:
        return (0, _FINANCE_SNAPSHOT_TITLE_ORDER.index(title), -score)
    if dom == FINANCIAL_MARKETS_SNAPSHOT and title == _PRICE_OVERLAP_CAVEAT_TITLE:
        return (1, 0, -score)
    if dom == FINANCIAL_MARKETS_SNAPSHOT:
        return (2, 0, -score)
    if ins.get("type") == "correlation":
        return (4, 0, -score)
    return (3, 0, -score)


def _insight_key(ins: dict) -> tuple:
    """
    Return a hashable semantic deduplication key.

    Prefers (type, frozenset_of_columns) when column references are present;
    falls back to (type, normalised_title_prefix) otherwise.
    """
    itype = ins.get("type", "")

    # Collect all column references present in this insight dict
    col_refs: list[str] = []
    for field in ("col_a", "col_b"):
        v = ins.get(field)
        if v:
            col_refs.append(v)

    # Some insight types embed columns in a known pattern in 'title'
    # e.g. "Segment gap: region → revenue" — extract both sides
    if not col_refs and itype in {"segment", "concentration", "trend", "distribution", "anomaly"}:
        title = ins.get("title", "")
        # "Segment gap: cat → num" / "Rate gap: cat → target"
        if "→" in title:
            parts = title.split("→")
            left = parts[0].split(":")[-1].strip()
            right = parts[1].strip()
            col_refs = [left, right]
        # "Trend detected: col (direction)"
        elif "Trend detected:" in title:
            col_part = title.split(":")[-1].strip().split(" (")[0]
            col_refs = [col_part]
        # "Anomalies in col" / "Skewed distribution: col" / "Constant column: col"
        elif ":" in title:
            col_part = title.split(":")[-1].strip()
            col_refs = [col_part]

    if col_refs:
        return (itype, frozenset(col_refs))

    # Fallback: normalised title prefix (original behaviour)
    return (itype, ins.get("title", "")[:40].lower())


def deduplicate_insights(insights: list[dict]) -> list[dict]:
    """Remove duplicate insights using semantic (type + columns) keys."""
    seen: set = set()
    deduped: list[dict] = []
    for ins in insights:
        key = _insight_key(ins)
        if key not in seen:
            seen.add(key)
            deduped.append(ins)
    return deduped


def _correlation_financial_demote_active(ins: dict, ctx: DatasetContext | None) -> bool:
    """Pull generic correlations down when ranking alongside finance domain tiles."""
    if ctx is None or ins.get("type") != "correlation":
        return False
    dom = ins.get("domain")
    if ctx.dataset_type == FINANCIAL_MARKETS_SNAPSHOT and ctx.confidence >= CONFIDENCE_THRESHOLD:
        return dom != FINANCIAL_MARKETS_SNAPSHOT
    if ctx.dataset_type == FINANCIAL_MARKETS_TIMESERIES:
        return dom != FINANCIAL_MARKETS_TIMESERIES
    return False


def _composite_score(ins: dict, ctx: DatasetContext | None = None) -> float:
    """
    Composite ranking score for a single insight.

    Components
    ----------
    severity        50% — high/medium/low maps to 1.0/0.6/0.2
    confidence      25% — normalised 0–1 (insight's 0–100 scale)
    target_driver   25% — flat bonus when insight links a predictor to a
                          known binary outcome (is_target_driver=True)

    Rationale: a rate-gap insight with "medium" severity and a 0.30 target-
    driver bonus scores ≈ 0.56, beating a "medium" non-target insight at ≈ 0.34
    but losing to a "high" non-target insight at ≈ 0.72.  This preserves the
    primacy of genuine data anomalies while elevating business-outcome drivers
    above weak pattern findings.

    Domain-tagged ``financial_markets_snapshot`` / ``financial_markets_timeseries``
    insights receive a small additive bonus so finance tiles compete with generic
    correlations without overruling strong high-severity generic findings.
    """
    sev   = _SEV_WEIGHT.get(ins.get("severity", "low"), 0.2)
    conf  = float(ins.get("confidence", 50)) / 100.0
    bonus = _TARGET_DRIVER_BONUS if ins.get("is_target_driver") else 0.0
    base = sev * 0.50 + conf * 0.25 + bonus * 0.25
    score = min(1.0, base + _financial_domain_rank_bonus(ins, ctx))
    if _correlation_financial_demote_active(ins, ctx):
        score *= _CORRELATION_SNAPSHOT_DEMOTE
    return score


def rank_insights(
    insights: list[dict],
    ctx: DatasetContext | None = None,
) -> tuple[list[dict], int]:
    """
    Sort insights for display: confident ``financial_markets_snapshot`` and
    ``financial_markets_timeseries`` runs use explicit premium-title ordering,
    caveat placement, then generics and correlations.

    Other contexts: tier tuple sort (includes composite), dedupe, cap.

    Returns (ranked_deduped_list, total_before_cap).
    """
    if _snapshot_rank_active(ctx):
        deduped = deduplicate_insights(list(insights))
        ordered = _finance_snapshot_ordered_list(deduped, ctx)
        total_found = len(deduped)
        return ordered[:MAX_INSIGHTS], total_found

    if _timeseries_rank_active(ctx):
        deduped = deduplicate_insights(list(insights))
        ordered = _finance_timeseries_ordered_list(deduped, ctx)
        total_found = len(deduped)
        return ordered[:MAX_INSIGHTS], total_found

    insights.sort(key=lambda x: _snapshot_rank_sort_tuple(x, ctx))
    deduped = deduplicate_insights(insights)
    total_found = len(deduped)
    return deduped[:MAX_INSIGHTS], total_found
