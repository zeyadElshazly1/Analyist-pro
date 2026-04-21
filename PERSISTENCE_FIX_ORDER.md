# Persistence Fix Order

## Goal
Define the order we should fix persistence/state risks without creating chaos.

## Rule
Fix the highest-trust, highest-workflow-risk items first.

## Priority Principles
1. anything that can break project/file identity comes first
2. anything that can break analysis/run continuity comes second
3. anything that can break report/export continuity comes third
4. lower-risk cleanup comes after

---

## Wave 1 — Critical Workflow Identity

Protects: project identity, file identity, source file resolution, prepared dataset resolution.

---

### 1.1 — Wire `dataset_loader.py` to load from `PreparedDataset` before re-cleaning

**File / module:** `apps/api/app/services/dataset_loader.py`
**Exact issue:** Six routes (chat, query, pivot, ml, cohorts, explore) each call a local `_load()` function that reads the raw uploaded file and re-runs the full cleaning pipeline on every request. The `PreparedDataset` model exists (`models.py:233`) and stores the cleaned Parquet artifact keyed by `project_id + file_hash`, but no route uses it. Every request re-cleans from scratch.
**Why it belongs in Wave 1:** File identity resolution — the "current prepared file" for a project should come from persisted storage. If the file cache is cold and the Parquet artifact exists, loading from Parquet is cheaper, stable, and reproducible. Without this, every route is implicitly re-deriving the prepared dataset from scratch, which means the "source of truth" for the current data is a repeated computation rather than a stored artifact.
**What should be changed:** In `dataset_loader.py`, after resolving the file path and computing `file_hash`, check for a `PreparedDataset` row with matching `project_id + file_hash`. If found, load from the stored Parquet path. If not found, run cleaning, then create a `PreparedDataset` row and write the Parquet file. All six routes that call `load_prepared()` benefit automatically.

---

### 1.2 — Add a formal `file_id` FK from `AnalysisResult` to `ProjectFile`

**File / module:** `apps/api/app/models.py` — `AnalysisResult` table
**Exact issue:** `AnalysisResult.file_hash` is a plain string matched against `ProjectFile.file_hash` at query time. There is no foreign key. If a `ProjectFile` row is deleted or its hash is updated, the link between the analysis run and its source file silently breaks — the run still exists but its origin is unresolvable.
**Why it belongs in Wave 1:** This is a file identity issue. An analysis run must formally know which file it was computed from. Without this link, a consultant who returns to a project cannot reliably trace run → source file, which is the first thing they need to trust the output.
**What should be changed:** Add `file_id = Column(Integer, ForeignKey("project_files.id"), nullable=True)` to `AnalysisResult`. Populate it in `analysis_stream.py` when the `AnalysisResult` stub is written (Wave 2.1 below). Add an Alembic migration. The column is `nullable=True` to allow existing rows to remain valid.

---

### 1.3 — Harden the `PROJECT_FILES` DB fallback and never allow it to be bypassed

**File / module:** `apps/api/app/state.py` — `get_project_file_info()`
**Exact issue:** `get_project_file_info()` has a DB fallback that reads from `ProjectFile` on a cache miss. This fallback is the safety net that makes the in-memory dict safe to use as a cache. Several routes access `state.PROJECT_FILES[project_id]` directly (dict access without calling the helper function), which bypasses the fallback entirely.
**Why it belongs in Wave 1:** If any route bypasses the helper and reads the dict directly when the entry is absent, it will either raise a `KeyError` or silently use stale data. File identity must always go through the helper.
**What should be changed:** Audit all call sites that access `PROJECT_FILES` directly. Replace direct dict access with calls to `get_project_file_info()`. Add a comment to `PROJECT_FILES` marking it as a private implementation detail that must not be accessed outside `state.py`.

---

## Wave 2 — Run Continuity

Protects: analysis run persistence, step status continuity, analysis result retrieval, compare linkage.

---

### 2.1 — Write a stub `AnalysisResult` row at pipeline start; update status on each stage

**File / module:** `apps/api/app/routes/analysis_stream.py`
**Exact issue:** No `AnalysisResult` row is written until the pipeline fully completes. If any stage fails, no DB record exists. A consultant who sees an error has no trace of what happened. The system cannot distinguish "run in progress", "run failed at cleaning", or "never started".
**Why it belongs in Wave 2:** This is the core run continuity fix. Without a stub row, failed runs are invisible and in-progress runs are untrackable. Every downstream improvement (failure diagnostics, retry logic, run history display) depends on this.
**What should be changed:**
1. At the beginning of `analysis_stream.py`, before any file processing, write an `AnalysisResult` stub with `status="created"`, `started_at=utcnow()`, `trigger_source="user"`, `file_id` (from Wave 1.2), and `project_id`.
2. Update `status="intake_complete"`, `status="cleaning_complete"`, etc. after each major stage.
3. On any unhandled exception, catch it, set `status="failed"` and `error_summary=str(e)[:500]`, and commit before re-raising.
4. On success, set `status="report_ready"` and commit the full `result_json`.
This requires the Alembic migration from Wave 2.2 to run first.

---

### 2.2 — Add `started_at`, `status`, `trigger_source`, `error_summary` to `AnalysisResult`

**File / module:** `apps/api/app/models.py` — `AnalysisResult` table
**Exact issue:** `AnalysisResult` has `created_at` (completion time only) and no status field. There is no way to represent an in-progress or failed run in the DB, and no way to measure run duration.
**Why it belongs in Wave 2:** These four columns are the prerequisite for Wave 2.1. The Alembic migration should be written and deployed before the analysis stream code changes are shipped.
**What should be changed:** Write one Alembic migration adding:
- `started_at = Column(DateTime(timezone=True), nullable=True)`
- `status = Column(String(32), default="created", nullable=False)`
- `trigger_source = Column(String(32), nullable=True)` — values: `"user"`, `"background_job"`, `"retry"`
- `error_summary = Column(Text, nullable=True)`

---

### 2.3 — Fix `last_insights` — re-hydrate from `AnalysisResult` instead of in-memory dict

**File / module:** `apps/api/app/state.py` + wherever `last_insights` is read (AI chat service)
**Exact issue:** After every analysis run, `analysis_stream.py:299–302` writes the top-5 insight strings into `PROJECT_FILES[project_id]["last_insights"]`. The AI chat service reads this to provide dataset context. This value is never written to the DB and is lost on every server restart. After a restart, the AI chat feature silently provides no context.
**Why it belongs in Wave 2:** The AI chat feature (`ai_chat`) is a paid feature gate. Silent degradation of a paid feature on restart is a direct trust risk. Fixing it is a one-function change once Wave 2.1 has landed (the `AnalysisResult` is now reliably written).
**What should be changed:** In the AI chat service, before reading `PROJECT_FILES[id]["last_insights"]`, check if the value is present. If absent, load the latest `AnalysisResult` for the project from the DB and extract `result_json.get("insights", [])[:5]`. Remove the write to `PROJECT_FILES` after analysis — the value should always be derived from the DB, not cached in memory.

---

### 2.4 — Persist compare output to a `CompareRun` record

**File / module:** `apps/api/app/routes/analysis.py` — `GET /analysis/diff` and `apps/api/app/routes/explore.py` — `POST /explore/multifile`
**Exact issue:** Both compare routes compute a diff result and return it to the caller. Nothing is written to the DB. A consultant cannot reference a previous comparison, and the report builder cannot include compare findings without recomputing on demand.
**Why it belongs in Wave 2:** Compare is the second most important paid feature. The compare-to-report connection (Phase 3 in `V1_BUILD_ORDER.md`) requires a persisted `CompareRun` ID to link to. Without this, Phase 3 cannot be built.
**What should be changed:**
1. Create a `CompareRun` model: `project_id`, `run_a_id` (FK to `AnalysisResult`, nullable), `run_b_id` (FK to `AnalysisResult`, nullable), `file_a_id` (FK to `ProjectFile`), `file_b_id` (FK to `ProjectFile`), `diff_json` (Text), `created_at`.
2. After computing the diff in both routes, write a `CompareRun` row and return `compare_run_id` in the response alongside the existing diff payload.
3. Add Alembic migration for the new table.

---

## Wave 3 — Report / Export Continuity

Protects: report draft persistence, export artifact retrieval, reliable reopening of prior deliverables.

---

### 3.1 — Persist AI story result to `AnalysisResult`

**File / module:** `apps/api/app/routes/analysis.py` — `POST /analysis/story/{analysis_id}`
**Exact issue:** The AI story endpoint generates a 5-slide narrative, returns it to the caller, and writes nothing to the DB. If the user navigates away or reloads, the story is gone. There is no record of which AI model was used or when the story was generated.
**Why it belongs in Wave 3:** The AI story (`ai_story`) is a paid feature. It feeds into report delivery — a consultant who generates an AI story expects to be able to include it in their report draft. Without persistence, it is a one-shot ephemeral output that cannot be referenced by the report builder.
**What should be changed:** Add `story_result_json = Column(Text, nullable=True)` and `ai_model_version = Column(String(64), nullable=True)` to `AnalysisResult`. After generating the story in `POST /analysis/story/{id}`, write the result JSON and model version to the corresponding `AnalysisResult` row. Return the `analysis_id` in the response so the frontend can later retrieve the story from `GET /analysis/{id}`.

---

### 3.2 — Verify `ReportDraft` FK integrity and export call chain

**File / module:** `apps/api/app/models.py` — `ReportDraft` + `apps/api/app/routes/reports.py`
**Exact issue:** `ReportDraft` links to `AnalysisResult` by FK. The export route (`POST /reports/export/{project_id}`) loads the latest `AnalysisResult` for the project and builds the report from its `result_json`. If the `AnalysisResult` row for a project changes (new analysis run), a previously created `ReportDraft` may now reference stale insight IDs.
**Why it belongs in Wave 3:** This is a report continuity issue. A consultant who creates a draft, runs a new analysis, and then exports should either get the draft's original insights or be warned that the underlying data has changed. Currently neither happens — the export silently uses the latest run regardless of which run the draft was created from.
**What should be changed:** Confirm that `ReportDraft.analysis_result_id` FK is set when a draft is created. Modify the export route to load `result_json` from `ReportDraft.analysis_result_id` rather than the project's latest `AnalysisResult`. This ensures export output always matches the run the consultant was reviewing when they built the draft.

---

## Wave 4 — Cleanup / Hardening

Lower-priority items that should happen after the core workflow is safe.

---

### 4.1 — Confirm `MODELS_DIR` is a persistent volume in deployment

**File / module:** `apps/api/app/config.py` + deployment configuration
**Exact issue:** Trained AutoML models are serialised to `MODELS_DIR` on disk. If this directory is inside the container filesystem (e.g. `/tmp` or the container root), all trained models are lost on container restart or redeploy. Failure is silent at training time and only surfaces when a user tries to run predictions.
**Why it belongs in Wave 4:** AutoML is a power tool, not a core workflow feature. The risk is real but the audience is secondary. Fix the deployment config and add a startup warning, but do not block Wave 1–3 work on it.
**What should be changed:** In `config.py`, confirm `MODELS_DIR` defaults to a path that is volume-mounted in the deployment environment. Add a startup check: if `MODELS_DIR` is under `/tmp` or does not exist as a mounted path, log a `WARNING` that AutoML models will not survive restart.

---

### 4.2 — Add LRU eviction to `PROJECT_FILES`

**File / module:** `apps/api/app/state.py`
**Exact issue:** The `PROJECT_FILES` dict accumulates one entry per project loaded in the current process and entries are never evicted. Over a long-running process with many projects, the dict grows unboundedly.
**Why it belongs in Wave 4:** This is a memory growth issue, not a data-correctness issue. The DB fallback already ensures correctness after eviction. Fix after Wave 1–3 changes are stable.
**What should be changed:** Replace the plain `dict` with an `OrderedDict` or `functools.lru_cache` equivalent capped at 200 entries. When the cap is exceeded, evict the least-recently-used entry. The `get_project_file_info()` DB fallback handles reloading evicted entries transparently.

---

### 4.3 — Add `user_id` directly to `AnalysisResult`

**File / module:** `apps/api/app/models.py` — `AnalysisResult`
**Exact issue:** `AnalysisResult` has no `user_id` column. Ownership is derived via `project_id → Project.user_id`. If project ownership ever changes, the run has no independent ownership record.
**Why it belongs in Wave 4:** Not an immediate workflow risk — project ownership does not change in normal usage. Fix after Wave 2 migrations are complete, as a single additional column in the same migration pass.
**What should be changed:** Add `user_id = Column(String, ForeignKey("users.id"), nullable=True)` to `AnalysisResult`. Populate it in `analysis_stream.py` when the stub row is written (already done in Wave 2.1). Add as a nullable column so existing rows remain valid.
