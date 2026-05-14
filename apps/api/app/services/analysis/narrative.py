"""
Narrative generation and insight enrichment.

_WHY_IT_MATTERS / _LIKELY_DRIVERS: per-type contextual text.
_detect_domain: heuristic domain label from column names.
_enrich_insight: adds why_it_matters + likely_drivers to an insight dict.
generate_narrative: 3-paragraph executive summary.
"""
import pandas as pd

from app.services.analysis.confidence import safe_confidence_from_insight
from app.services.analysis.trust_filters import is_summary_eligible


# ── Contextual lookup tables ──────────────────────────────────────────────────

_WHY_IT_MATTERS: dict[str, str] = {
    "correlation": (
        "Strong correlations reveal which variables move together — enabling better "
        "predictions and exposing hidden leverage points."
    ),
    "anomaly": (
        "Anomalies can indicate data quality problems, fraud signals, equipment failures, "
        "or genuinely extreme business events."
    ),
    "segment": (
        "Segment gaps show where performance diverges — identifying high-value groups "
        "and underperformers to prioritise."
    ),
    "distribution": (
        "Skewed distributions break parametric tests and inflate means. Knowing the "
        "shape prevents faulty downstream analysis."
    ),
    "data_quality": (
        "Data quality issues silently corrupt every metric built on top of them. "
        "Fixing them is the highest-ROI action before any analysis."
    ),
    "concentration": (
        "Pareto concentration means a small group drives most of the outcome — a key "
        "risk and opportunity signal."
    ),
    "interaction": (
        "Interaction effects mean the 'one size fits all' strategy is wrong. The same "
        "action yields very different results in different segments."
    ),
    "simpsons_paradox": (
        "Simpson's Paradox means aggregate trends can be reversed or misleading — "
        "decisions made on aggregate data may be exactly wrong."
    ),
    "missing_pattern": (
        "Structured missingness (MAR/MNAR) biases any model trained on this data. "
        "Simple imputation will not fix it."
    ),
    "multicollinearity": (
        "Collinear features make model coefficients unstable and uninterpretable — a "
        "common root cause of unexplainable model behaviour."
    ),
    "leading_indicator": (
        "A leading indicator gives advance warning of what's about to change — enabling "
        "proactive rather than reactive decisions."
    ),
    "trend": (
        "A statistically confirmed trend will persist into future periods unless a causal "
        "driver changes, affecting any forecast built on this data."
    ),
}

_LIKELY_DRIVERS: dict[str, str] = {
    "correlation": (
        "One variable may be causally driving the other, or both may share a common "
        "upstream cause (confounding)."
    ),
    "anomaly": (
        "Likely causes: data entry errors, instrument/sensor failures, fraud, one-off "
        "extreme events, or valid edge cases."
    ),
    "segment": (
        "Demographic, behavioural, operational, or geographic differences between groups "
        "are the most common drivers."
    ),
    "distribution": (
        "Long tails often arise from multiplicative processes, power laws, censoring, or "
        "a mix of distinct sub-populations."
    ),
    "data_quality": (
        "Common root causes: ETL errors, schema drift, manual entry mistakes, or missing "
        "upstream data feeds."
    ),
    "concentration": (
        "Power-law concentration often reflects winner-take-most dynamics, geographic "
        "clustering, or a dominant product/customer."
    ),
    "interaction": (
        "Context-dependent effects arise from subgroup-specific behaviours, policies, or "
        "market conditions."
    ),
    "simpsons_paradox": (
        "Driven by group composition effects — the mix of large/small groups distorts the "
        "aggregate relationship."
    ),
    "missing_pattern": (
        "Structured missingness is typically caused by a selection process: certain types "
        "of records are more likely to be incomplete."
    ),
    "multicollinearity": (
        "Features derived from the same underlying construct, highly correlated raw inputs, "
        "or redundant engineered features."
    ),
    "leading_indicator": (
        "Could reflect a causal mechanism, a shared upstream signal, or a lagged "
        "demand/supply effect."
    ),
    "trend": (
        "Seasonality, macro-economic shifts, product lifecycle changes, or ongoing "
        "operational drift are common drivers."
    ),
}


# ── Domain detection ──────────────────────────────────────────────────────────

def _detect_domain(column_names: list[str]) -> str:
    cols = " ".join(column_names).lower()
    if any(k in cols for k in [
        "revenue", "sales", "price", "cost", "margin", "profit", "cltv", "arpu", "ltv"
    ]):
        return "Finance / Sales"
    if any(k in cols for k in [
        "patient", "diagnosis", "treatment", "hospital", "medical",
        "health", "dose", "symptom",
    ]):
        return "Healthcare"
    if any(k in cols for k in [
        "order", "product", "sku", "inventory", "shipment", "cart", "purchase"
    ]):
        return "E-commerce"
    if any(k in cols for k in [
        "user", "session", "click", "conversion", "funnel",
        "page", "bounce", "impression",
    ]):
        return "Marketing / Analytics"
    if any(k in cols for k in [
        "sensor", "temperature", "pressure", "machine",
        "fault", "vibration", "rpm", "voltage",
    ]):
        return "IoT / Manufacturing"
    if any(k in cols for k in [
        "age", "gender", "income", "education", "employment", "population", "survey"
    ]):
        return "Demographics"
    return "General"


# ── Insight enrichment ────────────────────────────────────────────────────────

def _enrich_insight(insight: dict) -> dict:
    """Add why_it_matters and likely_drivers to an insight dict (non-destructive)."""
    itype = insight.get("type", "")
    enriched = dict(insight)
    enriched.setdefault(
        "why_it_matters",
        _WHY_IT_MATTERS.get(itype, "Understanding this pattern can improve decision quality."),
    )
    enriched.setdefault(
        "likely_drivers",
        _LIKELY_DRIVERS.get(itype, "Requires domain investigation to confirm the root cause."),
    )
    return enriched


# ── Narrative trust helpers ───────────────────────────────────────────────────

def _raw_confidence(ins: dict) -> float:
    return safe_confidence_from_insight(ins)


def _is_narrative_eligible(ins: dict) -> bool:
    return is_summary_eligible(ins)


# ── Grain-aware context sentence (90Q) ───────────────────────────────────────

_GRAIN_LABELS: dict[str, str] = {
    "order":       "transaction-level",
    "transaction": "transaction-level",
    "customer":    "customer-level",
    "time_period": "time-series",
    "product":     "product-level",
    "employee":    "employee-level",
    "session":     "session-level",
    "event":       "event-level",
}

_STRATEGY_LABELS: dict[str, str] = {
    "trend_analysis":        "trend analysis",
    "segment_comparison":    "segment comparison",
    "correlation_analysis":  "correlation analysis",
    "anomaly_detection":     "anomaly detection",
    "distribution_analysis": "distribution analysis",
    "target_analysis":       "target-driver analysis",
}


def _build_grain_context_sentence(profile: dict) -> str:
    """Return a one-sentence dataset context string, or '' if profile is unusable."""
    grain = profile.get("grain_label") or "unknown"
    grain_phrase = _GRAIN_LABELS.get(grain)

    fp = profile.get("fingerprint") or {}
    row_count = fp.get("row_count")
    date_range = fp.get("date_range")

    rec_types = (profile.get("strategy") or {}).get("recommended_analysis_types") or []
    type_labels = [_STRATEGY_LABELS[t] for t in rec_types[:2] if t in _STRATEGY_LABELS]

    date_phrase = ""
    if isinstance(date_range, dict) and date_range.get("min") and date_range.get("max"):
        date_phrase = f", {date_range['min']}–{date_range['max']}"

    row_phrase = f" ({row_count:,} records{date_phrase})" if row_count else ""

    type_phrase = ""
    if type_labels:
        joined = " and ".join(type_labels)
        verb = "are" if len(type_labels) > 1 else "is"
        type_phrase = f" {joined.capitalize()} {verb} the primary lens for this data structure."

    if grain_phrase:
        return f"This is a {grain_phrase} dataset{row_phrase}.{type_phrase}"
    if row_phrase or type_phrase:
        return f"This dataset contains{row_phrase} records.{type_phrase}"
    return ""


# ── Narrative builder ─────────────────────────────────────────────────────────

def generate_narrative(
    insights: list[dict],
    df: pd.DataFrame,
    total_found: int = 0,
    pre_analysis_profile: dict | None = None,
) -> str:
    """
    Generate a 3-paragraph executive summary connecting the top insights.

    ``total_found`` is the full count before the MAX_INSIGHTS cap so the
    summary can tell users how many findings are available.

    ``pre_analysis_profile`` is optional — when supplied, a grain-aware
    context sentence is prepended to paragraph 1.

    Plan-suppressed and low-confidence insights are excluded from the
    narrative text. The input list is not mutated.
    """
    n_rows, n_cols = len(df), len(df.columns)
    missing_pct = round(df.isnull().sum().sum() / max(n_rows * n_cols, 1) * 100, 1)

    eligible_insights = [i for i in insights if _is_narrative_eligible(i)]

    correlations  = [i for i in eligible_insights if i["type"] == "correlation"]
    anomalies     = [i for i in eligible_insights if i["type"] == "anomaly"]
    segments      = [i for i in eligible_insights if i["type"] == "segment"]
    concentration = [i for i in eligible_insights if i["type"] == "concentration"]
    interactions  = [i for i in eligible_insights if i["type"] == "interaction"]
    leading       = [i for i in eligible_insights if i["type"] == "leading_indicator"]
    trends        = [i for i in eligible_insights if i["type"] == "trend"]
    multicollin   = [i for i in eligible_insights if i["type"] == "multicollinearity"]
    high_sev      = [i for i in eligible_insights if i.get("severity") == "high"]

    shown_str = (
        f" (showing top {len(eligible_insights)} of {total_found})"
        if total_found > len(eligible_insights)
        else ""
    )

    context_sentence = ""
    if pre_analysis_profile:
        try:
            context_sentence = _build_grain_context_sentence(pre_analysis_profile)
        except Exception:
            context_sentence = ""

    # ── Paragraph 1: Data quality + scope ────────────────────────────────────
    quality = (
        f"has {missing_pct}% missing values, which may limit the reliability of some findings"
        if missing_pct > 5
        else f"is largely complete ({missing_pct}% missing values), supporting confident analysis"
    )
    type_counts: list[str] = []
    if correlations:
        type_counts.append(f"{len(correlations)} correlation{'s' if len(correlations) > 1 else ''}")
    if anomalies:
        type_counts.append(f"{len(anomalies)} anomaly finding{'s' if len(anomalies) > 1 else ''}")
    if segments:
        type_counts.append(f"{len(segments)} segment gap{'s' if len(segments) > 1 else ''}")
    if trends:
        type_counts.append(f"{len(trends)} trend{'s' if len(trends) > 1 else ''}")
    if interactions:
        type_counts.append(
            f"{len(interactions)} interaction effect{'s' if len(interactions) > 1 else ''}"
        )
    counts_str = ": " + ", ".join(type_counts) if type_counts else ""
    n_insights = len(eligible_insights)
    scope_sentence = (
        f"The dataset ({n_rows:,} rows × {n_cols} columns) {quality}. "
        f"Analysis surfaced {n_insights} insight{'s' if n_insights != 1 else ''}"
        f"{shown_str}{counts_str}."
    )
    para1 = f"{context_sentence}  {scope_sentence}" if context_sentence else scope_sentence

    # ── Paragraph 2: Strongest finding per category ───────────────────────────
    def _first_sentence(text: str) -> str:
        idx = text.find(". ")
        return text[:idx] if idx != -1 else text

    parts: list[str] = []
    if correlations:
        tc = correlations[0]
        col_a = tc.get("col_a") or tc["title"].split(": ")[-1].split(" & ")[0]
        col_b = tc.get("col_b") or tc["title"].split(" & ")[-1]
        parts.append(
            f"The strongest relationship is between '{col_a}' and '{col_b}': "
            f"{_first_sentence(tc['finding'])}."
        )
    if trends:
        parts.append(f"A notable trend was found: {_first_sentence(trends[0]['finding'])}.")
    if segments:
        parts.append(f"Segment analysis reveals: {_first_sentence(segments[0]['finding'])}.")
    if concentration:
        parts.append(_first_sentence(concentration[0]["finding"]) + ".")
    if interactions:
        parts.append(
            f"Interaction effects were detected in {len(interactions)} variable pair(s) — "
            "the same relationship behaves differently across subgroups."
        )
    if multicollin:
        parts.append(_first_sentence(multicollin[0]["finding"]) + ".")
    para2 = (
        " ".join(parts)
        if parts
        else "No strong relationships or segment gaps were detected in this dataset."
    )

    # ── Paragraph 3: Prioritised actions ─────────────────────────────────────
    actions: list[str] = []
    if high_sev:
        actions.append(
            f"Address the {len(high_sev)} high-severity finding(s) first — "
            f"starting with: {high_sev[0]['title']}."
        )
    if multicollin:
        actions.append(
            "Resolve multicollinearity before building any predictive model "
            "(drop or combine the flagged columns)."
        )
    if trends:
        col_name = trends[0].get("title", "").split(": ")[-1].split(" (")[0]
        actions.append(
            f"Investigate the driver of the trend in '{col_name}'. "
            "Detrend the data if you plan to use correlations between trended series."
        )
    if leading:
        actions.append(f"Explore the leading-indicator relationship: {leading[0]['title']}.")
    if interactions:
        actions.append(
            "Segment all analyses by the moderating variable(s) to avoid misleading "
            "aggregate conclusions."
        )
    if not actions:
        actions.append("No urgent actions required. Continue monitoring for data drift over time.")
    para3 = " ".join(actions)

    return f"{para1} {para2} {para3}"
