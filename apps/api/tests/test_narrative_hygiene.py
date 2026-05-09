"""
88F — Narrative trust-awareness tests.

Verifies that generate_narrative() excludes plan-suppressed and
low-confidence insights from the generated text, and that the input
list is never mutated.
"""
from __future__ import annotations

import pandas as pd
import pytest

from app.services.analysis.narrative import generate_narrative, _is_narrative_eligible


# ── Unit tests for _is_narrative_eligible ─────────────────────────────────────

class TestIsNarrativeEligible:
    def test_clean_high_confidence_eligible(self):
        ins = {"type": "trend", "severity": "medium", "confidence": 80}
        assert _is_narrative_eligible(ins) is True

    def test_suppressed_by_plan_not_eligible(self):
        ins = {"type": "data_quality", "severity": "high", "confidence": 90, "suppressed_by_plan": True}
        assert _is_narrative_eligible(ins) is False

    def test_suppressed_false_is_eligible(self):
        ins = {"type": "trend", "severity": "medium", "confidence": 80, "suppressed_by_plan": False}
        assert _is_narrative_eligible(ins) is True

    def test_low_confidence_not_eligible(self):
        ins = {"type": "segment", "severity": "medium", "confidence": 35}
        assert _is_narrative_eligible(ins) is False

    def test_exactly_50_confidence_eligible(self):
        ins = {"type": "anomaly", "severity": "high", "confidence": 50}
        assert _is_narrative_eligible(ins) is True

    def test_49_confidence_not_eligible(self):
        ins = {"type": "anomaly", "severity": "high", "confidence": 49}
        assert _is_narrative_eligible(ins) is False

    def test_bad_confidence_type_defaults_to_50_eligible(self):
        ins = {"type": "trend", "severity": "low", "confidence": "invalid"}
        assert _is_narrative_eligible(ins) is True


# ── Integration tests for generate_narrative ──────────────────────────────────

class TestNarrativeHygiene:
    def test_suppressed_high_severity_finding_not_used_in_narrative_actions(self):
        df = pd.DataFrame({"revenue": [1, 2, 3], "order_date_month": [1, 1, 1]})
        insights = [
            {
                "type": "data_quality",
                "severity": "high",
                "confidence": 90,
                "title": "order_date_month concentration",
                "finding": "order_date_month appears concentrated.",
                "suppressed_by_plan": True,
                "plan_penalty_reason": "date_part_feature",
            },
            {
                "type": "trend",
                "severity": "medium",
                "confidence": 80,
                "title": "Revenue trend",
                "finding": "Revenue increased over time.",
            },
        ]

        narrative = generate_narrative(insights, df, total_found=len(insights))

        assert "order_date_month concentration" not in narrative
        assert "Revenue increased over time" in narrative

    def test_low_confidence_finding_not_used_in_narrative(self):
        df = pd.DataFrame({"revenue": [1, 2, 3]})
        insights = [
            {
                "type": "segment",
                "severity": "medium",
                "confidence": 35,
                "title": "Weak segment",
                "finding": "Weak possible segment gap.",
            }
        ]

        narrative = generate_narrative(insights, df, total_found=len(insights))

        assert "Weak segment" not in narrative
        assert "Weak possible segment gap" not in narrative

    def test_clean_high_confidence_finding_still_used(self):
        df = pd.DataFrame({"region": ["A", "B", "A"], "revenue": [10, 5, 12]})
        insights = [
            {
                "type": "segment",
                "severity": "medium",
                "confidence": 80,
                "title": "Segment gap: region → revenue",
                "finding": "Region A outperforms Region B.",
            }
        ]

        narrative = generate_narrative(insights, df, total_found=len(insights))

        assert "Region A outperforms Region B" in narrative

    def test_all_filtered_insights_produce_safe_fallback_narrative(self):
        df = pd.DataFrame({"x": [1, 2, 3]})
        insights = [
            {
                "type": "data_quality",
                "severity": "high",
                "confidence": 90,
                "title": "Noisy date part",
                "finding": "Noisy finding.",
                "suppressed_by_plan": True,
            }
        ]

        narrative = generate_narrative(insights, df, total_found=len(insights))

        assert "Noisy date part" not in narrative
        assert (
            "No urgent actions required" in narrative
            or "No strong relationships" in narrative
        )

    def test_narrative_filter_does_not_mutate_input(self):
        df = pd.DataFrame({"x": [1, 2, 3]})
        insight = {
            "type": "trend",
            "severity": "medium",
            "confidence": 20,
            "title": "Weak trend",
            "finding": "Weak trend.",
        }
        before = dict(insight)
        original_list = [insight]

        generate_narrative(original_list, df, total_found=1)

        assert insight == before
        assert original_list == [insight]

    def test_suppressed_insight_does_not_appear_in_high_sev_action(self):
        """Even if suppressed_by_plan is True, the title must not show up in para3."""
        df = pd.DataFrame({"a": [1, 2, 3]})
        insights = [
            {
                "type": "anomaly",
                "severity": "high",
                "confidence": 88,
                "title": "Suspicious anomaly in artifact_col",
                "finding": "artifact_col has outliers.",
                "suppressed_by_plan": True,
                "plan_penalty_reason": "ignored_column",
            }
        ]

        narrative = generate_narrative(insights, df, total_found=len(insights))

        assert "Suspicious anomaly in artifact_col" not in narrative

    def test_mixed_eligible_and_suppressed_only_eligible_mentioned(self):
        df = pd.DataFrame({"region": ["A", "B"], "revenue": [100, 50]})
        insights = [
            {
                "type": "data_quality",
                "severity": "high",
                "confidence": 95,
                "title": "Noisy date finding",
                "finding": "Date noise description.",
                "suppressed_by_plan": True,
            },
            {
                "type": "segment",
                "severity": "high",
                "confidence": 90,
                "title": "Segment gap: region → revenue",
                "finding": "Revenue differs across regions significantly.",
            },
        ]

        narrative = generate_narrative(insights, df, total_found=len(insights))

        assert "Date noise description" not in narrative
        assert "Revenue differs across regions significantly" in narrative

    def test_empty_insights_does_not_crash(self):
        df = pd.DataFrame({"x": [1, 2, 3]})
        narrative = generate_narrative([], df, total_found=0)
        assert isinstance(narrative, str)
        assert len(narrative) > 0
