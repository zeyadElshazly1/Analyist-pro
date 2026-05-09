"""88C — Executive panel respects plan hygiene and confidence gating."""
from __future__ import annotations

from app.services.analysis.orchestrator import generate_executive_panel


def test_suppressed_plan_finding_excluded_from_risks():
    insights = [
        {
            "type": "data_quality",
            "severity": "medium",
            "confidence": 70,
            "title": "order_date_month concentration",
            "finding": "order_date_month appears concentrated.",
            "action": "Investigate order_date_month.",
            "suppressed_by_plan": True,
            "plan_penalty_reason": "date_part_feature",
        }
    ]

    panel = generate_executive_panel(insights)

    assert panel["risks"] == []
    assert panel["action_plan"] == []


def test_low_confidence_finding_excluded_from_panel():
    insights = [
        {
            "type": "segment",
            "severity": "medium",
            "confidence": 35,
            "title": "Segment gap: region → revenue",
            "finding": "Possible weak segment gap.",
            "action": "Review region performance.",
        }
    ]

    panel = generate_executive_panel(insights)

    assert panel["opportunities"] == []
    assert panel["action_plan"] == []


def test_high_trust_opportunity_still_appears():
    insights = [
        {
            "type": "segment",
            "severity": "medium",
            "confidence": 80,
            "title": "Segment gap: region → revenue",
            "finding": "Region A outperforms Region B.",
            "action": "Prioritize Region A growth playbook.",
        }
    ]

    panel = generate_executive_panel(insights)

    assert len(panel["opportunities"]) == 1
    assert panel["opportunities"][0]["title"] == "Segment gap: region → revenue"
    assert len(panel["action_plan"]) == 1


def test_high_trust_risk_still_appears():
    insights = [
        {
            "type": "anomaly",
            "severity": "high",
            "confidence": 85,
            "title": "Anomalies in amount",
            "finding": "Several unusual amount values were detected.",
            "action": "Review anomalous rows before reporting.",
        }
    ]

    panel = generate_executive_panel(insights)

    assert len(panel["risks"]) == 1
    assert panel["risks"][0]["title"] == "Anomalies in amount"
    assert len(panel["action_plan"]) == 1


def test_executive_panel_filter_does_not_mutate_input():
    insight = {
        "type": "data_quality",
        "severity": "medium",
        "confidence": 25,
        "title": "Noisy finding",
        "finding": "Noisy finding.",
        "action": "Review.",
        "suppressed_by_plan": True,
    }

    before = dict(insight)
    generate_executive_panel([insight])

    assert insight == before
