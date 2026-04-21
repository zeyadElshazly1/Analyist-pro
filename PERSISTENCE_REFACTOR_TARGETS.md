# Persistence Refactor Targets

## Goal
Identify the exact backend places that must be refactored so workflow-critical state comes from persistent storage, not in-memory state.

## Rule
We are not listing every technical cleanup item.
We are listing only the places that could break trust, reliability, or resumability for paying users.

## Priority Levels

### P0
Can break the main workflow or cause wrong project/file/run behavior.

### P1
Can cause inconsistency, confusion, or deployment risk.

### P2
Should be cleaned later, but not urgent for V1 foundation.

## Required Table

| Priority | File / Module | Current Risky State Usage | Why It Is Risky | What Should Become Source of Truth | Recommended Refactor |
|---|---|---|---|---|---|
| **P0** | `apps/api/app/state.py` + `apps/api/app/routes/analysis_stream.py:299–302` | `PROJECT_FILES[project_id]["last_insights"]` — top-5 insight strings written to in-memory dict after each analysis run | Lost on every server restart or worker recycle. The AI chat service reads this to give context about the dataset. If empty, it silently provides no context — the paid AI chat feature degrades without any error shown to the user | `AnalysisResult.result_json["insights"]` in the DB — the full insight list is already stored there | On AI chat requests, if `PROJECT_FILES[id]["last_insights"]` is missing or empty, load the latest `AnalysisResult` for the project and extract `result_json["insights"][:5]` as the fallback. Remove the write to `PROJECT_FILES` after analysis and derive this on demand from DB. |
| **P0** | `apps/api/app/routes/analysis_stream.py` (entire run) | No `AnalysisResult` row is written until the pipeline fully completes. If any stage fails, no record exists. | A paying user who sees a spinner stop with an error has no persistent trace of what stage failed or why. The audit log only records successes (`action="analysis"`). Failed runs are invisible in the DB — the system cannot distinguish "never ran" from "failed midway". | `AnalysisResult` with a `status` field, written as a stub at pipeline entry | Write a stub `AnalysisResult` row with `status="created"` and `started_at=utcnow()` at the start of `analysis_stream.py` before any processing. Update `status` at each stage. On failure, set `status="failed"` and write `error_summary`. On success, set `status="report_ready"`. |
| **P1** | `apps/api/app/models.py` — `AnalysisResult` | `AnalysisResult` has no `started_at`, no `status`, no `trigger_source`, no `error_summary` columns | Cannot measure run duration. Cannot represent an in-progress run. Cannot distinguish "running" from "never started" from "failed". The report builder and billing metrics depend on being able to trust run records. | `AnalysisResult` extended with four new columns | Add Alembic migration: `started_at DATETIME`, `status VARCHAR(32) DEFAULT 'created'`, `trigger_source VARCHAR(32)`, `error_summary TEXT`. Populate `started_at` and `status` as described in the P0 row above. |
| **P1** | `apps/api/app/routes/analysis.py` — `POST /analysis/story/{analysis_id}` | AI story (5-slide narrative) is generated and returned to the caller but never written to any DB table | A consultant who navigates away after generating an AI story loses it permanently. There is no way to retrieve a previously generated story. A report draft cannot reference or include a stored story. The model/version used is also never recorded. | A `story_result` column on `AnalysisResult` or a separate `StoryResult` table | Add a `story_result_json` column to `AnalysisResult` (or a child `StoryResult` table). After generating the AI story, write the result and the `ai_model_version` string used. Return the persisted record's ID in the response so the frontend can later retrieve it. |
| **P1** | `apps/api/app/routes/analysis.py` — `GET /analysis/diff` and `apps/api/app/routes/explore.py` — `POST /explore/multifile` | Compare results are computed on demand and returned to the caller. No `CompareRun` record is written. | A consultant cannot reference a previous comparison from a report draft. The compare-to-report connection (the second most important paid workflow) requires persisted compare output — there is nothing to link to. Each compare is also re-computed from scratch on every call, wasting time on large files. | A `CompareRun` table linking two `AnalysisResult` or `ProjectFile` rows with stored diff output | Create a `CompareRun` model: `project_id`, `run_a_id` (FK to AnalysisResult), `run_b_id` (FK to AnalysisResult), `diff_json`, `created_at`. Write a `CompareRun` row on each compare call. Return the `compare_run_id` in the response. The report builder can then reference a `CompareRun` by ID. |
| **P1** | `apps/api/app/services/automl/trainer.py` + deployment config | Trained ML models are serialised to `MODELS_DIR` on disk. If `MODELS_DIR` is inside a container with no volume mount, trained models are lost on container restart. | A user who trained a model and returns to run predictions will get a "model not found" error after any container restart or deployment. Silent data loss — no error at training time, failure only at prediction time. | `MODELS_DIR` on a persistent volume (bind mount or managed disk) | In `apps/api/app/config.py`, confirm `MODELS_DIR` defaults to a path outside the container filesystem. Add a startup check that logs a warning if `MODELS_DIR` is inside `/tmp` or a non-persistent path. Document the volume mount requirement in deployment docs. |
| **P2** | `apps/api/app/state.py` — `PROJECT_FILES` dict | The `PROJECT_FILES` dict accumulates entries for every project loaded in the current process. Entries are never evicted. | Over a long-running process with many projects, the dict grows unboundedly. Not a data-correctness risk, but a memory growth risk in production. The DB fallback already exists so this is safe to evict. | `ProjectFile` DB table + disk (already is the real source of truth) | Add a simple LRU eviction policy (e.g. max 200 entries) or a TTL-based expiry on `PROJECT_FILES` entries. The DB fallback in `get_project_file_info()` ensures correctness after eviction. |

---

## What Counts As Risky
- app.state holding workflow-critical current file/project/run data
- globals holding user/project/file-linked state
- temporary process memory being treated as canonical truth
- routes that assume current file context without loading from DB/storage
- export/report logic depending on non-persisted state

## What Does NOT Count
- safe caching
- memoization
- derived read-only short-lived helpers
- performance-only temporary objects that can be rebuilt safely

## Deliverable
At the end of this doc, we should know the exact persistence-first refactor targets for the backend.

---

## Summary

| Priority | Target | Impact |
|----------|--------|--------|
| P0 | `last_insights` in-memory — re-hydrate from `AnalysisResult` | Stops silent AI chat degradation on restart |
| P0 | Write stub `AnalysisResult` at pipeline start, update on failure | Makes failed runs visible in the DB |
| P1 | Add `started_at`, `status`, `trigger_source`, `error_summary` to `AnalysisResult` | Enables run duration, in-progress state, failure diagnostics |
| P1 | Persist AI story result to `AnalysisResult` or `StoryResult` | Stops AI story loss on navigation; enables report-to-story linking |
| P1 | Persist compare output to `CompareRun` table | Enables compare-to-report connection |
| P1 | Confirm `MODELS_DIR` is volume-mounted in deployment | Stops silent ML model loss on restart |
| P2 | Add LRU eviction to `PROJECT_FILES` | Prevents unbounded memory growth in long-running processes |
