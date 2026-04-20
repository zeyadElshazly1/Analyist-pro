# Backend Single Source of Truth

## Goal
Project, file, analysis run, and report state must come from persistent storage first, not temporary app memory.

## Problem
If important workflow state depends on in-memory app state:
- reloads can break flows
- deployment becomes fragile
- background jobs become harder
- multiple server instances become risky
- trust drops for paying users

## Rule
The backend must treat the database + storage as the source of truth.

## Must Be Persisted
- users
- projects
- uploaded files
- file metadata
- prepared datasets
- cleaning results
- health/profile results
- analysis runs
- comparison runs
- report drafts
- export artifacts

## App Memory Should Only Be Used For
- caching
- temporary performance optimization
- short-lived computed state

## Never Rely On App Memory For
- current project file identity
- latest analysis ownership
- canonical run results
- export availability
- billing or plan enforcement

## Desired Principle
If the server restarts, the user should still be able to open the project and continue from persisted state.

---

## Current Risk Audit

### HIGH — Workflow-Critical In-Memory State

#### `app/state.py` — `PROJECT_FILES` dict
- **What it holds:** File paths, filenames, file hashes, sizes, and `last_insights` for every active project. Acts as the routing layer — routes call `get_project_file_info(project_id)` to resolve the current file path.
- **Is it safe?** Partially. The dict is a cache backed by the `ProjectFile` DB table and disk scan. On a cache miss the system recovers from the database. However if the DB fallback fails (e.g. path no longer on disk), the project becomes inaccessible until re-upload.
- **Verdict:** Safe cache for file path resolution. Dangerous if treated as the only source. Current code has a DB fallback — this must be maintained and never bypassed.

#### `app/state.py` → `PROJECT_FILES[id]["last_insights"]`
- **What it holds:** List of top 5 insight strings written after each analysis run. Used by the AI chat service to provide context about the dataset.
- **Is it safe?** No. This is never persisted. Lost on every server restart or worker recycle. The `AnalysisResult` table holds the full analysis JSON, which includes insights — but `last_insights` is not read back from DB on cache miss.
- **Verdict:** Dangerous workflow state disguised as a cache. If AI chat quality depends on this, it silently degrades on restart. Should be derived from the persisted `AnalysisResult` instead.

---

### MEDIUM — Partially Persisted

#### `app/services/automl/trainer.py` — `_artifacts` (function-local)
- **What it holds:** Trained ML pipeline, label encoder, feature names, and metrics assembled during a training run.
- **Is it safe?** Yes — the dict is immediately serialised to disk via `joblib.dump()` through `app/services/automl/persistence.py`. The in-memory copy is temporary and discarded after the function returns.
- **Verdict:** Safe. Disk-backed. Only risky if `MODELS_DIR` is ephemeral (e.g. container with no volume mount).

---

### LOW — Pure Performance Caches (safe)

#### `app/services/cache.py` — `_redis_client`, `_redis_available`
- **What it holds:** Lazy Redis connection singleton. Caches analysis results keyed by `project_id:file_hash` with a 1-hour TTL.
- **Verdict:** Safe cache. Analysis re-runs if cache is cold. No workflow data lost.

#### `app/middleware/auth.py` — `_jwks_client`
- **What it holds:** Cached Supabase JWKS public key client for JWT verification.
- **Verdict:** Safe. Re-fetched from Supabase JWKS endpoint on restart. Auth continues to work.

#### `app/services/audit.py` — `_fail_count`, `_EXECUTOR`
- **What it holds:** Consecutive DB-write failure counter and background thread pool for audit log writes.
- **Verdict:** Safe. In-flight audit writes at crash time may be lost, but audit logs are non-critical observability data.

#### `app/limiter.py` — `limiter` / `app.state.limiter`
- **What it holds:** Rate limit counters (in-memory by default, configurable for Redis).
- **Verdict:** Safe. Counters reset on restart — briefly allows more requests than intended, not a data risk.

#### `app/worker.py` — `celery_app`
- **What it holds:** Celery task queue config backed by Redis.
- **Verdict:** Safe. Task queue state lives in Redis, not in process memory.

---

### NONE — Immutable Config / Hard-Coded Constants (no risk)

| File | Variables | Notes |
|------|-----------|-------|
| `app/config.py` | `UPLOAD_DIR`, `MAX_UPLOAD_BYTES`, `ALLOWED_EXTENSIONS`, etc. | Env vars + defaults. Immutable at runtime. |
| `app/services/cleaning/constants.py` | `_BOOL_TRUE`, `_BOOL_FALSE`, `_CURRENCY_RE`, date formats | Hard-coded cleaning patterns. |
| `app/services/cleaning/semantic.py` | `_ID_KEYWORDS`, `_EMAIL_RE`, etc. | Hard-coded column type detection patterns. |
| `app/services/profiling/dataset_classifier.py` | `_TX_KEYWORDS`, `_AMT_KEYWORDS`, etc. | Hard-coded dataset classification patterns. |
| `app/services/analysis/ranking.py` | `_SEV_WEIGHT` | Hard-coded severity weights for insight ranking. |
| `app/services/ai_chat/llm_client.py` | `_INTENT_HINTS`, `_CLAUDE_MODEL` | Hard-coded LLM config and prompt hints. |
| `app/services/correlation_matrix/num_num.py` | `skew_cache` (function-local) | Per-call temp dict, discarded on return. |

---

## Risk Summary

| Risk | File | Variable | Safe Cache or Dangerous? |
|------|------|----------|--------------------------|
| HIGH | `app/state.py` | `PROJECT_FILES` | Safe cache — but DB fallback must never be removed |
| HIGH | `app/state.py` | `last_insights` (nested) | Dangerous — silently degrades on restart, not re-hydrated from DB |
| MEDIUM | `automl/trainer.py` | `_artifacts` | Safe if `MODELS_DIR` is a persistent volume |
| LOW | `cache.py` | `_redis_client` | Safe cache — graceful degradation |
| LOW | `auth.py` | `_jwks_client` | Safe cache — re-fetched on restart |
| LOW | `audit.py` | `_fail_count`, `_EXECUTOR` | Safe — non-critical observability data |
| LOW | `limiter.py` | `limiter` | Safe — rate counters only |
| NONE | config, constants, patterns | various | Immutable — no risk |

## Action Items

1. **Fix `last_insights`** — on AI chat requests, if `PROJECT_FILES[id]["last_insights"]` is empty, read insights from the latest `AnalysisResult` row in the DB instead of silently returning nothing.
2. **Verify `MODELS_DIR` is volume-mounted** in any containerised deployment so trained ML models survive restarts.
3. **Never remove the DB fallback** in `get_project_file_info()` — it is the safety net that makes `PROJECT_FILES` safe to use as a cache.
