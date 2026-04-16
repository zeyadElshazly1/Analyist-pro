"""
Dataset type classifier.

BUG FIX: The original profiler.py used a single rule:
    if datetime_cols and numeric_cols: return "timeseries"

This mislabelled any dataset that happened to contain a date field AND a
numeric column (e.g. employee table with hire_date + salary) as "timeseries".

This module replaces that rule with a multi-signal scoring model that weighs:
  - Whether timestamps are dense (most rows have a distinct datetime)
  - Whether a transaction ID column is present
  - Whether financial columns (amount, price, revenue…) are present
  - Whether most string columns have low cardinality (survey-like)
  - Keyword patterns in column names

Returns a (dataset_type, confidence_pct) tuple so callers can expose
confidence to users.
"""
import numpy as np
import pandas as pd


def _detect_dataset_type(df: pd.DataFrame) -> tuple[str, int]:
    """
    Infer the dataset's domain type using a scoring model.

    Returns
    -------
    (dataset_type, confidence_pct)
        dataset_type : "timeseries" | "transactional" | "survey" | "general"
        confidence_pct : int in [40, 95]
    """
    scores: dict[str, int] = {
        "timeseries":    0,
        "transactional": 0,
        "survey":        0,
        "general":       0,
    }

    datetime_cols = df.select_dtypes(include=["datetime64"]).columns
    numeric_cols  = df.select_dtypes(include=[np.number]).columns
    object_cols   = df.select_dtypes(include=["object", "category"]).columns

    n_rows = max(len(df), 1)

    # ── Timeseries signals ────────────────────────────────────────────────────
    for col in datetime_cols:
        unique_ratio = df[col].nunique() / n_rows
        if unique_ratio > 0.5:
            # Most rows have a distinct timestamp → true time-ordered events
            scores["timeseries"] += 3
        else:
            # Date column present but low cardinality (e.g. hire_date repeats)
            scores["timeseries"] += 1

    # ── Transactional signals ─────────────────────────────────────────────────
    _TX_KEYWORDS = {"id", "order", "transaction", "invoice", "receipt", "ticket"}
    _AMT_KEYWORDS = {"amount", "price", "revenue", "cost", "qty", "quantity", "total", "sale"}

    for col in df.columns:
        col_lower = col.lower()
        unique_ratio = df[col].nunique() / n_rows
        # High-cardinality ID-like column → strong transactional signal
        # Also penalise timeseries for having a transaction ID
        if unique_ratio > 0.9 and any(kw in col_lower for kw in _TX_KEYWORDS):
            scores["transactional"] += 3
            scores["timeseries"]    -= 2  # ID column breaks time-series logic

    for col in numeric_cols:
        if any(kw in col.lower() for kw in _AMT_KEYWORDS):
            scores["transactional"] += 1

    # ── Survey signals ────────────────────────────────────────────────────────
    _SURVEY_KEYWORDS = {
        "rating", "score", "response", "satisfaction",
        "agree", "disagree", "rank", "feedback", "opinion",
    }
    if len(object_cols) > 0:
        low_card = sum(1 for col in object_cols if df[col].nunique() <= 10)
        if low_card / len(object_cols) > 0.5:
            scores["survey"] += 2

    if any(kw in col.lower() for col in df.columns for kw in _SURVEY_KEYWORDS):
        scores["survey"] += 2

    # ── General baseline ──────────────────────────────────────────────────────
    # If nothing fires strongly, "general" wins by tiebreak
    scores["general"] = 0  # kept at 0; wins only when all others are ≤ 0

    # ── Pick winner ───────────────────────────────────────────────────────────
    best = max(scores, key=scores.get)
    best_score = scores[best]

    # Confidence: proportion of total absolute signal that went to winner
    total_signals = sum(abs(v) for v in scores.values())
    if total_signals == 0 or best_score <= 0:
        return "general", 40

    confidence = round(min(95, max(40, best_score / total_signals * 100 + 40)))
    return best, int(confidence)
