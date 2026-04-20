# Result Schema Standardization

## Goal
Every stage of the analysis pipeline should produce output in a consistent, predictable shape.

## Problem
If each pipeline stage returns data in a different format, the system becomes fragile at every boundary:
- reporting breaks when it reads the wrong key
- the frontend receives inconsistent shapes and has to guess field names
- tests have to mock different structures per stage
- future stages cannot build on previous outputs without translation layers

## Rule
Each pipeline stage should produce a typed result that downstream stages, the API, and the frontend can all trust.

## Pipeline Stages That Need Standardized Outputs

### 1. Intake Result
Fields required:
- `file_name`
- `detected_header_row`
- `preamble_rows_skipped`
- `detected_delimiter`
- `detected_encoding`
- `detected_sheet` if Excel
- `guessed_column_types` (column name → type)
- `confidence` (0.0 – 1.0)
- `warnings` list

### 2. Cleaning Result
Fields required:
- `rows_before`
- `rows_after`
- `columns_before`
- `columns_after`
- `steps_applied` list (step name, detail, impact)
- `confidence_score` (0.0 – 1.0)
- `time_saved_estimate`

### 3. Health / Profile Result
Fields required:
- `total_score` (0–100)
- `grade` (A–F)
- `breakdown` (dimension → score)
- `deductions` list
- `column_health` list (per-column)
- `fix_suggestions` list
- `profile` list (per-column stats)

### 4. Insights Result
Fields required:
- `insights` list, each with:
  - `id` (stable string, e.g. `insight_001`)
  - `type` (trend | outlier | correlation | distribution | quality | comparison)
  - `severity` (critical | warning | info)
  - `confidence` (0.0 – 1.0)
  - `title`
  - `finding`
  - `evidence`
  - `action`
  - `columns_referenced` list of column names
- `narrative` plain-English paragraph
- `executive_panel` with opportunities / risks / action plan

### 5. Compare Result
Fields required:
- `comparable` boolean
- `match_confidence` (0.0 – 1.0)
- `schema_changes` (added, removed, renamed)
- `row_delta`
- `health_delta`
- `metric_changes` list
- `quality_changes` list
- `client_summary` object (top findings, caution flags)

### 6. AI Summary Result
Fields required:
- `model_used`
- `generated_at`
- `slides` list (title, narrative, key_points)
- `tone`

## Standard Field Conventions

| Convention | Rule |
|------------|------|
| Confidence | Always 0.0 – 1.0 float, not 0–100 int |
| Severity | Always `critical` / `warning` / `info` string |
| Grade | Always A / B / C / D / F string |
| Timestamps | Always ISO 8601 UTC string |
| Column references | Always use `columns_referenced: list[str]` |
| IDs | Every major output object should have a stable string `id` |
| Percentages | Always 0.0 – 1.0 float, not 0–100 int (except display labels) |
| Missing values | Always `missing_pct` as 0.0 – 1.0 float |

## Standardization Priority
1. `InsightResult` — most downstream consumers, most inconsistent today
2. `CleaningResult` — used in report and cleaning review UI
3. `IntakeResult` — shown to user first; sets expectations for the whole session
4. `HealthResult` — used in export, compare, and trust indicators
5. `CompareResult` — required before compare block can feed into report builder
6. `AIStoryResult` — required before AI story can be persisted and retrieved

---

## Current Schema Audit

### What Is Already Consistent

**Snake_case naming is dominant across all stages**
All field names across intake (`detected_header_row`), cleaning (`rows_before`, `steps_applied`), health (`total_score`, `column_health`), profiling (`missing_pct`, `dtype`), and insights (`severity`, `finding`) use snake_case consistently. No camelCase leakage into any pipeline output.

**`missing_pct` naming is shared between profiling and cleaning**
`profile_dataset` returns per-column `missing_pct`. The cleaning summary also tracks missingness under `missing_pct`. Both stages use the same field name for the same concept.

**`grade` A–F is used in both health scoring and cleaning confidence display**
`calculate_health_score` returns `grade` as a letter. The cleaning summary surfaces a `confidence_score` that maps to the same A–F display. The report context builder expects `grade` in both places and formats them the same way.

**`recommended_chart` is present on profile column outputs**
`profile_dataset` returns `recommended_chart` on every column dict. This is the only column-level field that feeds directly into chart selection in the report builder, and it is consistently present.

**Insight fields `title`, `finding`, `evidence`, `action` are consistent across all insight generators**
Every insight-producing function (`analyze_dataset`, column compare interpretation, diff run classification) produces these four text fields. Downstream consumers (report builder, export, insight checkboxes) can rely on them being present.

---

### Where Schemas Are Inconsistent

**Confidence scale mismatch — 0–100 vs 0.0–1.0**
The intake `ParseReport` returns `confidence` as a `0.0–1.0` float. The health scorer returns `dataset_type_confidence` as a `0.0–1.0` float. But insight `confidence` is `0–100` integer, and cleaning `confidence_score` is also `0–100` integer. Any code that reads confidence from multiple stages and compares or aggregates them will produce silently wrong results.

**Column references in insights — three different shapes**
Insight dicts produced by `analyze_dataset` use three different field names to refer to the column(s) involved in a finding:
- Correlation insights use `col_a` and `col_b` (two separate fields)
- Distribution and outlier insights use `column` (single string)
- Some multi-column insights use `columns` (a list)

The report builder and export pipeline cannot reliably extract which columns an insight is about. A consumer that reads `insight["column"]` will miss all correlation findings; one that reads `insight["col_a"]` will miss all single-column findings.

**`dtype_confidence` is a string enum, not numeric**
`profile_dataset` returns `dtype_confidence` as `"low"` / `"medium"` / `"high"` — a string, not a number. All other confidence fields across the pipeline are numeric. A consumer that tries to threshold or sort by confidence across profile and insight outputs must handle two incompatible types.

**No `id` field on individual insights, column profiles, or intake sessions**
Insights have no stable identifier. The report builder stores `selected_insight_ids_json` but currently has no reliable ID to store — it would have to use list index or a hash of the finding text. Column profiles have no ID either. This makes it impossible to reference a specific insight from a report draft without fragile index-based tracking.

**No `schema_version` or `generated_at` on any pipeline output**
None of the stage outputs carry a version tag or timestamp. If the analysis engine is updated and output shapes change, there is no way to detect that a stored `result_json` was produced by an older version. Debugging schema mismatches in stored results requires guessing when the run happened.

**Compare output uses `a`/`b` prefix keys, not a standard shape**
`compare_files` returns `health_score_a`, `health_score_b`, `row_count_a`, `row_count_b`, etc. — flat dict with letter-prefix convention. This is different from every other stage output. The diff route (`GET /analysis/diff`) uses a different shape again, returning nested `run_a`/`run_b` objects. A frontend consuming either compare route cannot reuse the same parsing logic.

**Insight `type` values are string literals, not constants**
Insight `type` field uses strings like `"trend"`, `"outlier"`, `"correlation"` defined inline in `analyze_dataset`. There is no enum or constant list. If a new insight generator misspells a type or uses a synonym (`"anomaly"` vs `"outlier"`), the frontend severity filter and report template logic will silently drop or misclassify that insight.

---

### Which Result Types to Standardize First

**1. `InsightResult` — highest priority**
This is the most inconsistently shaped output and the most widely consumed. The three column reference conventions (`col_a`/`col_b` vs `column` vs `columns`) already cause silent data loss in the report builder. The `0–100` confidence scale means insight confidence cannot be compared with intake or health confidence. Standardizing this first unblocks: stable IDs for report draft selection, reliable column references for chart generation, and consistent confidence thresholding.

**Minimum changes needed:**
- Add `id` field (stable hash or sequential string)
- Replace `col_a`/`col_b`/`column`/`columns` with one field: `columns_referenced: list[str]`
- Normalize `confidence` to `0.0–1.0`
- Define `type` as an enum or constant set

**2. `CleaningResult` — second priority**
The cleaning result is the first output the user sees after intake, and it feeds the cleaning review UI (Step 10 in the plan). Its `confidence_score` uses `0–100` while intake uses `0.0–1.0`. Standardizing `CleaningResult` confidence to `0.0–1.0` is a one-field change but removes a silent scale inconsistency that will otherwise affect every cross-stage trust calculation.

**3. `IntakeResult` — third priority**
The intake stage (`ParseReport`) is already the most consistently shaped output in the pipeline — it uses `0.0–1.0` confidence, has a `warnings` list, and carries structured field types. What it is missing is: an `id` field and a `schema_version`. Adding those two fields makes `IntakeResult` the reference shape that all other stages should match.
