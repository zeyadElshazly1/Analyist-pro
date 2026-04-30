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

## Final Totals (all 10 areas — pre-reconciliation)

| Severity | Count | Description |
|----------|-------|-------------|
| P0 | 3 | Blocks demo / pilot — crash or data corruption |
| P1 | 22 | Hurts trust or core workflow |
| P2 | 15 | Polish / UX gap |
| **Total** | **40** | |

---

## Reconciliation Pass (post-Tasks 1–11)

*Branch: `claude/audit-toolkit-positioning-ADYPw` — clean working tree, up to date with origin.*
*TypeScript compile: zero errors.*

### Stale findings — already fixed in current code

| Issue | Was | Now |
|-------|-----|-----|
| P0-1 cleaning-report "(0 values)" | `n_values_converted` always rendered | `> 0` guard — `cleaning-report.tsx:20` |
| P0-2 Backend missing canonical `cleaning_result` | Raw report list emitted | `build_cleaning_result().model_dump()` stored as `"cleaning_result"` — `analysis.py:124` |
| P0-3 health-score null crash on `columns_with_missing` | Unguarded dereference | `missingness?.columns_with_missing ?? []` — `health-score.tsx:63` |
| P1 SSE endpoint missing | Not in analysis.py | Exists in `analysis_stream.py:60` — `@router.get("/stream/{project_id}")` |
| P1 `diff_pct` null crash in compare | Unguarded arithmetic | `diffPct != null ? ...diffPct.toFixed(1)... : ""` — `multifile-compare.tsx:199` |
| P1 `create_run_stub` None not handled | No fallback | `if run is None:` fallback path — `analysis.py:138` |
| `confPct()` negative confidence | No clamp | Normalises 0–1 → 0–100 correctly — `insights-list.tsx:53–56` |
| CleaningSummaryCards fake zeroes | Showed `NaN` | All values guarded with `?? 0` |
| IntakeReview not wired | Missing | `UploadDataset` renders `<IntakeReview>` after upload |

### Confirmed real issues (current code)

#### P0 — Blocks demo / pilot
**None.** All three original P0s are stale/fixed.

#### P1 — Must fix before pilot

| # | File | Line | Issue |
|---|------|------|-------|
| R1 | `apps/api/app/routes/analysis.py` | 594 | `GET /analysis/diff` — no `require_feature` dep; free users can compare runs |
| R2 | `apps/api/app/routes/analysis.py` | 895 | `GET /analysis/download-cleaned` — no `require_feature` dep; free users can export cleaned CSV |
| R3 | `apps/web/src/components/ui/upgrade-wall.tsx` | 13–33 | `FEATURE_LABELS` says `"Pro"` / `"Team"` — brand is `"Consultant"` / `"Studio"` |
| R4 | `apps/web/src/components/ui/upgrade-wall.tsx` | 30–33 | Upgrade wall cites MB limits (`"10 MB"` / `"100 MB"`) — pricing page shows row counts |
| R5 | `apps/web/src/components/project/report-builder.tsx` | 339–358 | `saveTimer` never cleared on unmount — `setSaved`/`setSaving` fire on unmounted component |
| R6 | `apps/web/src/components/project/report-builder.tsx` | 76, 349 | Draft saves array indices as `selected_insight_ids` — wrong insights recalled if order changes |
| R7 | `apps/web/src/components/project/upload-dataset.tsx` | 118 | Upload hint hardcodes `"Max 100 MB"` — not plan-aware, contradicts pricing page |

#### NEEDS_RUNTIME

| # | Issue | Why |
|---|-------|-----|
| NR1 | Reopen on non-`report_ready` run shows blank page | Backend returns all-null blocks; `RunStateBanner` guards entry; `RunAnalysis` null-block rendering not verified statically |
| NR2 | `finalise_run` swallows DB errors | Intentional best-effort design; real impact depends on Redis availability |

### Corrected final counts

| Severity | Count |
|----------|-------|
| P0 | **0** |
| P1 | **7** (R1–R7) |
| Needs Runtime | 2 |
| Stale / resolved | 9 |

### Recommendation

**Demo is safe to run.** No P0s in current code.

**Fix order before pilot:**
1. UpgradeWall label names + MB vs rows (R3, R4) — 2-line change
2. Autosave timer cleanup (R5) — one `useEffect` cleanup
3. Plan gates on diff + download-cleaned (R1, R2) — add `require_feature` to two routes
4. Report draft index vs ID (R6) — insight ID mapping in draft save/load
5. Upload hint plan-awareness (R7) — pass plan context to upload component

**Recommend fixing all 3 P0s before showing the product to a pilot user with a real file.**

## Must Fix Before Pilot

Beyond P0s, the highest-risk P1s for a live pilot:
- Issue 31: SSE streaming endpoint missing — "Analyze File" button doesn't work
- Issues 36–37: Free users bypass plan gates on diff and CSV export
- Issue 34: Upgrade wall shows wrong plan names
- Issue 26: Reopening a partial run shows blank analysis page

---

## QA Pass Findings — First Pass

_Pass run: 2026-04-27. Read-only code review against the consultant workflow.
Issues are observed in code; runtime repro steps describe how a consultant would
hit each issue during a demo._

## Summary

| Severity | Count |
|----------|------:|
| P0       | 4     |
| P1       | 8     |
| P2       | 8     |
| P3       | 3     |
| **Total**| **23**|

---

## P0 — Blocks demo / pilot

### P0-1. Report export ignores the report draft (selected findings + custom summary)
- **area:** Build Report / Export
- **issue:** The "Build Report" tab lets the consultant pick which insights to
  include, edit narrative summaries, and autosave a `ReportDraft`. The export
  endpoints (`/reports/export?format=html|xlsx|pdf`) do not consume that draft.
  `generate_html_report`, `generate_excel_report`, and `generate_pdf_report` are
  all called with `analysis_result` directly and have no parameter for selected
  insights or custom summary text. `build_context()` in
  `apps/api/app/services/reporting/context.py` does not look at `ReportDraft`.
- **severity:** P0
- **repro steps:**
  1. Run an analysis that produces 8+ insights.
  2. Open Build Report, deselect 6 of the insights so only 2 remain.
  3. Edit the executive summary text.
  4. Export → HTML / Excel / PDF.
- **expected behavior:** Export contains only the 2 selected insights and the
  edited summary text.
- **actual behavior:** Export contains all insights from the latest analysis
  result. Custom summary text is ignored.
- **fix needed:** `/reports/export` must load the `ReportDraft` linked to the
  project (or run), pass `selected_insight_ids` and edited summary fields into
  `build_context`, and the Jinja template / Excel / PDF renderers must filter
  insights and use the draft summary.
- **status:** open

### P0-2. Plan size limits contradict each other across marketing, billing, and middleware
- **area:** Pricing / Billing
- **issue:** Three different stories are told about file-size limits:
  - Marketing (`apps/web/src/app/(marketing)/pricing/page.tsx`): "Up to 10K /
    500K / 2M rows per file".
  - In-app billing (`apps/web/src/app/(app)/billing/page.tsx`): "Up to 10K rows"
    on Free, then "Up to 100 MB / 500 MB per file" on Consultant / Studio.
  - Backend middleware (`apps/api/app/middleware/plans.py`): hard-enforces 10
    MB / 100 MB / 500 MB, regardless of row count.
- **severity:** P0
- **repro steps:**
  1. Sign up on Free plan.
  2. Upload a 12 MB CSV with 4,000 rows (well under "10K rows").
- **expected behavior:** Upload succeeds because rows < 10K, per pricing page.
- **actual behavior:** Backend rejects with 402 / 413 because file > 10 MB.
- **fix needed:** Pick one canonical metric (MB) and align marketing, billing
  page, upload hint, and 402 messages. Or, if rows is the truthful limit, the
  middleware needs to switch to row-counting.
- **status:** open

### P0-3. "Intake Review" tab/step shows no intake data
- **area:** Upload + Intake
- **issue:** `project-tabs.tsx` defines the first step as **"Intake Review"**
  mapped to the `overview` primary tab. But the `overview` tab in
  `run-analysis.tsx` renders StatsCards + HealthScore + CleaningSummaryCards +
  InsightHighlights — never the `IntakeReview` component. The IntakeReview
  component (with parse confidence, header detection, warnings, preview sample)
  is rendered exclusively inside `upload-dataset.tsx`, after the upload click,
  and disappears as soon as the user moves on to "Analyze File".
- **severity:** P0
- **repro steps:**
  1. Upload a CSV.
  2. Click "Analyze File" and let it complete.
  3. Click the "Intake Review" step in the workflow rail.
- **expected behavior:** Tab shows parse status, warnings, low-confidence
  banner, header row detected, preview sample.
- **actual behavior:** Tab shows the generic Overview dashboard. There is no
  way to see intake review again, even mid-session.
- **fix needed:** Render `<IntakeReview/>` on the Intake Review tab using the
  intake data from the run. Requires P0-4 (persistence) to be solved for
  reopened runs.
- **status:** open

### P0-4. `intake_result` is never persisted in stored runs
- **area:** Upload + Intake / Reopen Flow
- **issue:** Upload returns an `intake_result` (parse confidence, warnings,
  preview, header detection). The analysis pipeline does not include
  `intake_result` in the `result_json` it stores. Both
  `apps/api/app/routes/analysis.py::run_analysis` and
  `apps/api/app/routes/analysis_stream.py::_run_analysis_stream` build a
  `result` dict that omits `intake_result`. `/run/{run_id}/results` therefore
  cannot return it.
- **severity:** P0
- **repro steps:**
  1. Upload a malformed CSV that produces a low-confidence parse warning.
  2. Run analysis. Note warning visible during upload.
  3. Refresh the page or come back the next day; reopen the latest run.
- **expected behavior:** Intake Review tab still shows the parse warnings.
- **actual behavior:** No trace of intake review data anywhere in the reopened
  run. Consultant cannot answer "how confident were we in the parse?" after
  the fact.
- **fix needed:** Persist `intake_result` in `result_json` during both run
  paths; include it in `RunResultsResponse`; have `adaptStoredResults` in
  `apps/web/src/app/(app)/projects/[id]/page.tsx` carry it into
  `AnalysisResult`.
- **status:** open

---

## P1 — Hurts trust or core workflow

### P1-1. "Health Check" tab does not show the health score
- **area:** Health Check
- **issue:** Step 3 ("Health Check") maps to the `profile` primary tab, which
  renders only `<ProfileView/>` (per-column profile table). The actual
  `<HealthScore/>` component (grade A–F, verdict, deductions, client readiness,
  affected columns) is rendered on the `overview` tab.
- **severity:** P1
- **repro steps:** Click "Health Check" in the workflow rail.
- **expected behavior:** See grade, verdict, score breakdown, warnings, and
  affected columns.
- **actual behavior:** See only column-level profile statistics; no health
  grade or readiness verdict is on this tab.
- **fix needed:** Move/duplicate `<HealthScore/>` into the `profile` tab, or
  add a `health` primary tab and remap the step.
- **status:** open

### P1-2. Compare result is session-only and lost on reload / reopen
- **area:** Compare / Reopen Flow
- **issue:** `compareResult` lives only in React state in `RunAnalysis`. It is
  not part of `AnalysisResult` returned by `/run/{id}/results`, and
  `adaptStoredResults` does not reconstruct it. Refreshing the page during a
  comparison session, or reopening a run later, drops the compare data.
- **severity:** P1
- **repro steps:**
  1. Run analysis on file A, run "Compare with another file" against file B.
  2. See compare summary, schema diff, metric deltas.
  3. Refresh the page.
- **expected behavior:** Compare result reappears; it is also visible to Build
  Report.
- **actual behavior:** Compare result is gone; Build Report shows no compare
  context for that run.
- **fix needed:** Persist `compare_result` either inside the run's
  `result_json` (when the user attaches a compare to a run) or in a sibling
  table keyed by `run_id`; load it via `adaptStoredResults`.
- **status:** open

### P1-3. Report draft can drift from re-run insights (stale selected indices)
- **area:** Build Report
- **issue:** `ReportDraft.selected_insights` stores insight identifiers that
  index into the analysis result's `insight_results` list. When the consultant
  re-runs analysis, the index positions can shift (insights are recomputed),
  but the draft still points at the same ordinal slots. Combined with P0-1
  (export ignores draft), and P2-3 (`_get_stored_analysis` returns the latest
  run, not the draft's run), this means the Build Report tab can silently
  preview different findings than what the user originally selected.
- **severity:** P1
- **repro steps:**
  1. Run analysis. Select insights #2 and #5 in Build Report. Wait for
     autosave.
  2. Re-run analysis (e.g., after a small file edit) — now insight ordering
     differs.
  3. Reopen Build Report.
- **expected behavior:** Either the original chosen insights are still
  selected (because the draft is keyed to that run), or the user is told the
  draft no longer matches.
- **actual behavior:** Selection silently maps to whatever sits in those
  ordinal positions in the new run.
- **fix needed:** Key `selected_insights` by stable insight IDs (not list
  index) or scope drafts to a specific `analysis_result_id` and refuse to
  load drafts cross-run.
- **status:** open

### P1-4. Upload hint says "Max 100 MB" for everyone
- **area:** Upload + Intake / Pricing
- **issue:** `apps/web/src/components/project/upload-dataset.tsx` shows the
  static hint `CSV, XLSX, XLS · Max 100 MB`. Free plan caps at 10 MB.
- **severity:** P1
- **repro steps:** Sign up on Free plan, open a project. Read upload hint.
- **expected behavior:** Hint reflects the user's plan limit (e.g., "Max 10
  MB on Free — upgrade to Consultant for 100 MB").
- **actual behavior:** "Max 100 MB" is shown to Free users; their first
  upload of an 11 MB file fails with a 402 they did not see coming.
- **fix needed:** Render the hint from the active plan's `max_file_mb`.
- **status:** open

### P1-5. Studio plan CTA is inconsistent (links to /signup vs mailto)
- **area:** Pricing / Billing
- **issue:** Marketing pricing page labels Studio CTA "Contact us" but the
  link is `/signup`. In-app billing labels Studio "Contact sales" with a
  `mailto:sales@...` link. Two different mental models for the same plan.
- **severity:** P1
- **repro steps:** Click "Contact us" on the marketing pricing page.
- **expected behavior:** Opens a contact / sales flow.
- **actual behavior:** Drops the user into the generic signup form for a
  self-serve plan.
- **fix needed:** Pick one path (mailto, or a /contact page) and use it
  consistently.
- **status:** open

### P1-6. Report Builder export history is client-only and lost on refresh
- **area:** Export
- **issue:** `exportHistory` in `apps/web/src/components/project/report-builder.tsx`
  is local React state. The backend already maintains a per-format export log
  in `ReportResult.export_statuses` (sourced from `AuditLog`), but the Report
  Builder never reads it.
- **severity:** P1
- **repro steps:** Export HTML successfully. Refresh the page. Reopen Build
  Report.
- **expected behavior:** Export history strip shows the recent successful
  export.
- **actual behavior:** Export history strip is empty.
- **fix needed:** Hydrate `exportHistory` from `report_result.export_statuses`
  in the draft response and append client-side after a new export.
- **status:** open

### P1-7. Run state banner says "opens at Intake Review" but always opens at Overview
- **area:** Reopen Flow
- **issue:** `RunStateBanner` (and the resume CTA in dashboard / project
  rail) tells the consultant they will resume at "Intake Review", but
  `RunAnalysis` always sets the active tab to `overview` on hydrate.
  Combined with P0-3 (Intake Review tab is empty anyway), the resume copy is
  fully misleading.
- **severity:** P1
- **repro steps:** Resume an in-progress run from the dashboard.
- **expected behavior:** Lands on the Intake Review tab with intake data.
- **actual behavior:** Lands on Overview, which is the dashboard.
- **fix needed:** Either fix the resume target tab to match the copy, or
  update the copy to "opens at Overview" until P0-3 is done.
- **status:** open

### P1-8. CleaningSummaryCards shows always-zero counters when sourced from canonical
- **area:** Cleaning Review
- **issue:** `cleaning-summary-cards.tsx` displays `placeholders_replaced`,
  `duplicate_cols_removed`, and `date_features_created`. None of those keys
  exist in the canonical `CleaningSummary` schema (`apps/api/app/schemas/cleaning.py`)
  and none are populated by `fromCanonical()`. When canonical
  `cleaning_result` is present (the normal path), these counters render as 0
  even when the cleaning step actually did the work.
- **severity:** P1
- **repro steps:** Run analysis on a CSV with placeholders like "N/A",
  "—", or "?".
- **expected behavior:** "Placeholders replaced: N" reflects real value.
- **actual behavior:** "Placeholders replaced: 0", every time.
- **fix needed:** Either add these counters to the canonical
  `CleaningSummary` and have the pipeline emit them, or remove the cards.
  Showing zero numbers makes cleaning look weaker than it is.
- **status:** open

---

## P2 — Polish

### P2-1. Confidence value normalization is inconsistent across paths
- **area:** Findings
- **issue:** Live SSE results carry insight `confidence` as 0.0–1.0
  (canonical). The reopen path's `adaptStoredResults` multiplies confidence
  by 100 (0–100 scale). Consumers (`insights-list.tsx`,
  `insight-highlights.tsx`, `recommended-action.tsx`, `report-builder.tsx`)
  defensively handle both ranges, but the data shape genuinely differs across
  load paths and is a foot-gun for any future code.
- **severity:** P2
- **repro steps:** Add a new component that just reads
  `insight.confidence`. It will produce different numbers for live vs
  reopened runs.
- **fix needed:** Normalize at one boundary; pick canonical 0.0–1.0 and
  remove the ×100 conversion in `adaptStoredResults`.
- **status:** open

### P2-2. ReportBuilder auto-selects insights where `report_safe` is undefined
- **area:** Build Report
- **issue:** Auto-selection (`report-builder.tsx` lines ~304–308) keeps any
  insight where `report_safe !== false`, which includes undefined. This
  pre-selects findings the backend never explicitly cleared as report-safe.
- **severity:** P2
- **fix needed:** Change the condition to `=== true`.
- **status:** open

### P2-3. `_get_stored_analysis` returns the latest run, not the draft's linked run
- **area:** Build Report / Export
- **issue:** `apps/api/app/routes/reports.py::_get_stored_analysis` does
  `order_by(AnalysisResult.created_at.desc()).first()`. The `ReportDraft`
  already carries `analysis_result_id`. With multiple analysis runs in a
  project, exports and the report-result endpoint quietly use the wrong run.
  Tied closely to P0-1 and P1-3.
- **severity:** P2
- **fix needed:** Honor `draft.analysis_result_id` when present.
- **status:** open

### P2-4. `planAtLeast` blows up on legacy plan strings
- **area:** Pricing / Billing
- **issue:** `apps/web/src/lib/plans.ts::planAtLeast` calls
  `PLAN_ORDER.indexOf(userPlan)` directly. If `userPlan` is a legacy value
  (`"pro"`, `"team"`), `indexOf` returns -1 and the function says the user
  is below every tier. Most call sites normalize beforehand, but the helper
  itself is unsafe.
- **severity:** P2
- **fix needed:** Add a frontend `normalizePlan` and call it inside
  `planAtLeast`.
- **status:** open

### P2-5. Cache hit returns immediately, skipping run-stub creation
- **area:** Run Lifecycle
- **issue:** Both `analysis.run_analysis` and `analysis_stream._run_analysis_stream`
  check `get_cached_analysis(...)` *before* calling `create_run_stub`. On a
  cache hit, no new `AnalysisResult` row is added to history, the cached
  result is returned by reference. This is by design but means re-uploading
  the same file does not appear in run history at all, which can confuse a
  consultant looking for "today's run".
- **severity:** P2
- **fix needed:** Either insert a thin run row that points at the cached
  result, or surface a `from_cache: true` indicator in the run history list
  with a tooltip ("Loaded from cache — same file as run #X").
- **status:** open

### P2-6. Pricing FAQ teaser links lead nowhere
- **area:** Pricing / Billing
- **issue:** Pricing page lists "Can I switch plans?", "What about refunds?"
  etc. as styled bullets, but they have no anchors or destinations. Looks
  unfinished in a demo.
- **severity:** P2
- **fix needed:** Either wire them to a FAQ section / contact link or remove
  them.
- **status:** open

### P2-7. Stripe still references legacy env vars `STRIPE_PRO_PRICE_ID` / `STRIPE_TEAM_PRICE_ID`
- **area:** Pricing / Billing
- **issue:** `apps/api/app/routes/billing.py::STRIPE_PLAN_MAP` still falls
  back to the legacy environment names. Harmless if both are set, but
  invites configuration drift between staging and production.
- **severity:** P2
- **fix needed:** Drop the legacy fallbacks once deploys are migrated to the
  canonical env names.
- **status:** open

### P2-8. CleaningSummaryCards prints "undefined × undefined" on the legacy path
- **area:** Cleaning Review
- **issue:** When falling back to legacy `summary` and both `original_rows`
  and `original_cols` are absent, the shape line renders as `undefined ×
  undefined`. Edge case, but visible if the legacy path is ever hit by
  imported data.
- **severity:** P2
- **fix needed:** Guard the fallback with a placeholder ("—") or hide the
  line when shape data is missing.
- **status:** open

---

## P3 — Cleanup later

### P3-1. Product-name typo "Analyist Pro" in user-visible strings
- **area:** Branding
- **issue:** "Analyist Pro" (typo) appears in:
  - `apps/web/src/components/project/report-builder.tsx` line ~610 (preview
    cover footer).
  - `apps/api/app/routes/analysis.py` line ~904 (docstring / comment).
  Other places use "Analyst Pro" or unspaced "AnalystPro". Exported HTML
  template uses "Analyst Pro" correctly.
- **severity:** P3 (P1 if the preview cover screenshot ever appears in a
  demo recording — fix before recording).
- **fix needed:** Standardize to "Analyst Pro" everywhere except the
  Stripe / domain identifiers.
- **status:** open

### P3-2. Header naming drift between page title and section titles
- **area:** Navigation polish
- **issue:** Dashboard page header is "Client Workspaces", but the section
  cards inside say "New project" / "All projects". Mixed vocabulary.
- **severity:** P3
- **fix needed:** Pick one ("Client Workspaces" → "New workspace" / "All
  workspaces" or vice versa).
- **status:** open

### P3-3. Dead `runAnalysis()` sync wrapper in API client
- **area:** Frontend hygiene
- **issue:** `apps/web/src/lib/api.ts` still exports a `runAnalysis()`
  function that POSTs to the sync `/analysis/run` endpoint, but the live
  workflow uses SSE via `/analysis/stream`. The sync helper has no UI
  caller. Drift risk if someone wires it back without realizing it skips
  streaming progress.
- **severity:** P3
- **fix needed:** Either delete the helper or document it as deprecated.
- **status:** open

---

## Exit Verdict (preliminary)

- **Safe for demo today:** Cleaning Review (P1-8 caveat), Findings (P2-1
  caveat), Run Lifecycle (P2-5 caveat). The happy path of upload → analyze
  → see findings → preview report works inside one tab session.
- **Must fix before pilot users:** All P0s (export ignoring draft is the
  killer; rows-vs-MB is the trust killer; intake review tab being a
  facade is a credibility killer). All P1s should be triaged before pilot
  outreach.
- **Can wait until after first customer feedback:** All P2 / P3.

