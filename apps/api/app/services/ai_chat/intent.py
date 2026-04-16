"""
Query intent detector.

detect_intent(message) → str

Routes user messages to one of the recognised intents so the engine can
choose an appropriate system-prompt flavour and the fallback engine can pick
the right local computation.
"""
from __future__ import annotations

# Ordered list of (intent, trigger_patterns).
# First match wins — put more specific intents before broader ones.
_INTENT_PATTERNS: list[tuple[str, list[str]]] = [
    ("story",   ["story", "slide", "presentation", "executive", "deck", "report"]),
    ("shape",   ["how many rows", "row count", "how big", "size of", "shape"]),
    ("schema",  ["what column", "list column", "which column", "what field", "what variable", "column name"]),
    ("missing", ["missing", "null", "nan", "empty", "incomplete", "no value"]),
    ("trend",   ["trend", "over time", "monthly", "weekly", "daily", "seasonal", "time series"]),
    ("corr",    ["correlat", "relationship between", "related to", "associat", "depend on"]),
    ("anomaly", ["anomal", "outlier", "unusual", "strange", "weird", "spike", "unexpected"]),
    ("top",     ["top ", "bottom ", "highest ", "lowest ", "most ", "least ", "rank", "best ", "worst "]),
    ("group",   [" by region", " by month", " by year", " by category", " by group",
                 "group by", "segment by", "split by", "breakdown", "per region",
                 "per month", "per category", "grouped", "compare "]),
    ("mean",    ["average", "mean of", "median of", "typical", "central"]),
    ("summary", ["summary", "describe", "overview", "statistic", "stat", "summarize", "summarise"]),
    ("predict", ["predict", "forecast", "estimate", "classify", "model"]),
]


def detect_intent(message: str) -> str:
    """
    Return the first matching intent from _INTENT_PATTERNS, or 'general'.

    Intent is used to:
      - Tailor the LLM system prompt (e.g., "focus on groupby" for 'group')
      - Route the fallback engine to the right local computation
      - Include in the response payload for frontend use
    """
    msg = message.lower()
    for intent, patterns in _INTENT_PATTERNS:
        if any(p in msg for p in patterns):
            return intent
    return "general"
