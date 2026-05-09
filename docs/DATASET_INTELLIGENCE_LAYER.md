# Dataset Intelligence Layer — Design Document

> Status: Design only — no code yet.
> Companion docs: [MESSY_FILE_QA_LOG.md](./MESSY_FILE_QA_LOG.md) · [PILOT_DEMO_PACKAGE.md](./PILOT_DEMO_PACKAGE.md)

---

## Purpose

The Dataset Intelligence Layer is a pre-analysis classification step that runs after file intake and before the cleaning pipeline. Its job is to answer:

> "What kind of dataset is this, and how should the pipeline treat it?"

Without this layer, Analyst Pro runs the same generic analysis on every file. That produces technically correct but contextually weak output: date-part correlations ranked above business metrics, artifact columns treated as data, charts that are statistically valid but not meaningful to the actual use case.

The intelligence layer produces a structured `analysis_plan` object. Every downstream step — cleaning, health scoring, finding ranking, chart selection, report template — can read from this plan to make better decisions without hardcoded domain packs.

---

## Where It Sits

```
upload
  └─ intake (parse, detect types, preview)
       └─ ── DATASET INTELLIGENCE LAYER ──
            (classify + plan before any analysis runs)
               └─ cleaning  (informed by columns_to_ignore, helper column flags)
                    └─ health score
                         └─ findings  (informed by target_metrics, insight_priorities)
                              └─ chart selection  (informed by recommended_charts)
                                   └─ report builder  (informed by report_template_hint)
```

The layer runs once per file, immediately after the intake phase produces its column type map and sample rows. It is a fast, cheap operation — deterministic signals first, AI planner second (only when confidence is below threshold).

---

## Output Schema — `analysis_plan`

```python
@dataclass
class AnalysisPlan:
    # What kind of dataset this appears to be.
    # "sales" | "finance" | "hr" | "insurance" | "marketing" | "operations" |
    # "research" | "generic"
    dataset_kind: str

    # 0.0–1.0. Below 0.6, fall back to generic analysis and log a warning.
    confidence: float

    # One or two sentences describing the apparent business context.
    # Generated from deterministic signals; AI may refine if confidence is low.
    business_context: str

    # The primary unit of observation: "policy", "order", "employee", "customer", etc.
    primary_entity: str | None

    # Columns most likely to be the key business metrics to explain or predict.
    # Cleaning and finding ranker prioritise these.
    target_metrics: list[str]

    # Columns that provide the most useful segmentation for findings.
    # e.g. region, product_category, department, policy_type
    important_dimensions: list[str]

    # Detected date/time columns (used to suppress date-part over-ranking).
    time_columns: list[str]

    # Columns to exclude or heavily discount: IDs, artifact/helper columns,
    # single-value columns, mostly-empty columns.
    columns_to_ignore: list[str]

    # Ordered list of chart types + column pairings most likely to tell the
    # business story. Finding ranker and chart selector read this list.
    recommended_charts: list[ChartHint]

    # Ordered list of finding categories to prioritise.
    # e.g. ["correlation", "outlier", "trend"] for sales;
    #      ["distribution", "segment_comparison"] for HR
    insight_priorities: list[str]

    # Warnings to surface at the top of the analysis.
    # e.g. "85% of rows have the same region — segment findings may be skewed"
    analysis_warnings: list[str]

    # Hint to the report builder about which template or tone to use.
    # "executive_summary" | "detailed_audit" | "trend_report" | "generic"
    report_template_hint: str


@dataclass
class ChartHint:
    chart_type: str          # "scatter" | "bar" | "line" | "histogram" | "heatmap"
    x_column: str
    y_column: str | None     # None for single-column charts (histogram)
    rationale: str           # one-line reason this chart was recommended
    priority: int            # 1 = highest
```

---

## Deterministic Signals

These run first, without any AI call. They are fast, reproducible, and cheap.

### 1. Column name patterns

| Signal | Inferred meaning |
|--------|-----------------|
| `*_id`, `*_key`, `*_num`, `*_code` | ID / reference column — likely `columns_to_ignore` candidate |
| `date_*`, `*_date`, `*_at`, `*_time`, `*_month`, `*_year` | Date/time column → `time_columns` |
| `revenue`, `sales`, `amount`, `price`, `cost`, `margin` | Target metric → `target_metrics` |
| `premium`, `claim`, `policy`, `coverage`, `loss` | Insurance context |
| `salary`, `tenure`, `department`, `attrition`, `performance` | HR context |
| `quantity`, `discount`, `order`, `product`, `region` | Sales context |
| `return`, `yield`, `portfolio`, `ticker`, `close`, `volume` | Finance/market context |
| `Unnamed:`, `avg `, `avg_`, `total_`, `sum_`, `helper` | Artifact/helper column → `columns_to_ignore` |

### 2. Structural signals

| Signal | Use |
|--------|-----|
| Single-value columns (all rows identical) | `columns_to_ignore` |
| >80% missing | `columns_to_ignore` candidate; `analysis_warnings` |
| Columns that are row-sequential integers | Likely index — `columns_to_ignore` |
| All-unique string column | Likely an ID — `columns_to_ignore` |
| >3 numeric columns with similar names and partial overlap | Artifact columns from a pivot/spreadsheet |

### 3. Type balance

| Balance | Inference |
|---------|-----------|
| Mostly numeric, 1–2 categoricals | Regression/metric-heavy dataset → prioritise correlation and trend findings |
| Mixed numeric + categorical (even split) | Classification-like dataset → prioritise segment comparison findings |
| Mostly categorical, few numerics | Survey or categorical inventory → prioritise distribution findings |

### 4. Date column heuristics

- If date columns exist: extract derived features (month, quarter, year, weekday) are flagged in `time_columns` so the finding ranker can down-weight them.
- If >1 date column exists and one has high cardinality: likely a transaction/event log → trend findings prioritised.
- If date column has low cardinality (e.g. only 3 distinct months): likely a reporting snapshot → trend findings suppressed.

### 5. Target-like column detection

A column is a candidate `target_metric` if:
- Its name matches a known metric pattern (revenue, salary, churn, claim_amount)
- OR it is numeric with moderate variance (not constant, not a sequential ID)
- AND it is not already classified as an ID or artifact column

---

## AI Planner Input

The AI planner runs only when deterministic signals produce confidence < 0.6, or when the dataset kind is ambiguous between two candidates.

**Input object passed to the AI planner:**

```json
{
  "schema_summary": [
    {"column": "policy_id",    "dtype": "int64",   "unique_pct": 1.0,  "missing_pct": 0.0},
    {"column": "premium",      "dtype": "float64", "unique_pct": 0.42, "missing_pct": 0.01},
    {"column": "effective_date","dtype": "object", "unique_pct": 0.15, "missing_pct": 0.0},
    ...
  ],
  "sample_rows": [
    {"policy_id": 10001, "premium": 1420.50, "effective_date": "2023-01-15", ...},
    ...
  ],
  "profile_summary": {
    "row_count": 1050,
    "col_count": 22,
    "numeric_cols": 9,
    "categorical_cols": 8,
    "date_cols": 3,
    "missing_pct_overall": 0.04
  },
  "missingness_summary": [
    {"column": "claim_amount", "missing_pct": 0.72},
    {"column": "region",       "missing_pct": 0.03}
  ],
  "suspicious_columns": [
    {"column": "avg S",  "reason": "artifact name pattern, 90% missing"},
    {"column": "Unnamed: 14", "reason": "unnamed spreadsheet column"}
  ],
  "deterministic_draft": {
    "dataset_kind": "insurance",
    "confidence": 0.55,
    "reason_for_low_confidence": "premium column present but no explicit claim columns"
  }
}
```

**AI planner output** must conform to the `AnalysisPlan` schema. The planner may not:
- Invent column names that are not in `schema_summary`
- Set `confidence` above 0.85 when fewer than 4 strong signals are present
- Recommend a domain pack — that decision is made by the roadmap rules, not the planner

---

## Safety Rules

| Rule | Enforcement |
|------|------------|
| AI cannot invent column names | All column references in `AnalysisPlan` are validated against the actual schema at plan-build time; invalid names are silently dropped |
| Confidence required | If `confidence < 0.6`, downstream pipeline ignores `dataset_kind` and runs generic analysis; plan still logged for debugging |
| Fallback to generic | Generic analysis is always the safe path; intelligence layer adds signal, never removes capability |
| No domain pack from intelligence layer | The layer emits a `dataset_kind` hint, not a domain pack. Domain packs require 3+ independent pilot requests (see roadmap rules) |
| User review (future) | `analysis_plan` will be surfaced in the Intake Review tab so users can override `columns_to_ignore` and `target_metrics` before committing to analysis |
| Re-run safety | If a cached plan exists for the same file hash, it is reused. If column count or schema changes, the plan is invalidated and rebuilt |

---

## Examples

### Example 1 — Auto Insurance Policy File

**File:** `auto_insurance_data.xlsx`
**Strong signals:** `premium`, `policy_id`, `effective_date`, `claim_*`, `coverage_type`

```json
{
  "dataset_kind": "insurance",
  "confidence": 0.82,
  "business_context": "Auto insurance policy portfolio with premium and claim data. Primary interest is loss ratio, premium distribution, and claim frequency by segment.",
  "primary_entity": "policy",
  "target_metrics": ["premium", "claim_amount", "loss_ratio"],
  "important_dimensions": ["coverage_type", "region", "vehicle_age_band"],
  "time_columns": ["effective_date", "expiry_date"],
  "columns_to_ignore": ["policy_id", "customer_id", "avg S", "avg P", "Unnamed: 14"],
  "recommended_charts": [
    {"chart_type": "histogram", "x_column": "premium", "y_column": null, "rationale": "Distribution of premium across portfolio", "priority": 1},
    {"chart_type": "bar",       "x_column": "coverage_type", "y_column": "claim_amount", "rationale": "Average claim by coverage type", "priority": 2},
    {"chart_type": "scatter",   "x_column": "premium", "y_column": "claim_amount", "rationale": "Premium vs claim — loss ratio proxy", "priority": 3}
  ],
  "insight_priorities": ["correlation", "segment_comparison", "outlier"],
  "analysis_warnings": ["effective_date_month/quarter/year detected — date-part features will be down-ranked in findings"],
  "report_template_hint": "detailed_audit"
}
```

---

### Example 2 — Sales by Region / Product

**File:** `acme_retail_november_2024_sales.csv`
**Strong signals:** `revenue`, `quantity`, `order_date`, `region`, `product_category`, `sales_rep`

```json
{
  "dataset_kind": "sales",
  "confidence": 0.91,
  "business_context": "Retail sales transaction log for November 2024. Primary interest is revenue by region, product category, and rep performance.",
  "primary_entity": "order",
  "target_metrics": ["revenue", "quantity"],
  "important_dimensions": ["region", "product_category", "sales_rep"],
  "time_columns": ["order_date"],
  "columns_to_ignore": ["order_id", "customer_id"],
  "recommended_charts": [
    {"chart_type": "bar",     "x_column": "region",           "y_column": "revenue",  "rationale": "Revenue by region — top-line performance split", "priority": 1},
    {"chart_type": "bar",     "x_column": "product_category", "y_column": "revenue",  "rationale": "Revenue by category — product mix", "priority": 2},
    {"chart_type": "line",    "x_column": "order_date",       "y_column": "revenue",  "rationale": "Revenue trend — detect spike on Nov 19", "priority": 3},
    {"chart_type": "scatter", "x_column": "discount_pct",     "y_column": "revenue",  "rationale": "Discount vs revenue — margin impact", "priority": 4}
  ],
  "insight_priorities": ["trend", "correlation", "segment_comparison", "outlier"],
  "analysis_warnings": [],
  "report_template_hint": "executive_summary"
}
```

---

### Example 3 — Finance / Market Data

**File:** `equity_returns_q3.csv`
**Strong signals:** `ticker`, `close`, `volume`, `return_pct`, `date`

```json
{
  "dataset_kind": "finance",
  "confidence": 0.88,
  "business_context": "Equity price and return data. Primary interest is return distribution, volatility, and correlation between instruments.",
  "primary_entity": "instrument",
  "target_metrics": ["return_pct", "close", "volume"],
  "important_dimensions": ["ticker", "sector"],
  "time_columns": ["date"],
  "columns_to_ignore": ["row_id"],
  "recommended_charts": [
    {"chart_type": "line",      "x_column": "date",       "y_column": "close",      "rationale": "Price over time per instrument", "priority": 1},
    {"chart_type": "histogram", "x_column": "return_pct", "y_column": null,         "rationale": "Return distribution — normality and tail risk", "priority": 2},
    {"chart_type": "heatmap",   "x_column": "ticker",     "y_column": "return_pct", "rationale": "Cross-instrument correlation", "priority": 3}
  ],
  "insight_priorities": ["correlation", "outlier", "trend"],
  "analysis_warnings": [],
  "report_template_hint": "trend_report"
}
```

---

### Example 4 — HR Attrition

**File:** `hr_employee_attrition.csv`
**Strong signals:** `attrition`, `department`, `salary`, `tenure`, `performance_rating`

```json
{
  "dataset_kind": "hr",
  "confidence": 0.86,
  "business_context": "Employee HR dataset with attrition outcome. Primary interest is which attributes correlate with voluntary departure.",
  "primary_entity": "employee",
  "target_metrics": ["attrition", "salary", "tenure"],
  "important_dimensions": ["department", "job_level", "gender"],
  "time_columns": ["hire_date", "exit_date"],
  "columns_to_ignore": ["employee_id", "name"],
  "recommended_charts": [
    {"chart_type": "bar",       "x_column": "department",         "y_column": "attrition",    "rationale": "Attrition rate by department", "priority": 1},
    {"chart_type": "histogram", "x_column": "tenure",             "y_column": null,            "rationale": "Tenure distribution — early vs late attrition", "priority": 2},
    {"chart_type": "bar",       "x_column": "performance_rating", "y_column": "attrition",    "rationale": "Performance vs attrition — flight risk signal", "priority": 3}
  ],
  "insight_priorities": ["segment_comparison", "correlation", "distribution"],
  "analysis_warnings": [],
  "report_template_hint": "detailed_audit"
}
```

---

## How This Beats Generic LLM Upload Analysis

| Generic LLM analysis | Analyst Pro with intelligence layer |
|----------------------|-------------------------------------|
| Treats every file as text and summarises it | Classifies the dataset kind and builds a structured analysis plan |
| Cannot distinguish ID columns from data columns | `columns_to_ignore` removes IDs and artifacts before finding generation |
| Date-part features (month, quarter) rank alongside business metrics | `time_columns` signals the finding ranker to down-weight date-part correlations |
| Recommends the same chart types regardless of context | `recommended_charts` is tailored to the dataset kind and target metrics |
| Report structure is generic | `report_template_hint` selects a report framing appropriate to the business context |
| Low confidence is silent | `analysis_warnings` surfaces known data quality or context issues to the user |
| All columns treated equally | `target_metrics` and `important_dimensions` direct the finding ranker toward the most business-relevant signal |
| Domain knowledge requires prompt engineering | Deterministic signal extraction produces stable, reproducible classification without prompt drift |

---

## Implementation Phases (for reference — no code in this task)

| Phase | Scope | Gate |
|-------|-------|------|
| 1 | Deterministic signal extraction only — no AI planner | After design doc is approved |
| 2 | AI planner for low-confidence cases | After Phase 1 tests pass |
| 3 | Persist `analysis_plan` to DB alongside run record | After Phase 2 stable |
| 4 | Expose plan in Intake Review UI for user override | After 3+ pilots request editing the plan |
| 5 | Domain-specific signal packs (insurance, HR, etc.) | Only after 3+ independent pilot requests per domain |

---

*Design document created: 2026-05-08*

*Implementation complete: see [`docs/DATASET_INTELLIGENCE_CHECKPOINT_86.md`](DATASET_INTELLIGENCE_CHECKPOINT_86.md) for 86A–86L summary.*
