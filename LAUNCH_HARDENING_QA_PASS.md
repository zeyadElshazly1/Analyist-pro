# Launch Hardening QA Pass

## Goal
Run a focused QA and hardening pass on the consultant workflow before demo mode and pilot outreach.

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

## Issues Log

<!-- Last updated: areas 1–7 audited; areas 8–10 pending -->

---

### Area 1 — Upload + Intake

| # | File | Line | Sev | Issue |
|---|------|------|-----|-------|
| 1 | `apps/web/src/components/analysis/cleaning-report.tsx` | 20 | P0 | `n_values_converted` is rendered even when 0, producing "(0 values)" noise on every type fix row |
| 2 | `apps/api/app/services/cleaning/pipeline.py` + `upload.py` | — | P0 | Backend doesn't emit the canonical `CleaningResult` schema — returns raw report list; frontend's `cleaningItemsFromCanonical()` never runs because `cleaning_result` block is missing/wrong shape |
| 3 | `apps/web/src/components/analysis/stats-cards.tsx` | 42 | P1 | Null dereference on `rowCount` before `.toLocaleString()` — crashes when `dataset_summary` is absent |
| 4 | `apps/web/src/components/analysis/stats-cards.tsx` | 55 | P1 | Coercion produces `"undefined%"` in missing-data display when `missing_pct` is undefined |

---

### Area 2 — Cleaning Review

| # | File | Line | Sev | Issue |
|---|------|------|-----|-------|
| 5 | `apps/web/src/components/project/cleaning-review.tsx` | 204 | P1 | `confidence_score` renders as "0/100" when `cleaning_summary` is undefined (should be hidden) |
| 6 | `apps/web/src/components/analysis/cleaning-summary-cards.tsx` | 108–109 | P1 | `NaN` in delta calculations — arithmetic on potentially undefined fields |
| 7 | `apps/web/src/components/analysis/cleaning-summary-cards.tsx` | 120–122 | P1 | `"undefined × N"` in template interpolation — missing null guard |

---

### Area 3 — Health Check

| # | File | Line | Sev | Issue |
|---|------|------|-----|-------|
| 8 | `apps/web/src/components/analysis/health-score.tsx` | 63 | P0 | `columns_with_missing` dereference assumed to exist — crashes if null (uncaught TypeError in render) |
| 9 | `apps/web/src/components/analysis/health-score.tsx` | 133 | P1 | Null sneaks through `??` chain in score reading — displays incorrect fallback instead of actual score |

**Subtotal areas 1–3: 3 P0, 5 P1**

---

### Area 4 — Findings

| # | File | Line | Sev | Issue |
|---|------|------|-----|-------|
| 10 | `apps/web/src/components/analysis/insights-list.tsx` | 58–68 | P1 | `isReportSafe()` returns `true` when `report_safe` is undefined and severity is missing — overpromotes low-quality findings |
| 11 | `apps/web/src/components/analysis/insights-list.tsx` | 53–56 | P2 | `confPct()` does not clamp negative confidence values — `-0.5` becomes `-50%` |
| 12 | `apps/web/src/components/analysis/insight-highlights.tsx` | 31 | P1 | Confidence normalization duplicated inline rather than shared — canonical (0–1) and legacy (0–100) insights sort incorrectly when mixed |
| 13 | `apps/web/src/components/analysis/recommended-action.tsx` | 39 | P2 | `!!(i.recommendation ?? i.action)` passes empty strings — insights with `recommendation: ""` appear in the action list |

---

### Area 5 — Compare

| # | File | Line | Sev | Issue |
|---|------|------|-----|-------|
| 14 | `apps/web/src/components/analysis/multifile-compare.tsx` | 82–86 | P1 | `rowVol.diff_pct` used without null guard — `NaN` or crash when API returns undefined |
| 15 | `apps/web/src/components/analysis/multifile-compare.tsx` | 115–116 | P2 | `Number(overlapPct).toFixed(1)` — `NaN` when `overlap_pct_of_a` is null |
| 16 | `apps/web/src/components/analysis/multifile-compare.tsx` | 101–113 | P1 | Legacy `a_mean`/`b_mean` field mapping coexists with canonical `mean_a`/`mean_b` — silent mismatch when legacy path is taken |

---

### Area 6 — Report Builder

| # | File | Line | Sev | Issue |
|---|------|------|-----|-------|
| 17 | `apps/web/src/components/project/report-builder.tsx` | 299–335 | P1 | `getDraftReport()` catch block silently swallows errors — load failure is invisible to the user |
| 18 | `apps/web/src/components/project/report-builder.tsx` | 353–358 | P2 | `saveDraftReport()` failure is silently swallowed — user has no feedback if autosave fails |
| 19 | `apps/web/src/components/project/report-builder.tsx` | 322 | P1 | `selected_insight_ids` are used as array indices on load but saving passes them as-is — index vs ID contract is undocumented and fragile |
| 20 | `apps/web/src/components/project/report-builder.tsx` | 339–359 | P1 | Autosave `setTimeout` not cleared on unmount — fires on unmounted component, potential memory leak |
| 21 | `apps/web/src/components/project/report-builder.tsx` | 283 | P2 | `template` field in `Draft` type is set but never persisted in `persistDraft()` — dead code |

---

### Area 7 — Export

| # | File | Line | Sev | Issue |
|---|------|------|-----|-------|
| 22 | `apps/web/src/components/project/report-builder.tsx` | 388–405 | P1 | `pdfUnavailable` is not cleared at the start of `handleExport()` for non-PDF formats — banner stays visible after a successful HTML/Excel export |
| 23 | `apps/web/src/components/project/report-builder.tsx` | 879, 887 | P2 | Fallback buttons in pdfUnavailable banner call `handleExport()` after calling `setPdfUnavailable(false)` — race condition, state may not have updated |
| 24 | `apps/api/app/routes/reports.py` | 295–322 | P1 | `selected_insight_ids_json` not initialized to `"[]"` on draft creation — `None` stored, JSON parse fails on next load |
| 25 | `apps/web/src/lib/api.ts` | 965 | P1 | `exportReport()` filename comes from client-side `a.download` attribute; some browsers ignore this when Content-Disposition is set by the server — download name may be wrong |

**Subtotal areas 4–7: 9 P1, 8 P2**

---

### Area 8 — Reopen Flow

| # | File | Line | Sev | Issue |
|---|------|------|-----|-------|
| 26 | `apps/web/src/app/(app)/projects/[id]/page.tsx` | 144–169 | P1 | "Resume analysis" button appears when `has_result=true` but `getRunResults` returns all-null blocks for non-`report_ready` runs — user sees a blank analysis page |
| 27 | `apps/web/src/app/(app)/projects/[id]/page.tsx` | 144 | P2 | Banner doesn't distinguish "run in progress" from "all runs failed" — shows ambiguous state for projects with only failed runs |
| 28 | `apps/web/src/app/(app)/projects/[id]/page.tsx` | 42–46 | P2 | `adaptStoredResults` passes through malformed `insight_results` items silently — no validation or warning for missing required fields |

---

### Area 9 — Run Lifecycle

| # | File | Line | Sev | Issue |
|---|------|------|-----|-------|
| 29 | `apps/api/app/routes/analysis.py` | 81–82 | P1 | `create_run_stub` returns `None` on DB failure; `set_run_status` and `finalise_run` are then called with `run=None` and silently no-op — run status is never persisted |
| 30 | `apps/api/app/services/run_tracker.py` | 38–60 | P1 | `set_run_status` and `finalise_run` swallow `SQLAlchemyError` silently — DB commit failures are invisible; run record stays at `"created"` while result is returned successfully |
| 31 | `apps/api/app/routes/analysis.py` | — | P1 | **SSE streaming endpoint (`GET /analysis/stream/{project_id}`) does not exist in the codebase** — frontend's `EventSource` always gets a 404 which triggers `onerror`, making the "Analyze File" button non-functional for real users |
| 32 | `apps/api/app/services/run_tracker.py` | 38–60 | P2 | `set_run_status` accepts any string — typos like `"cleanng_complete"` are persisted silently with no validation against the canonical status enum |
| 33 | `apps/api/app/services/run_resolver.py` | 25–49 | P2 | `resolve_latest_run` returns any `report_ready` run regardless of timestamp — an old completed run beats a newer in-progress run; no secondary sort by `id desc` |

---

### Area 10 — Pricing / Billing

| # | File | Line | Sev | Issue |
|---|------|------|-----|-------|
| 34 | `apps/web/src/components/ui/upgrade-wall.tsx` | 13–33 | P1 | `FEATURE_LABELS` hardcodes `"Pro"` and `"Team"` plan names — pricing page says `"Consultant"` and `"Studio"`; users see conflicting names when hitting upgrade walls |
| 35 | `apps/web/src/app/(marketing)/pricing/page.tsx` | 23–38 | P1 | Pricing says "Up to 500K rows per file" for Consultant but backend enforces `max_file_mb=100` — a wide dataset can hit the limit at far fewer rows; row-count claim is misleading |
| 36 | `apps/api/app/routes/analysis.py` | 594–600 | P1 | `GET /analysis/diff` (file comparison) has no `require_feature("file_compare")` guard — free users can compare runs without upgrading |
| 37 | `apps/api/app/routes/analysis.py` | 895–954 | P1 | `GET /analysis/download-cleaned/{project_id}` has no `require_feature("report_export")` guard — free users can download cleaned CSV exports |
| 38 | `apps/api/app/middleware/plans.py` | 69–71 | P2 | `UPGRADE_MESSAGES` messages are correct but not guaranteed to surface in frontend — no documented contract for feature string names between backend and `UpgradeWall` |
| 39 | `apps/api/app/routes/analysis.py` | 565–592 | P2 | `POST /analysis/story` correctly gates on `ai_story` but `UpgradeWall` label says `"Pro"` — inconsistent with `"Consultant"` on pricing page |
| 40 | `apps/api/app/routes/team.py` | — | P2 | Team invite/manage endpoints not verified to enforce Studio plan limit — free or Consultant users may be able to invite team members |

---

## Final Totals (all 10 areas)

| Severity | Count | Description |
|----------|-------|-------------|
| P0 | 3 | Blocks demo / pilot — crash or data corruption |
| P1 | 22 | Hurts trust or core workflow |
| P2 | 15 | Polish / UX gap |
| **Total** | **40** | |

## Safe for Demo?

The `/demo` page bypasses upload and analysis — **the demo itself is safe** as long as none of the P0 components are rendered. The 3 P0 issues only trigger when real data flows through the cleaning/health pipeline:
- P0 #1 (cleaning-report "(0 values)") — triggered during Cleaning Review with real file
- P0 #2 (cleaning_result contract) — triggered during Cleaning Review with real file
- P0 #3 (health-score crash) — triggered during Health Check with real file

**Recommend fixing all 3 P0s before showing the product to a pilot user with a real file.**

## Must Fix Before Pilot

Beyond P0s, the highest-risk P1s for a live pilot:
- Issue 31: SSE streaming endpoint missing — "Analyze File" button doesn't work
- Issues 36–37: Free users bypass plan gates on diff and CSV export
- Issue 34: Upgrade wall shows wrong plan names
- Issue 26: Reopening a partial run shows blank analysis page

