# Pre-Analysis Intelligence V2 — Checkpoint 90H

**Branch:** `claude/backend-chart-export-context-culfe`
**Date:** 2026-05-13
**Suite:** 1556 passed · 2 skipped · 1 pre-existing failure (test_report_draft_export.py)

---

## Status at checkpoint

| Checkpoint item | Status |
|---|---|
| Fresh sync result includes `pre_analysis_profile` | ✅ |
| Fresh stream result includes `pre_analysis_profile` | ✅ |
| Celery task result includes `pre_analysis_profile` | ✅ |
| Cache-hit backfill builds profile from **cleaned** dataset | ✅ |
| `RunResults` exposes `pre_analysis_profile` | ✅ |
| Saved legacy runs without the block return `None` (backward-compat) | ✅ |
| No downstream behavior changed (ranking, hygiene, charts unaffected) | ✅ |

---

## What 90G delivered (tasks 90B–90G)

Six new modules, all deterministic and side-effect-free:

| Module | Task | Purpose |
|---|---|---|
| `app/schemas/pre_analysis.py` | 90B | 6 Pydantic models: `DatasetFingerprint`, `ColumnSemanticRole`, `AnalysisStrategy`, `AnalysisRisk`, `HypothesisPlan`, `PreAnalysisProfile` |
| `app/services/analysis/fingerprint.py` | 90C | `extract_dataset_fingerprint(df)` → `DatasetFingerprint` |
| `app/services/analysis/column_roles.py` | 90D | `classify_column_roles(df, fingerprint)` → `list[ColumnSemanticRole]` |
| `app/services/analysis/grain_detector.py` | 90E | `detect_grain(fingerprint, column_roles)` → `(grain_label, grain_confidence)` |
| `app/services/analysis/strategy_builder.py` | 90F | `build_analysis_strategy`, `detect_analysis_risks`, `build_hypothesis_plan` |
| `app/services/analysis/pre_analysis.py` | 90G | `build_pre_analysis_profile(df)` → `PreAnalysisProfile` — composer wiring all sub-steps |

Test coverage added: **262 new tests** across 8 new test files (42 + 35 + 64 + 37 + 61 + 6 + 15 + 4 tests).

---

## `pre_analysis_profile` output shape

Every analysis result now carries this top-level key. Sample for a 60-row orders dataset:

```json
{
  "grain_label": "order",
  "grain_confidence": 0.9,
  "planner_version": "v2.0-deterministic",
  "generated_at": "<ISO-8601 UTC>",
  "fingerprint": {
    "row_count": 60,
    "column_count": 6,
    "dataset_shape": "panel_data",
    "overall_missing_rate": 0.0
  },
  "column_roles": [
    {"column_name": "order_id",    "primary_role": "transaction_id",  "role_confidence": 0.9},
    {"column_name": "customer_id", "primary_role": "dimension",       "role_confidence": 0.7},
    {"column_name": "revenue",     "primary_role": "currency_amount", "role_confidence": 0.8},
    {"column_name": "units",       "primary_role": "metric",          "role_confidence": 0.7},
    {"column_name": "region",      "primary_role": "geographic",      "role_confidence": 0.8},
    {"column_name": "order_date",  "primary_role": "time",            "role_confidence": 0.95}
  ],
  "strategy": {
    "recommended_analysis_types": ["trend_analysis", "segment_comparison",
                                   "correlation_analysis", "anomaly_detection",
                                   "distribution_analysis"],
    "recommended_chart_families": ["line", "bar", "scatter", "histogram"]
  },
  "risks": [
    {"risk_name": "small_sample", "severity": "medium"}
  ],
  "hypothesis_plan": {
    "hypotheses": [
      "Check whether key metrics vary meaningfully across important dimensions.",
      "Check whether key metrics trend over the detected time column.",
      "Check whether high-cardinality ID or helper columns are incorrectly driving findings.",
      "Check whether metric pairs show strong correlation or anti-correlation.",
      "Check whether anomalous rows deviate from the main distribution.",
      "Review basic distributions and data quality before drawing conclusions."
    ]
  }
}
```

---

## Integration points

### All three pipeline paths

The profile is computed once per run from `df_clean` and stored in `result_json`:

```python
# analysis.py (sync), analysis_stream.py (inline stream), tasks.py (Celery)
try:
    _pre_analysis_profile = build_pre_analysis_profile(df_clean).model_dump()
except Exception:
    _pre_analysis_profile = None

result = {
    ...
    "pre_analysis_profile": _pre_analysis_profile,   # 90G — V2 dataset understanding
}
```

Failure is best-effort: a builder exception sets the key to `None` and never blocks the analysis response.

### Cache-hit backfill

All three paths backfill `pre_analysis_profile` for legacy cached results that predate 90G.
The backfill runs `clean_dataset` before building the profile, so it is consistent with fresh runs:

```python
if not cached.get("pre_analysis_profile"):
    try:
        _df_back = load_dataset(file_path)
        _df_back_clean, _, _ = clean_dataset(_df_back)
        _profile = build_pre_analysis_profile(_df_back_clean)
        cached = {**cached, "pre_analysis_profile": _profile.model_dump()}
        set_cached_analysis(project_id, file_hash, cached)
    except Exception:
        pass
```

### RunResults exposure

`GET /analysis/run/{run_id}/results` now returns `pre_analysis_profile` as an optional dict.
Legacy runs that never stored it return `None`. The field defaults to `None` in `RunResults`,
so all existing serialised runs remain deserializable without migration.

---

## What is explicitly NOT changed

- Insight ranking order — unchanged
- Chart selection logic — unchanged
- Analysis plan hygiene — unchanged
- Health score computation — unchanged
- Any frontend-facing API response shape beyond the new key

The V2 profile is **observational only** at this checkpoint. It is attached to every result and
persisted, but no existing decision path reads from it yet.

---

## Pre-conditions for using the profile downstream (future 90I+)

Before `pre_analysis_profile` fields can influence ranking, chart selection, or hygiene:

1. **Regression baseline locked** — capture current insight order for at least one fixed dataset
   so any future change can be detected.
2. **Strategy→hygiene mapping** — define which `recommended_analysis_types` suppress which
   insight types, with explicit confidence thresholds (not just presence/absence of a role).
3. **Risk→suppression rules** — define which `AnalysisRisk` names trigger which hygiene steps,
   with severity gates (`high` only, or `medium+`).
4. **A/B gate** — wrap any new behaviour behind a feature flag or plan guard until validated
   against the regression baseline.

---

## Known limitations at this checkpoint

| Limitation | Impact |
|---|---|
| `customer_id` with integer values classifies as `dimension` (not `entity_id`) because integer columns with low unique-rate fall into the metric → dimension path | Grain detector may return `unknown` instead of `customer` for integer ID columns without "id" token |
| `dataset_shape = "panel_data"` fires when both a time column and an entity-named column coexist, even for small datasets (60 rows) | `small_sample` risk fires alongside `panel_data` shape; both are correct but the combination may over-weight the panel interpretation |
| Backfill loads and cleans the file on every cache miss for `pre_analysis_profile` | Adds ~50–200 ms to first-reopen latency for legacy cached results; acceptable for a one-time backfill |

---

## Files changed in 90B–90G

```
apps/api/app/schemas/pre_analysis.py                   (new — 90B)
apps/api/app/services/analysis/fingerprint.py          (new — 90C)
apps/api/app/services/analysis/column_roles.py         (new — 90D)
apps/api/app/services/analysis/grain_detector.py       (new — 90E)
apps/api/app/services/analysis/strategy_builder.py     (new — 90F)
apps/api/app/services/analysis/pre_analysis.py         (new — 90G)
apps/api/app/routes/analysis.py                        (modified — 90G)
apps/api/app/routes/analysis_stream.py                 (modified — 90G)
apps/api/app/tasks.py                                  (modified — 90G)
apps/api/app/schemas/run_summary.py                    (modified — 90G)
apps/api/tests/test_pre_analysis_schema.py             (new — 90B, 42 tests)
apps/api/tests/test_fingerprint.py                     (new — 90C, 35 tests)
apps/api/tests/test_column_roles.py                    (new — 90D, 64 tests)
apps/api/tests/test_grain_detector.py                  (new — 90E, 37 tests)
apps/api/tests/test_strategy_builder.py                (new — 90F, 61 tests)
apps/api/tests/test_pre_analysis_profile_builder.py    (new — 90G, 15 tests)
apps/api/tests/test_run_results_pre_analysis_profile.py (new — 90G, 4 tests)
apps/api/tests/test_flow_alignment.py                  (modified — 90G)
```
