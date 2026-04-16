"""
Data story generator.

generate_data_story(analysis_result) → dict

Uses Claude to generate a structured 5-slide data story from an analysis result.
Falls back to a rule-based story when no Anthropic key is configured.
"""
from __future__ import annotations

import json
import logging
import os

logger = logging.getLogger(__name__)

_STORY_MODEL = os.environ.get("CLAUDE_STORY_MODEL", "claude-sonnet-4-6")

_STORY_SCHEMA = """{
  "title": "A compelling title for this data story (max 10 words)",
  "slides": [
    {
      "slide_num": 1,
      "title": "Executive Summary",
      "narrative": "2-3 sentence overview of the dataset and headline finding",
      "key_points": ["point 1", "point 2", "point 3"]
    },
    {
      "slide_num": 2,
      "title": "Key Findings",
      "narrative": "2-3 sentences describing the top statistical findings",
      "key_points": ["finding 1", "finding 2", "finding 3"]
    },
    {
      "slide_num": 3,
      "title": "Deep Dive",
      "narrative": "2-3 sentences on the most interesting or unexpected pattern",
      "key_points": ["detail 1", "detail 2", "detail 3"]
    },
    {
      "slide_num": 4,
      "title": "Recommendations",
      "narrative": "2-3 sentences on concrete actions based on the data",
      "key_points": ["action 1", "action 2", "action 3"]
    },
    {
      "slide_num": 5,
      "title": "Next Steps",
      "narrative": "2-3 sentences on what to analyze next or what data to collect",
      "key_points": ["next step 1", "next step 2", "next step 3"]
    }
  ]
}"""


def _build_story_prompt(analysis_result: dict) -> str:
    summary   = analysis_result.get("dataset_summary", {})
    health    = analysis_result.get("health_score", {})
    insights  = analysis_result.get("insights", [])[:8]
    narrative = analysis_result.get("narrative", "")

    context_lines = [
        f"Dataset: {summary.get('rows', '?')} rows × {summary.get('columns', '?')} columns",
        f"Health score: {health.get('total', health.get('overall', '?'))}/100",
        f"Missing data: {summary.get('missing_pct', 0):.1f}%",
        "",
        "Top insights:",
    ]
    for ins in insights:
        context_lines.append(
            f"- [{ins.get('severity', '').upper()}] "
            f"{ins.get('finding', ins.get('title', ''))}"
        )
    if narrative:
        context_lines.append(f"\nNarrative summary:\n{narrative[:600]}")

    context = "\n".join(context_lines)
    return (
        f"You are a senior data analyst. Based on this dataset analysis, "
        f"generate a concise 5-slide data story in JSON format.\n\n"
        f"Analysis context:\n{context}\n\n"
        f"Return ONLY valid JSON with this exact structure (no markdown, no explanation):\n"
        f"{_STORY_SCHEMA}"
    )


def _rule_based_story(analysis_result: dict) -> dict:
    summary   = analysis_result.get("dataset_summary", {})
    health    = analysis_result.get("health_score", {})
    insights  = analysis_result.get("insights", [])[:3]
    narrative = analysis_result.get("narrative", "")

    finding_texts = [i.get("finding", i.get("title", "")) for i in insights]
    action_texts  = [i.get("action", "") for i in insights if i.get("action")]
    score_label   = health.get("total", health.get("overall", "?"))

    return {
        "title": f"Data Story: {summary.get('columns', '?')}-Column Dataset Analysis",
        "slides": [
            {
                "slide_num": 1,
                "title": "Executive Summary",
                "narrative": (
                    narrative[:300] if narrative
                    else (
                        f"This dataset contains {summary.get('rows', '?')} rows and "
                        f"{summary.get('columns', '?')} columns with a health score of "
                        f"{score_label}/100."
                    )
                ),
                "key_points": [
                    f"{summary.get('rows', '?')} total records",
                    f"{summary.get('numeric_cols', '?')} numeric columns",
                    f"Health score: {score_label}/100",
                ],
            },
            {
                "slide_num": 2,
                "title": "Key Findings",
                "narrative": "The analysis identified several statistically significant patterns in the dataset.",
                "key_points": finding_texts[:3] or ["No high-severity insights detected."],
            },
            {
                "slide_num": 3,
                "title": "Deep Dive",
                "narrative": "The most interesting pattern involves the relationship between key variables.",
                "key_points": (
                    [i.get("evidence", "") for i in insights[:3] if i.get("evidence")]
                    or ["Run the full analysis for detailed statistical evidence."]
                ),
            },
            {
                "slide_num": 4,
                "title": "Recommendations",
                "narrative": "Based on the findings, the following actions are recommended.",
                "key_points": action_texts[:3] or ["Set ANTHROPIC_API_KEY for AI-powered recommendations."],
            },
            {
                "slide_num": 5,
                "title": "Next Steps",
                "narrative": "To deepen the analysis, consider exploring additional dimensions of the data.",
                "key_points": [
                    "Run correlation analysis to identify variable relationships",
                    "Apply ML predictions to forecast key metrics",
                    "Segment data by category columns to find group differences",
                ],
            },
        ],
    }


def generate_data_story(analysis_result: dict) -> dict:
    """
    Use Claude to generate a structured 5-slide data story from an analysis result.
    Returns: { title, slides: [{slide_num, title, narrative, key_points}] }
    Falls back to a rule-based story if no API key is configured or the call fails.
    """
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not anthropic_key:
        return _rule_based_story(analysis_result)

    prompt = _build_story_prompt(analysis_result)

    try:
        import anthropic  # noqa: PLC0415
        client   = anthropic.Anthropic(api_key=anthropic_key)
        response = client.messages.create(
            model=_STORY_MODEL,
            max_tokens=2048,
            messages=[{"role": "user", "content": prompt}],
        )
        text = response.content[0].text.strip()
        # Strip any accidental markdown fences
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        return json.loads(text)
    except ImportError:
        logger.warning("anthropic package not installed — falling back to rule-based story")
    except json.JSONDecodeError as exc:
        logger.warning("Story generation returned invalid JSON: %s — using rule-based fallback", exc)
    except Exception as exc:
        logger.error(
            "Story generation failed (%s: %s) — using rule-based fallback",
            type(exc).__name__, exc, exc_info=True,
        )

    return _rule_based_story(analysis_result)
