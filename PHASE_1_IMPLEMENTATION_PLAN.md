# Phase 1 Implementation Plan

## Goal
Prepare the codebase foundation for a trustworthy V1.

## Phase 1 Scope
1. pricing/plan name alignment
2. persistence/state risk fixes
3. canonical run model design
4. result schema standardization

## Success Condition
After Phase 1, the product foundation should be clearer, more stable, and easier to build on.

## Workstreams

### A. Pricing / Plan Alignment
Tasks:
- choose final plan names
- map all current names in frontend
- map all current names in backend
- map all current names in billing/Stripe
- define one canonical naming system
- list files that must be updated

Deliverable:
- one source of truth for plans and feature gates

### B. Persistence / State Audit
Tasks:
- list all risky workflow-critical in-memory state
- separate safe cache from dangerous app-state dependencies
- identify routes/services that need persistence-first refactor
- define what entities must always be loaded from DB/storage

Deliverable:
- exact refactor target list

### C. Canonical Run Model
Tasks:
- define what a run is
- define what outputs belong to a run
- define run statuses
- define run metadata
- map current tables/models to run concept
- identify missing links

Deliverable:
- a clear run model spec ready for implementation

### D. Result Schemas
Tasks:
- identify current intake result shape
- identify cleaning result shape
- identify health/profile result shape
- identify insight result shape
- identify compare result shape
- identify report result shape
- mark inconsistencies
- rank which schemas to standardize first

Deliverable:
- prioritized schema standardization plan

## Phase 1 Rule
Do not code random improvements before these foundation pieces are clear.

---

## Immediate Execution Order

1. **Plan / pricing name alignment (Workstream A)**
   All four workstreams are documented. This one has zero implementation risk, takes one day, and has immediate user-trust impact. A paying user who upgrades to the "Consultant" plan and sees `"pro"` displayed in the app will assume the billing failed. The exact file list and line numbers are already in `PRICING_PLAN_ALIGNMENT.md`. Rename `"pro"` → `"consultant"` and `"team"` → `"studio"` in `middleware/plans.py`, the billing page display, the DB default, and the three frontend locations where plan name is shown. Write and run an Alembic migration to update any existing `plan = "pro"` rows to `"consultant"`. This is a contained rename with no behaviour change.

2. **Result schema standardization — InsightResult first (Workstream D)**
   Schema inconsistencies affect everything downstream: the report builder's insight selection cannot reliably reference columns, confidence values from different stages cannot be compared, and the run model (Step 4) should store consistently shaped data from the start. The priority is `InsightResult`: add a stable `id` field, replace `col_a`/`col_b`/`column`/`columns` with one `columns_referenced: list[str]` field, and normalize `confidence` to `0.0–1.0`. Do not attempt to standardize all five schemas at once — fix InsightResult, ship it, then move to CleaningResult and IntakeResult in a subsequent pass. The full prioritization is in `RESULT_SCHEMA_STANDARDIZATION.md`.

3. **Persistence / state risk fixes (Workstream B)**
   With plan names correct and insight schemas stable, fix the two real in-memory risks. First: `PROJECT_FILES["last_insights"]` in `analysis_stream.py` stores the top-5 insight strings in memory and is never written to the DB. Move this into the `AnalysisResult.result_json` or a dedicated field so it survives a server restart. Second: wire `dataset_loader.py` to load from `PreparedDataset` (Parquet on disk) when `project_id + file_hash` match, rather than re-running cleaning on every route call. The `PreparedDataset` model already exists (`models.py:233`) — the loader just needs to use it. Both fixes remove silent degradation on server restart without any user-visible behaviour change.

4. **Canonical run model — add status, started_at, error fields (Workstream C)**
   With stable schemas and persistent datasets in place, extend `AnalysisResult` to become a proper run record. Add `started_at` (written at pipeline entry), `status` (enum: `created` → `failed` or `export_ready`), `trigger_source` (enum: `user`/`background_job`/`retry`), and `error_summary` (short text written on failure). Write a stub `AnalysisResult` row at the start of `analysis_stream.py` before processing begins, and update its `status` at each pipeline stage. This enables Metric 7 (Analysis Failure Rate), makes partial failures visible in the DB, and gives the report builder a reliable run record to attach drafts to. Deliver as one Alembic migration + changes to `analysis_stream.py` and `analysis.py`.
