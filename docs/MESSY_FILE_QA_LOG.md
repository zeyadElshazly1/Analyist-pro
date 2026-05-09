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
| 4 | auto_insurance_data.xlsx | Auto insurance / risk | ~1k | ~20 | Excel | Charts render and export without error | Chart selection is technically valid but does not surface the strongest business story; distributions are generic rather than focused on high-signal numeric fields (e.g. claim amount vs premium vs risk tier) | No | No | No | Yes | P2/P3 | Improve generic chart ranking to prioritise numeric fields that correlate with a likely target variable; deprioritise uniform or near-constant distributions | Defer — P3 polish; 86E did not affect chart selection; revisit after findings-ranker improvement is in place |
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
| 5 | #4 | Improve generic chart ranking toward high-signal fields | After findings ranker improvement lands |

---

*Log started: 2026-05-08 · Last updated: 2026-05-09 (86H — Issue #5 resolved)*
