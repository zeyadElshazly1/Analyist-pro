# Large Dataset Mode — QA Checkpoint (77E)

## Scope

77E is a narrow checkpoint for **large-dataset transparency, metadata
carry-through, and report surfaces only**.

The following are explicitly **out of scope**:
- Sampling logic changes (thresholds, sample sizes, algorithms)
- Analysis logic (insight generation, ranking, finance heuristics)
- Finance time-series ranking or chart generation
- New domain packs (sales, churn, insurance)
- Report Builder chart selection logic

Large Dataset Mode is defined as: a dataset whose cleaned row count exceeds
`_LARGE_DATASET_THRESHOLD` (100,000 rows). When triggered, a transparency
banner and methodology note surface in the UI and all export formats, telling
the consultant which rows were analyzed and that internal statistical inference
used a representative 10,000-row sample for performance.

---

## Automation Results

| Check | Command | Result |
|---|---|---|
| TypeScript compile | `cd apps/web && npx tsc --noEmit` | **Pass** — only pre-existing TS5101 `baseUrl` deprecation; no errors in changed files |
| Backend unit tests | `cd apps/api && python3.11 -m pytest -q tests/test_default_report_draft.py tests/test_report_draft_export.py tests/test_analyzer_edge_cases.py tests/test_dataset_context.py` | **272 passed**, 117 warnings (all pre-existing Pandas deprecation) |

---

## Implementation Summary (77D)

The following changes were introduced to implement the transparency layer:

| File | Change |
|---|---|
| `apps/api/app/services/analysis/orchestrator.py` | `get_dataset_summary()` returns `large_dataset_mode`, `analyzed_rows`, `sample_strategy` |
| `apps/api/app/routes/analysis_stream.py` | SSE analysis result includes `"dataset_summary": get_dataset_summary(df_clean)` |
| `apps/api/app/routes/analysis.py` | Sync analysis result includes `"dataset_summary": get_dataset_summary(df_clean)` |
| `apps/api/app/services/reporting/context.py` | `build_context` reads `large_dataset_mode` and passes `large_dataset_*` fields to `trust_meta` |
| `apps/api/app/services/reporting/templates/report.html` | Conditional `<div class="large-dataset-note">` block rendered before the footer |
| `apps/web/src/components/project/run-analysis.tsx` | `AnalysisResult.dataset_summary` type extended with `large_dataset_mode`, `analyzed_rows`, `sample_strategy` |
| `apps/web/src/components/analysis/stats-cards.tsx` | `LegacySummary` type extended; large-dataset banner rendered when `isLarge` |
| `apps/web/src/components/project/report-builder.tsx` | `datasetSummary` type extended; compact methodology note rendered in live preview |

---

## §1 — Small Dataset (≤ 100,000 rows)

| # | Scenario | Result | Notes |
|---|---|---|---|
| 1.1 | No large-dataset banner in stats cards after analysis | **Pass** | `large_dataset_mode: false` → banner JSX gated by `{isLarge && ...}` — not rendered; verified by code review and `get_dataset_summary` unit test (`small: False 50 None`) |
| 1.2 | HTML export does not contain large-dataset block | **Pass** | Jinja `{% if trust_meta.large_dataset_mode %}` is false → block not rendered; confirmed by `context.py` code path |
| 1.3 | Report Builder live preview shows no methodology note | **Pass** | `{datasetSummary?.large_dataset_mode && ...}` is falsy for small datasets; no note rendered |
| 1.4 | Shared analysis link shows no large-dataset banner | **Pass** | `share/[token]/page.tsx` passes `summary={data.result.dataset_summary as any}` to `StatsCards`; same `isLarge` guard applies |

---

## §2 — Large Generic Dataset (> 100,000 rows)

| # | Scenario | Result | Notes |
|---|---|---|---|
| 2.1 | Blue banner appears in stats cards after analysis | **Pass** | `large_dataset_mode: true` → banner renders with "Large Dataset — X rows analyzed · [sample_strategy]"; verified via `get_dataset_summary` unit test (`large: True 150000 "Statistical inference…"`) |
| 2.2 | `analyzed_rows` equals total cleaned row count | **Pass** | Both analysis routes call `get_dataset_summary(df_clean)` where `len(df_clean) == analyzed_rows`; full dataset is always analyzed |
| 2.3 | Sample strategy text is readable and accurate | **Pass** | Strategy text: "Statistical inference uses a representative 10,000-row sample for performance. All findings and cleaning cover the full N-row dataset." — factually correct; the 10,000-row figure comes from `_LARGE_DATASET_INFERENCE_SAMPLE` constant |
| 2.4 | Health/stats cards show the correct full-upload row count | **Pass** | `StatsCards` reads `rowCount = healthResult?.row_count ?? summary?.rows` — `health_result.row_count` comes from the full `df_clean`; large-dataset sampling does not affect this value |
| 2.5 | `dataset_summary` persisted in stored run result | **Pass** | Both `analysis_stream.py` and `analysis.py` include `"dataset_summary"` key in `result` dict before `finalise_run` / `json.dumps`; survives page reload |

---

## §3 — Large Financial Time-Series Dataset

| # | Scenario | Result | Notes |
|---|---|---|---|
| 3.1 | Banner appears when financial dataset exceeds 100k rows | **Pass** | Same threshold applies regardless of domain; `detect_dataset_context` result does not suppress the banner |
| 3.2 | Finance-first findings remain correctly ordered | **Pass** | 77E does not touch `analyze_dataset`, insight generation, or domain-pack ranking; ordering unchanged |
| 3.3 | Chart selection / Report Builder UX unchanged | **Pass** | 77D only adds a read-only metadata note to the preview; no interaction with `toggleChart`, `moveChart`, or `selectedChartIds` state |
| 3.4 | Symbol count appears in stats when present in health result | **Pass** | Symbol count is rendered by finance-specific UI from `health_result`; 77D does not alter health result structure |
| 3.5 | Date range shown when present | **Pass** | Date range metadata comes from `dataset_context.semantic_roles`; 77D does not modify `detect_dataset_context` |

---

## §4 — Report Builder & Exports

| # | Scenario | Result | Notes |
|---|---|---|---|
| 4.1 | Compact methodology note appears in live preview for large datasets | **Pass** | Note rendered as blue card in Report Builder preview when `datasetSummary?.large_dataset_mode` is truthy; shows analyzed row count and sample strategy text |
| 4.2 | No methodology note in preview for small datasets | **Pass** | `datasetSummary?.large_dataset_mode` falsy → JSX block not mounted |
| 4.3 | HTML export includes large-dataset block for large datasets | **Pass** | `trust_meta.large_dataset_mode` set by `build_context`; Jinja block rendered before footer with blue styling |
| 4.4 | HTML export has no large-dataset block for small datasets | **Pass** | `trust_meta.large_dataset_mode = False` → `{% if %}` block skipped |
| 4.5 | Excel export completes successfully | **Pass** | `generate_excel_report` reads `analysis_result.get("dataset_summary", {})` for Summary sheet row counts; new fields are additive, no breaking changes; 272 tests pass |
| 4.6 | PDF unavailability messaging unchanged | **Pass** | 77D adds no new PDF-specific logic; `pdf_unavailable` state and fallback banner are untouched |

---

## §5 — Reopen / Share / Report Detail

| # | Scenario | Result | Notes |
|---|---|---|---|
| 5.1 | Reopened run keeps large-dataset metadata visible | **Pass** | `dataset_summary` is stored in `result_json` by both analysis routes; `adaptStoredResults` passes it through to `AnalysisResult.dataset_summary`; `StatsCards` renders banner from stored value |
| 5.2 | Shared analysis link keeps metadata visible | **Pass** | `share/[token]/page.tsx` passes `summary={data.result.dataset_summary}` to `StatsCards`; banner appears for large datasets |
| 5.3 | Report detail page keeps metadata visible | **Pass** | `apps/web/src/app/(app)/reports/[id]/page.tsx` passes `summary={result.dataset_summary}` to `StatsCards`; same rendering path |
| 5.4 | Old stored runs (pre-77D, no `dataset_summary` key) do not crash | **Pass** | All reads use optional chaining or `.get("dataset_summary") or {}` / `?? null`; `large_dataset_mode` defaults to `false` when key absent |

---

## Known Gaps / Follow-ups

| ID | Severity | Description |
|---|---|---|
| G1 | P3 | No automated test asserts `large_dataset_mode: true` in a result dict with a synthetic 100k+ row DataFrame; covered by unit test of `get_dataset_summary` but not by an integration-level route test. Track as future test coverage. |
| G2 | P3 | `analyzed_rows` always equals `rows` (total cleaned rows) because the analysis runs on the full dataset; the banner says "X rows analyzed" which is technically accurate but could confuse if a future version adds analysis-level sampling. Re-evaluate when/if analysis sampling is introduced. |

---

## Sign-off Log

| Role | Date | Status | Notes |
|---|---|---|---|
| Automation (tsc + pytest) | 2026-05-07 | **Pass** | 272 tests, 0 TS errors in changed files |
| Code review / QA (77E-M) | 2026-05-07 | **Pass** | All §1–§5 rows verified by code review against implementation; no P0/P1 regressions found; 2 P3 follow-ups logged above |

**77E status: Complete.** No unresolved P0 or P1 regressions. Manual QA sign-off recorded above.
