# Canonical Run Model

## Goal
Every analysis execution should produce one clear, traceable run object.

## Problem
If the system stores results in scattered ways, it becomes hard to:
- debug failures
- trust outputs
- compare runs
- resume work later
- generate reports reliably

## Rule
A project analysis should create one canonical run record that links all major outputs together.

## Each Run Should Link To
- user
- project
- source file(s)
- prepared dataset
- intake result
- cleaning result
- health/profile result
- insights result
- chart result
- compare result if used
- AI summary result
- report draft(s)
- export artifact(s)
- timestamps
- status

## Required Run Statuses
- created
- intake_complete
- cleaning_complete
- profiling_complete
- insights_complete
- report_ready
- export_ready
- failed

## Required Metadata
- run id
- project id
- file ids
- dataset version/hash
- started at
- finished at
- trigger source
- model/version used if AI was involved
- error summary if failed

## V1 Principle
A consultant should be able to return to a project later and clearly see:
- what run happened
- what file it used
- what outputs were generated
- what report/export came from it

---

## Current Run Model Audit

### What Already Exists That Behaves Like a Run Model

**`AnalysisResult` table** is the closest thing to a canonical run record.

Fields it has today:

| Field | Purpose |
|-------|---------|
| `id` | Unique run identifier |
| `project_id` | Links run to a project |
| `file_hash` | SHA-256 of the source file at analysis time |
| `result_json` | Full analysis output packed as one JSON blob |
| `share_token` | Public share link UUID |
| `share_expires_at` | Share link expiry |
| `share_revoked` | Share link revocation flag |
| `created_at` | Run completion timestamp |

**`result_json` contains all major outputs in one object:**
- `dataset_summary` — row/column counts, domain, missing %
- `cleaning_summary` — before/after counts, steps applied, confidence, time saved estimate
- `cleaning_report` — per-step detail list (step name, detail, impact)
- `health_score` — total score, grade, breakdown dimensions, deductions, per-column health, fix suggestions
- `profile` — per-column statistics list
- `insights` — ranked findings list (type, severity, finding, evidence, action)
- `narrative` — plain-English summary paragraph
- `executive_panel` — opportunities, risks, and action plan

**`ReportDraft` is a child record** linked to `AnalysisResult` by foreign key — drafts can be created, edited, and versioned from a stored run.

**`PreparedDataset`** shares the same `project_id + file_hash` composite key as `AnalysisResult`, tying the cleaned Parquet artifact to the same file version.

**`AuditLog`** records successful analysis completions with action `"analysis_completed"`, project and insight count in detail.

---

### What Pieces Are Scattered

**File linkage is by hash string, not by foreign key**
`AnalysisResult.file_hash` is a string that matches `ProjectFile.file_hash`, but there is no foreign key relationship. The run is not formally attached to a `ProjectFile` row. If a file record is deleted or rehashed, the link between run and file silently breaks.

**No user_id on the run**
`AnalysisResult` has no `user_id` field. Ownership is derived indirectly: run → project → user. If ownership of a project ever changes, the run has no independent ownership record.

**All outputs packed into one JSON blob**
Cleaning results, health score, insights, profile, and narrative all live in `result_json`. They cannot be queried independently, updated in isolation, or linked to downstream records (e.g. "this report draft used these specific insights from this run's output"). If `result_json` is corrupt or truncated, all outputs for that run are lost together.

**`PreparedDataset` and `AnalysisResult` are siblings, not linked**
No foreign key exists between them. The system matches them by `file_hash + project_id` at query time, which is fragile if a project has multiple files with the same hash (edge case but possible).

**No started_at timestamp**
`created_at` is the completion time. There is no `started_at`, so run duration cannot be measured. Slow or failed runs leave no timing trace.

**No trigger_source field**
There is no field indicating whether the run was started by a user, a background job, a webhook, or a retry. Debugging why a run happened is not possible from the record alone.

**Intake metadata is buried in cleaning output**
Parse metadata (detected header row, preamble rows, delimiter, encoding) is stored inside `cleaning_summary` within `result_json`. It is not a first-class field. There is no structured `intake_result` that can be read independently or surfaced to the user as a separate step output.

**Compare runs are not linked to analysis runs**
`GET /analysis/diff` diffs two `AnalysisResult` rows directly. There is no `CompareRun` record that stores the comparison output, links to the two source runs, or can be referenced by a report draft. Compare outputs are ephemeral — they are computed on demand and never persisted.

**AI summary results are not stored**
`POST /analysis/story/{analysis_id}` generates a 5-slide AI narrative. The result is returned to the caller but never written to the DB. There is no record of which AI model was used, what was generated, or when. A consultant cannot retrieve a previously generated story.

**Failed runs leave no record**
Analysis is all-or-nothing. If the pipeline fails at any stage, no `AnalysisResult` row is written and no error record exists. The audit log only captures successes. A consultant who sees a spinner stop with an error has no way to retrieve what stage failed or why, and the system has no trace of the attempt.

**No run status field**
There is no status progression. A run either exists (success) or does not exist (failure or in-progress). There is no way to represent `in_progress`, `failed`, or `partial`.

---

### What Is Missing to Make Runs Canonical

| Missing Element | Current State | What Is Needed |
|-----------------|---------------|----------------|
| `user_id` on run | Derived via project → user join | Direct `user_id` FK on `AnalysisResult` |
| `file_id` FK | `file_hash` string only | FK to `ProjectFile.id` |
| `prepared_dataset_id` FK | Matched by `project_id + file_hash` | Direct FK between run and PreparedDataset |
| `status` field | No field; only completed runs exist | Status enum: `created` → `failed` or `export_ready` |
| `started_at` | Not stored | Timestamp written at pipeline start, before DB commit |
| `error_summary` | Not stored | Short text field written on failure |
| `trigger_source` | Not stored | Enum: `user`, `background_job`, `retry` |
| `ai_model_version` | Not stored | String written when AI features are invoked |
| Structured intake record | Buried in `cleaning_summary` JSON | Separate `intake_result` JSON field or table |
| Persisted compare result | Ephemeral, computed on demand | `CompareRun` record linking two `AnalysisResult` rows with stored diff output |
| Persisted AI story result | Returned but never saved | `StoryResult` record or field on `AnalysisResult` |
| In-progress / failed run records | Nothing written on failure | Write a stub record at start, update status at each stage |
