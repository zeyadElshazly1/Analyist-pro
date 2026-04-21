# Result Schema Implementation Spec

## Goal
Turn the schema standardization work into an implementation-ready spec.

## Rule
The backend should return predictable result shapes for each core workflow stage so the frontend, reports, and orchestration layer stay clean.

---

## 1. Priority Order

Implementation order is ranked by inconsistency severity and downstream consumer breadth — not by pipeline order.

| # | Schema | Why This Priority | Primary Dependent |
|---|--------|------------------|-------------------|
| 1 | **InsightResult** | Most inconsistent. Column references use three different field shapes. Confidence is 0–100 while every other stage uses 0.0–1.0. No `id` field, so report builder has no stable way to reference specific insights. | Report builder insight selection (`report-builder.tsx`), export pipeline, AI chat context |
| 2 | **CleaningResult** | Confidence is 0–100 (same mismatch as InsightResult). Cleaning review UI and report trust indicators depend on this. One-field fix. | `cleaning-review.tsx`, `cleaning_report` in export |
| 3 | **IntakeResult** | Already the most consistent output (confidence is 0.0–1.0 ✅, warnings list exists). Needs only `id`, `schema_version`, `row_count`, `column_count`. | `intake-review.tsx`, run model stub (links file parse to run) |
| 4 | **HealthResult** | Mostly correct. Main gap: field is named `total` not `total_score` — every consumer must know this divergence. | Health tab, export PDF/XLSX, compare delta |
| 5 | **CompareResult** | Two routes return different shapes. No `comparable` signal, no `match_confidence`, no `client_summary`. Needed before compare-to-report connection can be built. | Compare step, `CompareRun` table, report comparison block |
| 6 | **ReportResult** | Display adapter (Jinja2 context), not raw pipeline data. Lowest risk to standardize — it reads from the other schemas. Fix the upstream schemas first. | PDF/HTML/XLSX export templates |

---

## 2. IntakeResult Spec

### Required fields (V1)

| Field | Type | Notes |
|-------|------|-------|
| `file_kind` | `str` | `"flat_table"` / `"excel"` / `"csv"` |
| `header_row` | `int \| None` | Detected 0-indexed header row |
| `table_start_row` | `int \| None` | First data row after any preamble |
| `confidence` | `float` | **0.0–1.0** — already correct ✅ |
| `warnings` | `list[str]` | Parse warnings, empty list if clean |
| `status` | `str` | `"ok"` / `"parsed_with_warnings"` / `"fallback"` |
| `row_count` | `int` | **ADD** — rows in loaded DataFrame |
| `column_count` | `int` | **ADD** — columns in loaded DataFrame |

### Optional fields

| Field | Type | Notes |
|-------|------|-------|
| `footer_start_row` | `int \| None` | Detected footer row |
| `metadata_rows` | `list[int]` | Rows identified as metadata/preamble |
| `parsing_decisions` | `list[str]` | Human-readable log of decisions made |
| `metadata` | `dict` | Extracted title, source, notes |
| `tables_found` | `int` | For multi-table Excel files |
| `selected_table` | `int` | Which table was used |

### Example shape
```json
{
  "file_kind": "excel",
  "header_row": 2,
  "table_start_row": 3,
  "footer_start_row": null,
  "confidence": 0.92,
  "warnings": ["2 preamble rows detected and skipped"],
  "status": "parsed_with_warnings",
  "row_count": 1247,
  "column_count": 15,
  "metadata_rows": [0, 1],
  "parsing_decisions": ["Used row 2 as header (confidence 0.92)", "Sheet 'Data' selected"]
}
```

### Current gaps
- `row_count` and `column_count` not on `ParseReport` — add to `report.py` dataclass, populated in `file_loader.py` after DataFrame is loaded
- No `id` field — add if intake result needs to be referenced by the run model (deferred to run model work)
- `ParseReport` is a Python dataclass, not serialised to the DB — it is returned in the analysis result but not stored independently; this is acceptable for V1

---

## 3. CleaningResult Spec

### Required fields (V1)

| Field | Type | Notes |
|-------|------|-------|
| `rows_before` | `int` | Row count before cleaning |
| `rows_after` | `int` | Row count after cleaning |
| `columns_before` | `int` | Column count before cleaning |
| `columns_after` | `int` | Column count after cleaning |
| `steps_applied` | `list[dict]` | Each step: `{step, detail, impact}` |
| `confidence_score` | `float` | **CHANGE: 0.0–1.0** (currently 0–100 integer) |
| `confidence_grade` | `str` | `A` / `B` / `C` / `D` / `F` — already produced ✅ |
| `time_saved_estimate` | `str` | e.g. `"~8 minutes"` |

### Optional fields

| Field | Type | Notes |
|-------|------|-------|
| `steps_skipped` | `list[str]` | Steps that were evaluated but not applied |
| `columns_renamed` | `dict[str, str]` | Old → new column name map |

### Example shape
```json
{
  "rows_before": 1250,
  "rows_after": 1247,
  "columns_before": 15,
  "columns_after": 15,
  "steps_applied": [
    {"step": "remove_duplicates", "detail": "3 exact duplicate rows removed", "impact": "high"},
    {"step": "normalize_whitespace", "detail": "Leading/trailing spaces stripped in 4 columns", "impact": "low"}
  ],
  "confidence_score": 0.84,
  "confidence_grade": "B",
  "time_saved_estimate": "~8 minutes"
}
```

### Current gaps
- **`confidence_score` is 0–100 integer** (`cleaning/quality_score.py:55` returns `max(0, min(100, round(score)))`). Change the final return to divide by 100: `max(0.0, min(1.0, round(score) / 100))`. Update any consumer that reads this field (report builder trust indicator, cleaning review UI).
- `steps_applied` structure (step/detail/impact) is already consistent ✅

---

## 4. HealthResult Spec

### Required fields (V1)

| Field | Type | Notes |
|-------|------|-------|
| `total_score` | `int` | **RENAME from `total`** — 0–100 integer |
| `grade` | `str` | `A` / `B` / `C` / `D` / `F` ✅ |
| `label` | `str` | `"Excellent"` / `"Good"` / `"Fair"` / `"Poor"` / `"Critical"` ✅ |
| `breakdown` | `dict[str, int]` | Dimension → score (completeness, consistency, validity, uniqueness) ✅ |
| `deductions` | `list[str]` | Human-readable deduction reasons ✅ |
| `column_health` | `dict[str, dict]` | Per-column health score and issues ✅ |
| `fix_suggestions` | `list[dict]` | Actionable fix options ✅ |
| `dataset_type_confidence` | `float` | 0.0–1.0 — already correct ✅ |

### Optional fields

| Field | Type | Notes |
|-------|------|-------|
| `color` | `str` | Hex color for grade display |
| `business_impact` | `dict` | Unreliable row count, duplicate row count, outlier estimate |
| `max_scores` | `dict` | Maximum possible score per dimension |
| `dataset_type` | `str` | Detected dataset type (e.g. `"transactional"`) |

### Example shape
```json
{
  "total_score": 78,
  "grade": "B",
  "label": "Good",
  "breakdown": {"completeness": 85, "consistency": 72, "validity": 80, "uniqueness": 75},
  "deductions": ["Missing data in 'revenue': -5 pts", "Mixed types in 2 columns: -3 pts"],
  "column_health": {
    "revenue": {"score": 65, "issues": ["12% missing", "3 outliers"]}
  },
  "fix_suggestions": [
    {"issue": "Missing data", "options": [{"action": "Fill with median", "effect": "Safe for skewed columns", "risk": "Low"}]}
  ],
  "dataset_type": "transactional",
  "dataset_type_confidence": 0.85
}
```

### Current gaps
- **Field is named `total`, not `total_score`** (`health_scorer.py:247`). Every consumer must know this. Rename `"total"` → `"total_score"` in the return dict and update all consumers: `reporting/context.py`, `reporting/charts.py`, `routes/analysis_stream.py`, `routes/analysis.py`, `multifile_compare.py`.
- `color` and `max_scores` are internal display details — acceptable to keep but should not be required by downstream consumers.

---

## 5. InsightResult Spec

Each insight in the `insights` list must conform to this shape.

### Required fields (V1)

| Field | Type | Notes |
|-------|------|-------|
| `id` | `str` | **ADD** — stable string, e.g. `"insight_001"`. Used by report builder to select specific insights. |
| `type` | `str` | **CONSTANT** — one of: `correlation` / `anomaly` / `trend` / `distribution` / `quality` / `segment` |
| `severity` | `str` | `"high"` / `"medium"` / `"low"` (current code uses `"high"`/`"medium"`; unify to three levels) |
| `confidence` | `float` | **CHANGE: 0.0–1.0** (currently 0–100 across all generators) |
| `title` | `str` | Short label for display ✅ |
| `finding` | `str` | Full sentence description ✅ |
| `evidence` | `str` | Statistical basis ✅ |
| `action` | `str` | Recommended next step ✅ |
| `columns_referenced` | `list[str]` | **ADD/REPLACE** — all column names involved. Replaces `col_a`/`col_b` in correlation insights and the implicit column name in text-only insights. |

### Optional fields

| Field | Type | Notes |
|-------|------|-------|
| `chart_type` | `str` | Suggested chart for this insight |
| `chart_data` | `dict` | Pre-computed chart data payload |

### Example shape
```json
{
  "id": "insight_003",
  "type": "correlation",
  "severity": "high",
  "confidence": 0.82,
  "title": "Revenue correlates with Ad Spend",
  "finding": "Revenue and Ad Spend have a strong positive correlation (r=0.82).",
  "evidence": "Pearson r=0.82, p<0.001, n=1247 observations",
  "action": "Consider increasing Ad Spend allocation to test for revenue lift.",
  "columns_referenced": ["revenue", "ad_spend"]
}
```

### Current gaps
- **No `id` field** — add sequential ID during insight assembly in the analysis orchestrator, before writing to `result_json`
- **`confidence` is 0–100** in all four generators (`correlation.py:62`, `anomalies.py:45`, `anomalies.py:93`, `trends.py:63`). Divide each by 100 at the point of construction.
- **`col_a` / `col_b` in `correlation.py:63–64`** — replace with `"columns_referenced": [col1, col2]`
- **Anomaly, trend, distribution, quality insights have no column reference field** — column name is embedded in text only. Add `"columns_referenced": [col]` at the point of insight construction in each generator.
- **`severity` uses `"high"`/`"medium"` but not `"low"`** — add `"low"` as the third level for informational insights; replace `"info"` if used.
- **`type` values are string literals** defined inline in each generator, not from a shared constant. Define `INSIGHT_TYPES` in `services/analysis/constants.py` and import in each generator.

---

## 6. CompareResult Spec

### Required fields (V1)

| Field | Type | Notes |
|-------|------|-------|
| `comparable` | `bool` | **ADD** — are these files the same dataset refreshed? |
| `match_confidence` | `float` | **ADD** — 0.0–1.0 estimate of how likely files represent the same dataset |
| `schema_changes` | `dict` | Added, removed, renamed columns ✅ (already in multifile compare) |
| `row_delta` | `dict` | `{before, after, change, change_pct}` |
| `health_delta` | `dict` | `{score_before, score_after, change}` |
| `metric_changes` | `list[dict]` | Per-column: `{column, mean_before, mean_after, change_pct, flagged}` |
| `quality_changes` | `dict` | Missing % delta, new null columns, resolved issues |

### Optional fields

| Field | Type | Notes |
|-------|------|-------|
| `client_summary` | `dict` | `{top_findings: list[str], caution_flags: list[str]}` — plain-English for report |
| `row_overlap` | `dict` | `{count, pct}` — hash-based row overlap |
| `insight_diff` | `dict` | `{new: list, resolved: list, unchanged: list}` — from diff runs |

### Example shape
```json
{
  "comparable": true,
  "match_confidence": 0.91,
  "schema_changes": {
    "added": ["new_channel"],
    "removed": [],
    "renamed": [{"from": "Rev", "to": "Revenue"}]
  },
  "row_delta": {"before": 1200, "after": 1247, "change": 47, "change_pct": 0.039},
  "health_delta": {"score_before": 72, "score_after": 78, "change": 6},
  "metric_changes": [
    {"column": "revenue", "mean_before": 12400, "mean_after": 14800, "change_pct": 0.194, "flagged": true}
  ],
  "quality_changes": {"missing_pct_delta": -0.02, "new_null_columns": [], "resolved_issues": ["duplicates"]},
  "client_summary": {
    "top_findings": ["Revenue mean up 19% — largest change this period", "New column 'new_channel' appeared"],
    "caution_flags": ["Paid Social mean dropped 16% — verify source file"]
  }
}
```

### Current gaps
- **Two routes return different shapes**: `GET /analysis/diff` returns nested `{run_a, run_b, metric_deltas, insight_diff, column_diff}`; `POST /explore/multifile` returns flat dict with `health_score_a`, `health_score_b`, etc. These must converge to one shape.
- **No `comparable` or `match_confidence`** — add a simple heuristic: if `>60%` of column names overlap and row counts are within 50% of each other, mark `comparable=true` with confidence based on schema overlap percentage.
- **No `client_summary`** — add a summary generator function that takes the compare result and produces 2–4 plain-English finding strings ranked by magnitude.

---

## 7. ReportResult Spec

`ReportResult` is not a pipeline output — it is the assembled display context passed to export templates (`reporting/context.py`). The spec here is what the context must include to produce a reliable export.

### Required fields (V1)

| Field | Type | Notes |
|-------|------|-------|
| `project_name` | `str` | Source project name |
| `source_file` | `str` | Original filename |
| `analysis_timestamp` | `str` | ISO 8601 timestamp of the analysis run |
| `row_count` | `int` | Rows analyzed |
| `column_count` | `int` | Columns analyzed |
| `cleaning_steps_count` | `int` | Number of cleaning steps applied |
| `health_score` | `int` | From `HealthResult.total_score` |
| `health_grade` | `str` | From `HealthResult.grade` |
| `insights` | `list[dict]` | Selected `InsightResult` items |
| `profile` | `list[dict]` | Per-column stats from profiling |
| `narrative` | `str` | Plain-English summary paragraph |

### Optional fields

| Field | Type | Notes |
|-------|------|-------|
| `executive_summary` | `str` | From `ReportDraft.summary` if set |
| `compare_summary` | `str` | From `CompareRun.client_summary` if attached |
| `ai_story` | `list[dict]` | 5-slide narrative if generated |
| `template_name` | `str` | Which report template was used |

### Current gaps
- **`context.py` reads `health_score.breakdown`** but the actual key is `health_score["breakdown"]` — verify consistent key access after `total` → `total_score` rename
- **`context.py` and `charts.py` read profile as `dict.get("columns", [])`** but profiling returns a `list` directly — this is the profile schema bug identified in the implementation plan (Step 1)
- **No `analysis_timestamp` or `source_file` in current context** — these must be pulled from the `AnalysisResult` record and added to the template context

---

## 8. Standardization Strategy

### Standardize first — no large rewrites needed

**InsightResult confidence + column references** — each insight generator independently produces a confidence value and column reference. The fix is mechanical: divide confidence by 100 in each generator, rename `col_a`/`col_b` to `columns_referenced`, add `columns_referenced: [col]` to single-column generators. Routes/services affected:
- `services/analysis/correlation.py` — `col_a`/`col_b` + confidence
- `services/analysis/anomalies.py` — confidence only; add `columns_referenced`
- `services/analysis/trends.py` — confidence only; add `columns_referenced`
- `services/analysis/distributions.py` — add `columns_referenced`
- `services/analysis/data_quality.py` — add `columns_referenced`

**CleaningResult confidence** — one-line fix in `cleaning/quality_score.py:55`. Divide return value by 100.

**HealthResult field rename** — rename `"total"` → `"total_score"` in `health_scorer.py:247`. Update all consumers by searching for `.get("total"` in the codebase.

### Wrap/adapt without rewrites

**InsightResult `id` field** — add sequential ID assignment in the analysis orchestrator after all insight lists are merged and ranked, before writing to `result_json`. No generator needs to change.

**IntakeResult `row_count`/`column_count`** — add two fields to the `ParseReport` dataclass in `report.py` and populate them in `file_loader.py` after the DataFrame is loaded. No structural change.

### Wait until later

**CompareResult unification** — merging the two compare route response shapes requires either a new shared serializer or redirecting one route to call the other. Do this when the `CompareRun` table is built (Wave 2.4 in `PERSISTENCE_FIX_ORDER.md`).

**ReportResult template context standardization** — fix the profile schema bug (Step 1 in the implementation plan) first. Then add `analysis_timestamp` and `source_file` to context. Full ReportResult standardization depends on InsightResult and HealthResult being stable.

---

## 9. Implementation Recommendation

Execute in this sequence. Each step is independently shippable.

**Step 1 — Confidence scale normalization (one commit, all generators)**
Divide `confidence` by 100 in `correlation.py`, `anomalies.py`, `trends.py`. Divide `confidence_score` by 100 in `quality_score.py`. Update any frontend or export consumer that displays confidence as a percentage (multiply by 100 for display only, store and pass as 0.0–1.0). Verify: all confidence values in `result_json` are floats between 0.0 and 1.0.

**Step 2 — Column references in InsightResult (one commit, all generators)**
Add `"columns_referenced": [col]` to anomaly, trend, distribution, quality insight dicts. Replace `"col_a"` / `"col_b"` in correlation dicts with `"columns_referenced": [col1, col2]`. Add sequential `"id"` assignment in the orchestrator. Verify: report builder insight selection can now read `insight["columns_referenced"]` reliably.

**Step 3 — HealthResult field rename (one commit + consumer updates)**
Rename `"total"` → `"total_score"` in `health_scorer.py`. Search for all `get("total"` usages in the codebase and update. Run tests. This is a breaking change for any consumer reading the old key name.

**Step 4 — IntakeResult additions (one commit)**
Add `row_count` and `column_count` to `ParseReport` dataclass. Populate in `file_loader.py`. Surface in intake review UI (`intake-review.tsx`).

**Step 5 — CompareResult unification (after CompareRun table exists)**
Define one canonical compare response shape. Write a shared `build_compare_result()` function in `services/`. Both compare routes call it. Add `comparable`, `match_confidence`, and `client_summary` fields.

**Step 6 — ReportResult context cleanup (after Steps 1–3 are stable)**
Fix the profile schema bug, add `analysis_timestamp` and `source_file` to export context. Standardize context keys so all three export formats (HTML, PDF, XLSX) read from the same dict structure.
