"""Tests for client-safe deterministic executive summaries (Report Builder)."""

from __future__ import annotations

from app.services.reporting.executive_summary_draft import (
    build_fallback_executive_summary,
    build_structured_executive_summary,
)


def _telco_like_result() -> dict:
    return {
        "narrative": (
            "This dataset provides valuable insights into customer behavior and churn dynamics. "
            "We see important patterns throughout."
        ),
        "dataset_summary": {
            "rows": 7043,
            "columns": 21,
            "numeric_cols": 4,
            "categorical_cols": 17,
        },
        "health_result": {
            "health_score": {"grade": "B", "total_score": 72},
        },
        "cleaning_result": {
            "cleaning_summary": {"steps_applied": 4},
            "suspicious_columns": [{"column": "customerID", "issue_type": "id_like"}],
        },
        "insight_results": [
            {
                "title": "Churn rate is elevated among senior citizens versus non-seniors",
                "severity": "high",
                "category": "binary_rates",
                "columns_used": ["SeniorCitizen", "Churn"],
                "evidence": (
                    "Non-seniors churn about 24% in-sample; seniors about 45% "
                    "(counts 80 vs 20 in this extract)."
                ),
                "recommendation": (
                    "Pilot retention offers for senior customers on month-to-month fiber plans "
                    "before broad rollout."
                ),
                "report_safe": True,
                "caveats": ["Rates are descriptive; test incentives with a controlled experiment."],
            },
            {
                "title": "Electronic check payers show higher churn than automatic card payers",
                "severity": "medium",
                "category": "binary_rates",
                "columns_used": ["PaymentMethod", "Churn"],
                "evidence": "Gap ~8–12 points in comparable tenure bands in holding sample.",
                "report_safe": True,
            },
        ],
        "executive_panel": {
            "opportunities": [
                {
                    "title": "Seniors on fiber show concentrated churn risk",
                    "summary": "Worth targeted outreach",
                    "severity": "high",
                },
            ],
            "action_plan": [
                {
                    "action": "Run a 90-day senior retention pilot with two offer variants",
                    "reason": "Risk is concentrated and measurable in current data",
                },
            ],
        },
        "compare_result": {
            "row_volume_changes": {"count_a": 7000, "count_b": 7400, "diff": 400},
        },
    }


def test_telco_churn_summary_replaces_generic_narrative_and_uses_specifics():
    text = build_fallback_executive_summary(_telco_like_result())
    low = text.lower()
    assert "valuable insights" not in low
    assert "7,043" in text or "7043" in text
    assert "senior" in low or "churn" in low
    assert "associated" in low
    assert "Recommended next step" in text
    assert "caveats" in low or "Rates are descriptive" in text


def test_insurance_claims_summary():
    result = {
        "narrative": "Short overview only.",
        "dataset_summary": {
            "rows": 125_000,
            "columns": 42,
            "numeric_cols": 18,
            "categorical_cols": 24,
        },
        "health_result": {"health_score": {"grade": "C", "total_score": 54}},
        "cleaning_result": {
            "cleaning_summary": {"steps_applied": 7},
        },
        "insight_results": [
            {
                "title": (
                    "Claim frequency in the Coastal region is about 1.4× the inland baseline "
                    "after controlling for policy age band"
                ),
                "severity": "high",
                "category": "rate_comparison",
                "columns_used": ["region", "claim_count", "policy_tenure_months"],
                "evidence": "Coastal mean 0.31 claims/policy-year vs inland 0.22 (FY24 policies).",
                "recommendation": (
                    "Partner with underwriting to review coastal pricing and storm exposure "
                    "assumptions in the next renewal cycle."
                ),
                "why_it_matters": "Premium inadequacy may emerge if loss costs drift upward.",
                "report_safe": True,
            },
            {
                "title": "Missing driver-age on ~6% of rows limits age-stratified reporting",
                "severity": "medium",
                "category": "missing_pattern",
                "columns_used": ["driver_age"],
                "evidence": "6.1% null on driver_age; higher in legacy policy imports.",
                "report_safe": False,
            },
        ],
        "executive_panel": {
            "risks": [
                {
                    "title": "Regional loss ratio dispersion",
                    "summary": "Coastal corridor driving frequency anomalies",
                    "severity": "high",
                },
            ],
        },
    }
    text = build_structured_executive_summary(result)
    assert "125,000" in text or "125000" in text
    assert "coastal" in text.lower()
    assert "1.4" in text or "claim" in text.lower()
    assert "associated" in text.lower()
    assert "recommended next step" in text.lower()
    assert "report-safe" in text.lower() or "not marked report-safe" in text.lower()


def test_empty_and_weak_insight_fallback():
    result = {
        "narrative": "",
        "dataset_summary": {"rows": 500, "columns": 8},
        "insight_results": [],
    }
    text = build_structured_executive_summary(result)
    assert "500" in text
    assert "No ranked findings" in text
    assert "Recommended next step" in text

    sparse = build_fallback_executive_summary(
        {"narrative": "", "dataset_summary": {"rows": 10, "columns": 2}, "insight_results": [{}]},
    )
    assert "Recommended next step" in sparse
    assert "could not be summarised" in sparse.lower()


def test_strong_narrative_preserved():
    specific = (
        "Retention among Month-to-month contracts slipped to 61% in Q3 (n=4,200 policies), "
        "while Two-year contracts held at 94%. Electronic-check payers churned 11 points higher "
        "than bank-transfer auto-debit in the same cohort—finance should scenario-plan a 2% "
        "revenue-at-risk band before renewal pricing."
    )
    out = build_fallback_executive_summary({"narrative": specific, "insight_results": []})
    assert out == specific[:8000]


def test_generic_but_long_narrative_is_rewritten():
    fluff = (
        "This dataset provides valuable insights and important patterns across segments. "
        "We should delve deeper into comprehensive overview of behavior. " * 3
    )
    assert len(fluff) > 160
    out = build_fallback_executive_summary({"narrative": fluff, "dataset_summary": {"rows": 100, "columns": 5}})
    assert "valuable insights" not in out.lower()
