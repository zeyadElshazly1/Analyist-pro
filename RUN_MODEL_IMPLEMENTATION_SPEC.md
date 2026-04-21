# Run Model Implementation Spec

## Goal
Translate the canonical run concept into an implementation-ready spec.

## Rule
A run must be the central object that connects one analysis execution to its inputs, outputs, status, and artifacts.

---

## 1. Run Definition

**A run is one execution of the analysis pipeline against one specific file version in one project.**

A "file version" is defined by `file_hash` (SHA-256 of the uploaded file content). If the same file is uploaded twice, it has the same hash and reuses the same `PreparedDataset`. If a different file is uploaded to the same project, it has a different hash and creates a new run when analyzed.

**Exactly one run is created per analysis execution.** A run is not per upload (a file can be uploaded without being analyzed), and not per prepared dataset (the same prepared dataset can back multiple runs if the user re-runs analysis on the same file).

**When a run is created:** At the moment the user triggers analysis — before any file processing begins. A stub run record is written immediately with `status="created"`. This means a run always exists for every analysis attempt, including failures.

**What is NOT a run:**
- File upload (no analysis, no run — only a `ProjectFile` record)
- Compare operation (creates a `CompareRun` record, not an analysis run)
- Report draft creation (creates a `ReportDraft` record linked to an existing run)
- AI story generation (updates an existing run record, does not create a new run)

---

## 2. Run Triggers

| Trigger | Source | `trigger_source` value | Creates new run? |
|---------|--------|------------------------|-----------------|
| User clicks "Analyze File" in the app | `analysis_stream.py` | `"user"` | Yes |
| User re-runs analysis on the same file | `analysis_stream.py` | `"user"` | Yes (new run, same `file_hash`) |
| Background job or scheduled analysis | Future background worker | `"background_job"` | Yes |
| User retries after a failed run | `analysis_stream.py` or `analysis.py` | `"retry"` | Yes (new run, references prior failed run id) |
| Non-streaming analysis endpoint | `analysis.py` `POST /analysis/run/{project_id}` | `"user"` | Yes |

**Note:** The non-streaming `analysis.py` route and the streaming `analysis_stream.py` route both produce analysis results but use different code paths. Both must write a run record. This is the root cause of the `"analysis_completed"` vs `"analysis"` action name inconsistency in the audit logs.

---

## 3. Run Lifecycle

```
created
  └─► intake_complete
        └─► cleaning_complete
              └─► profiling_complete
                    └─► insights_complete
                          └─► report_ready
                                └─► export_ready
  └─► failed  (from any stage)
```

### Status definitions

| Status | Meaning | Written when |
|--------|---------|--------------|
| `created` | Stub run written, processing not yet started | Pipeline entry, before file read |
| `intake_complete` | File parsed, structure detected, row/column counts known | After `file_loader` / `sniffer` completes |
| `cleaning_complete` | Cleaning pipeline applied, `PreparedDataset` saved | After `cleaning/pipeline.py` completes |
| `profiling_complete` | Column profiles and health score computed | After `profiling/orchestrator.py` and `health_scorer` complete |
| `insights_complete` | Insights, narrative, and executive panel generated | After `analysis/analyze_dataset()` completes |
| `report_ready` | Full `result_json` committed to DB, run is readable | After `AnalysisResult` is fully written |
| `export_ready` | At least one export artifact has been generated and stored | After first successful export call |
| `failed` | Pipeline stopped at any stage with an unhandled error | In the except block; includes `error_summary` |

### V1 required statuses
`created`, `insights_complete`, `report_ready`, `failed`

### Optional for V1 (add later)
`intake_complete`, `cleaning_complete`, `profiling_complete`, `export_ready`

The minimum useful progression for V1 is: **created → report_ready** (success) or **created → failed** (failure). Intermediate statuses add observability but are not required for the core workflow to be trustworthy.

---

## 4. Run Links

| Link | Type | V1 Required | Notes |
|------|------|-------------|-------|
| `user_id` | FK → `users.id` | No (derive via project) | Useful for independent ownership record; add as nullable |
| `project_id` | FK → `projects.id` | **Yes** | Already on `AnalysisResult` |
| `file_id` | FK → `project_files.id` | **Yes** | Currently a string hash only; add FK |
| `prepared_dataset_id` | FK → `prepared_datasets.id` | No (match by hash) | Add after `PreparedDataset` loader is wired (Wave 1.1) |
| Intake result | Structured field in `result_json` or separate column | No | Currently buried in `cleaning_summary`; extract as `intake_result_json` later |
| Cleaning result | `result_json["cleaning_summary"]` + `result_json["cleaning_report"]` | **Yes (in JSON)** | Already present; no structural change needed for V1 |
| Health/profile result | `result_json["health_score"]` + `result_json["profile"]` | **Yes (in JSON)** | Already present |
| Insights result | `result_json["insights"]` + `result_json["narrative"]` + `result_json["executive_panel"]` | **Yes (in JSON)** | Already present |
| Chart result | Not stored; computed on demand from profile data | No | Deferred |
| Compare result | FK → `compare_runs.id` (new table) | No | Add after `CompareRun` table is created (Wave 2.4) |
| AI summary result | `story_result_json` column on `AnalysisResult` | No | Add as a nullable column (Wave 3.1) |
| Report draft ids | Via `ReportDraft.analysis_result_id` FK (reverse link) | **Yes (reverse FK)** | Already on `ReportDraft`; no change needed |
| Export artifact ids | Not stored; exports generated on demand | No | Deferred |

---

## 5. Required Metadata Fields

| Field | Column Name | Type | V1 Required | Default / Source |
|-------|-------------|------|-------------|-----------------|
| Run ID | `id` | Integer PK | **Yes** | Auto-increment; already exists |
| Project ID | `project_id` | Integer FK | **Yes** | Already exists |
| File ID | `file_id` | Integer FK nullable | **Yes** | Set at stub creation from resolved `ProjectFile` |
| Dataset hash | `file_hash` | String | **Yes** | Already exists (SHA-256) |
| Started at | `started_at` | DateTime(timezone=True) | **Yes** | Written at stub creation — `utcnow()` |
| Finished at | `created_at` | DateTime(timezone=True) | **Yes** | Already exists — rename semantics: this is completion time |
| Status | `status` | String(32) | **Yes** | Default `"created"` |
| Trigger source | `trigger_source` | String(32) | No | `"user"` / `"background_job"` / `"retry"` |
| AI model version | `ai_model_version` | String(64) | No | Written if AI story or AI chat is invoked |
| Error summary | `error_summary` | Text nullable | **Yes** | Written in except block; max ~500 chars |
| User ID | `user_id` | String FK nullable | No | Populate from `project.user_id` at stub creation |
| Full result JSON | `result_json` | Text (JSON) | **Yes** | Already exists; written at `report_ready` |
| Share token | `share_token` | UUID nullable | No | Already exists |
| Share expires at | `share_expires_at` | DateTime nullable | No | Already exists |
| Share revoked | `share_revoked` | Boolean | No | Already exists |

---

## 6. Current Model Mapping

### `AnalysisResult` — the run record, incomplete

`AnalysisResult` (`models.py`) is structurally the run record. It already holds the right core content but is missing several metadata fields.

| Run concept | Current state on `AnalysisResult` |
|-------------|-----------------------------------|
| Run ID | ✅ `id` (integer PK) |
| Project link | ✅ `project_id` (FK) |
| File version | ✅ `file_hash` (SHA-256 string) — but no FK to `ProjectFile` |
| Full result | ✅ `result_json` (all pipeline outputs packed as JSON) |
| Completion time | ✅ `created_at` |
| Share link | ✅ `share_token`, `share_expires_at`, `share_revoked` |
| **Status** | ❌ Missing — no field; only completed runs exist |
| **Started at** | ❌ Missing — no `started_at`; duration unmeasurable |
| **Trigger source** | ❌ Missing |
| **Error summary** | ❌ Missing — failed runs leave no record |
| **File FK** | ❌ Missing — `file_hash` string only |
| **User ID** | ❌ Missing — derived via project |
| **AI model version** | ❌ Missing |

### `ReportDraft` — correctly linked, complete for V1

`ReportDraft` (`models.py`) has `analysis_result_id` FK → `AnalysisResult`. It stores `title`, `summary`, `selected_insight_ids_json`, `selected_chart_ids_json`, `template`, `created_at`, `updated_at`. This is the correct shape for a run-linked deliverable record. No structural change needed for V1 — only the export path fix from `PERSISTENCE_FIX_ORDER.md` Wave 3.2.

### `PreparedDataset` — sibling, not linked

`PreparedDataset` (`models.py:233`) holds `project_id`, `file_hash`, `stored_path`, `cleaning_meta_json`, `created_at`. It shares the same `project_id + file_hash` composite with `AnalysisResult` but there is no FK between them. They are matched at query time by composite key. For V1 this is acceptable — add a `prepared_dataset_id` FK after the loader is wired (Wave 1.1).

### `AuditLog` — records successful completions only

`AuditLog` (`models.py`) records `action="analysis"` on success. It is not a run record — it is an observability event. It does not replace the run record and should not be expanded to serve that role.

### `CompareRun` — does not exist yet

No compare run record exists. Both compare routes (`GET /analysis/diff` and `POST /explore/multifile`) are stateless. This is the second-largest gap after the run status fields.

---

## 7. Implementation Recommendation

### Extend `AnalysisResult` — do not create a new table

`AnalysisResult` already is the run record. Its `result_json` holds all pipeline outputs. `ReportDraft` already links to it. The audit log references it by `resource_id`. Creating a separate `AnalysisRun` table would require migrating all existing foreign key references and duplicating the record structure.

**Extend `AnalysisResult` with the missing fields.** This is additive: all new columns are nullable or have safe defaults, so existing rows remain valid.

### What to do first

**One Alembic migration, shipped before any code changes:**

```python
# Migration: add run model fields to analysis_results

op.add_column("analysis_results", sa.Column("started_at",      sa.DateTime(timezone=True), nullable=True))
op.add_column("analysis_results", sa.Column("status",          sa.String(32), server_default="report_ready", nullable=False))
op.add_column("analysis_results", sa.Column("trigger_source",  sa.String(32), nullable=True))
op.add_column("analysis_results", sa.Column("error_summary",   sa.Text, nullable=True))
op.add_column("analysis_results", sa.Column("file_id",         sa.Integer, sa.ForeignKey("project_files.id"), nullable=True))
op.add_column("analysis_results", sa.Column("user_id",         sa.String, sa.ForeignKey("users.id"), nullable=True))
op.add_column("analysis_results", sa.Column("ai_model_version",sa.String(64), nullable=True))
op.add_column("analysis_results", sa.Column("story_result_json",sa.Text, nullable=True))
```

`status` for existing rows defaults to `"report_ready"` (they were all successful completions). `started_at` defaults to NULL (acceptable — historical runs have no start time).

### What to do second

Modify `analysis_stream.py` to:
1. Write the stub `AnalysisResult` with `status="created"`, `started_at=utcnow()`, `trigger_source="user"`, `file_id` at pipeline entry.
2. Update `status` at `insights_complete` after the insight generation stage.
3. On exception: set `status="failed"`, `error_summary=str(e)[:500]`, commit, then yield the error event to the client.
4. On success: set `status="report_ready"`, commit full `result_json`.

### What should wait until later

- Structured `intake_result_json` column (currently buried in `cleaning_summary` — extract in a later pass)
- `prepared_dataset_id` FK (add after Wave 1.1 PreparedDataset loader is wired)
- `CompareRun` table (add as a separate migration after Wave 2.4)
- `export_ready` status (add when export artifact persistence is built in Wave 3)
- Separate first-class columns for cleaning result, health result, insights result (the JSON blob works for V1; column extraction adds query flexibility but is not required yet)
