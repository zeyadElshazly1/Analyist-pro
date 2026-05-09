"""
Dataset Intelligence Layer — deterministic analysis planner.

Classifies an uploaded dataset from column names, dtypes, and profile
signals without any AI call.  Produces an AnalysisPlan that downstream
steps (cleaning, finding ranker, chart selector, report builder) can
read to make context-aware decisions.

AI planner (for low-confidence cases) is a future extension; this
module provides the deterministic foundation only.
"""
from __future__ import annotations

import re

from app.schemas.analysis_plan import AnalysisPlan, ChartHint

# ---------------------------------------------------------------------------
# Token sets — order matters (more specific first)
# ---------------------------------------------------------------------------

_FINANCE_TOKENS  = {"ticker", "symbol", "close", "open", "high", "low", "volume",
                    "return", "yield", "portfolio", "volatility", "price", "bid",
                    "ask", "spread", "equity", "market_cap", "pe_ratio"}
_SALES_TOKENS    = {"revenue", "sales", "order", "quantity", "discount", "unit_price",
                    "product", "customer", "region", "territory", "deal", "pipeline",
                    "conversion", "lead", "quota", "upsell"}
_INSURANCE_TOKENS= {"policy", "premium", "claim", "coverage", "severity",
                    "frequency", "deductible", "underwriting", "loss", "renewal",
                    "insured", "endorsement", "liability", "actuarial"}
_HR_TOKENS       = {"employee", "department", "salary", "tenure", "attrition",
                    "performance", "headcount", "hire", "exit", "promotion",
                    "engagement", "absence", "workforce", "payroll", "grade"}
_MARKETING_TOKENS= {"campaign", "impression", "click", "conversion_rate", "ctr",
                    "cpc", "spend", "channel", "ad", "audience", "funnel",
                    "email", "bounce", "engagement_rate"}
_OPS_TOKENS      = {"shipment", "inventory", "warehouse", "supplier", "lead_time",
                    "throughput", "downtime", "sla", "ticket", "incident",
                    "maintenance", "utilization", "capacity", "defect"}

# Each entry: (kind, token_set, entity, template, priorities)
_DOMAIN_RULES: list[tuple[str, set[str], str, str, list[str]]] = [
    ("finance",    _FINANCE_TOKENS,   "instrument", "trend_report",       ["correlation", "outlier", "trend"]),
    ("insurance",  _INSURANCE_TOKENS, "policy",     "detailed_audit",     ["correlation", "segment_comparison", "outlier"]),
    ("sales",      _SALES_TOKENS,     "order",      "executive_summary",  ["trend", "correlation", "segment_comparison", "outlier"]),
    ("hr",         _HR_TOKENS,        "employee",   "detailed_audit",     ["segment_comparison", "correlation", "distribution"]),
    ("marketing",  _MARKETING_TOKENS, "campaign",   "executive_summary",  ["trend", "segment_comparison", "correlation"]),
    ("operations", _OPS_TOKENS,       "event",      "detailed_audit",     ["outlier", "trend", "segment_comparison"]),
]

# ---------------------------------------------------------------------------
# Column classification patterns
# ---------------------------------------------------------------------------

_ID_PATTERN       = re.compile(r"(^|_)(id|key|num|code|ref|uid|uuid|hash)($|_)", re.I)
_UNNAMED_PATTERN  = re.compile(r"^unnamed[:\s_]", re.I)
_HELPER_PATTERN   = re.compile(r"^(avg |average |sum |total |count |helper |temp )", re.I)
_DATE_PATTERN     = re.compile(r"(date|time|month|year|quarter|week|day|_at$|_on$|timestamp)", re.I)

_TARGET_TOKENS: dict[str, list[str]] = {
    "sales":     ["revenue", "sales", "amount", "price", "margin", "profit", "income",
                  "quantity", "discount"],
    "finance":   ["return", "yield", "close", "volume", "volatility", "pnl", "gain",
                  "loss_amount"],
    "insurance": ["premium", "claim", "claim_amount", "severity", "frequency",
                  "loss_ratio", "loss"],
    "hr":        ["salary", "attrition", "tenure", "performance", "compensation"],
    "marketing": ["conversion_rate", "ctr", "cpc", "spend", "impressions", "clicks"],
    "operations":["throughput", "downtime", "sla", "defect_rate", "lead_time"],
}

_DIMENSION_TOKENS = {
    "region", "territory", "country", "state", "city", "zone",
    "category", "product_category", "product_type", "product",
    "department", "team", "division", "segment",
    "channel", "source", "medium", "platform",
    "coverage_type", "policy_type", "vehicle_type",
    "sector", "industry", "market",
    "gender", "age_band", "job_level", "grade",
    "status", "stage",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _normalise(col: str) -> str:
    """Lower-case, strip, collapse spaces/hyphens to underscores."""
    return re.sub(r"[\s\-]+", "_", col.strip().lower())


def _token_hits(normalised_cols: list[str], token_set: set[str]) -> int:
    """Count how many distinct tokens from the set appear in any column name."""
    hits = 0
    for col in normalised_cols:
        for tok in token_set:
            if tok in col:
                hits += 1
                break  # count each column at most once
    return hits


def _is_id_like(col_norm: str, dtype: str | None, unique_pct: float | None) -> bool:
    if _ID_PATTERN.search(col_norm):
        return True
    if unique_pct is not None and unique_pct >= 0.98 and dtype in ("object", "str", "string"):
        return True
    return False


def _classify_columns(
    columns: list[str],
    dtypes: dict[str, str] | None,
    profile_summary: dict | None,
) -> tuple[list[str], list[str], list[str], list[str]]:
    """Return (time_cols, id_cols, helper_cols, mostly_empty_cols)."""
    dtypes = dtypes or {}
    col_profiles: dict[str, dict] = {}
    if profile_summary and "columns" in profile_summary:
        col_profiles = {c["name"]: c for c in profile_summary["columns"]}

    time_cols, id_cols, helper_cols, empty_cols = [], [], [], []

    for col in columns:
        norm = _normalise(col)
        dtype = dtypes.get(col)
        profile = col_profiles.get(col, {})
        unique_pct = profile.get("unique_pct")
        missing_pct = profile.get("missing_pct", 0.0)

        if _DATE_PATTERN.search(norm):
            time_cols.append(col)
        elif _UNNAMED_PATTERN.match(col):
            helper_cols.append(col)
        elif _HELPER_PATTERN.match(col):
            helper_cols.append(col)
        elif _is_id_like(norm, dtype, unique_pct):
            id_cols.append(col)
        elif missing_pct >= 0.80:
            empty_cols.append(col)

    return time_cols, id_cols, helper_cols, empty_cols


def _detect_targets(normalised_cols: list[str], kind: str) -> list[str]:
    token_lists = _TARGET_TOKENS.get(kind, []) + _TARGET_TOKENS.get("sales", [])
    seen: set[str] = set()
    result = []
    for col in normalised_cols:
        if col in seen:
            continue
        for tok in token_lists:
            if tok in col:
                seen.add(col)
                result.append(col)
                break
    return result


def _detect_dimensions(normalised_cols: list[str]) -> list[str]:
    result = []
    for col in normalised_cols:
        for tok in _DIMENSION_TOKENS:
            if tok in col:
                result.append(col)
                break
    return result


def _make_charts(kind: str, targets: list[str], dims: list[str],
                 time_cols: list[str], all_cols: list[str]) -> list[ChartHint]:
    hints: list[ChartHint] = []
    priority = 1

    def _add(chart_type: str, x: str, y: str | None, rationale: str) -> None:
        nonlocal priority
        hints.append(ChartHint(chart_type=chart_type, x_column=x, y_column=y,
                                rationale=rationale, priority=priority))
        priority += 1

    # Time series is always first if a date column and a target exist
    if time_cols and targets:
        _add("line", time_cols[0], targets[0], f"{targets[0]} over time")

    # Primary dimension × target
    if dims and targets:
        _add("bar", dims[0], targets[0], f"{targets[0]} by {dims[0]}")

    # Second dimension if present
    if len(dims) > 1 and targets:
        _add("bar", dims[1], targets[0], f"{targets[0]} by {dims[1]}")

    # Distribution of primary target
    if targets:
        _add("histogram", targets[0], None, f"Distribution of {targets[0]}")

    # Scatter: two targets if available
    if len(targets) >= 2:
        _add("scatter", targets[0], targets[1], f"{targets[0]} vs {targets[1]}")

    return hints


def _validate_columns(plan: AnalysisPlan, valid: set[str]) -> AnalysisPlan:
    """Remove any column references that do not exist in the actual schema."""
    return AnalysisPlan(
        dataset_kind=plan.dataset_kind,
        confidence=plan.confidence,
        business_context=plan.business_context,
        primary_entity=plan.primary_entity,
        target_metrics=[c for c in plan.target_metrics if c in valid],
        important_dimensions=[c for c in plan.important_dimensions if c in valid],
        time_columns=[c for c in plan.time_columns if c in valid],
        columns_to_ignore=[c for c in plan.columns_to_ignore if c in valid],
        recommended_charts=[
            h for h in plan.recommended_charts
            if h.x_column in valid and (h.y_column is None or h.y_column in valid)
        ],
        insight_priorities=plan.insight_priorities,
        analysis_warnings=plan.analysis_warnings,
        report_template_hint=plan.report_template_hint,
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_analysis_plan(
    columns: list[str],
    dtypes: dict[str, str] | None = None,
    profile_summary: dict | None = None,
    sample_rows: list[dict] | None = None,  # reserved for AI planner phase
) -> AnalysisPlan:
    """Build a deterministic AnalysisPlan from column signals.

    Does not make any AI or network calls. Returns a generic plan when
    no domain signals are strong enough (confidence < 0.6).
    """
    if not columns:
        return AnalysisPlan(
            dataset_kind="generic",
            confidence=0.0,
            business_context="No columns detected.",
            report_template_hint="generic",
        )

    valid_cols: set[str] = set(columns)
    norm_cols: list[str] = [_normalise(c) for c in columns]
    # map normalised → original for output (first match wins)
    norm_to_orig: dict[str, str] = {}
    for orig, norm in zip(columns, norm_cols):
        norm_to_orig.setdefault(norm, orig)

    # --- Domain scoring ---
    scores: dict[str, int] = {}
    for kind, token_set, *_ in _DOMAIN_RULES:
        scores[kind] = _token_hits(norm_cols, token_set)

    best_kind = max(scores, key=lambda k: scores[k])
    best_hits = scores[best_kind]

    # Confidence bands
    if best_hits >= 5:
        confidence = min(0.95, 0.80 + (best_hits - 5) * 0.02)
    elif best_hits >= 3:
        confidence = 0.60 + (best_hits - 3) * 0.10
    elif best_hits >= 1:
        confidence = 0.40 + (best_hits - 1) * 0.10
    else:
        confidence = 0.35
        best_kind = "generic"

    # Rule: if second-best is within 1 hit, reduce confidence (ambiguous)
    sorted_scores = sorted(scores.values(), reverse=True)
    if len(sorted_scores) >= 2 and sorted_scores[0] - sorted_scores[1] <= 1 and best_hits >= 1:
        confidence = max(0.35, confidence - 0.15)

    # --- Column classification ---
    time_cols_raw, id_cols_raw, helper_cols_raw, empty_cols_raw = _classify_columns(
        columns, dtypes, profile_summary
    )
    ignore_raw = id_cols_raw + helper_cols_raw + empty_cols_raw

    # Resolve back to original column names where possible
    def _resolve(raw: list[str]) -> list[str]:
        return [c for c in raw if c in valid_cols]

    time_cols   = _resolve(time_cols_raw)
    ignore_cols = _resolve(ignore_raw)

    # Filter working set (exclude ignored + time from target/dimension detection)
    excluded = set(ignore_cols) | set(time_cols)
    active_norm = [n for n, o in zip(norm_cols, columns) if o not in excluded]
    active_orig = [o for o in columns if o not in excluded]

    targets_norm = _detect_targets(active_norm, best_kind)
    targets = [norm_to_orig.get(n, n) for n in targets_norm if norm_to_orig.get(n, n) in valid_cols]

    dims_norm = _detect_dimensions([n for n in active_norm if norm_to_orig.get(n, n) not in set(targets)])
    dims = [norm_to_orig.get(n, n) for n in dims_norm if norm_to_orig.get(n, n) in valid_cols]

    # --- Domain metadata ---
    kind_meta = {k: (ent, tmpl, prios) for k, _, ent, tmpl, prios in _DOMAIN_RULES}
    entity, template, priorities = kind_meta.get(
        best_kind, (None, "generic", ["correlation", "outlier", "trend"])
    )

    # --- Business context ---
    if best_kind == "generic" or confidence < 0.6:
        context = (
            "General-purpose dataset. Analysis will surface top statistical"
            " findings without domain-specific prioritisation."
        )
    else:
        context = (
            f"Dataset classified as {best_kind} with {best_hits} signal matches. "
            f"Primary entity: {entity or 'row'}. "
            f"Key metrics: {', '.join(targets[:3]) or 'not detected'}."
        )

    # --- Warnings ---
    warnings: list[str] = []
    if time_cols:
        warnings.append(
            f"Date columns detected ({', '.join(time_cols[:3])}). "
            "Date-part features (month/quarter/year) will be down-weighted in findings."
        )
    if len(ignore_cols) > 5:
        warnings.append(
            f"{len(ignore_cols)} columns flagged as ID/artifact/helper and will be excluded from analysis."
        )

    # --- Charts ---
    charts = _make_charts(best_kind, targets[:3], dims[:3], time_cols, list(active_orig))

    plan = AnalysisPlan(
        dataset_kind=best_kind,
        confidence=round(confidence, 3),
        business_context=context,
        primary_entity=entity,
        target_metrics=targets,
        important_dimensions=dims,
        time_columns=time_cols,
        columns_to_ignore=ignore_cols,
        recommended_charts=charts,
        insight_priorities=priorities,
        analysis_warnings=warnings,
        report_template_hint=template if confidence >= 0.6 else "generic",
    )

    return _validate_columns(plan, valid_cols)
