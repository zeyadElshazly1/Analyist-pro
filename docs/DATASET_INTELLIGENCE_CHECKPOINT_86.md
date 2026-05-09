# Dataset Intelligence Layer — Phase 86 Checkpoint

> **What this doc is:** A single-page summary of everything built in 86A–86L so any reviewer
> or future contributor can understand what the Dataset Intelligence Layer is, where it lives,
> what it changed, and what remains open — without reading the full chat history.
>
> **Related docs:**
> - Design: [`docs/DATASET_INTELLIGENCE_LAYER.md`](DATASET_INTELLIGENCE_LAYER.md)
> - QA evidence: [`docs/MESSY_FILE_QA_LOG.md`](MESSY_FILE_QA_LOG.md)

---

## Goal of the Phase

Before 86A, Analyst Pro was a generic analysis engine: every dataset got the same findings
ranked by raw statistics, the same first-come-first-served chart columns, and no awareness
of what the dataset was *about*.

The goal of this phase was to add a **Dataset Intelligence Layer** — a lightweight, fully
deterministic classification step that runs at analysis time, infers what kind of dataset
was uploaded, and uses that context to make findings and charts more business-relevant.

**Hard constraints throughout:**
- No AI call in the critical path
- No domain-specific packs built without 3+ independent pilot requests
- No deletion of findings or charts — only ranking adjustments
- Full generic fallback when confidence is low

---

## Completed Tasks (86A–86L)

| Task | Description | Key file(s) |
|------|------------|-------------|
| **86A** | Design doc — schema, planner contract, 4 domain examples | `docs/DATASET_INTELLIGENCE_LAYER.md` |
| **86B** | `AnalysisPlan` Pydantic schema + deterministic planner service | `app/schemas/analysis_plan.py`, `app/services/analysis/analysis_planner.py` |
| **86C** | Persist `analysis_plan` in `result_json` for all three pipeline paths; cache-hit backfill | `app/routes/analysis.py`, `app/routes/analysis_stream.py`, `app/tasks.py` |
| **86D** | Surface `analysis_plan` in Intake Review via `AnalysisPlanCard` frontend component | `apps/web/src/components/analysis/analysis-plan-card.tsx`, `api.ts` types |
| **86E** | Finding hygiene — confidence penalties for date-part features (×0.35) and ignored columns (×0.40) | `app/services/analysis/analysis_plan_hygiene.py` |
| **86F** | Messy-file re-test after 86E — documented finding QA results for insurance + finance files | `docs/MESSY_FILE_QA_LOG.md` |
| **86G** | Fix finance date regex false positive — tighten `_DATE_PATTERN`; add `ticker`/`symbol` to ID list | `app/services/analysis/analysis_planner.py` |
| **86H** | Verify 86G fix on real global markets CSV — 13 false-positive columns corrected | `docs/MESSY_FILE_QA_LOG.md` |
| **86I** | Chart score hygiene — `apply_analysis_plan_chart_hygiene()` adjusts scores on already-built charts | `app/services/analysis/chart_plan_hygiene.py`, `app/routes/charts.py` |
| **86J** | Chart QA after 86I — identified remaining root cause (column budget) | `docs/MESSY_FILE_QA_LOG.md` |
| **86K** | Chart generation column prioritisation — `prioritize_columns_for_charts()` reorders before budget slices | `app/services/analysis/chart_plan_hygiene.py`, `app/services/charting/orchestrator.py` |
| **86L** | Close Issue #4 — verified 0 → 7 target metric charts on insurance file; finance regression-free | `docs/MESSY_FILE_QA_LOG.md` |

---

## Architecture Summary

```
                        ┌─────────────────────────────────────────────────────┐
                        │              Analysis Pipeline                       │
                        │  (analysis.py / analysis_stream.py / tasks.py)      │
                        │                                                      │
  df_clean ──────────► analyze_dataset()                                      │
                        │         │                                            │
                        │         ▼                                            │
                        │  build_analysis_plan(columns, dtypes)  ◄── 86B/86C  │
                        │         │                                            │
                        │         ▼                                            │
                        │  apply_analysis_plan_hygiene(insights, plan)  ◄─ 86E│
                        │         │                                            │
                        │         ▼                                            │
                        │  build_insight_results(insights)                    │
                        │         │                                            │
                        │         ▼                                            │
                        │  result_json  ◄── includes "analysis_plan"  ◄── 86C │
                        └─────────────────────────────────────────────────────┘

                        ┌─────────────────────────────────────────────────────┐
                        │              Chart Pipeline  (charts.py)            │
                        │                                                      │
  df_clean ──────────► build_analysis_plan(columns, dtypes)  ◄──────── 86I/K │
                        │         │                                            │
                        │         ▼                                            │
                        │  build_chart_data(df_plot, analysis_plan=plan)       │
                        │    └── prioritize_columns_for_charts()  ◄────── 86K │
                        │         │                                            │
                        │         ▼                                            │
                        │  apply_analysis_plan_chart_hygiene(charts, plan) ◄ 86I
                        │         │                                            │
                        │         ▼                                            │
                        │  return {"charts": charts}                          │
                        └─────────────────────────────────────────────────────┘

                        ┌─────────────────────────────────────────────────────┐
                        │              Frontend                                │
                        │                                                      │
  result.analysis_plan ──► AnalysisPlanCard  ◄──────────────────────── 86D   │
  (Intake Review tab)                                                         │
                        └─────────────────────────────────────────────────────┘
```

---

## AnalysisPlan Schema

```python
class AnalysisPlan(BaseModel):
    dataset_kind: str                    # "finance" | "insurance" | "sales" | "hr" |
                                         #  "marketing" | "operations" | "generic"
    confidence: float                    # 0.0–1.0 (clamped); < 0.6 = generic fallback
    business_context: str                # human-readable classification rationale
    primary_entity: str | None           # "policy", "order", "employee", etc.
    target_metrics: list[str]            # columns with business outcome signal
    important_dimensions: list[str]      # categorical grouping columns
    time_columns: list[str]              # genuine date/timestamp columns
    columns_to_ignore: list[str]         # IDs, artifact cols, mostly-empty cols
    recommended_charts: list[ChartHint]  # planner-suggested chart pairs
    insight_priorities: list[str]        # e.g. ["correlation", "trend", "outlier"]
    analysis_warnings: list[str]         # emitted when date cols or many ignores found
    report_template_hint: str            # "executive_summary" | "detailed_audit" | etc.
```

**Confidence bands:**
- ≥ 5 domain token hits → 0.80–0.95
- ≥ 3 hits → 0.60–0.79
- ≥ 1 hit → 0.40–0.59
- 0 hits → 0.35, kind = "generic"
- Second-best within 1 hit → confidence −0.15 (ambiguous)

---

## Where It Is Wired

| Location | What it does |
|----------|-------------|
| `app/routes/analysis.py` | Builds plan after cleaning; applies finding hygiene before `build_insight_results()`; stores plan in result dict |
| `app/routes/analysis_stream.py` | Same as above; also backfills plan on pre-86C cache hits |
| `app/tasks.py` | Same as above for Celery worker path |
| `app/routes/charts.py` | Builds plan from `df_clean`; passes it to `build_chart_data()` for column reordering; applies score hygiene after |
| `app/services/charting/orchestrator.py` | Accepts `analysis_plan=None`; calls `prioritize_columns_for_charts()` before budget slices |
| Frontend `run-analysis.tsx` | Reads `result.analysis_plan`; renders `AnalysisPlanCard` in Intake Review tab |

---

## What Behaviour Changed

### Findings
- **Date-part derived features** (e.g. `effective_date_month`, `effective_date_quarter`) receive a ×0.35 confidence multiplier and `suppressed_by_plan=True`. They remain in the list but rank below business-relevant findings.
- **All-artifact column findings** (e.g. a correlation between two ID columns) receive a ×0.40 multiplier.
- **Genuine trend findings** on real date columns (e.g. `order_date` → `revenue`) are preserved — the trend exception prevents false penalisation.
- Insurance file before: date-noise findings at positions #2, #4, #7. After: `frequency × severity` at #1, business-relevant findings throughout.

### Charts
- **Column generation order** is reordered to `target_metrics → important_dimensions → others → columns_to_ignore` before histogram/scatter budget slices, so target metrics always generate charts regardless of their position in the DataFrame.
- **Chart scores** are adjusted post-generation: target × dimension +1.5, target × time-series +1.2, target-only +0.8, dimension-only +0.3, all-ignored-column ×0.40.
- Insurance file before: 0 target metric charts (age/vehicle_year/policy_length_years dominated). After: 7 target metric charts including `effective_date × annual_premium_usd` trend (score 11.20) and `frequency × severity` scatter (score 9.80).
- Finance snapshot path is **unaffected** — it uses a domain-specific builder that branches before generic reordering.

### Intake Review UI
- A new `AnalysisPlanCard` component renders dataset kind, confidence, target metrics, dimensions, time columns, ignored columns, and warnings in the Intake Review tab.
- Confidence states: emerald (≥ 0.8), amber (0.6–0.8), grey (< 0.6 / generic).

### Planner column classification
- `_DATE_PATTERN` now requires underscore or string boundary around calendar unit tokens (`day`, `week`, `month`, `year`, `quarter`) — prevents `dayLow`, `dayHigh`, `fiftyDayAverage`, `earningsQuarterlyGrowth` etc. from being misclassified as time columns.
- `ticker` and `symbol` added to `_ID_PATTERN` — land in `columns_to_ignore` instead of floating unclassified.

---

## What Did Not Change

- **No finding is deleted.** Hygiene only adjusts `confidence`; ranking decides the final order. Every finding remains available.
- **No chart is deleted.** Score adjustment only; `rank_and_cap` still applies the same `MAX_CHARTS=10` cap.
- **No AI call in the critical path.** `build_analysis_plan()` is purely deterministic — token matching over column names.
- **Generic fallback is preserved.** Any code path that receives `analysis_plan=None` or `confidence < 0.6` behaves exactly as before 86A.
- **Finance snapshot and timeseries chart builders** are unchanged — they branch before the generic column reordering.
- **No domain-specific insight packs.** The planner identifies domain but adds no domain-specific finding logic.

---

## Test Evidence

| Suite | Result |
|-------|--------|
| Full backend suite (post-86L) | **1154 passed, 2 skipped** |
| `test_analysis_planner.py` | 35 tests — domain classification, column sorting, confidence, validity |
| `test_analysis_planner_finance_dates.py` | 28 tests — finance false-positive regression coverage |
| `test_analysis_plan_finding_hygiene.py` | 18 tests — ignored-column penalty, date-part penalty, trend exception, no-mutation |
| `test_analysis_plan_chart_hygiene.py` | 22 tests — score boost/penalty, pass-through, no-mutation |
| `test_analysis_plan_chart_generation_order.py` | 38 tests — `prioritize_columns_for_charts` unit + `build_chart_data` integration |
| `test_86C_analysis_plan_persistence.py` | 8 tests — plan present in result, cache backfill |
| TypeScript compilation (86D) | Clean — `AnalysisPlan`, `ChartHint` types in `api.ts` |

---

## Messy-File QA Outcomes

| Issue | File | Problem | Outcome |
|-------|------|---------|---------|
| **#1** | auto_insurance_data.xlsx | Grade shown as raw Python dict | **Resolved** (85E backend + 85F UI) |
| **#2** | auto_insurance_data.xlsx | Date-derived findings over-ranked | **Improved** (86E — 3/13 penalised; date-noise dropped from top positions) |
| **#3** | auto_insurance_data.xlsx | Artifact columns not removed at cleaning stage | **Partially improved** (86E penalises all-artifact findings; cleaning-stage removal deferred) |
| **#4** | auto_insurance_data.xlsx | Generic charts, no target metric charts | **Resolved** (86I score hygiene + 86K column prioritisation — 0 → 7 target charts) |
| **#5** | yahoo_finance_global_markets_2026.csv | Finance date regex false positives | **Resolved** (86G tighter regex + 86H verification — 13 misclassified columns corrected) |

Full evidence: [`docs/MESSY_FILE_QA_LOG.md`](MESSY_FILE_QA_LOG.md)

---

## Remaining Deferred Items

| Item | Reason deferred | Trigger to schedule |
|------|----------------|---------------------|
| Helper/artifact column removal in cleaning pipeline (Issue #3) | Requires second file confirming same artifact pattern | Second file with >3 artifact columns |
| AI planner for low-confidence cases | Not needed while deterministic planner is sufficient | Low-confidence rate > 20% in pilot data |
| User override / edit of analysis_plan | Good UX but no pilot demand yet | Pilot consultant feedback requesting it |
| Domain-specific signal packs (finance, insurance, sales, HR…) | **Guardrail: 3+ independent pilot requests per domain before any build work** | 3+ pilot requests for that domain |

---

## Next Recommended Step

1. **Run a final demo smoke test** using the improved Dataset Intelligence Layer on a representative file (e.g. `demo_data/acme_retail_november_2024_sales.csv`). Confirm the full flow: upload → analysis → Intake Review card → findings order → chart order → export.

2. If no P0/P1 found in smoke test, **proceed to pilot outreach** — the platform is ready for the first real consultant.

3. After first pilot session, review `docs/MESSY_FILE_QA_LOG.md` with any new file observations before building new intelligence features.

---

*Checkpoint created: 2026-05-09*
*Branch: `claude/backend-chart-export-context-culfe`*
