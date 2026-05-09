# Analyst Pro — Messy File QA Log

> Purpose: Track real-world messy file behavior so the generic analysis engine can be improved based on evidence, not guesses.
>
> Rule: Log issues here first. A fix is scheduled only when severity warrants it (P0/P1 immediately; P2 after 2+ independent file observations or clear generic improvement; P3 batched). Domain-specific packs require 3+ independent pilot requests before any build work starts.

---

## How to Use This Log

1. Upload a real or representative messy file to Analyst Pro.
2. Walk the full workflow: intake → cleaning → health → findings → report builder → export.
3. Note anything that looks wrong, confusing, or misleading — even if the pipeline didn't error.
4. Add a row to the table below.
5. Classify severity using the labels in the guide at the bottom.
6. Do not start a build task until the decision rules are met.

---

## Issue Log

| # | File | Dataset type | Rows | Cols | File type | What worked | What looked bad | UI issue? | Cleaning issue? | Insight issue? | Chart issue? | Severity | Suggested task | Build now or defer? |
|---|------|-------------|------|------|-----------|-------------|-----------------|-----------|-----------------|----------------|--------------|----------|----------------|---------------------|
| 1 | auto_insurance_data.xlsx | Auto insurance / risk | ~1k | ~20 | Excel | Upload, intake, health score, findings list, export all completed without error | Cleaning Review grade shown as raw Python object: `Grade {'score': 70, 'grade': 'B', 'label': 'Good'}` instead of formatted label. After 85E backend fix, UI rendered `Grade Grade B — 70/100 · Good — 70/100 data quality score` (double "Grade", duplicate score). | Yes | No | No | No | P2 | **RESOLVED — 85E + 85F** — backend adapter now emits `"Grade B — 70/100 · Good"`; frontend helpers `formatGradeLabel()` / `extractGradeLetter()` render it cleanly without duplication | **Done** — backend fixed 85E, UI duplication fixed 85F (2026-05-08) |
| 2 | auto_insurance_data.xlsx | Auto insurance / risk | ~1k | ~20 | Excel | — | Date-derived findings dominate ranking: `effective_date_month`, `effective_date_quarter`, `effective_date_year`, weekend flag findings ranked above business-relevant correlations | No | No | Yes | No | P2 | **IMPROVED by 86E** — `apply_analysis_plan_hygiene()` penalised 3/13 findings (×0.35 confidence) — date-part noise dropped from positions #2, #4, #7 to bottom of ranking; top findings now business-relevant (`frequency × severity`, genuine trends) | **Partially resolved** — 86E reduces date-part over-ranking for insurance. Full fix deferred: second file confirmation before broadening |
| 3 | auto_insurance_data.xlsx | Auto insurance / risk | ~1k | ~20 | Excel | — | Spreadsheet artifact columns not removed: `avg S`, `avg P`, `Unnamed: X`, `severity per payment` — these are helper/formula columns, not data columns | No | Yes | No | No | P2 | **PARTIALLY IMPROVED by 86E** — artifact columns (`avg_S`, `Unnamed: 14`, etc.) now listed in `columns_to_ignore`; findings where ALL columns are artifacts are penalised ×0.40. Cleaning-stage removal still open. | Defer — cleaning-stage removal still needed; schedule when second file shows artifact columns |
| 4 | auto_insurance_data.xlsx | Auto insurance / risk | ~1k | ~20 | Excel | Charts render and export without error | **RESOLVED by 86I + 86K** — chart generation column order now plan-aware; target metrics surface before generic numeric columns. Before: 0 target metric charts. After: 7 target metric charts (trend, scatter, histogram, boxplot). Top-2 charts: `effective_date × annual_premium_usd` and `effective_date × severity` time-series trends. | No | No | No | Yes | P2/P3 | **Done** — 86I score hygiene (2026-05-09) + 86K column-order prioritisation (2026-05-09). Finance snapshot charts verified as unchanged. | **Resolved** (2026-05-09) |
| 5 | yahoo_finance_global_markets_2026.csv | Finance / market data | ~451 | ~131 | CSV | Upload, analysis pipeline completed without error | **RESOLVED by 86G** — `dayLow`, `dayHigh`, `fiftyDayAverage`, `twoHundredDayAverage`, `averageVolume10days`, `fiftyTwoWeekLow`, `fiftyTwoWeekHigh`, `priceToSalesTrailing12Months`, `earningsQuarterlyGrowth` are all correctly excluded from `time_columns` after tightening `_DATE_PATTERN`. Real date columns (`price_date`, `build_timestamp`, `exDividendDate`) still detected. `ticker`/`symbol` now in `columns_to_ignore`. | No | No | No | No | P2 | **Done** — backend planner fix 86G (2026-05-09) |

---

## Issue #1 — Reproduction Audit (85D, 2026-05-08)

**Method:** Static code trace — no additional file upload needed.

**Finding:** `score_to_grade()` in `apps/api/app/services/cleaning/quality_score.py:58` always returns a `dict` (`{"score": int, "grade": str, "label": str}`). In `cleaning_adapter.py:98` this dict is passed through `str()`, producing a raw Python object string on every file without exception. The bug is in the adapter, not the data.

**Verdict:** Confirmed reproducible universally — not file-shape-specific.

**Root cause:** `str(summary.get("confidence_grade", "F"))` — the default `"F"` is a string but the real value is always a dict, so `str()` stringifies the dict.

**Fix location:** `apps/api/app/services/cleaning_adapter.py:98`

**Fix:** Replace `str(summary.get("confidence_grade", "F"))` with `summary.get("confidence_grade", {}).get("grade", "F")`

**Next task:** ~~85E — Fix Cleaning Review grade formatting.~~ → Done. 85F fixed UI duplication (double "Grade", duplicate "/100"). Issue #1 fully resolved.

---

## Issue #2–5 — 86E Re-test (86F, 2026-05-09)

**Method:** Programmatic re-test — both files analysed via Python against the 86E pipeline (`build_analysis_plan` + `apply_analysis_plan_hygiene`) without a running server.

### Insurance file (`auto_insurance_data.xlsx`)

- **Plan:** `insurance`, 94% confidence
- **`time_columns` identified:** `effective_date`, `policy_end_date` + all derived parts (`effective_date_month`, `effective_date_quarter`, `effective_date_year`, `effective_date_day_of_week`, `effective_date_is_weekend`, `policy_end_date_year`, etc.)
- **`columns_to_ignore`:** `policy_id`, `customer_id`, `avg_S`, `Unnamed: 14` (artifact/ID columns correctly caught)
- **Findings penalised:** 3/13 (×0.35 confidence)
  - `effective_date_month × effective_date_quarter` — was #2, now near-bottom
  - `effective_date_year × policy_end_date_year` — was #4, now near-bottom
  - `effective_date_day_of_week × effective_date_is_weekend` — was #7, now near-bottom
- **Top findings after hygiene:** `frequency × severity` (conf=99.8), genuine trend findings, distribution findings — business-relevant ranking restored
- **Issue #2 verdict:** Improved. Date-part noise suppressed as intended.
- **Issue #3 verdict:** Partially improved. Artifact columns in `columns_to_ignore`; all-artifact findings will be penalised. Cleaning-stage removal still open.

### Finance file (`yahoo_finance_global_markets_2026.csv`)

- **Plan:** `finance`, 95% confidence
- **`time_columns` (false positives):** `daylow`, `dayhigh`, `fiftytwoweeklow`, `fiftytwoweekhigh`, `fiftydayaverage`, `twohundreddayaverage`, `averagevolume10days`, `pricetosalestrailing12months`, `earningsquarterlygrowth`, `lastfiscalyearend`, `mostrecentquarter`, `nextfiscalyearend`, `trading_days`, `price_date`, `build_timestamp`
  - Root cause: `_REAL_DATE_FRAGMENTS` regex matches bare `day` substring — catches financial columns containing "day" (daylow, dayhigh, fiftydayaverage) even though they are price/volume metrics
- **`columns_to_ignore`:** empty — `ticker`, `symbol` not matched by current ID regex (requires trailing digits or `_id` / `_uuid` patterns)
- **Findings penalised:** 0/15 — hygiene did not apply
- **Before/after 86E:** identical top-10 ranking for finance file
- **Issue #5 verdict:** New issue logged. Planner date classification needs tightening for finance domain; ID pattern needs `ticker`/`symbol` support.

### Summary

| File | Plan confidence | Findings penalised | Effect |
|------|-----------------|--------------------|--------|
| auto_insurance_data.xlsx | 94% | 3/13 | Date-part noise dropped from top positions ✓ |
| yahoo_finance_global_markets_2026.csv | 95% | 0/15 | False-positive time_columns; hygiene did not apply ✗ |

---

## Issue #5 — 86G Fix Verification (86H, 2026-05-09)

**Method:** Programmatic re-test — `yahoo_finance_global_markets_2026.csv` (451 rows × 131 columns) run through updated planner and hygiene layer.

### Results

**`time_columns` after fix (3 columns — all genuine date/timestamp fields):**
| Column | Verdict |
|--------|---------|
| `exDividendDate` | ✓ Real date column (contains `date`) |
| `price_date` | ✓ Real date column (contains `date`) |
| `build_timestamp` | ✓ Real timestamp (contains `timestamp`) |

**Finance metric columns no longer misclassified:**
| Column | Before 86G | After 86G |
|--------|-----------|-----------|
| `dayLow` | In time_cols ✗ | NOT in time_cols ✓ |
| `dayHigh` | In time_cols ✗ | NOT in time_cols ✓ |
| `fiftyDayAverage` | In time_cols ✗ | NOT in time_cols ✓ |
| `twoHundredDayAverage` | In time_cols ✗ | NOT in time_cols ✓ |
| `averageVolume10days` | In time_cols ✗ | NOT in time_cols ✓ |
| `fiftyTwoWeekLow` | In time_cols ✗ | NOT in time_cols ✓ |
| `fiftyTwoWeekHigh` | In time_cols ✗ | NOT in time_cols ✓ |
| `priceToSalesTrailing12Months` | In time_cols ✗ | NOT in time_cols ✓ |
| `earningsQuarterlyGrowth` | In time_cols ✗ | NOT in time_cols ✓ |
| `lastFiscalYearEnd` | In time_cols ✗ | NOT in time_cols ✓ |
| `mostRecentQuarter` | In time_cols ✗ | NOT in time_cols ✓ |
| `nextFiscalYearEnd` | In time_cols ✗ | NOT in time_cols ✓ |
| `trading_days` | In time_cols ✗ | NOT in time_cols ✓ |

**Entity identifiers:**
- `ticker`: `columns_to_ignore=True`, `target_metrics=False` ✓
- `symbol`: `columns_to_ignore=True`, `target_metrics=False` ✓

**Hygiene simulation (synthetic insights on formerly-misclassified columns):**
- `dayLow vs dayHigh`: conf=80.0, not penalised ✓
- `fiftyDayAverage vs twoHundredDayAverage`: conf=75.0, not penalised ✓
- `price_date trend`: conf=85.0, not penalised ✓ (genuine date trend preserved)

**Verdict:** Issue #5 fully resolved. No useful finance findings accidentally suppressed.

---

## Domain Pack Decision Gate

| Domain | Files tested | Pilot requests | Decision |
|--------|-------------|----------------|----------|
| Auto insurance | 1 | 0 | Do not build — log only |
| Telco / churn | — | 0 | Do not build — log only |
| Sales | 1 (demo dataset) | 0 | Do not build — log only |
| HR / attrition | — | 0 | Do not build — log only |
| Finance | 1 | 0 | Do not build — log only |

**Threshold to start a domain pack: 3+ independent pilot requests for the same domain.**

---

## Severity Guide

| Severity | Meaning | Response |
|----------|---------|----------|
| P0 | Blocks upload, analysis, or export entirely | Fix before next demo |
| P1 | Severely degrades core workflow | Fix within current sprint |
| P2 | Noticeable issue but workaround exists | Schedule when confirmed by 2+ files or clear generic value |
| P3 | Polish or minor UX | Batch with other P3s |
| defer | Valid but out of scope for pilot phase | Log, revisit post-pilot |

---

## Prioritised Fix Queue (updated when items graduate)

| Priority | Issue # | Task description | Trigger to schedule |
|----------|---------|-----------------|---------------------|
| 1 | #1 | ~~85E/85F — backend adapter + UI helpers~~ | **Resolved** (2026-05-08) |
| 2 | #2 | ~~86E — date-part hygiene penalty~~ | **Partially resolved** (2026-05-09) — insurance file improved; full resolution after second file confirmation |
| 3 | #5 | ~~86G — tighten _DATE_PATTERN; add ticker/symbol to _ID_PATTERN~~ | **Resolved** (2026-05-09) — verified on real global markets CSV (86H) |
| 4 | #3 | Improve helper/mostly-empty column detection in cleaning pipeline | Second file with artifact columns |
| 5 | #4 | ~~86I + 86K — plan-aware chart score hygiene + column-order prioritisation~~ | **Resolved** (2026-05-09) — 0 → 7 target metric charts on insurance file; finance snapshot unchanged |

---

## Issue #4 — 86I Chart Hygiene Re-test (86J, 2026-05-09)

**Method:** Programmatic re-test — both files run through full pipeline: `build_chart_data()` → `apply_analysis_plan_chart_hygiene()`.

### Insurance file (`auto_insurance_data.xlsx`)

**Plan:** `insurance`, 94% confidence. Targets: `annual_premium_usd`, `frequency`, `severity`, `original_vehicle_price_usd`. Dims: `gender`, `territory`, `vehicle_type`. Time cols: 15 (including all `effective_date_*` and `policy_end_date_*` derived features).

**Before hygiene — raw top-10:**
```
 1. bar      age / Count                       score=8.00
 2. bar      number_of_previous_accidents /    score=8.00
 3. bar      vehicle_year / Count              score=8.00
 4. bar      policy_length_years / Count       score=8.00
 5. heatmap  Column / Column                   score=8.00
 6. boxplot  gender / age                      score=7.00
 7. bar      effective_date_is_weekend /       score=6.00
 8. bar      policy_end_date_is_weekend /      score=6.00
 9. bar      gender / Count                    score=6.00
10. bar      territory / Count                 score=6.00
```

**After hygiene — top-10:**
```
 1. bar      age / Count                       score=8.00   (unchanged)
 2. bar      number_of_previous_accidents /    score=8.00   (unchanged)
 3. bar      vehicle_year / Count              score=8.00   (unchanged)
 4. bar      policy_length_years / Count       score=8.00   (unchanged)
 5. heatmap  Column / Column                   score=8.00   (unchanged)
 6. boxplot  gender / age                      score=7.30   [important_dimension +0.30]
 7. bar      gender / Count                    score=6.30   [important_dimension +0.30]
 8. bar      territory / Count                 score=6.30   [important_dimension +0.30]
 9. bar      effective_date_is_weekend /       score=6.00   (unchanged)
10. bar      policy_end_date_is_weekend /      score=6.00   (unchanged)
```
Charts boosted: 3. Charts penalised: 0.

**What improved:** Dimension charts (`gender`, `territory`) promoted above weekend-flag charts. ✓

**Remaining gap — root cause identified:** Target metric columns (`annual_premium_usd`, `frequency`, `severity`) are at numeric column positions 5-7 in DataFrame order. The chart generator's histogram budget is `MAX_HIST_COLS=4` — only the first 4 numeric columns get histogram charts. The hygiene layer can only adjust scores for charts that already exist; it cannot generate missing charts. Target metrics do appear in the scatter budget (positions 5-6) but the score cap keeps them below the top 10. This requires a follow-up task to reorder chart generation to prioritise target_metrics before generic numeric columns.

---

### Finance file (`yahoo_finance_global_markets_2026.csv`)

**Plan:** `finance`, 95% confidence. Targets: 42 columns including return/volatility/price metrics. Dims: `country`, `sector`, `industry`, `market_cap_tier`. Time cols: `price_date`, `build_timestamp`, + derived date parts. Ignore: `ticker`.

**Note:** Finance file uses the domain-specific snapshot chart builder (`build_financial_snapshot_charts`) — not the generic histogram/scatter path. Charts are already semantically relevant (return leaderboards, risk-return scatter, sector averages).

**After hygiene — top-8 (all charts):**
```
 1. bar      shortname / return_1y_pct (%)     score=8.85  (unchanged — snapshot builder)
 2. bar      shortname / volatility_1y_ann (%) score=8.78  (unchanged)
 3. bar      shortname / return_1y_pct (%)     score=8.75  (unchanged)
 4. bar      sector / Mean return_1y_pct (%)   score=8.75  [important_dimension +0.30]
 5. bar      asset_class / Mean return_1y_pct  score=8.55  (unchanged)
 6. scatter  volatility_1y_ann / return_1y_pct score=8.54  (unchanged)
 7. bar      shortname / analyst_upside_pct    score=8.40  (unchanged)
 8. bar      shortname / pct_of_52w_high (%)   score=8.35  (unchanged)
```
Charts boosted: 1 (`sector` is a dimension → +0.30). Charts penalised: 0.

**What improved:** `sector × return` promoted above `asset_class × return` — sector is the more granular dimension. Finance metric columns (dayLow, dayHigh, etc.) not penalised ✓. `ticker` chart absent ✓ (in columns_to_ignore; correctly excluded from chart generation).

---

### Issue #4 Verdict

| File | Improvement | Remaining gap |
|------|------------|---------------|
| Insurance | Dimension charts boosted (+0.30); weekend-flag noise demoted | Target metric histograms not generated — column budget exhausted before reaching `annual_premium_usd` / `frequency` / `severity` |
| Finance | Sector dimension boosted; domain-specific charts unchanged; no false penalisation | None — finance already uses semantic chart builder |

**Conclusion:** Issue #4 is **partially improved** by 86I. Dimension-level boosting works correctly. The deeper gap for insurance — target metric columns falling outside the 4-column histogram budget — requires a follow-up task to reorder chart column selection by plan priority before generating charts. This is a chart-generation-order change, not a score-adjustment change.

**Follow-up task logged:** Chart generation column order should prefer `target_metrics` > `important_dimensions` > other numeric columns within each budget slice. Until then, `annual_premium_usd`, `frequency`, and `severity` histograms will not appear for the insurance file.

---

## Issue #4 — 86K Column-Order Fix Verification (86L, 2026-05-09)

**Method:** Programmatic re-test — both files run through full pipeline with `build_chart_data(analysis_plan=plan)` + `apply_analysis_plan_chart_hygiene()`.

### Insurance file (`auto_insurance_data.xlsx`) — before vs after

| Metric | Before 86K | After 86K |
|--------|-----------|-----------|
| Target metric charts generated | 0 | **7** |
| Charts boosted by plan | 3 | **6** |
| Charts penalised | 0 | 0 |
| Top-1 chart | `age` histogram | `effective_date × annual_premium_usd` trend |

**After 86K — full top-10:**
```
 1. line      effective_date / annual_premium_usd  score=11.20  [target_metric_trend]
 2. line      effective_date / severity             score=11.20  [target_metric_trend]
 3. scatter   frequency / severity                  score=9.80   [target_metric]
 4. bar       annual_premium_usd / Count            score=8.80   [target_metric]
 5. bar       severity / Count                      score=8.80   [target_metric]
 6. boxplot   gender / annual_premium_usd           score=8.50   [target_metric_x_dimension]
 7. bar       frequency / Count                     score=8.00
 8. bar       age / Count                           score=8.00
 9. heatmap   Column / Column                       score=8.00
10. bar       effective_date_is_weekend / Count     score=6.00
```

**Root cause resolved:** Target metrics (`annual_premium_usd`, `frequency`, `severity`) were at numeric column positions 5-7 — beyond the `MAX_HIST_COLS=4` budget. `prioritize_columns_for_charts()` reorders them to positions 1-3 before the budget slices, so all three now generate histogram and time-series charts.

### Finance file (`yahoo_finance_global_markets_2026.csv`) — regression check

Finance uses the domain-specific snapshot chart builder (`build_financial_snapshot_charts`) which branches before the generic reordering code. Output is identical to 86J:
- 8 charts total, all domain-specific (return leaderboards, risk-return scatter, sector averages)
- `sector × return` still boosted +0.30 by 86I hygiene
- No regression ✓

### Issue #4 final verdict

**Resolved.** The chart ranking gap is closed across both dimensions:
- **86I** (score hygiene): promotes plan-relevant charts that already exist in the output
- **86K** (column-order prioritisation): ensures target metrics are generated within budget constraints in the first place

Both mechanisms are required and complementary. Generic fallback (no plan or confidence < 0.6) is unchanged.

---

*Log started: 2026-05-08 · Last updated: 2026-05-09 (86L — Issue #4 resolved)*
