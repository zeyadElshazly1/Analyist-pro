"""
Data story generator.

generate_data_story(analysis_result) → { title, slides }

Uses the AI provider to produce five consultant-grade slides from structured
analysis context.  Invalid model output is repaired; provider failure uses a
deterministic slide deck that mirrors the same structure.
"""
from __future__ import annotations

import json
import logging
import os
import re
from typing import Any

logger = logging.getLogger(__name__)

_STORY_MODEL = os.environ.get("CLAUDE_STORY_MODEL", "claude-sonnet-4-6")

# Fixed slide roles (titles must match — slide_num 1..5 in order).
STORY_SLIDE_TITLES: tuple[str, ...] = (
    "Executive takeaway",
    "Data quality & trust",
    "Biggest opportunity or driver",
    "Main risk or caveat",
    "Recommended next actions",
)

_STORY_SCHEMA = """{
  "title": "≤10 words, specific to this dataset (name a metric, segment, or column — no generic deck title)",
  "slides": [
    {
      "slide_num": 1,
      "title": "Executive takeaway",
      "narrative": "2–4 sentences: headline conclusion using NUMBERS, column names, or segments from the context. No fluff.",
      "key_points": ["specific bullet 1 with a number or field name", "specific bullet 2", "specific bullet 3"]
    },
    {
      "slide_num": 2,
      "title": "Data quality & trust",
      "narrative": "2–4 sentences on trust: health score/grade, cleaning, missingness, ID/uniqueness risks if noted.",
      "key_points": ["point 1", "point 2", "point 3"]
    },
    {
      "slide_num": 3,
      "title": "Biggest opportunity or driver",
      "narrative": "2–4 sentences on the strongest upside or driver pattern (report_safe insights preferred).",
      "key_points": ["point 1", "point 2", "point 3"]
    },
    {
      "slide_num": 4,
      "title": "Main risk or caveat",
      "narrative": "2–4 sentences: limitations, caveats, non-report_safe findings, or comparison caveats.",
      "key_points": ["point 1", "point 2", "point 3"]
    },
    {
      "slide_num": 5,
      "title": "Recommended next actions",
      "narrative": "2–4 sentences tying actions to the evidence above (measurable when possible).",
      "key_points": ["point 1", "point 2", "point 3"]
    }
  ]
}"""

_BANNED_PHRASES = (
    "valuable insights",
    "comprehensive overview",
    "delve deeper",
    "sheds light",
    "robust analysis",
    "key takeaways",
    "interesting pattern",
    "several statistically significant",
    "the data reveals",
    "wealth of information",
)


def _insights_list(analysis_result: dict) -> list[dict]:
    raw = analysis_result.get("insight_results") or analysis_result.get("insights") or []
    return [x for x in raw if isinstance(x, dict)]


def _severity_sort_key(ins: dict) -> tuple[int, int]:
    s = (ins.get("severity") or "").lower()
    rank = {"critical": 0, "high": 1, "medium": 2, "low": 3}.get(s, 4)
    ev = ins.get("evidence")
    ev_len = len(ev) if isinstance(ev, str) else 0
    return (rank, -ev_len)


def _top_report_safe_insights(insights: list[dict], *, limit: int = 6) -> list[dict]:
    safe = [i for i in insights if i.get("report_safe") is True]
    pool = safe if safe else list(insights)
    pool.sort(key=_severity_sort_key)
    return pool[:limit]


def _health_snapshot(analysis_result: dict) -> dict[str, Any]:
    out: dict[str, Any] = {}
    hr = analysis_result.get("health_result")
    if isinstance(hr, dict):
        hs = hr.get("health_score")
        if isinstance(hs, dict):
            out["grade"] = hs.get("grade")
            out["total_score"] = hs.get("total_score")
        warns = hr.get("health_warnings")
        if isinstance(warns, list) and warns:
            out["health_warnings_sample"] = [
                w for w in warns[:5] if isinstance(w, dict)
            ]
    hs2 = analysis_result.get("health_score")
    if isinstance(hs2, dict) and "total_score" not in out and "grade" not in out:
        out["legacy_total"] = hs2.get("total") or hs2.get("score")
        out["legacy_grade"] = hs2.get("grade")
    return out


def _cleaning_snapshot(analysis_result: dict) -> dict[str, Any]:
    cr = analysis_result.get("cleaning_result")
    if not isinstance(cr, dict):
        cs = analysis_result.get("cleaning_summary")
        return {"cleaning_summary": cs} if isinstance(cs, dict) else {}
    snap: dict[str, Any] = {}
    cs = cr.get("cleaning_summary")
    if isinstance(cs, dict):
        snap["cleaning_summary"] = cs
    sus = cr.get("suspicious_columns")
    if isinstance(sus, list):
        snap["suspicious_columns_count"] = len(sus)
        snap["suspicious_columns_sample"] = [
            x for x in sus[:5] if isinstance(x, dict)
        ]
    return snap


def _compact_insight(ins: dict) -> dict[str, Any]:
    title = ins.get("title") or ins.get("finding") or ins.get("explanation") or ""
    return {
        "severity": ins.get("severity"),
        "category": ins.get("category"),
        "report_safe": ins.get("report_safe"),
        "title": str(title)[:450],
        "evidence": str(ins.get("evidence") or "")[:450],
        "columns_used": ins.get("columns_used"),
        "recommendation": str(ins.get("recommendation") or "")[:350],
        "why_it_matters": str(ins.get("why_it_matters") or "")[:300],
        "caveats": ins.get("caveats"),
    }


def _build_structured_context(analysis_result: dict) -> dict[str, Any]:
    insights = _insights_list(analysis_result)
    top_safe = _top_report_safe_insights(insights, limit=8)
    risks_any = sorted(insights, key=_severity_sort_key)[:6]

    ctx: dict[str, Any] = {
        "dataset_summary": analysis_result.get("dataset_summary") or {},
        "health": _health_snapshot(analysis_result),
        "cleaning": _cleaning_snapshot(analysis_result),
        "pipeline_narrative_excerpt": str(analysis_result.get("narrative") or "")[:900],
        "top_report_safe_insights": [_compact_insight(i) for i in top_safe],
        "other_notable_insights": [_compact_insight(i) for i in risks_any if i not in top_safe][:4],
        "executive_panel": analysis_result.get("executive_panel"),
        "compare_result": analysis_result.get("compare_result"),
    }
    return ctx


def _build_story_prompt(analysis_result: dict) -> str:
    ctx = _build_structured_context(analysis_result)
    ctx_json = json.dumps(ctx, indent=2, default=str)[:14000]

    banned = ", ".join(f'"{p}"' for p in _BANNED_PHRASES[:8])
    return (
        "You are a principal analytics consultant preparing slides for a client working session.\n\n"
        "You MUST:\n"
        "- Use ONLY facts present in the JSON context below — cite concrete column names, metrics, "
        "percentages, row counts, or segments whenever possible.\n"
        "- Produce exactly 5 slides with slide_num 1 through 5 and the EXACT titles shown in the schema.\n"
        "- Give each slide exactly 3 key_points: short, specific bullets (no placeholders like 'TBD').\n"
        "- Avoid causal overclaiming: prefer 'associated with', 'concentrated in', 'higher rate in' unless "
        "the context explicitly states causality.\n"
        f"- Do NOT use empty corporate filler or phrases like: {banned}.\n\n"
        "Structured analysis context (JSON):\n"
        f"{ctx_json}\n\n"
        "Return ONLY valid JSON (no markdown fences, no commentary) with this structure:\n"
        f"{_STORY_SCHEMA}\n"
    )


def _clip(s: str, n: int) -> str:
    s = (s or "").strip()
    return s if len(s) <= n else s[: n - 1] + "…"


def _dedupe_points(points: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for p in points:
        t = str(p).strip()
        if not t or t.lower() in seen:
            continue
        seen.add(t.lower())
        out.append(t)
    return out


def deterministic_story_slides(analysis_result: dict) -> dict[str, Any]:
    """Five fixed-role slides with concrete copy when the AI path is unavailable."""
    ds = analysis_result.get("dataset_summary") or {}
    rows = ds.get("rows")
    cols = ds.get("columns")
    nc = ds.get("numeric_cols")
    cc = ds.get("categorical_cols")

    health = _health_snapshot(analysis_result)
    score = health.get("total_score")
    if score is None:
        score = health.get("legacy_total")
    grade = health.get("grade") or health.get("legacy_grade")

    cleaning = _cleaning_snapshot(analysis_result)
    steps = None
    if isinstance(cleaning.get("cleaning_summary"), dict):
        steps = cleaning["cleaning_summary"].get("steps_applied")
    sus_n = cleaning.get("suspicious_columns_count")

    insights = _insights_list(analysis_result)
    top_safe = _top_report_safe_insights(insights, limit=4)
    sorted_risk = sorted(insights, key=_severity_sort_key)
    risk_ins = next(
        (i for i in sorted_risk if i.get("report_safe") is False),
        sorted_risk[0] if sorted_risk else {},
    )

    ep = analysis_result.get("executive_panel")
    opp_title = ""
    risk_ep_title = ""
    action = ""
    if isinstance(ep, dict):
        opps = ep.get("opportunities") or []
        if isinstance(opps, list) and opps and isinstance(opps[0], dict):
            opp_title = str(opps[0].get("title") or opps[0].get("summary") or "")
        risks = ep.get("risks") or []
        if isinstance(risks, list) and risks and isinstance(risks[0], dict):
            risk_ep_title = str(risks[0].get("title") or risks[0].get("summary") or "")
        acts = ep.get("action_plan") or []
        if isinstance(acts, list) and acts and isinstance(acts[0], dict):
            action = str(acts[0].get("action") or acts[0].get("title") or "")

    def _ins_title(i: dict) -> str:
        return str(i.get("title") or i.get("finding") or i.get("explanation") or "").strip()

    def _cols(i: dict) -> str:
        cu = i.get("columns_used")
        if isinstance(cu, list) and cu:
            return ", ".join(str(c) for c in cu[:4])
        return ""

    top1 = top_safe[0] if top_safe else {}
    t1 = _ins_title(top1)
    c1 = _cols(top1)
    ev1 = str(top1.get("evidence") or "").strip()[:240]

    compare = analysis_result.get("compare_result")
    compare_bit = ""
    if isinstance(compare, dict):
        if isinstance(compare.get("summary_draft"), str) and compare["summary_draft"].strip():
            compare_bit = _clip(compare["summary_draft"], 280)
        else:
            rv = compare.get("row_volume_changes")
            if isinstance(rv, dict) and isinstance(rv.get("count_a"), int) and isinstance(rv.get("count_b"), int):
                compare_bit = (
                    f"Comparison files: {rv['count_a']:,} vs {rv['count_b']:,} rows"
                    f"{(' (Δ ' + str(rv.get('diff')) + ')') if rv.get('diff') is not None else ''}."
                )

    row_bits = []
    if isinstance(rows, int):
        row_bits.append(f"{rows:,} rows")
    if isinstance(cols, int):
        row_bits.append(f"{cols} columns")
    dataset_line = " and ".join(row_bits) if row_bits else "the loaded extract"
    if isinstance(nc, int) and isinstance(cc, int):
        dataset_line += f", spanning about {nc} numeric and {cc} categorical fields"

    ex_narrative = (
        f"The working dataset covers {dataset_line}. "
        + (f"{compare_bit} " if compare_bit else "")
        + (
            f"Primary signal to brief: {t1}."
            if t1
            else "Review generated findings in the analysis run to anchor this story."
        )
    )

    score_bit = ""
    if score is not None:
        try:
            score_bit = f"Health score {round(float(score))}/100"
        except (TypeError, ValueError):
            score_bit = f"Health score {score}/100"
        if grade:
            score_bit += f" (grade {grade})."
        else:
            score_bit += "."
    else:
        score_bit = "Health metrics were sparse — validate key fields before high-stakes decisions."

    warn_txt = ""
    ws = health.get("health_warnings_sample") or []
    if isinstance(ws, list) and ws:
        w0 = ws[0]
        if isinstance(w0, dict) and w0.get("message"):
            warn_txt = f" Warning flagged: {_clip(str(w0['message']), 140)}"

    clean_bit = ""
    if isinstance(steps, int) and steps > 0:
        clean_bit += f"{steps} automated cleaning step(s) ran."
    if isinstance(sus_n, int) and sus_n > 0:
        clean_bit += f" {sus_n} column(s) flagged during cleaning for review."

    q_narrative = (
        f"{score_bit}{warn_txt} "
        f"{clean_bit or 'Review the cleaning log for schema and type fixes before publishing numbers.'}"
    )

    opp_head = opp_title or t1 or "Prioritize the strongest report-ready signal from the findings tab."
    opp_body = ""
    if t1:
        opp_body = f"{t1}"
        if c1:
            opp_body += f" Fields involved include {c1}."
        if ev1:
            opp_body += f" Evidence excerpt: {ev1}"
    col_extra = _cols(top_safe[1]) if len(top_safe) > 1 else ""

    risk_head = risk_ep_title
    if not risk_head and risk_ins:
        risk_head = _ins_title(risk_ins) or "Data limitations"
    risk_narr = ""
    caveats: list[str] = []
    if risk_ins:
        c = risk_ins.get("caveats")
        if isinstance(c, list):
            caveats = [str(x) for x in c if x][:2]
        elif isinstance(c, str) and c.strip():
            caveats = [c.strip()]
        risk_narr = (
            f"Main caveat: {risk_head}. "
            f"{' '.join('Caveat: ' + cv + '.' for cv in caveats)}"
            if caveats
            else f"Watch {risk_head} — confirm definitions and sample coverage before acting."
        )
    else:
        risk_narr = "No single risk insight was ranked — still validate definitions, leakage from IDs, and missingness."

    recs: list[str] = []
    if action:
        recs.append(action)
    for ins in top_safe:
        r = ins.get("recommendation")
        if isinstance(r, str) and r.strip():
            recs.append(r.strip())
            break
    if isinstance(ep, dict):
        acts = ep.get("action_plan") or []
        if isinstance(acts, list) and len(acts) > 1 and isinstance(acts[1], dict):
            a2 = acts[1].get("action") or acts[1].get("title")
            if isinstance(a2, str) and a2.strip():
                recs.append(a2.strip())
    next_narr = (
        "Execution path: "
        + (
            "; ".join(_clip(r, 160) for r in recs[:2])
            if recs
            else "Agree one pilot metric with stakeholders, replicate numbers on a fresh extract, then scale."
        )
    )

    deck_title = (
        f"{_clip(t1 or opp_head, 45)} — data story"
        if (t1 or opp_head)
        else f"Data story ({rows or '?'} × {cols or '?'})"
    )

    def kp_dataset() -> list[str]:
        pts = [
            f"Dataset: {dataset_line}",
        ]
        if compare_bit:
            pts.append(_clip(compare_bit, 160))
        pts.append("Anchor numbers to the analysis run before client readout.")
        return _dedupe_points(pts)[:3]

    def kp_quality() -> list[str]:
        pts = [
            _clip(score_bit, 160),
            _clip(clean_bit or "Open the Cleaning step for what changed in types and missingness.", 160),
            _clip(warn_txt or "Spot-check ID-like columns and join keys.", 160),
        ]
        return _dedupe_points(pts)[:3]

    def kp_opp() -> list[str]:
        pts = [
            _clip(opp_head, 200),
        ]
        if c1:
            pts.append(f"Columns: {c1}")
        if col_extra:
            pts.append(f"Secondary angle: {col_extra}")
        if len(pts) < 3 and ev1:
            pts.append(_clip(ev1, 160))
        while len(pts) < 3:
            pts.append("Quantify impact with one agreed baseline segment.")
        return _dedupe_points(pts)[:3]

    def kp_risk() -> list[str]:
        pts = [_clip(risk_head, 200)]
        for cv in caveats:
            pts.append(_clip(cv, 160))
        while len(pts) < 3:
            pts.append("Treat correlations as associative until tested experimentally.")
        return _dedupe_points(pts)[:3]

    def kp_next() -> list[str]:
        pts = []
        for r in recs[:3]:
            pts.append(_clip(r, 200))
        while len(pts) < 3:
            pts.append("Schedule a replay on new data to confirm stability.")
        return _dedupe_points(pts)[:3]

    slides = [
        {
            "slide_num": 1,
            "title": STORY_SLIDE_TITLES[0],
            "narrative": _clip(ex_narrative, 720),
            "key_points": kp_dataset(),
        },
        {
            "slide_num": 2,
            "title": STORY_SLIDE_TITLES[1],
            "narrative": _clip(q_narrative, 720),
            "key_points": kp_quality(),
        },
        {
            "slide_num": 3,
            "title": STORY_SLIDE_TITLES[2],
            "narrative": _clip(
                f"{opp_head}. {opp_body}" if opp_body else opp_head,
                720,
            ),
            "key_points": kp_opp(),
        },
        {
            "slide_num": 4,
            "title": STORY_SLIDE_TITLES[3],
            "narrative": _clip(risk_narr, 720),
            "key_points": kp_risk(),
        },
        {
            "slide_num": 5,
            "title": STORY_SLIDE_TITLES[4],
            "narrative": _clip(next_narr, 720),
            "key_points": kp_next(),
        },
    ]

    for s in slides:
        kps = _dedupe_points([str(x) for x in s["key_points"] if str(x).strip()])
        while len(kps) < 3:
            kps.append("See analysis run for supporting detail.")
        s["key_points"] = kps[:3]

    return {"title": _clip(deck_title, 120), "slides": slides}


def _normalize_ai_story(
    raw: dict[str, Any] | None,
    analysis_result: dict,
) -> dict[str, Any]:
    """Enforce 5 slides, canonical titles, and 3 key points each."""
    fb = deterministic_story_slides(analysis_result)
    if not isinstance(raw, dict):
        return fb

    title = raw.get("title")
    if not isinstance(title, str) or len(title.strip()) < 3:
        title = fb["title"]
    title = _clip(title.strip(), 150)

    slides_in = raw.get("slides")
    if not isinstance(slides_in, list) or len(slides_in) != 5:
        return fb

    out_slides: list[dict[str, Any]] = []
    for i in range(5):
        s = slides_in[i] if isinstance(slides_in[i], dict) else {}
        nar = s.get("narrative")
        nar_fb = fb["slides"][i]["narrative"]
        narrative = _clip(str(nar).strip(), 900) if isinstance(nar, str) and nar.strip() else nar_fb

        kps_in = s.get("key_points")
        pts: list[str] = []
        if isinstance(kps_in, list):
            pts = _dedupe_points([str(x).strip() for x in kps_in if str(x).strip()])
        fb_pts = fb["slides"][i]["key_points"]
        merged: list[str] = []
        for j in range(3):
            if j < len(pts):
                merged.append(_clip(pts[j], 320))
            else:
                merged.append(fb_pts[j])
        out_slides.append(
            {
                "slide_num": i + 1,
                "title": STORY_SLIDE_TITLES[i],
                "narrative": narrative,
                "key_points": merged,
            }
        )

    for phrase in _BANNED_PHRASES:
        low = phrase.lower()
        if low in title.lower():
            title = fb["title"]
            break

    return {"title": title, "slides": out_slides}


def generate_data_story(analysis_result: dict) -> dict[str, Any]:
    """
    Return { title, slides } with exactly five slides and three key_points each.
    """
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not anthropic_key:
        return deterministic_story_slides(analysis_result)

    prompt = _build_story_prompt(analysis_result)

    try:
        import anthropic  # noqa: PLC0415

        client = anthropic.Anthropic(api_key=anthropic_key)
        response = client.messages.create(
            model=_STORY_MODEL,
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}],
        )
        text = response.content[0].text.strip()
        if text.startswith("```"):
            parts = text.split("```")
            text = parts[1] if len(parts) > 1 else text
            if text.lstrip().lower().startswith("json"):
                text = re.sub(r"^json\s*", "", text.lstrip(), flags=re.I)
        parsed = json.loads(text)
        return _normalize_ai_story(parsed, analysis_result)
    except ImportError:
        logger.warning("anthropic package not installed — deterministic data story")
    except json.JSONDecodeError as exc:
        logger.warning("Story JSON invalid (%s) — using normalized fallback", exc)
    except Exception as exc:
        logger.error(
            "Story generation failed (%s: %s) — deterministic fallback",
            type(exc).__name__,
            exc,
            exc_info=True,
        )

    return deterministic_story_slides(analysis_result)


__all__ = ["generate_data_story", "deterministic_story_slides", "STORY_SLIDE_TITLES"]
