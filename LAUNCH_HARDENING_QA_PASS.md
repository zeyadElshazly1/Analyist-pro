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

### Areas 8–10 — Reopen Flow, Run Lifecycle, Pricing

*Audit in progress.*

---

## Running Totals (areas 1–7)

| Severity | Count |
|----------|-------|
| P0 | 3 |
| P1 | 14 |
| P2 | 8 |
| **Total** | **25** |

