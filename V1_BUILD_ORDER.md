# V1 Build Order

## Goal
Define the exact order we should build or fix things in so we do not waste time.

## Rule
Build in the order that improves:
1. core workflow completion
2. trust
3. report delivery
4. monetization

## Recommended Build Order

### Phase 1 — Foundation
- pricing/plan name alignment
- persistence/state risk fixes
- canonical run model design
- result schema standardization

### Phase 2 — Core Workflow Reliability
- intake review polish
- cleaning/health polish
- insight evidence layer
- compare workflow polish

### Phase 3 — Client Delivery
- report builder V1
- export reliability
- report/report-section assembly UX
- add findings/charts/compare results into report

### Phase 4 — Product Focus
- navigation simplification
- power tools demotion
- homepage messaging rewrite
- pricing page alignment

### Phase 5 — Measurement + Sales Readiness
- event tracking for core workflow
- core success metrics
- first demo workspace
- first paid offer preparation

## Build Rule
Do not spend serious time improving advanced tools before the main workflow is reliable and sellable.

---

## Current Status Check

### Which Phases Are Already Partly Done

**Phase 1 — Foundation: ~25% done (documented, not built)**

| Item | Status |
|------|--------|
| Pricing/plan name alignment | Documented in `PRICING_PLAN_ALIGNMENT.md`. Not fixed. Backend (`middleware/plans.py:43,51`) still uses `"pro"` and `"team"`. Frontend pricing page correctly says "Consultant"/"Studio" but the billing app page and API responses still return `"pro"`. |
| Persistence/state risk fixes | `PreparedDataset` model exists (`models.py:233`) — the Parquet artifact persistence design is in place. The `PROJECT_FILES["last_insights"]` in-memory risk is documented but not resolved. |
| Canonical run model design | Documented in `CANONICAL_RUN_MODEL.md`. No `started_at`, `status`, `trigger_source`, or `error_summary` fields added to `AnalysisResult` yet. |
| Result schema standardization | Documented in `RESULT_SCHEMA_STANDARDIZATION.md`. No code changes made. Confidence scale mismatch and column reference inconsistency in insights still exist in the codebase. |

**Phase 2 — Core Workflow Reliability: ~40% done**

| Item | Status |
|------|--------|
| Intake review polish | `intake-review.tsx` component built (137 lines). Backend parse metadata needs to be confirmed as returned in upload response. |
| Cleaning/health polish | `cleaning-review.tsx` component built (158 lines). Cleaning pipeline is fully functional. |
| Insight evidence layer | Insights are generated with `finding`, `evidence`, `action` fields. Column reference inconsistency (`col_a`/`col_b` vs `column` vs `columns`) still present. |
| Compare workflow polish | Compare works (multifile, column compare, diff runs). No narrative summary, no anomaly escalation, and compare findings cannot be added to a report. |

**Phase 3 — Client Delivery: ~50% done**

| Item | Status |
|------|--------|
| Report builder V1 | `report-builder.tsx` component built (235 lines) with template picker, insight selection checkboxes, and PDF/XLSX export links. Backend `POST /reports/draft` and `ReportDraft` model exist. |
| Export reliability | HTML, PDF, and XLSX export pipelines work. PDF has a silent fallback to HTML documented in Step 14 of the implementation plan. The `report-builder.tsx` now uses direct href links for PDF/XLSX rather than the `exportReport()` API function — should be verified. |
| Report/section assembly UX | Template picker and insight selection exist in `report-builder.tsx`. No section reorder, no comparison block slot, no visual preview of the assembled output. |
| Add compare results into report | Not built. Compare step and report builder remain disconnected. |

**Phase 4 — Product Focus: ~60% done**

| Item | Status |
|------|--------|
| Navigation simplification | Done. `project-tabs.tsx` uses a 5-step progress bar with an "Advanced tools" collapsible drawer. Power tools are demoted. |
| Power tools demotion | Done. SQL, AutoML, A/B tests, Segments, Pivot, Join are in the drawer and hidden by default. |
| Homepage messaging rewrite | Partially done. Headline, subheadline, badge, and outcome proofs are already consultant-focused. Feature card copy (AI-powered insights, Time series, Export-ready) and How It Works step 3 ("11 analysis tabs") still need rewrites per `HOMEPAGE_MESSAGING_V1.md`. |
| Pricing page alignment | Partially done. Pricing page correctly uses "Consultant"/"Studio". Backend still uses `"pro"`/`"team"`. Billing app page and API responses are misaligned. |

**Phase 5 — Measurement + Sales Readiness: ~25% done**

| Item | Status |
|------|--------|
| Event tracking for core workflow | 6 activation events exist: `upload`, `analysis_completed`/`analysis` (duplicate names), `compare_used`, `report_draft_created`, `export_completed`. 24 events missing including all failure events and billing funnel events. |
| Core success metrics | Documented in `CORE_METRICS_V1.md`. 5 of 11 metrics are partially measurable from existing events. |
| First demo workspace | Not created. |
| First paid offer preparation | Documented in `FIRST_PAID_OFFER.md`. 3 blockers identified. |

---

### Which Phase Should Start First in Practice

**Phase 1 items that are documentation-only should not delay Phase 3 work.**

The documentation in Phases 1 and 2 is done. The actual code fixes for plan naming, result schema, and the run model are real engineering tasks — but they do not block the most commercially important work, which is Phase 3.

**Start with Phase 3 — Client Delivery.** The export pipeline is the primary paid hook. It works, but the assembly experience before export is too thin to sell confidently. A consultant who opens the report builder today sees a form with no preview and no way to include comparison findings. Fixing that is the highest-ROI improvement available right now: it does not require new infrastructure, it directly supports the first paid offer, and it removes the most visible gap during a demo.

**Run Phase 1 plan-naming fix in parallel.** It is a one-day, high-impact change (rename `"pro"` → `"consultant"` and `"team"` → `"studio"` in `middleware/plans.py` and billing display). It should not wait for Phase 3 to finish because a paying customer who upgrades today sees the wrong plan name.

---

### What the Next Real Engineering Target Should Be

**Target: Connect the report builder to the full workflow — three concrete changes**

**1. Wire the PDF export button properly** (`apps/web/src/components/project/report-builder.tsx`)
The report builder links to `/api/reports/export/{id}?format=pdf` as a direct `<a href>`. This should go through the authenticated `exportReport()` API function instead of a bare link to avoid auth header stripping. One of the highest-trust moments in the paid workflow is clicking "Export PDF" — it must work reliably.

**2. Add a comparison block to the report builder** (`apps/web/src/components/project/report-builder.tsx` + `apps/api/app/routes/reports.py`)
Add a `comparison_notes` text field to `ReportDraft`. In the Compare step, add an "Add to report" button next to key compare findings (schema changes, metric deltas, health delta). Clicking it writes the finding text into `comparison_notes`. The report builder shows this field as an editable block. This single connection makes the two biggest paid features — compare and export — feel like one workflow instead of two disconnected tools.

**3. Fix the Report step primary tab** (`apps/web/src/components/project/project-tabs.tsx:61`)
Change `primaryTab: "ask-ai"` to `primaryTab: "overview"` (or link directly to `/reports/{id}`). Clicking "Report" in the step bar should take the user to the report builder, not to an AI chat window. This is a one-line fix with immediate UX impact.

**After those three:** Fix plan naming (`"pro"` → `"consultant"` in `middleware/plans.py`). Then instrument `analysis_failed` and `export_failed` audit events. Then build the first demo workspace with sample files.
