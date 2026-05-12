# Analysis Brain Checkpoint — Tasks 88A–88V

## Purpose

This document records the generic backend intelligence and trust-hardening work completed in tasks 88A–88V, immediately before outreach. It serves as a handoff reference: the pipeline is stronger, safer, and more self-documenting than it was at the 86-series checkpoint, without any domain-specific additions or frontend changes required.

---

## Scope Guardrails

- No domain packs added
- No churn/sales/insurance-specific logic added
- No frontend changes required
- Generic analysis quality, trust, ranking, and persistence improvements only

---

## Completed Improvements

### 1. Plan Hygiene and Column Awareness (88A–88B)

The analysis planner gained awareness of ignored and low-signal columns. The `apply_analysis_plan_hygiene()` function was wired into all three pipeline paths (sync route, stream route, Celery task) to suppress findings that reference date-part artefacts or columns explicitly excluded from analysis. Suppressed insights remain in the pipeline but are flagged with `suppressed_by_plan=True` and a `plan_penalty_reason` so downstream layers can act on them.

### 2. Trust-Aware Output Surfaces (88C, 88E, 88F, 88S)

The executive panel (88C) was updated to exclude suppressed and low-confidence insights from its opportunities/risks/action_plan tiles. The canonical `InsightResult` schema (88E) gained `suppressed_by_plan` and `plan_penalty_reason` fields, and `report_safe` now gates on both confidence and plan suppression. The narrative (88F) was made trust-aware: `generate_narrative()` filters ineligible insights before building paragraphs.

A shared `is_summary_eligible()` helper (88S) in `trust_filters.py` became the single source of truth for "can this insight appear in business-facing summaries," replacing duplicate logic in `narrative.py` and `orchestrator.py`.

### 3. Ranking and Candidate Recovery (88D, 88G, 88H, 88Q)

`rerank_after_plan_hygiene()` (88D) sorts post-hygiene insights so clean findings appear before suppressed ones at the same severity level. To avoid discarding good insights before hygiene can demote noisy ones, `rank_insights()` (88G) gained an optional `limit` parameter; the orchestrator now passes a 3× candidate multiplier so hygiene operates on a wider pool before the final cap is applied.

Deduplication (88H) was improved to extract column identifiers from `col_a`/`col_b`, `column`, `columns`, and six title patterns, collapsing duplicates that differ only in column order or phrasing. The generic ranking branch (88Q) was made non-mutating by replacing `.sort()` with `sorted()`.

### 4. Confidence Hardening (88I–88R)

A systematic hardening pass across all five layers where confidence values are consumed:

| Task | Layer | Change |
|------|-------|--------|
| 88I | `ranking.py` | `_composite_score` no longer crashes on malformed confidence |
| 88J | `insight_adapter.py` | `build_insight_result` clamps confidence to `[0.0, 1.0]` |
| 88K | `analysis_plan_hygiene.py` | `_penalise` clamps before multiplying |
| 88N | `narrative.py`, `orchestrator.py` | Eligibility helpers clamp before threshold comparison |
| 88P | `confidence.py` | Shared `safe_confidence_0_100` / `safe_confidence_from_insight` created; all five layers now use it |
| 88R | `confidence.py` | NaN and ±infinity handled: NaN → default 50, +∞ → 100, −∞ → 0 |

Missing/None/non-numeric confidence defaults to 50 everywhere. Negative values clamp to 0. Above-100 values clamp to 100.

### 5. Selection Metadata and Saved-Run Consistency (88L–88V)

`post_hygiene_candidate_count` (88L) is now captured before the final cap and passed to `generate_narrative()`, enabling "showing top X of Y" text when the candidate pool is wider than the cap.

`build_insight_selection_meta()` (88M) in `finalize_insights.py` records a structured metadata block in `result_json`:

```json
{
  "post_hygiene_candidate_count": 32,
  "visible_insight_count": 15,
  "summary_eligible_visible_count": 11,
  "summary_ineligible_visible_count": 4,
  "suppressed_candidate_count": 4,
  "suppressed_visible_count": 1,
  "final_cap": 15
}
```

The `RunResults` schema (88O) exposes `insight_selection_meta` so reopened saved runs return the same block as live analysis. Legacy cached payloads (88U) are backfilled with a best-effort version on the next cache hit, marked `backfilled_from_cache: true`. A dedicated route regression test (88V) covers the end-to-end cache-hit backfill path.

---

## Current Pipeline Flow

1. Detectors produce raw insights via `analyze_dataset()`
2. `rank_insights(limit=MAX_INSIGHTS × 3)` returns a wider candidate pool
3. `apply_analysis_plan_hygiene()` marks noisy findings with `suppressed_by_plan=True`
4. `rerank_after_plan_hygiene()` floats clean insights above suppressed ones
5. `final_cap_with_candidate_count()` records the pre-cap count and slices to `MAX_INSIGHTS`
6. `build_insight_selection_meta()` records trust/selection counts in the result
7. `generate_narrative()` and `generate_executive_panel()` use `is_summary_eligible()` to filter ineligible insights before building user-facing text
8. `build_insight_results()` maps pipeline insights to canonical `InsightResult` objects with hygiene metadata
9. Saved runs and cache hits expose/backfill `insight_selection_meta` for consistency

---

## Validation Snapshot

| Test file | Coverage |
|-----------|----------|
| `test_ranking_hygiene.py` | 33 tests — rerank, dedup, candidate pool, non-mutating sort |
| `test_trust_filters.py` + `test_narrative_hygiene.py` + `test_executive_panel.py` | 50 tests — eligibility, narrative, panel |
| `test_finalize_insights.py` + `test_confidence_utils.py` + `test_analysis_cache_backfill.py` | 28+ tests — metadata, confidence, cache backfill |
| `test_analysis_plan_finding_hygiene.py` + `test_insight_adapter.py` | 72 tests — hygiene penalties, canonical adapter |
| Full backend suite | **must be run and green before outreach** |

Last confirmed full suite result: **1222+ passed, 0 failed** (run after 88R).

---

## Outreach Readiness Impact

- **Fewer noisy top findings** — suppressed date-part and ignored-column insights are demoted below clean findings rather than appearing in the top slot
- **Safer executive summary** — only insights that pass both the confidence threshold and plan-suppression check appear in opportunities/risks/action tiles
- **Clearer trust metadata** — `insight_selection_meta` gives QA and future frontend a precise breakdown of candidate recovery, suppression, and summary eligibility
- **Consistent saved-run and cache behavior** — reopened analyses return the same metadata shape as live runs, whether from a fresh pipeline, cache hit, or legacy stored result
- **Less crash risk** — malformed confidence (None, "unknown", NaN, ±∞, negative, above 100) is handled safely at every layer
- **Better first-demo impression** — the pipeline surface is cleaner, its trust signals are accurate, and the narrative accurately reflects the candidate pool size

---

## Not Done / Deferred

- No domain-specific intelligence packs (churn, sales, insurance, etc.)
- No frontend rendering of `insight_selection_meta` yet
- No report-builder use of `summary_eligible_visible_count` yet
- No new AI planner behavior
- No changes to chart export, sidebar, or any other frontend surface
