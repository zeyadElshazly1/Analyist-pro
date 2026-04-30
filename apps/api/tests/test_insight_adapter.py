"""
Tests for insight_adapter: insight_id uniqueness guarantees.

Covers:
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
"""
from __future__ import annotations

import pytest

from app.services.insight_adapter import (
    _make_id,
    build_insight_result,
    build_insight_results,
)


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

        original_id = build_insight_result(raw_ins).insight_id
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
