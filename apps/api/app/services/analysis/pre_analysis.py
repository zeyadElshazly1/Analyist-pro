"""
90G — Pre-Analysis Profile composer.

Single entry point: build_pre_analysis_profile(df) → PreAnalysisProfile.
Wires fingerprint → column roles → grain → strategy → risks → hypotheses.
Pure orchestration; all sub-steps are deterministic and side-effect-free.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd

from app.schemas.pre_analysis import PreAnalysisProfile
from app.services.analysis.fingerprint import extract_dataset_fingerprint
from app.services.analysis.column_roles import classify_column_roles
from app.services.analysis.grain_detector import detect_grain
from app.services.analysis.strategy_builder import (
    build_analysis_strategy,
    detect_analysis_risks,
    build_hypothesis_plan,
)


def build_pre_analysis_profile(df: pd.DataFrame) -> PreAnalysisProfile:
    """Return a fully-populated :class:`PreAnalysisProfile` for *df*.

    Never raises; callers should wrap in try/except if best-effort behaviour
    is required (e.g. cache-hit backfill paths).
    """
    fingerprint = extract_dataset_fingerprint(df)
    column_roles = classify_column_roles(df, fingerprint)
    grain_label, grain_confidence = detect_grain(fingerprint, column_roles)
    strategy = build_analysis_strategy(fingerprint, column_roles, grain_label)
    risks = detect_analysis_risks(fingerprint, column_roles)
    hypothesis_plan = build_hypothesis_plan(fingerprint, column_roles, grain_label)

    return PreAnalysisProfile(
        fingerprint=fingerprint,
        column_roles=column_roles,
        grain_label=grain_label,
        grain_confidence=grain_confidence,
        strategy=strategy,
        risks=risks,
        hypothesis_plan=hypothesis_plan,
        generated_at=datetime.now(timezone.utc).isoformat(),
        planner_version="v2.0-deterministic",
    )
