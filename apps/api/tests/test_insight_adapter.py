"""
Tests for insight_adapter: insight_id uniqueness guarantees and columns_used.

Covers:
  - Dict/list/tuple evidence is JSON-stringified for InsightResult (finance packs).
  - _make_id includes title so same (category, columns) with different titles
    produces distinct IDs.
  - build_insight_results returns a list where all insight_ids are globally
    unique within the run, even when multiple insights would otherwise hash to
    the same value.
  - The deduplication suffix scheme (_2, _3, …) is deterministic and stable
    (first occurrence always keeps the original ID).
  - Single-item and empty lists are handled gracefully.
  - Real-world collision patterns (data_quality insights with no columns,
    multiple segment insights on the same column pair) are resolved correctly.
  - 88B: plan-aware text extraction augments columns_used without breaking
    backward compatibility or legacy title-pattern extraction.
"""
from __future__ import annotations

import pytest

from app.schemas.analysis_plan import AnalysisPlan
from app.services.insight_adapter import (
    _make_id,
    build_insight_result,
    build_insight_results,
)


class TestStructuredEvidence:
    """Finance-domain insights can carry dict/list evidence — adapter must stringify for InsightResult."""

    def test_dict_evidence_does_not_crash_and_becomes_json_string(self):
        raw = {
            "type": "segment",
            "title": "Top return leaders",
            "severity": "medium",
            "confidence": 85,
            "finding": "Example finding.",
            "evidence": {"selected_return_column": "return_1y_pct"},
            "action": "Review.",
            "why_it_matters": "Context.",
        }
        result = build_insight_result(raw, analysis_plan=None)
        assert isinstance(result.evidence, str)
        assert "selected_return_column" in result.evidence
        assert "return_1y_pct" in result.evidence
        assert result.title == "Top return leaders"
        assert result.category == "segment"
        assert result.confidence == pytest.approx(0.85)


# ─────────────────────────────────────────────────────────────────────────────
# _make_id unit tests
# ─────────────────────────────────────────────────────────────────────────────

class TestMakeId:
    def test_same_inputs_produce_same_id(self):
        id1 = _make_id("segment", ["col_a", "col_b"], "Segment gap: col_a → col_b")
        id2 = _make_id("segment", ["col_a", "col_b"], "Segment gap: col_a → col_b")
        assert id1 == id2, "Identical inputs must produce the same deterministic ID"

    def test_different_categories_produce_different_ids(self):
        id_seg  = _make_id("segment",      ["revenue"], "Segment gap: region → revenue")
        id_dist = _make_id("distribution", ["revenue"], "Segment gap: region → revenue")
        assert id_seg != id_dist

    def test_different_titles_produce_different_ids(self):
        """Same category + same columns → different IDs when titles differ.

        This is the key regression case: before the fix,
        'Constant column: age' and 'High-cardinality column: age' both mapped to
        data_quality+['age'], producing identical 12-char hashes.
        """
        id_const  = _make_id("data_quality", ["age"], "Constant column: age")
        id_hc     = _make_id("data_quality", ["age"], "High-cardinality column: age")
        assert id_const != id_hc, (
            "Two data_quality insights about the same column but different titles "
            "must produce distinct IDs"
        )

    def test_column_order_does_not_matter(self):
        """Columns are sorted before hashing — order in the list must not affect ID."""
        id_ab = _make_id("correlation", ["col_b", "col_a"], "Correlation: col_a & col_b")
        id_ba = _make_id("correlation", ["col_a", "col_b"], "Correlation: col_a & col_b")
        assert id_ab == id_ba

    def test_empty_columns_and_title(self):
        """Completely empty inputs must still return a 12-char hex string."""
        result = _make_id("data_quality", [], "")
        assert isinstance(result, str)
        assert len(result) == 12
        assert all(c in "0123456789abcdef" for c in result)

    def test_id_length_is_always_12(self):
        for title in ["", "X", "A very long insight title that exceeds normal length"]:
            result = _make_id("segment", ["a", "b"], title)
            assert len(result) == 12, f"ID length must be 12 for title={title!r}"


# ─────────────────────────────────────────────────────────────────────────────
# build_insight_results — uniqueness guarantee
# ─────────────────────────────────────────────────────────────────────────────

def _raw(type_: str, title: str, **kw) -> dict:
    """Minimal raw insight dict for testing."""
    return {"type": type_, "title": title, "severity": "medium", "confidence": 70, **kw}


class TestBuildInsightResultsUniqueness:
    def test_empty_list_returns_empty(self):
        assert build_insight_results([]) == []

    def test_single_insight_has_valid_id(self):
        results = build_insight_results([_raw("segment", "Segment gap: region → revenue")])
        assert len(results) == 1
        assert len(results[0].insight_id) == 12

    def test_distinct_titles_produce_distinct_ids(self):
        """No collision when titles differ — most common real-world case."""
        raws = [
            _raw("data_quality", "Constant column: age"),
            _raw("data_quality", "High-cardinality column: age"),
            _raw("data_quality", "Missing column: email"),
        ]
        results = build_insight_results(raws)
        ids = [r.insight_id for r in results]
        assert len(ids) == len(set(ids)), f"Duplicate IDs found: {ids}"

    def test_truly_duplicate_insights_get_suffixed_ids(self):
        """When two insights share (type, title, columns), the second gets _2 suffix."""
        raw_ins = _raw("segment", "Rate gap: contract → churn")
        results = build_insight_results([raw_ins, raw_ins])

        ids = [r.insight_id for r in results]
        assert len(ids) == 2
        assert ids[0] != ids[1], "Duplicate insights must receive unique IDs"
        assert ids[1] == f"{ids[0]}_2", (
            f"Second duplicate should be '{ids[0]}_2', got {ids[1]!r}"
        )

    def test_three_identical_insights_get_sequential_suffixes(self):
        raw_ins = _raw("anomaly", "Anomalies in revenue")
        results = build_insight_results([raw_ins, raw_ins, raw_ins])

        ids = [r.insight_id for r in results]
        assert len(set(ids)) == 3, f"Expected 3 unique IDs, got: {ids}"
        assert ids[1] == f"{ids[0]}_2"
        assert ids[2] == f"{ids[0]}_3"

    def test_first_occurrence_keeps_original_id(self):
        """The original hash is preserved for the first occurrence so that
        previously-saved Report Builder selections remain valid."""
        raw_ins = _raw("correlation", "Relationship detected: revenue & profit")
        results = build_insight_results([raw_ins, raw_ins])

        original_id = build_insight_result(raw_ins, analysis_plan=None).insight_id
        assert results[0].insight_id == original_id, (
            "First occurrence must keep the canonical hash, not get a suffix"
        )

    def test_all_ids_unique_in_large_realistic_batch(self):
        """Simulate a realistic 15-insight run with several near-collision titles."""
        raws = [
            _raw("data_quality", "Constant column: tenure"),
            _raw("data_quality", "Constant column: age"),        # same type, diff title
            _raw("data_quality", "High-cardinality column: id"),
            _raw("data_quality", "Missing column: email"),
            _raw("segment",      "Rate gap: contract → churn"),
            _raw("segment",      "Rate gap: internetservice → churn"),
            _raw("segment",      "Rate gap: paymentmethod → churn"),
            _raw("segment",      "Segment gap: region → revenue"),
            _raw("segment",      "Segment gap: region → cost"),   # same cat, diff cols in title
            _raw("correlation",  "Relationship detected: a & b"),
            _raw("correlation",  "Relationship detected: b & c"),
            _raw("anomaly",      "Anomalies in revenue"),
            _raw("anomaly",      "Multivariate anomalies detected (3 rows)"),
            _raw("distribution", "Skewed distribution: revenue"),
            _raw("distribution", "Skewed distribution: cost"),
        ]
        results = build_insight_results(raws)
        ids = [r.insight_id for r in results]
        assert len(ids) == len(set(ids)), (
            f"Duplicate IDs found in realistic batch: "
            f"{[x for x in ids if ids.count(x) > 1]}"
        )

    def test_data_quality_no_columns_different_titles_unique(self):
        """
        Regression test for the original bug:
        data_quality insights that yield no columns from _extract_columns
        (e.g. "Multivariate anomalies detected (10 rows)") previously all
        hashed to the same ID because the key was just 'data_quality:'.
        Including the title in the hash fixes this.
        """
        raws = [
            _raw("data_quality", "Missing values detected"),
            _raw("data_quality", "Duplicate rows detected"),
            _raw("data_quality", "Schema inconsistency detected"),
        ]
        results = build_insight_results(raws)
        ids = [r.insight_id for r in results]
        assert len(set(ids)) == 3, (
            "data_quality insights with no extractable columns must still produce "
            f"unique IDs when titles differ. Got: {ids}"
        )

    def test_insight_ids_do_not_contain_spaces(self):
        """Insight IDs must be safe for use as HTML ids and URL segments."""
        raws = [_raw("segment", f"Some title {n}") for n in range(10)]
        results = build_insight_results(raws)
        for r in results:
            assert " " not in r.insight_id, f"ID contains space: {r.insight_id!r}"


# ─────────────────────────────────────────────────────────────────────────────
# 88B — columns_used + AnalysisPlan-aware text extraction
# ─────────────────────────────────────────────────────────────────────────────


class TestPlanAwareColumnsUsed:
    def test_build_insight_results_without_plan_still_works(self):
        raw = [
            {
                "type": "correlation",
                "severity": "medium",
                "confidence": 80,
                "col_a": "revenue",
                "col_b": "cost",
                "title": "Revenue vs Cost",
                "finding": "Revenue correlates with cost.",
            }
        ]

        result = build_insight_results(raw)

        assert result[0].columns_used == ["revenue", "cost"]

    def test_columns_used_extracts_known_text_only_column_from_plan(self):
        plan = AnalysisPlan(
            dataset_kind="generic",
            confidence=0.8,
            business_context="General dataset",
            primary_entity="record",
            target_metrics=["revenue"],
            important_dimensions=["region"],
            time_columns=["order_date"],
            columns_to_ignore=[],
            recommended_charts=[],
            insight_priorities=[],
            analysis_warnings=[],
            report_template_hint="generic",
        )

        raw = [
            {
                "type": "data_quality",
                "severity": "medium",
                "confidence": 70,
                "title": "Order date month concentration",
                "finding": "order_date_month appears concentrated.",
            }
        ]

        result = build_insight_results(raw, analysis_plan=plan)

        assert "order_date_month" in result[0].columns_used

    def test_columns_used_extracts_real_date_and_metric_from_text(self):
        plan = AnalysisPlan(
            dataset_kind="generic",
            confidence=0.8,
            business_context="General dataset",
            primary_entity="record",
            target_metrics=["revenue"],
            important_dimensions=[],
            time_columns=["order_date"],
            columns_to_ignore=[],
            recommended_charts=[],
            insight_priorities=[],
            analysis_warnings=[],
            report_template_hint="generic",
        )

        raw = [
            {
                "type": "trend",
                "severity": "medium",
                "confidence": 75,
                "title": "Revenue over order_date",
                "finding": "revenue changes over order_date.",
            }
        ]

        result = build_insight_results(raw, analysis_plan=plan)

        assert sorted(result[0].columns_used) == ["order_date", "revenue"]

    def test_columns_used_does_not_extract_unknown_fake_column(self):
        plan = AnalysisPlan(
            dataset_kind="generic",
            confidence=0.8,
            business_context="General dataset",
            primary_entity="record",
            target_metrics=["revenue"],
            important_dimensions=[],
            time_columns=["order_date"],
            columns_to_ignore=[],
            recommended_charts=[],
            insight_priorities=[],
            analysis_warnings=[],
            report_template_hint="generic",
        )

        raw = [
            {
                "type": "data_quality",
                "severity": "medium",
                "confidence": 70,
                "title": "fake_column_month issue",
                "finding": "fake_column_month appears unusual.",
            }
        ]

        result = build_insight_results(raw, analysis_plan=plan)

        assert "fake_column_month" not in result[0].columns_used


class TestLegacyTitlePatternColumnExtraction:
    """Guarantees pre-88B title / structured extraction still behaves the same."""

    def test_correlation_col_a_col_b(self):
        raw = {
            "type": "correlation",
            "severity": "medium",
            "confidence": 80,
            "col_a": "revenue",
            "col_b": "cost",
            "title": "Revenue vs Cost",
            "finding": "Correlated.",
        }
        assert build_insight_result(raw).columns_used == ["revenue", "cost"]

    def test_segment_gap_arrow(self):
        raw = {
            "type": "segment",
            "severity": "medium",
            "confidence": 70,
            "title": "Segment gap: category → metric",
            "finding": "Gap.",
        }
        assert build_insight_result(raw).columns_used == ["category", "metric"]

    def test_interaction_cross_moderated(self):
        """× branch records the pair before 'moderated by' (historic behavior)."""
        raw = {
            "type": "interaction",
            "severity": "medium",
            "confidence": 70,
            "title": "Interaction effect: c1 × c2 moderated by c3",
            "finding": "Effect.",
        }
        assert build_insight_result(raw).columns_used == ["c1", "c2"]

    def test_anomalies_in_amount(self):
        raw = {
            "type": "anomaly",
            "severity": "medium",
            "confidence": 70,
            "title": "Anomalies in amount",
            "finding": "Outliers.",
        }
        assert build_insight_result(raw).columns_used == ["amount"]

    def test_high_cardinality_customer_id(self):
        raw = {
            "type": "data_quality",
            "severity": "low",
            "confidence": 60,
            "title": "High-cardinality column: customer_id",
            "finding": "Many distinct values.",
        }
        assert build_insight_result(raw).columns_used == ["customer_id"]


# ── 88E — Plan hygiene metadata ───────────────────────────────────────────────

class TestPlanHygieneMetadata:
    def test_suppressed_by_plan_metadata_maps_to_insight_result(self):
        raw = {
            "type": "trend",
            "severity": "medium",
            "confidence": 70,
            "title": "Revenue by order_date_month",
            "finding": "order_date_month appears noisy.",
            "suppressed_by_plan": True,
            "plan_penalty_reason": "date_part_feature",
        }

        result = build_insight_result(raw)

        assert result.suppressed_by_plan is True
        assert result.plan_penalty_reason == "date_part_feature"

    def test_suppressed_insight_is_not_report_safe_even_if_otherwise_eligible(self):
        raw = {
            "type": "trend",
            "severity": "high",
            "confidence": 95,
            "title": "Strong trend",
            "finding": "Looks strong but was suppressed.",
            "suppressed_by_plan": True,
            "plan_penalty_reason": "date_part_feature",
        }

        result = build_insight_result(raw)

        assert result.report_safe is False

    def test_suppressed_insight_gets_plan_caveat(self):
        raw = {
            "type": "trend",
            "severity": "medium",
            "confidence": 70,
            "title": "Suppressed trend",
            "finding": "Suppressed finding.",
            "suppressed_by_plan": True,
            "plan_penalty_reason": "date_part_feature",
        }

        result = build_insight_result(raw)

        assert any("down-weighted by the analysis plan" in c for c in result.caveats)

    def test_unsuppressed_insight_defaults_are_backward_compatible(self):
        raw = {
            "type": "trend",
            "severity": "medium",
            "confidence": 70,
            "title": "Normal trend",
            "finding": "Normal finding.",
        }

        result = build_insight_result(raw)

        assert result.suppressed_by_plan is False
        assert result.plan_penalty_reason is None

    def test_suppressed_caveat_not_duplicated_on_repeated_calls(self):
        raw = {
            "type": "trend",
            "severity": "medium",
            "confidence": 70,
            "title": "Suppressed trend",
            "finding": "Suppressed finding.",
            "suppressed_by_plan": True,
            "plan_penalty_reason": "date_part_feature",
        }

        result = build_insight_result(raw)
        plan_caveats = [c for c in result.caveats if "down-weighted by the analysis plan" in c]
        assert len(plan_caveats) == 1

    def test_suppressed_false_does_not_override_report_safe(self):
        """suppressed_by_plan=False must not affect report_safe gating."""
        raw = {
            "type": "trend",
            "severity": "high",
            "confidence": 90,
            "title": "Strong clean trend",
            "finding": "Clean finding.",
            "suppressed_by_plan": False,
        }

        result = build_insight_result(raw)

        assert result.report_safe is True
        assert result.suppressed_by_plan is False

    def test_plan_penalty_reason_none_when_not_suppressed(self):
        raw = {
            "type": "segment",
            "severity": "high",
            "confidence": 80,
            "title": "Segment gap: region → revenue",
            "finding": "Region drives revenue.",
        }

        result = build_insight_result(raw)

        assert result.plan_penalty_reason is None


# ── 88J — Hardened confidence parsing in adapter ─────────────────────────────

def test_adapter_missing_confidence_defaults_to_50_percent():
    raw = {
        "type": "trend",
        "severity": "medium",
        "title": "Missing confidence",
        "finding": "Finding.",
    }

    result = build_insight_result(raw)

    assert result.confidence == 0.5


def test_adapter_invalid_confidence_defaults_to_50_percent():
    raw = {
        "type": "trend",
        "severity": "medium",
        "confidence": "unknown",
        "title": "Invalid confidence",
        "finding": "Finding.",
    }

    result = build_insight_result(raw)

    assert result.confidence == 0.5


def test_adapter_none_confidence_defaults_to_50_percent():
    raw = {
        "type": "trend",
        "severity": "medium",
        "confidence": None,
        "title": "None confidence",
        "finding": "Finding.",
    }

    result = build_insight_result(raw)

    assert result.confidence == 0.5


def test_adapter_negative_confidence_clamps_to_zero():
    raw = {
        "type": "trend",
        "severity": "medium",
        "confidence": -20,
        "title": "Negative confidence",
        "finding": "Finding.",
    }

    result = build_insight_result(raw)

    assert result.confidence == 0.0


def test_adapter_confidence_above_100_clamps_to_one():
    raw = {
        "type": "trend",
        "severity": "medium",
        "confidence": 999,
        "title": "Huge confidence",
        "finding": "Finding.",
    }

    result = build_insight_result(raw)

    assert result.confidence == 1.0


def test_build_insight_results_survives_mixed_malformed_confidence():
    raws = [
        {
            "type": "trend",
            "severity": "medium",
            "confidence": "bad",
            "title": "Bad confidence",
            "finding": "Finding 1.",
        },
        {
            "type": "segment",
            "severity": "medium",
            "confidence": None,
            "title": "None confidence",
            "finding": "Finding 2.",
        },
        {
            "type": "anomaly",
            "severity": "high",
            "confidence": 90,
            "title": "Good confidence",
            "finding": "Finding 3.",
        },
    ]

    result = build_insight_results(raws)

    assert len(result) == 3
    assert [r.confidence for r in result] == [0.5, 0.5, 0.9]


def test_report_safe_uses_clamped_confidence():
    raw = {
        "type": "trend",
        "severity": "high",
        "confidence": 999,
        "title": "Clamped high confidence",
        "finding": "Finding.",
    }

    result = build_insight_result(raw)

    assert result.confidence == 1.0
    assert result.report_safe is True


def test_report_safe_false_when_invalid_confidence_defaults_below_threshold():
    raw = {
        "type": "trend",
        "severity": "high",
        "confidence": "unknown",
        "title": "Invalid confidence",
        "finding": "Finding.",
    }

    result = build_insight_result(raw)

    assert result.confidence == 0.5
    assert result.report_safe is False
