"""
Client-ready deterministic executive summaries for Report Builder.

Used when the pipeline narrative is missing, short, or generic fluff.  Pulls
from ``dataset_summary``, ``health_result``, ``cleaning_result``,
``insight_results``, ``executive_panel``, and ``compare_result`` without
claiming causation unless the insight text already encodes it.
"""
from __future__ import annotations

import re
from typing import Any

from app.services.dataset_context.schema import FINANCIAL_MARKETS_SNAPSHOT


# Phrases that read as empty “AI report speak” — trigger structured rewrite.
_GENERIC_SUBSTRINGS: tuple[str, ...] = (
    "valuable insights",
    "this dataset provides",
    "dataset provides valuable",
    "comprehensive overview",
    "key takeaways",
    "delve deeper",
    "unlock the potential",
    "sheds light on",
    "important patterns",
    "wealth of information",
    "robust analysis shows",
)

MIN_STRONG_NARRATIVE_CHARS = 160

# Known SnapshotFinanceInsightPack titles (financial_markets_snapshot domain).
_PERF_RISK_SNAPSHOT_TITLES: tuple[str, ...] = (
    "Top return leaders",
    "Largest return laggards",
    "Highest volatility assets",
    "Best risk-adjusted performers",
)
_SEGMENT_SNAPSHOT_TITLES: tuple[str, ...] = (
    "Asset classes show different return profiles",
    "Sectors show different return profiles",
)
_EXPECTATIONS_SNAPSHOT_TITLES: tuple[str, ...] = (
    "Highest analyst-implied upside",
    "Assets cluster at different 52-week positions",
    "Price fields are highly overlapping",
)

# Narrative phrases counted toward “reuse pipeline narrative” for snapshot runs.
_FINANCE_NARRATIVE_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\breturn\b", re.I), "return"),
    (re.compile(r"\bvolatility\b", re.I), "volatility"),
    (re.compile(r"\bsharpe\b", re.I), "sharpe"),
    (re.compile(r"asset\s+class", re.I), "asset_class"),
    (re.compile(r"\bsector\b", re.I), "sector"),
    (re.compile(r"\banalyst\b", re.I), "analyst"),
    (re.compile(r"52[-\s]?week", re.I), "52_week"),
    (re.compile(r"risk[-\s]?adjusted", re.I), "risk_adjusted"),
)

_FORBIDDEN_CLIENT_WORDS_RE = re.compile(
    r"\b(buy|sell|hold|undervalued|overvalued)\b",
    re.I,
)


def _dataset_context_dict(result_data: dict[str, Any]) -> dict[str, Any] | None:
    ds = result_data.get("dataset_summary")
    if not isinstance(ds, dict):
        return None
    dc = ds.get("dataset_context")
    return dc if isinstance(dc, dict) else None


def _is_financial_markets_snapshot_result(result_data: dict[str, Any]) -> bool:
    dc = _dataset_context_dict(result_data)
    if not dc:
        return False
    return dc.get("dataset_type") == FINANCIAL_MARKETS_SNAPSHOT


def _finance_narrative_marker_count(low: str) -> int:
    """How many distinct finance-term groups appear (used for narrative reuse gate)."""
    seen: set[str] = set()
    for rx, tag in _FINANCE_NARRATIVE_PATTERNS:
        if rx.search(low):
            seen.add(tag)
    return len(seen)


def _insight_primary_text(ins: dict) -> str:
    """Prefer finding, then explanation, then title."""
    for key in ("finding", "explanation"):
        v = ins.get(key)
        if isinstance(v, str) and v.strip():
            return v.strip()
    t = ins.get("title")
    return t.strip() if isinstance(t, str) and t.strip() else ""


def _snapshot_finance_insights_by_title(insights_raw: Any) -> dict[str, dict]:
    rows = insights_raw if isinstance(insights_raw, list) else []
    out: dict[str, dict] = {}
    for ins in rows:
        if not isinstance(ins, dict):
            continue
        if ins.get("domain") != FINANCIAL_MARKETS_SNAPSHOT:
            continue
        title = str(ins.get("title") or "").strip()
        if title:
            out[title] = ins
    return out


def _paragraph_perf_and_risk(by_title: dict[str, dict]) -> str | None:
    parts: list[str] = []
    for title in _PERF_RISK_SNAPSHOT_TITLES:
        ins = by_title.get(title)
        if not ins:
            continue
        body = _insight_primary_text(ins)
        if not body:
            body = title
        parts.append(f"{title}: {body}".strip())
        if len(parts) >= 4:
            break
    if not parts:
        return None
    return (
        "Performance and risk: " + " ".join(parts[:4])[:3600].rstrip()
        + ("…" if len(" ".join(parts[:4])) > 3600 else "")
    )


def _paragraph_segmentation(by_title: dict[str, dict]) -> str | None:
    sentences: list[str] = []
    for title in _SEGMENT_SNAPSHOT_TITLES:
        ins = by_title.get(title)
        if not ins:
            continue
        txt = _insight_primary_text(ins)
        if txt:
            sentences.append(f"{title} — {txt}")
        else:
            sentences.append(title + ".")
    if not sentences:
        return None
    return "Segmentation: " + "; ".join(sentences)[:2000]


def _paragraph_expectations(by_title: dict[str, dict]) -> str | None:
    sentences: list[str] = []
    for title in _EXPECTATIONS_SNAPSHOT_TITLES:
        ins = by_title.get(title)
        if not ins:
            continue
        txt = _insight_primary_text(ins)
        if txt:
            sentences.append(f"{title}: {txt}")
        else:
            sentences.append(title + ".")
    if not sentences:
        return None
    return "Market context & positioning: " + " ".join(sentences)[:2400]


def _snapshot_dataset_intro(result_data: dict[str, Any], dc: dict[str, Any]) -> str:
    ds = result_data.get("dataset_summary")
    rows = cols = None
    if isinstance(ds, dict):
        rows = ds.get("rows") if isinstance(ds.get("rows"), int) else None
        cols = ds.get("columns") if isinstance(ds.get("columns"), int) else None

    roles = dc.get("semantic_roles") if isinstance(dc, dict) else None
    has_asset_class = has_sector = False
    if isinstance(roles, dict):
        vals = roles.values()
        has_asset_class = any(v == "asset_class" for v in vals if isinstance(v, str))
        has_sector = any(v == "sector" for v in vals if isinstance(v, str))

    if isinstance(rows, int):
        row_core = f"{rows:,} instruments"
    else:
        row_core = "instruments in this upload"

    col_tail = f" across {cols} columns" if isinstance(cols, int) else ""

    segments: list[str] = []
    if has_asset_class and has_sector:
        segments.append("labelled asset classes and sectors for cross-sectional comparison")
    elif has_asset_class:
        segments.append("labelled asset classes for segmentation")
    elif has_sector:
        segments.append("labelled sectors for segmentation")

    base = (
        "This analysis reviews a financial market snapshot of "
        + row_core
        + col_tail
        + (" with " + " and ".join(segments) if segments else "")
        + ". These results are descriptive and suited to institutional screening—not forecasts of future outcomes."
    )
    return base


def _mixed_asset_classes_warning_sentence(warnings: Any) -> str | None:
    if not isinstance(warnings, (list, tuple)):
        return None
    for w in warnings:
        if isinstance(w, str) and "mixed asset classes" in w.lower():
            return (
                "Because the dataset mixes asset classes, compare results within similar asset "
                "groups before drawing broad conclusions."
            )
    return None


def build_financial_snapshot_executive_summary(result_data: dict[str, Any]) -> str:
    """
    Client-ready structured summary tuned for ``financial_markets_snapshot``.
    Screening language only; avoids buy/sell/hold style terms.
    """
    dc = _dataset_context_dict(result_data)
    paragraphs: list[str] = []

    if not isinstance(dc, dict):
        paragraphs.append(_snapshot_dataset_intro(result_data, {}))
    else:
        paragraphs.append(_snapshot_dataset_intro(result_data, dc))

    raw_ins = result_data.get("insight_results") or result_data.get("insights") or []
    by_title = _snapshot_finance_insights_by_title(raw_ins)

    p_perf = _paragraph_perf_and_risk(by_title)
    if p_perf:
        paragraphs.append(p_perf)
    elif isinstance(raw_ins, list) and any(isinstance(x, dict) for x in raw_ins):
        paragraphs.append(
            "Performance and risk: Ranked insights were sparse in the export—open the findings "
            "panel for return, volatility, and risk-adjusted views once the analysis finishes."
        )
    else:
        paragraphs.append(
            "Performance and risk: Cross-section return and volatility signals were not available "
            "for automatic narration in this artifact."
        )

    p_seg = _paragraph_segmentation(by_title)
    if p_seg:
        paragraphs.append(p_seg)

    p_exp = _paragraph_expectations(by_title)
    if p_exp:
        paragraphs.append(p_exp)

    reco_bits: list[str] = [
        "Use these views to screen issuers or universes and flag outliers for governance review-only follow-up; "
        "compare names within asset class buckets where classifications are trustworthy, validate metric "
        "definitions with your market data steward, and treat extremes as hypotheses rather than decisive labels.",
        "This is a screening analysis, not investment advice.",
    ]
    if isinstance(dc, dict):
        mix_note = _mixed_asset_classes_warning_sentence(dc.get("warnings"))
        if mix_note:
            reco_bits.insert(1, mix_note)
    reco_body = " ".join(reco_bits)

    grade, score = _health_grade_and_score(result_data)
    q_tail = _quality_verdict_sentence(grade, score)
    clean = _cleaning_clause(result_data)
    qual_suffix = q_tail + (" " + clean if clean else "")
    paragraphs.append(reco_body + " " + qual_suffix)

    out = "\n\n".join(p for p in paragraphs if p.strip())
    if _FORBIDDEN_CLIENT_WORDS_RE.search(out):
        out = _FORBIDDEN_CLIENT_WORDS_RE.sub("[redacted]", out)
    return out[:8000]


def _narrative_should_use_as_is(narrative: str) -> bool:
    """Treat pipeline narrative as final only when it is substantive and on-topic."""
    s = narrative.strip()
    if len(s) < MIN_STRONG_NARRATIVE_CHARS:
        return False
    low = s.lower()
    if any(g in low for g in _GENERIC_SUBSTRINGS):
        return False
    return True


def _severity_rank_val(ins: dict) -> int:
    sev = (ins.get("severity") or "").lower()
    return {"critical": 0, "high": 1, "medium": 2, "low": 3}.get(sev, 4)


def _insight_body(ins: dict) -> str:
    for key in ("title", "explanation", "finding"):
        v = ins.get(key)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return ""


def _columns_phrase(ins: dict) -> str:
    cols = ins.get("columns_used")
    if isinstance(cols, list) and cols:
        clean = [str(c) for c in cols[:4] if c is not None]
        if not clean:
            return ""
        if len(clean) == 1:
            return clean[0]
        return ", ".join(clean[:-1]) + f", and {clean[-1]}"


def _top_insights(raw: list[Any], *, limit: int = 3) -> list[dict]:
    dicts = [x for x in raw if isinstance(x, dict)]
    dicts.sort(
        key=lambda d: (
            _severity_rank_val(d),
            -len(_insight_body(d)),
        ),
    )
    return dicts[:limit]


def _health_grade_and_score(result_data: dict[str, Any]) -> tuple[str | None, float | None]:
    hr = result_data.get("health_result")
    if isinstance(hr, dict):
        hs = hr.get("health_score")
        if isinstance(hs, dict):
            grade = hs.get("grade")
            score = hs.get("total_score")
            if isinstance(score, (int, float)):
                return (str(grade) if grade is not None else None, float(score))
    hs = result_data.get("health_score")
    if isinstance(hs, dict):
        grade = hs.get("grade")
        for key in ("total", "score"):
            v = hs.get(key)
            if isinstance(v, (int, float)):
                return (str(grade) if grade is not None else None, float(v))
    return (None, None)


def _quality_verdict_sentence(grade: str | None, score: float | None) -> str:
    if score is not None:
        rounded = int(round(score))
        g = f" (grade {grade})" if grade else ""
        if rounded >= 80:
            tail = "structure and completeness look strong for client-facing reporting, subject to the caveats below."
        elif rounded >= 60:
            tail = "shows moderate quality — review flagged issues before wide distribution."
        else:
            tail = "indicates material quality issues; treat findings as directional until data is improved."
        return f"Data quality score is {rounded}/100{g}; this {tail}"
    if grade:
        return f"Data quality grade is {grade}; validate key fields before acting on quantitative conclusions."
    return "Data quality metrics were limited; confirm critical fields manually before strategic decisions."


def _cleaning_clause(result_data: dict[str, Any]) -> str:
    cr = result_data.get("cleaning_result")
    if not isinstance(cr, dict):
        return ""
    parts: list[str] = []
    cs = cr.get("cleaning_summary")
    if isinstance(cs, dict):
        steps = cs.get("steps_applied")
        if isinstance(steps, int) and steps > 0:
            parts.append(f"{steps} cleaning step(s) were applied in the pipeline.")
    sus = cr.get("suspicious_columns")
    if isinstance(sus, list) and sus:
        parts.append(f"{len(sus)} column(s) were flagged for review during cleaning.")
    return " ".join(parts)


def _compare_clause(result_data: dict[str, Any]) -> str:
    comp = result_data.get("compare_result")
    if not isinstance(comp, dict):
        return ""
    sd = comp.get("summary_draft")
    if isinstance(sd, str) and sd.strip():
        return sd.strip()[:400]
    rv = comp.get("row_volume_changes")
    if isinstance(rv, dict):
        a, b = rv.get("count_a"), rv.get("count_b")
        diff = rv.get("diff")
        if isinstance(a, int) and isinstance(b, int):
            extra = ""
            if isinstance(diff, int) and diff != 0:
                extra = f" Net row change: {diff:+,}."
            return (
                f"Comparison context: baseline file has {a:,} rows; comparison file has {b:,} rows.{extra}"
            )
    return ""


def _format_finding_line(ins: dict) -> str:
    body = _insight_body(ins)
    if not body:
        return ""
    sev = (ins.get("severity") or "").lower()
    sev_lbl = f"{sev.capitalize()}-severity: " if sev else ""
    cols = _columns_phrase(ins)
    ev = ins.get("evidence")
    ev_s = ev.strip() if isinstance(ev, str) else ""
    line = f"{sev_lbl}{body}"
    if cols:
        line += f" (fields involved: {cols})"
    if ev_s:
        line += f" Supporting context: {ev_s[:220]}{'…' if len(ev_s) > 220 else ''}"
    if not re.search(r"\b(causes?|caused|causing|proves?|proof that)\b", line, re.I):
        line += " This pattern is associated with the fields above—not established as a root cause without further validation."
    else:
        line += " Interpret with care: the source wording may imply causation that observational data alone cannot support."
    return line


def _executive_panel_clause(result_data: dict[str, Any]) -> tuple[str, str]:
    """Return (implication paragraph, recommendation paragraph) fragments."""
    ep = result_data.get("executive_panel")
    if not isinstance(ep, dict):
        return "", ""

    implications: list[str] = []
    for bucket in ("opportunities", "risks"):
        items = ep.get(bucket) or []
        if not isinstance(items, list):
            continue
        for it in items[:2]:
            if not isinstance(it, dict):
                continue
            t = it.get("title") or it.get("summary")
            if isinstance(t, str) and t.strip():
                implications.append(t.strip()[:280])
            if len(implications) >= 2:
                break
        if len(implications) >= 2:
            break

    impl_txt = ""
    if implications:
        impl_txt = (
            "From a business perspective, the strongest themes are: "
            + " ".join(f"«{s}»" for s in implications[:2])
            + " These describe associations and concentrations in the data rather than proven causal drivers."
        )

    actions = ep.get("action_plan") or []
    rec = ""
    if isinstance(actions, list) and actions:
        first = actions[0]
        if isinstance(first, dict):
            act = first.get("action") or first.get("title")
            reason = first.get("reason")
            if isinstance(act, str) and act.strip():
                rec = f"Recommended next step: {act.strip()[:320]}"
                if isinstance(reason, str) and reason.strip():
                    rec += f" Rationale: {reason.strip()[:200]}"
    return impl_txt, rec


def _fallback_recommendation(top: list[dict]) -> str:
    for ins in top:
        r = ins.get("recommendation")
        if isinstance(r, str) and r.strip():
            return f"Recommended next step: {r.strip()[:400]}"
        w = ins.get("why_it_matters")
        if isinstance(w, str) and w.strip():
            return (
                "Recommended next step: Prioritise follow-up on the highest-severity finding first — "
                f"{w.strip()[:280]}"
            )
    return (
        "Recommended next step: Review the detailed findings section with stakeholders, "
        "validate data definitions, and agree on one measurable follow-up (e.g. retention pilot or pricing test) "
        "before scaling any initiative."
    )


def _caveats_sentence(insights: list[dict]) -> str:
    caveats: list[str] = []
    for ins in insights:
        c = ins.get("caveats")
        if isinstance(c, list):
            for item in c[:2]:
                if isinstance(item, str) and item.strip():
                    caveats.append(item.strip()[:200])
        elif isinstance(c, str) and c.strip():
            caveats.append(c.strip()[:200])
        if len(caveats) >= 3:
            break
    unsafe = [i for i in insights if i.get("report_safe") is False]
    bits: list[str] = []
    if caveats:
        bits.append("Notable caveats: " + "; ".join(caveats[:3]) + ".")
    if unsafe:
        bits.append(
            "Some findings above are not marked report-safe for external use — have an analyst review wording before client delivery."
        )
    return " ".join(bits)


def build_structured_executive_summary(result_data: dict[str, Any]) -> str:
    """Build 2–4 short paragraphs; always client-safe baseline language."""
    paragraphs: list[str] = []

    ds = result_data.get("dataset_summary") or {}
    rows = cols = None
    num_c = cat_c = None
    if isinstance(ds, dict):
        rows = ds.get("rows")
        cols = ds.get("columns")
        num_c = ds.get("numeric_cols")
        cat_c = ds.get("categorical_cols")

    bits: list[str] = []
    if isinstance(rows, int):
        bits.append(f"{rows:,} rows")
    if isinstance(cols, int):
        bits.append(f"{cols} columns")
    context = "The working dataset"
    if bits:
        context += " contains " + " and ".join(bits)
        if isinstance(num_c, int) and isinstance(cat_c, int):
            context += f" (about {num_c} numeric and {cat_c} categorical fields)"
    else:
        context += " was analyzed"
    context += "."
    cc = _compare_clause(result_data)
    if cc:
        context += " " + cc
    paragraphs.append(context)

    grade, score = _health_grade_and_score(result_data)
    q_line = _quality_verdict_sentence(grade, score)
    clean = _cleaning_clause(result_data)
    if clean:
        q_line += " " + clean
    paragraphs.append(q_line)

    raw = result_data.get("insight_results") or result_data.get("insights") or []
    top = _top_insights(raw if isinstance(raw, list) else [], limit=3)
    if top:
        finding_lines = []
        for ins in top:
            fl = _format_finding_line(ins)
            if fl:
                finding_lines.append(fl)
        if finding_lines:
            paragraphs.append(
                "Key signals from the analysis:\n• "
                + "\n• ".join(finding_lines)
            )
        else:
            paragraphs.append(
                "Structured findings were present but could not be summarised automatically — "
                "review the Findings tab and paste the key points you want executives to see."
            )
    else:
        paragraphs.append(
            "No ranked findings were available for automatic summary. "
            "Open the Findings tab to enrich this report once insights are generated."
        )

    impl, ep_rec = _executive_panel_clause(result_data)
    rec = ep_rec or _fallback_recommendation(top)
    biz_bits = []
    if impl:
        biz_bits.append(impl)
    biz_bits.append(rec)
    paragraphs.append(" ".join(b for b in biz_bits if b))

    cav = _caveats_sentence(top)
    if cav:
        paragraphs.append(cav)

    out = "\n\n".join(p for p in paragraphs if p.strip())
    return out[:8000]


def build_fallback_executive_summary(result_data: dict[str, Any]) -> str:
    """
    Prefer a strong pipeline narrative when appropriate; otherwise build a structured summary
    from analysis blocks.

    Financial market snapshots default to the finance-specific draft unless the pipeline
    narrative is already strong and contains multiple finance-specific terms.
    """
    narrative = (result_data.get("narrative") or "").strip()
    low = narrative.lower()

    if _is_financial_markets_snapshot_result(result_data):
        if _narrative_should_use_as_is(narrative) and _finance_narrative_marker_count(low) >= 2:
            return narrative[:8000]
        return build_financial_snapshot_executive_summary(result_data)

    if _narrative_should_use_as_is(narrative):
        return narrative[:8000]
    return build_structured_executive_summary(result_data)
