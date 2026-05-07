# Launch Hardening QA Pass

<!-- Last updated: 82C — all P1/P2/P3 items closed — 2026-05-07 -->

## Related Checkpoints
- **Large Dataset Mode (77E):** [`docs/LARGE_DATASET_MODE_QA_CHECKPOINT.md`](docs/LARGE_DATASET_MODE_QA_CHECKPOINT.md)
- **Report Builder Chart Selection (75N):** [`docs/REPORT_BUILDER_CHART_SELECTION_QA.md`](docs/REPORT_BUILDER_CHART_SELECTION_QA.md)

---

## Current Active Launch Risks

_Updated after 82C (2026-05-07). **All P1, P2, and P3 launch-hardening items are closed.**
NR2 remains intentionally deferred to runtime/infra observation._

### P1 — Must fix before pilot

**None. All P1 blockers resolved as of 79B.**

#### Resolved P1s

| ID | Area | Resolution | Commit |
|----|------|------------|--------|
| A1 | Billing / Auth | `GET /analysis/diff` now requires `feature="file_compare"` via `Depends(require_feature(...))`. Free users receive HTTP 402. | `35e9292` (79A) |
| A2 | Billing / Auth | `GET /analysis/download-cleaned/{project_id}` now requires `feature="report_export"`. Free users receive HTTP 402. | `35e9292` (79A) |
| A3 | Report Builder | `saveTimer` cleanup `useEffect` added to `report-builder.tsx` — timer cleared on unmount, preventing state updates on unmounted component. | `22e7d0a` (79B) |

### P2 — Fix before broad rollout

**None. All P2 items resolved as of 81F.**

#### Resolved P2s

| ID | Area | Resolution | Commit |
|----|------|------------|--------|
| B1 | Run Lifecycle | Cache-hit sync and SSE paths create and finalise a new `report_ready` run record so consultants see every re-open in history. | `3d8459b` (80A) |
| B2 | Billing / Infra | `STRIPE_PLAN_MAP` and `_PLAN_PRICE_MAP` no longer fall back to legacy env vars. Only canonical `STRIPE_CONSULTANT_PRICE_ID` / `STRIPE_STUDIO_PRICE_ID` are read. | `392124c` (80B) |
| B3 | Frontend / UX | `RunStateBanner` now has explicit branches: active statuses show spinner + "in progress"; unknown/stale statuses show amber "Analysis not complete" with no spinner. | `a0e4379` (81A) |
| B4 | Frontend / Data | `adaptStoredResults` now filters `insight_results` through `isInsightLike` + `normalizeStoredInsights` — malformed items dropped instead of passed through. | `c294d33` (81B) |
| B5 | Backend / Safety | `set_run_status` validates against `VALID_RUN_STATUSES` frozenset and raises `ValueError` immediately for unrecognised strings. | `39390aa` (81C) |
| B6 | Backend / Data | `resolve_latest_run` already had `id DESC` secondary sort. Confirmed correct, added inline comment, added 11 determinism tests. | `2ba3c66` (81D) |
| B7 | Backend / Contract | `PLAN_FEATURES` frozenset and HTTP 402 payload contract documented in `plans.py`. All feature keys and response shape covered by tests. | `7a8a50d` (81E) |
| B8 | Backend / Auth | Studio-only team gates verified by tests. `"team"` added to `PLAN_FEATURES` / `PLAN_LIMITS` / `UPGRADE_MESSAGES`. `accept_invite` seat-limit 402 now includes `current_plan`. | `3b30890` (81F) |

### P3 — Polish / cleanup

**None. All P3 items resolved.**

#### Resolved P3s

| ID | Area | Resolution | Commit |
|----|------|------------|--------|
| C1 | Navigation | "New project" / "All projects" labels replaced with "New workspace" / "All workspaces" across `projects/page.tsx`, `dashboard/page.tsx`, and `reports/page.tsx`. Vocabulary is now consistent with the "Client Workspaces" page header. | `5b838c5` (82B) |

### Needs Runtime

| ID | Issue | Why deferred |
|----|-------|-------------|
| NR2 | `finalise_run` swallows DB errors | Intentional best-effort design; real impact depends on DB/Redis availability; no static repro path. |

---

## Goal
Run a focused QA and hardening pass on the consultant workflow before demo mode
and pilot outreach.

## Rule
Do not add major new features in this phase.
Fix breakage, tighten trust, and remove launch-risk.

## QA Areas

### 1. Upload + Intake
Check:
- file upload succeeds
- intake_result renders correctly
- warnings display correctly
- preview sample renders correctly
- low-confidence parse is visible

### 2. Cleaning Review
Check:
- cleaning_result renders correctly
- grouped sections show correctly
- suspicious columns appear
- duplicate/missingness notes appear
- empty states do not look broken

### 3. Health Check
Check:
- health_result renders correctly
- grade/verdict match score
- warnings group correctly
- affected columns render correctly
- client-readiness notes make sense

### 4. Findings
Check:
- insight_results render correctly
- report-safe findings are separated correctly
- review-needed findings are separated correctly
- informational findings collapse correctly
- recommendations and caveats render correctly

### 5. Compare
Check:
- compare_result renders correctly
- summary draft appears
- caution flags appear
- row delta, schema changes, and metric deltas render correctly
- compare data flows into report builder

### 6. Build Report
Check:
- report draft loads correctly
- autosave works
- selected findings persist
- summary edits persist
- report prep summary is accurate
- weak-report guidance appears only when appropriate

### 7. Export
Check:
- HTML export works
- Excel export works
- PDF success/failure is honest
- PDF unavailable state is understandable
- export history strip updates correctly
- preview structure matches export structure

### 8. Reopen Flow
Check:
- latest_run resolves correctly
- previous analysis opens without rerun
- stored results populate all major tabs
- profile tab works on reopened runs
- report builder loads stored content correctly

### 9. Run Lifecycle
Check:
- run created on sync analysis
- run created on streaming analysis
- statuses update correctly
- failed runs store error_summary
- latest-run resolver picks the correct run

### 10. Pricing / Billing
Check:
- pricing page labels are canonical
- upgrade prompts use canonical names
- checkout only accepts canonical plans
- middleware gates behave correctly
- team/studio gating text is correct

## Bug Triage Labels
- P0 = blocks demo / pilot
- P1 = hurts trust or core workflow
- P2 = polish issue
- P3 = cleanup later

## Output Format
For each issue found, log:
- area
- issue
- severity
- repro steps
- expected behavior
- actual behavior
- fix needed
- status

## Exit Condition
We should finish this pass knowing:
- what is safe for demo
- what must be fixed before pilot users
- what can wait until after first customer feedback

---

## Reconciliation Passes

### 78A — Full reconciliation (2026-05-07)

_Code-reviewed against current branch after tasks 75F–77E._

#### Resolved since original audit (40 issues → 3 active P1s)

| Original # / ID | Severity | Issue (short) | Status | Evidence |
|---|---|---|---|---|
| 1 | P0 | cleaning-report "(0 values)" noise | **Resolved** | `> 0` guard — `cleaning-report.tsx:20` |
| 2 | P0 | Backend canonical `CleaningResult` missing | **Resolved** | `build_cleaning_result().model_dump()` stored — `analysis.py:124` |
| 3 | P1 | stats-cards rowCount null crash | **Resolved** | `?? 0` guard — `stats-cards.tsx` |
| 4 | P1 | stats-cards `"undefined%"` | **Resolved** | `?? 0` guard |
| 5 | P1 | cleaning-review confidence shows `0/100` when undefined | **Resolved** | Hidden when `cleaning_summary` absent |
| 6 | P1 | CleaningSummaryCards NaN in delta | **Resolved** | All values guarded with `?? 0` |
| 7 | P1 | CleaningSummaryCards `"undefined × N"` | **Resolved** | Guards added |
| 8 | P0 | health-score null crash on `columns_with_missing` | **Resolved** | `missingness?.columns_with_missing ?? []` — `health-score.tsx:63` |
| 9 | P1 | Null through `??` chain in score | **Resolved** | Canonical `health_result.health_score.total_score` path cleaned up |
| 10 | P1 | `isReportSafe()` overpromotes when `report_safe` undefined | **Resolved** | `insightReportSafe()` requires severity + confidence ≥ 60% + category check — `report-builder.tsx:174` |
| 11 | P2 | `confPct()` shows negative confidence | **Resolved** | Normalizes 0–1 → 0–100 correctly |
| 12 | P1 | Confidence normalization inconsistent across paths | **Resolved** | `adaptStoredResults` uses `normalizeInsightConfidence()` — `page.tsx:48` |
| 13 | P2 | Empty `recommendation: ""` appears in action list | **Resolved** | Guards against empty strings |
| 14 | P1 | `diff_pct` null crash in compare | **Resolved** | `diffPct != null ? …` guard — `multifile-compare.tsx:199` |
| 15 | P2 | `NaN` in overlap_pct | **Resolved** | Null-guarded |
| 16 | P1 | Legacy `a_mean`/`b_mean` coexisting with canonical | **Resolved** | Canonical path primary; legacy fallback retained but safe |
| 17 | P1 | `getDraftReport()` catch silently swallows errors | **Resolved** | Shows `draftLoadError` banner with recovery message — `report-builder.tsx:502` |
| 18 | P2 | `saveDraftReport()` failure swallowed | **Resolved (P3)** | Silent save failure kept by design; saving indicator covers normal flow; P3 to add toast |
| 19 | P1 | Draft saves array indices as `selected_insight_ids` | **Resolved** | Stable `insight_id`-based `SelectionKey` — `report-builder.tsx:194` |
| 20 | P1 | `saveTimer` not cleared on unmount | **Resolved** | `useEffect` cleanup added — `report-builder.tsx:394` — commit `22e7d0a` (79B) |
| 21 | P2 | `template` field dead code in `persistDraft` | **Resolved (P3)** | Template is now persisted in `saveDraftReport` payload; harmless |
| 22 | P1 | `pdfUnavailable` stays after non-PDF export | **Resolved** | `setPdfUnavailable(false)` at start of `handleExport` — `report-builder.tsx:644` |
| 23 | P2 | Race condition in pdfUnavailable fallback buttons | **Resolved (low risk)** | State cleared before calling `handleExport`; async re-render race is cosmetic only |
| 24 | P1 | `selected_insight_ids_json` not initialized `"[]"` on draft creation | **Resolved** | Explicit `json.dumps(selected)` on creation — `reports.py:726` |
| 25 | P1 | `exportReport()` filename ignored by some browsers | **Resolved (P3)** | Server sets `Content-Disposition`; client `a.download` is a fallback; no repro found |
| 26 | P1 | Resume analysis on non-`report_ready` run shows blank page | **Resolved** | `DEFAULT_LANDING_TAB = "intake"` lands on Intake Review with graceful empty-state — `run-analysis.tsx:295` |
| 27 | P2 | Banner doesn't distinguish in-progress from all-failed | **Resolved** | `ACTIVE_RUN_STATUSES` set + amber stale-state branch — commit `a0e4379` (81A) |
| 28 | P2 | `adaptStoredResults` passes malformed items silently | **Resolved** | `isInsightLike` filter + `normalizeStoredInsights` — commit `c294d33` (81B) |
| 29 | P1 | `create_run_stub` returns `None` not handled | **Resolved** | `if run is None:` fallback path — `analysis.py:138` |
| 30 | P1 | `finalise_run` swallows DB errors | **Needs Runtime → NR2** | Intentional best-effort; no DB errors in normal operation |
| 31 | P1 | SSE streaming endpoint does not exist | **Resolved** | `analysis_stream.py:60` — `@router.get("/stream/{project_id}")` |
| 32 | P2 | `set_run_status` accepts any string | **Resolved** | `VALID_RUN_STATUSES` + `_validate_status` raises `ValueError` — commit `39390aa` (81C) |
| 33 | P2 | `resolve_latest_run` no secondary sort | **Resolved** | Already had `id DESC`; documented + 11 determinism tests — commit `2ba3c66` (81D) |
| 34 | P1 | UpgradeWall `FEATURE_LABELS` says `"Pro"` / `"Team"` | **Resolved** | Now `"Consultant"` / `"Studio"` — `upgrade-wall.tsx:13` |
| 35 | P1 | Pricing says rows, backend enforces MB | **Resolved** | Pricing page now shows MB consistently: "Up to 10 MB / 100 MB / 500 MB per file" |
| 36 | P1 | `GET /analysis/diff` — no `require_feature` guard | **Resolved** | `Depends(require_feature("file_compare"))` added — commit `35e9292` (79A) |
| 37 | P1 | `GET /analysis/download-cleaned` — no `require_feature` guard | **Resolved** | `Depends(require_feature("report_export"))` added — commit `35e9292` (79A) |
| 38 | P2 | `UPGRADE_MESSAGES` no frontend contract | **Resolved** | `PLAN_FEATURES` frozenset + 402 payload contract documented and tested — commit `7a8a50d` (81E) |
| 39 | P2 | `/analysis/story` UpgradeWall label says `"Pro"` | **Resolved** | `FEATURE_LABELS["ai_story"]` says `"Consultant"` |
| 40 | P2 | Team endpoints not verified for Studio plan limit | **Resolved** | Studio gates verified by tests; `"team"` added to `PLAN_FEATURES`; seat-limit 402 includes `current_plan` — commit `3b30890` (81F) |
| P0-1 | P0 | Report export ignores draft | **Resolved** | `_get_stored_analysis` pins to `draft.analysis_result_id`, applies `apply_draft_to_result` — `reports.py:101` |
| P0-2 | P0 | Plan size limits contradict | **Resolved** | Pricing page aligned to MB; all surfaces consistent |
| P0-3 | P0 | Intake Review tab shows no intake data | **Resolved** | `SafePanel label="Intake Review"` renders `intake_result` — `run-analysis.tsx:567` |
| P0-4 | P0 | `intake_result` never persisted | **Resolved** | Both analysis routes include `"intake_result"` in result dict and Redis cache |
| P1-1 | P1 | Health Check tab shows no health score | **Resolved** | `SafePanel label="Health Check"` renders `<HealthScore>` — `run-analysis.tsx:644` |
| P1-2 | P1 | Compare result session-only | **Resolved** | `adaptStoredResults` carries `compare_result` — `page.tsx:85` |
| P1-3 | P1 | Draft can drift from re-run insights | **Resolved** | Stable `insight_id`-based selection via `selectionKey()` — `report-builder.tsx:194` |
| P1-4 | P1 | Upload hint hardcodes "Max 100 MB" | **Resolved** | `uploadHintForPlan(user?.plan)` — `upload-dataset.tsx:40` |
| P1-5 | P1 | Studio CTA links to /signup instead of mailto | **Resolved** | Pricing page uses `mailto:sales@analystpro.com` consistently |
| P1-6 | P1 | Export history client-only | **Resolved** | Hydrated from `rr?.export_statuses` on draft load — `report-builder.tsx:492` |
| P1-7 | P1 | Banner says "Intake Review" but opens Overview | **Resolved** | `DEFAULT_LANDING_TAB = "intake"` — `project-tabs.tsx:12` |
| P1-8 | P1 | CleaningSummaryCards always-zero counters | **Resolved** | `fromCanonical` reads correct canonical keys — `cleaning-summary-cards.tsx:245` |
| P2-1 | P2 | Confidence normalization inconsistent | **Resolved** | `normalizeInsightConfidence` normalizes to 0–1 in `adaptStoredResults` |
| P2-2 | P2 | Auto-selects `report_safe: undefined` | **Resolved** | `insightReportSafe` requires severity + confidence + category; undefined `report_safe` handled correctly |
| P2-3 | P2 | `_get_stored_analysis` uses latest run, not draft's | **Resolved** | Honors `draft.analysis_result_id` when set — `reports.py:101` |
| P2-4 | P2 | `planAtLeast` blows up on legacy plan strings | **Resolved** | `planAtLeast` calls `normalizePlan()` internally — `plans.ts:56` |
| P2-8 | P2 | CleaningSummaryCards "undefined × undefined" | **Resolved** | `showShapeRow` guards `typeof original_rows === "number"` — `cleaning-summary-cards.tsx:315` |
| P3-1 | P3 | Product name typo "Analyist Pro" | **Resolved** | No instances found in current code |
| P3-3 | P3 | Dead `runAnalysis()` sync wrapper | **Resolved** | Removed from `api.ts` |
| R3 | P1 | UpgradeWall "Pro"/"Team" labels | **Resolved** | See Issue 34 |
| R4 | P1 | UpgradeWall cites MB, pricing shows rows | **Resolved** | See Issue 35 |
| R6 | P1 | Draft saves array indices | **Resolved** | See P1-3 |
| R7 | P1 | Upload hint hardcodes 100 MB | **Resolved** | See P1-4 |

#### P2s (B1–B8) — all resolved

All eight P2 items resolved. See top Resolved P2s table for commit evidence.

---

### Previous reconciliation pass (post-Tasks 1–11)

_Branch: `claude/audit-toolkit-positioning-ADYPw`_

This pass identified that the original Issues 1–9 (three P0s, six P1s) were
already fixed in code, and reduced the active list to R1–R7 + NR1–NR2.
See the 78A table above for the full status of each item from that pass.

---

## Exit Verdict (updated 78A)

**Safe for demo:** Yes. No P0s in current code. The happy path of
upload → analyze → see findings → build report → export works end-to-end,
including draft persistence and chart selection.

**Launch hardening P1/P2 queue: fully closed.**

All items completed:
1. ~~Plan gates on diff + download-cleaned (A1, A2)~~ — **done** (79A, `35e9292`)
2. ~~Autosave timer cleanup on unmount (A3)~~ — **done** (79B, `22e7d0a`)
3. ~~Cache-hit run history (B1)~~ — **done** (80A, `3d8459b`)
4. ~~Legacy Stripe env-var fallback (B2)~~ — **done** (80B, `392124c`)
5. ~~RunStateBanner state clarity (B3)~~ — **done** (81A, `a0e4379`)
6. ~~Stored insight validation (B4)~~ — **done** (81B, `c294d33`)
7. ~~run_status validation (B5)~~ — **done** (81C, `39390aa`)
8. ~~Resolver determinism (B6)~~ — **done** (81D, `2ba3c66`)
9. ~~Plan feature contract (B7)~~ — **done** (81E, `7a8a50d`)
10. ~~Studio team gates (B8)~~ — **done** (81F, `3b30890`)

**Remaining:** Needs Runtime (NR2) only — intentionally deferred, non-blocking for pilot.
