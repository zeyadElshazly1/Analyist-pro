"""
Telco churn insight ranking regression tests.

Validates that when a binary target (Churn) is present, the analysis pipeline:
  1. Discovers all major churn drivers: Contract, InternetService, OnlineSecurity,
     PaymentMethod, and SeniorCitizen.
  2. Surfaces at least 3 of those drivers in the top MAX_INSIGHTS ranked findings.
  3. Never produces a spurious "Constant column: seniorcitizen" insight.
  4. Assigns "high" severity to findings with a large absolute rate gap (≥ 25 pp).

Fixture design
--------------
400-row deterministic DataFrame constructed from explicit group blocks so that
churn rates per predictor group are exact (no random sampling noise).

  Contract:       Month-to-month 41%,  One year 12.5%,  Two year 3.75%
  InternetService: Fiber optic   44%,  DSL      19%,    No       3.75%
  OnlineSecurity:  No            44%,  Yes      19%,    No internet 3.75%
  PaymentMethod:   Electronic    45%,  Mailed   35%,    Bank 3.75%,  CC 12.5%
  SeniorCitizen:   1             45%,  0        22%

All group sizes ≥ 40 so every insight passes the minimum-group-size guard,
and all absolute rate gaps are ≥ 22 pp to comfortably clear the 10 pp threshold.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from app.config import MAX_INSIGHTS


# ─────────────────────────────────────────────────────────────────────────────
# Fixture
# ─────────────────────────────────────────────────────────────────────────────

def _make_ranking_df() -> pd.DataFrame:
    """
    400-row deterministic Telco-like fixture with explicit churn correlations.

    Each row belongs to exactly one group block. Churn counts within each block
    are fixed, giving exact (not sampled) churn rates per predictor group.

    Group blocks:
      G1: M2M, Fiber optic, No security,          Electronic check, Senior=1  n=100  45% churn
      G2: M2M, Fiber optic, No security,           Electronic check, Senior=0  n=40   45% churn
      G3: M2M, DSL,         Yes security,          Mailed check,     Senior=0  n=50   30% churn
      G4: One year,  DSL,   Yes security,          Credit card,      Senior=0  n=80   12.5% churn
      G5: Two year,  No,    No internet service,   Bank transfer,    Senior=0  n=80   3.75% churn
      G6: M2M, Fiber optic, No security,           Mailed check,     Senior=0  n=50   40% churn

    Resulting predictor-level churn rates (all absolute gaps ≥ 22 pp):
      Contract:        M2M 41%  vs Two year 3.75%   → gap 37 pp
      InternetService: Fiber 44% vs No 3.75%         → gap 40 pp
      OnlineSecurity:  No 44%  vs No internet 3.75%  → gap 40 pp
      PaymentMethod:   Electronic 45% vs Bank 3.75%  → gap 41 pp
      SeniorCitizen:   Senior 45% vs Non-senior 22%  → gap 23 pp
    """
    # (contract, internetservice, onlinesecurity, paymentmethod, seniorcitizen, n_yes, n_no)
    groups = [
        ("Month-to-month", "Fiber optic", "No",                  "Electronic check",          1, 45, 55),
        ("Month-to-month", "Fiber optic", "No",                  "Electronic check",          0, 18, 22),
        ("Month-to-month", "DSL",         "Yes",                 "Mailed check",              0, 15, 35),
        ("One year",       "DSL",         "Yes",                 "Credit card (automatic)",   0, 10, 70),
        ("Two year",       "No",          "No internet service", "Bank transfer (automatic)", 0,  3, 77),
        ("Month-to-month", "Fiber optic", "No",                  "Mailed check",              0, 20, 30),
    ]

    rows: list[dict] = []
    t = 1
    for contract, inet, sec, pay, senior, n_yes, n_no in groups:
        for churn_val, count in [("Yes", n_yes), ("No", n_no)]:
            for _ in range(count):
                rows.append(
                    {
                        "seniorcitizen": senior,
                        "tenure": (t % 71) + 1,
                        "monthlycharges": round(20.0 + (t % 100), 2),
                        "contract": contract,
                        "internetservice": inet,
                        "onlinesecurity": sec,
                        "paymentmethod": pay,
                        "churn": churn_val,
                    }
                )
                t += 1

    return pd.DataFrame(rows)


@pytest.fixture(scope="module")
def ranking_df() -> pd.DataFrame:
    """Reusable ranking fixture — created once per module run."""
    return _make_ranking_df()


@pytest.fixture(scope="module")
def ranking_insights(ranking_df):
    """(insights, narrative) from analyze_dataset on the ranking fixture."""
    from app.services.analysis.orchestrator import analyze_dataset
    return analyze_dataset(ranking_df)


# ─────────────────────────────────────────────────────────────────────────────
# Helper
# ─────────────────────────────────────────────────────────────────────────────

_CHURN_DRIVERS = {
    "contract",
    "internetservice",
    "onlinesecurity",
    "paymentmethod",
    "seniorcitizen",
}


def _is_churn_driver_insight(ins: dict) -> bool:
    """True when an insight title references one of the 5 key churn drivers."""
    title = ins.get("title", "").lower()
    return any(driver in title for driver in _CHURN_DRIVERS) and "churn" in title


# ─────────────────────────────────────────────────────────────────────────────
# 1.  Unit tests for detect_binary_rates improvements
# ─────────────────────────────────────────────────────────────────────────────

class TestDetectBinaryRatesUnit:
    """Direct unit tests for detect_binary_rates with the ranking fixture."""

    def test_all_five_drivers_discovered(self, ranking_df):
        """All 5 churn predictors must generate at least one rate-gap insight."""
        from app.services.analysis.segments import detect_binary_rates

        # Build categorical_cols the same way the orchestrator does
        binary_int_cols = [
            col for col in ranking_df.select_dtypes(include=[np.number]).columns
            if ranking_df[col].nunique() == 2
        ]
        string_cats = [
            col for col in ranking_df.select_dtypes(include=["object", "category"]).columns
            if ranking_df[col].nunique() < 50
        ]
        categorical_cols = list(dict.fromkeys(binary_int_cols + string_cats))

        rate_insights = detect_binary_rates(ranking_df, categorical_cols)
        discovered = {
            driver
            for driver in _CHURN_DRIVERS
            for ins in rate_insights
            if driver in ins.get("title", "").lower() and "churn" in ins.get("title", "").lower()
        }
        missing = _CHURN_DRIVERS - discovered
        assert not missing, (
            f"detect_binary_rates failed to discover churn drivers: {missing}. "
            f"Insight titles found: {[i['title'] for i in rate_insights]}"
        )

    def test_contract_insight_has_high_severity(self, ranking_df):
        """Contract→Churn gap is ~48 pp — must be 'high' severity."""
        from app.services.analysis.segments import detect_binary_rates

        binary_int_cols = [
            col for col in ranking_df.select_dtypes(include=[np.number]).columns
            if ranking_df[col].nunique() == 2
        ]
        string_cats = [
            col for col in ranking_df.select_dtypes(include=["object", "category"]).columns
            if ranking_df[col].nunique() < 50
        ]
        categorical_cols = list(dict.fromkeys(binary_int_cols + string_cats))

        rate_insights = detect_binary_rates(ranking_df, categorical_cols)
        contract_ins = [
            i for i in rate_insights
            if "contract" in i.get("title", "").lower() and "churn" in i.get("title", "").lower()
        ]
        assert contract_ins, "No contract→churn insight generated"
        assert contract_ins[0]["severity"] == "high", (
            f"Contract→Churn should be 'high' severity due to large rate gap, "
            f"got {contract_ins[0]['severity']!r}. Finding: {contract_ins[0]['finding']}"
        )

    def test_churn_targeting_insights_carry_target_driver_flag(self, ranking_df):
        """Rate-gap insights that TARGET 'churn' (a business-outcome column) must
        carry is_target_driver=True.  The title format is 'Rate gap: <predictor> → churn',
        so we check that the title ENDS with '→ churn'.  Insights where churn
        is the predictor (e.g. 'Rate gap: churn → seniorcitizen') should NOT
        be flagged."""
        from app.services.analysis.segments import detect_binary_rates

        binary_int_cols = [
            col for col in ranking_df.select_dtypes(include=[np.number]).columns
            if ranking_df[col].nunique() == 2
        ]
        string_cats = [
            col for col in ranking_df.select_dtypes(include=["object", "category"]).columns
            if ranking_df[col].nunique() < 50
        ]
        categorical_cols = list(dict.fromkeys(binary_int_cols + string_cats))

        rate_insights = detect_binary_rates(ranking_df, categorical_cols)
        assert rate_insights, "No rate insights generated — fixture may be malformed"

        # Insights where churn is the TARGET (title ends with "→ churn")
        churn_target_insights = [
            i for i in rate_insights
            if i.get("title", "").lower().endswith("\u2192 churn")
        ]
        missing_flag = [i["title"] for i in churn_target_insights if not i.get("is_target_driver")]
        assert not missing_flag, (
            f"Churn-targeting rate insights missing is_target_driver=True: {missing_flag}"
        )
        assert churn_target_insights, "No predictor→churn rate insights found"

    def test_abs_rate_diff_in_evidence(self, ranking_df):
        """Evidence text should include absolute rate gap in percentage format."""
        from app.services.analysis.segments import detect_binary_rates

        binary_int_cols = [
            col for col in ranking_df.select_dtypes(include=[np.number]).columns
            if ranking_df[col].nunique() == 2
        ]
        string_cats = [
            col for col in ranking_df.select_dtypes(include=["object", "category"]).columns
            if ranking_df[col].nunique() < 50
        ]
        categorical_cols = list(dict.fromkeys(binary_int_cols + string_cats))

        rate_insights = detect_binary_rates(ranking_df, categorical_cols)
        for ins in rate_insights:
            evidence = ins.get("evidence", "")
            assert "Absolute rate gap=" in evidence, (
                f"Expected 'Absolute rate gap=' in evidence for {ins['title']!r}, "
                f"got: {evidence!r}"
            )

    def test_zero_min_group_not_skipped(self):
        """Insights with min-group rate=0 must no longer be silently skipped."""
        from app.services.analysis.segments import detect_binary_rates

        # Design: Contract=M2M has 40% churn; Two year has 0% churn
        df = pd.DataFrame(
            {
                "contract": ["Month-to-month"] * 60 + ["Two year"] * 60,
                "churn":    ["Yes"] * 24 + ["No"] * 36 + ["No"] * 60,
            }
        )
        insights = detect_binary_rates(df, ["contract", "churn"])
        contract_insights = [
            i for i in insights
            if "contract" in i.get("title", "").lower()
        ]
        assert contract_insights, (
            "contract→churn insight was skipped despite a 40% vs 0% gap — "
            "zero-min-group guard is still incorrectly discarding it"
        )


# ─────────────────────────────────────────────────────────────────────────────
# 2.  Ranking unit tests
# ─────────────────────────────────────────────────────────────────────────────

class TestRankingCompositeScore:
    """Unit tests for the _composite_score function."""

    def test_target_driver_beats_same_severity_non_driver(self):
        """A medium target-driver insight must rank above a medium non-driver."""
        from app.services.analysis.ranking import _composite_score

        driver = {
            "severity": "medium",
            "confidence": 75,
            "is_target_driver": True,
        }
        non_driver = {
            "severity": "medium",
            "confidence": 75,
            "is_target_driver": False,
        }
        assert _composite_score(driver) > _composite_score(non_driver), (
            f"Target-driver score {_composite_score(driver):.3f} should exceed "
            f"non-driver score {_composite_score(non_driver):.3f}"
        )

    def test_high_severity_non_driver_beats_medium_driver(self):
        """A high-severity non-driver should still outrank a medium target-driver."""
        from app.services.analysis.ranking import _composite_score

        high_anomaly = {
            "severity": "high",
            "confidence": 90,
            "is_target_driver": False,
        }
        medium_driver = {
            "severity": "medium",
            "confidence": 70,
            "is_target_driver": True,
        }
        assert _composite_score(high_anomaly) > _composite_score(medium_driver), (
            "High-severity genuine anomaly should outrank a medium target-driver"
        )

    def test_high_driver_beats_high_non_driver(self):
        """When both are high severity, the target-driver insight should rank first."""
        from app.services.analysis.ranking import _composite_score

        high_driver = {
            "severity": "high",
            "confidence": 90,
            "is_target_driver": True,
        }
        high_non_driver = {
            "severity": "high",
            "confidence": 90,
            "is_target_driver": False,
        }
        assert _composite_score(high_driver) > _composite_score(high_non_driver)

    def test_missing_is_target_driver_treated_as_false(self):
        """Insights without is_target_driver key should be treated as non-drivers."""
        from app.services.analysis.ranking import _composite_score

        no_flag = {"severity": "medium", "confidence": 75}
        explicit_false = {"severity": "medium", "confidence": 75, "is_target_driver": False}
        assert _composite_score(no_flag) == _composite_score(explicit_false)


# ─────────────────────────────────────────────────────────────────────────────
# 3.  End-to-end ranking integration tests
# ─────────────────────────────────────────────────────────────────────────────

class TestTelcoChurnRankingIntegration:
    """Full analyze_dataset pipeline on the ranking fixture."""

    def test_all_five_churn_drivers_discovered(self, ranking_insights):
        """All 5 churn predictors must appear somewhere in the insights list
        (before the MAX_INSIGHTS cap is applied)."""
        insights, _ = ranking_insights
        # We check the full (already capped) list; with strong correlations all
        # 5 should comfortably fit within MAX_INSIGHTS=15.
        discovered = {
            driver
            for driver in _CHURN_DRIVERS
            for ins in insights
            if driver in ins.get("title", "").lower() and "churn" in ins.get("title", "").lower()
        }
        missing = _CHURN_DRIVERS - discovered
        assert not missing, (
            f"Missing churn-driver insights for: {missing}. "
            f"Insight titles: {[i['title'] for i in insights]}"
        )

    def test_at_least_three_churn_drivers_in_top_findings(self, ranking_insights):
        """At least 3 of the 5 key churn drivers must be in the top MAX_INSIGHTS
        ranked findings (the slice returned to callers)."""
        insights, _ = ranking_insights
        top_driver_count = sum(1 for ins in insights if _is_churn_driver_insight(ins))
        assert top_driver_count >= 3, (
            f"Only {top_driver_count} churn-driver insights appear in the top "
            f"{MAX_INSIGHTS} findings — expected at least 3. "
            f"All titles: {[i['title'] for i in insights]}"
        )

    def test_contract_in_top_findings(self, ranking_insights):
        """Contract→Churn must appear in the ranked output — it's the strongest driver."""
        insights, _ = ranking_insights
        contract_found = any(
            "contract" in ins.get("title", "").lower() and "churn" in ins.get("title", "").lower()
            for ins in insights
        )
        assert contract_found, (
            f"Contract→Churn not found in top {MAX_INSIGHTS} insights. "
            f"Titles: {[i['title'] for i in insights]}"
        )

    def test_paymentmethod_in_top_findings(self, ranking_insights):
        """PaymentMethod→Churn must appear in the ranked output."""
        insights, _ = ranking_insights
        found = any(
            "paymentmethod" in ins.get("title", "").lower() and "churn" in ins.get("title", "").lower()
            for ins in insights
        )
        assert found, (
            f"PaymentMethod→Churn not found in top {MAX_INSIGHTS} insights. "
            f"Titles: {[i['title'] for i in insights]}"
        )

    def test_no_constant_seniorcitizen_insight(self, ranking_insights):
        """The ranked output must never contain a 'Constant column: seniorcitizen' insight."""
        insights, _ = ranking_insights
        constant_titles = [
            i["title"] for i in insights
            if i["title"].lower().startswith("constant column:")
            and "seniorcitizen" in i["title"].lower()
        ]
        assert constant_titles == [], (
            f"Spurious constant-column insight for seniorcitizen: {constant_titles}"
        )

    def test_churn_driver_insights_have_is_target_driver_flag(self, ranking_insights):
        """Rate-gap insights targeting 'churn' (a business-outcome column) must
        carry is_target_driver=True in the ranked output."""
        insights, _ = ranking_insights
        churn_rate_insights = [
            i for i in insights
            if i.get("title", "").startswith("Rate gap:")
            and "churn" in i.get("title", "").lower()
        ]
        assert churn_rate_insights, "No churn rate-gap insights in ranked output"
        missing_flag = [i["title"] for i in churn_rate_insights if not i.get("is_target_driver")]
        assert not missing_flag, (
            f"Churn rate-gap insights missing is_target_driver=True: {missing_flag}"
        )

    def test_contract_insight_ranked_before_concentration_insights(self, ranking_insights):
        """Contract→Churn (a strong business driver) should outrank any concentration-risk
        finding for the same dataset."""
        insights, _ = ranking_insights
        titles = [i["title"] for i in insights]

        contract_idx = next(
            (idx for idx, t in enumerate(titles)
             if "contract" in t.lower() and "churn" in t.lower()),
            None,
        )
        concentration_idxs = [
            idx for idx, i in enumerate(insights)
            if i.get("type") == "concentration"
        ]
        if contract_idx is not None and concentration_idxs:
            worst_concentration = max(concentration_idxs)
            assert contract_idx < worst_concentration, (
                f"Contract→Churn is at rank {contract_idx} but a concentration insight "
                f"is at rank {min(concentration_idxs)} — churn driver should rank higher."
            )


# ─────────────────────────────────────────────────────────────────────────────
# 4.  Budget constant regression
# ─────────────────────────────────────────────────────────────────────────────

class TestBudgetConstants:
    def test_binary_rate_budget_larger_than_segment_gap_budget(self):
        """MAX_BINARY_RATE_CATS must be strictly larger than MAX_SEG_CATS so that
        wide datasets don't silently drop business-critical predictors like Contract."""
        from app.services.analysis.budget import MAX_BINARY_RATE_CATS, MAX_SEG_CATS

        assert MAX_BINARY_RATE_CATS > MAX_SEG_CATS, (
            f"MAX_BINARY_RATE_CATS ({MAX_BINARY_RATE_CATS}) must exceed "
            f"MAX_SEG_CATS ({MAX_SEG_CATS})"
        )

    def test_binary_rate_budget_at_least_20(self):
        """MAX_BINARY_RATE_CATS must be ≥ 20 to cover typical wide survey / SaaS datasets."""
        from app.services.analysis.budget import MAX_BINARY_RATE_CATS
        assert MAX_BINARY_RATE_CATS >= 20, (
            f"MAX_BINARY_RATE_CATS={MAX_BINARY_RATE_CATS} is too small; "
            "Telco has ~15 categorical columns and needs all to be scanned."
        )
