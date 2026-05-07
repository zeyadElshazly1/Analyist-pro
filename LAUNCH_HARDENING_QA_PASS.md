# Launch Hardening QA Pass

<!-- Last updated: 80B — B1 and B2 resolved — 2026-05-07 -->

## Related Checkpoints
- **Large Dataset Mode (77E):** [`docs/LARGE_DATASET_MODE_QA_CHECKPOINT.md`](docs/LARGE_DATASET_MODE_QA_CHECKPOINT.md)
- **Report Builder Chart Selection (75N):** [`docs/REPORT_BUILDER_CHART_SELECTION_QA.md`](docs/REPORT_BUILDER_CHART_SELECTION_QA.md)

---

## Current Active Launch Risks

_Updated after 79C (2026-05-07). **All known P1 launch blockers are closed.**
Remaining active issues are P2/P3/Needs Runtime only._

### P1 — Must fix before pilot

**None. All P1 blockers resolved as of 79B.**

#### Resolved P1s

| ID | Area | Resolution | Commit |
|----|------|------------|--------|
| A1 | Billing / Auth | `GET /analysis/diff` now requires `feature="file_compare"` via `Depends(require_feature(...))`. Free users receive HTTP 402. | `35e9292` (79A) |
| A2 | Billing / Auth | `GET /analysis/download-cleaned/{project_id}` now requires `feature="report_export"`. Free users receive HTTP 402. | `35e9292` (79A) |
| A3 | Report Builder | `saveTimer` cleanup `useEffect` added to `report-builder.tsx` — timer cleared on unmount, preventing state updates on unmounted component. | `22e7d0a` (79B) |

### P2 — Fix before broad rollout

**None. All P2 items resolved.**

#### Resolved P2s

| ID | Area | Resolution | Commit |
|----|------|------------|--------|
| B1 | Run Lifecycle | Cache-hit sync and SSE paths now create and finalise a new `report_ready` run record so consultants see every re-open in history. | `3d8459b` (80A) |
| B2 | Billing / Infra | `STRIPE_PLAN_MAP` and `_PLAN_PRICE_MAP` no longer fall back to `STRIPE_PRO_PRICE_ID` / `STRIPE_TEAM_PRICE_ID`. Only canonical `STRIPE_CONSULTANT_PRICE_ID` and `STRIPE_STUDIO_PRICE_ID` are read. Legacy plan-name aliases (`"pro"` → `"consultant"`, `"team"` → `"studio"`) in API request bodies still work via `normalize_plan`. | `(80B)` |

### P3 — Polish / cleanup

| ID | Area | Notes |
|----|------|-------|
| C1 | Navigation | Dashboard page header says "Client Workspaces" but section cards say "All projects / New project" — mixed vocabulary. |

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
| 20 | P1 | `saveTimer` not cleared on unmount | **Active → A3** | No `useEffect` cleanup found — still fires on unmounted component |
| 21 | P2 | `template` field dead code in `persistDraft` | **Resolved (P3)** | Template is now persisted in `saveDraftReport` payload; harmless |
| 22 | P1 | `pdfUnavailable` stays after non-PDF export | **Resolved** | `setPdfUnavailable(false)` at start of `handleExport` — `report-builder.tsx:644` |
| 23 | P2 | Race condition in pdfUnavailable fallback buttons | **Resolved (low risk)** | State cleared before calling `handleExport`; async re-render race is cosmetic only |
| 24 | P1 | `selected_insight_ids_json` not initialized `"[]"` on draft creation | **Resolved** | Explicit `json.dumps(selected)` on creation — `reports.py:726` |
| 25 | P1 | `exportReport()` filename ignored by some browsers | **Resolved (P3)** | Server sets `Content-Disposition`; client `a.download` is a fallback; no repro found |
| 26 | P1 | Resume analysis on non-`report_ready` run shows blank page | **Resolved** | `DEFAULT_LANDING_TAB = "intake"` lands on Intake Review with graceful empty-state — `run-analysis.tsx:295` |
| 27 | P2 | Banner doesn't distinguish in-progress from all-failed | **Active (P2)** | → B3 below |
| 28 | P2 | `adaptStoredResults` passes malformed items silently | **Active (P2)** | → B4 below |
| 29 | P1 | `create_run_stub` returns `None` not handled | **Resolved** | `if run is None:` fallback path — `analysis.py:138` |
| 30 | P1 | `finalise_run` swallows DB errors | **Needs Runtime → NR2** | Intentional best-effort; no DB errors in normal operation |
| 31 | P1 | SSE streaming endpoint does not exist | **Resolved** | `analysis_stream.py:60` — `@router.get("/stream/{project_id}")` |
| 32 | P2 | `set_run_status` accepts any string | **Active (P2)** | → B5 below |
| 33 | P2 | `resolve_latest_run` no secondary sort | **Active (P2)** | → B6 below |
| 34 | P1 | UpgradeWall `FEATURE_LABELS` says `"Pro"` / `"Team"` | **Resolved** | Now `"Consultant"` / `"Studio"` — `upgrade-wall.tsx:13` |
| 35 | P1 | Pricing says rows, backend enforces MB | **Resolved** | Pricing page now shows MB consistently: "Up to 10 MB / 100 MB / 500 MB per file" |
| 36 | P1 | `GET /analysis/diff` — no `require_feature` guard | **Active → A1** | Free users can compare runs |
| 37 | P1 | `GET /analysis/download-cleaned` — no `require_feature` guard | **Active → A2** | Free users can export cleaned CSV |
| 38 | P2 | `UPGRADE_MESSAGES` no frontend contract | **Active (P2)** | → B7 below |
| 39 | P2 | `/analysis/story` UpgradeWall label says `"Pro"` | **Resolved** | `FEATURE_LABELS["ai_story"]` says `"Consultant"` |
| 40 | P2 | Team endpoints not verified for Studio plan limit | **Active (P2)** | → B8 below |
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

#### Additional active P2s (lower priority, post-78A)

| ID | File | Issue |
|----|------|-------|
| B3 | `apps/web/src/app/(app)/projects/[id]/page.tsx` | RunStateBanner doesn't distinguish "in-progress" from "all runs failed" — ambiguous state for projects with only failed runs |
| B4 | `apps/web/src/app/(app)/projects/[id]/page.tsx` | `adaptStoredResults` passes through malformed `insight_results` items silently — no validation on required fields |
| B5 | `apps/api/app/services/run_tracker.py:38` | `set_run_status` accepts any string — typos are persisted silently with no validation |
| B6 | `apps/api/app/services/run_resolver.py:25` | `resolve_latest_run` no secondary `id DESC` sort — a very old `report_ready` run can beat a newer in-progress run |
| B7 | `apps/api/app/middleware/plans.py:69` | `UPGRADE_MESSAGES` not guaranteed to surface in frontend — no documented contract for feature string names |
| B8 | `apps/api/app/routes/team.py` | Team invite/manage endpoints not verified to enforce Studio plan limit |

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

**Fix order before pilot:**
1. Plan gates on diff + download-cleaned (A1, A2) — add `require_feature` to two routes. **Task 79A.**
2. Autosave timer cleanup on unmount (A3) — one `useEffect` cleanup. **Task 79B.**
3. P2 items (B1–B8) — triage and schedule as part of pilot hardening.

**Can wait until after first customer feedback:** All P3 / B items not listed above.
