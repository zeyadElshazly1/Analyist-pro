# Pre-Analysis Intelligence Layer V2

## Purpose

Before any detector runs, before any insight is ranked, and before any chart is drawn, the system should understand the dataset deeply. The Pre-Analysis Intelligence Layer V2 produces a structured profile of the uploaded data — its shape, column semantics, grain, risks, and natural hypotheses — so that every downstream component (cleaning, ranking, charting, narrative, executive panel, report builder) can make better, more targeted decisions without guessing from raw column names or relying on fragile token-matching heuristics.

The goal is a dataset understanding layer that is deterministic, testable, generic (no domain packs), and extensible to an AI-assisted planner in a later phase.

---

## Current State

`app/services/analysis/analysis_planner.py` implements a deterministic planner that:

- Reads column names and infers intent from name tokens (e.g., "revenue", "churn", "date")
- Reads pandas dtypes and basic profile signals (cardinality, missingness flags)
- Produces an `AnalysisPlan` dataclass with ignored columns, priority columns, and suppression hints
- Makes no AI call — fully deterministic
- Has a documented extension point for an AI planner that is not yet wired in

The `AnalysisPlan` is consumed by `analysis_plan_hygiene.py`, which uses it to suppress or penalise findings that reference ignored or low-signal columns.

---

## Problems With Current Pre-Analysis

| Problem | Impact |
|---------|--------|
| Column intent is derived purely from name tokens | Columns with abbreviated, domain-specific, or numeric names are misclassified |
| No semantic role classification | Ranking, charting, and narrative cannot distinguish a metric from a dimension or an entity ID from a target variable |
| Grain/entity detection is absent | One-row-per-customer datasets are treated identically to one-row-per-event datasets, leading to irrelevant findings |
| No relationship map between columns | Correlated pairs, parent–child hierarchies, and ID–label pairs are invisible to the planner |
| No analysis-risk map | High-cardinality IDs, constant columns, sparse columns, and leakage candidates are not flagged early |
| No hypothesis generation | Analysts get generic findings instead of findings oriented around the dataset's natural questions |
| No dataset complexity score | Every dataset is analysed with the same depth and breadth regardless of how rich or sparse it is |
| Weak target/label detection | The system cannot distinguish an outcome variable from an ordinary numeric column |

---

## V2 Capabilities

### 1. Dataset Fingerprint

The fingerprint captures objective, computable facts about the dataset as a whole:

- **Dimensions**: row count, column count
- **Column type breakdown**: numeric, categorical, datetime, boolean, free-text, mixed
- **Missingness profile**: per-column missing rate; overall missingness density
- **Duplicate profile**: exact-duplicate row count; near-duplicate rate estimate
- **Cardinality profile**: unique-value counts per column; high-cardinality flag threshold
- **Data density**: proportion of cells that are populated and non-zero
- **Dataset shape classification** — one of:
  - `transactional` — one row per business event (order, claim, payment)
  - `snapshot` — one row per entity at a point in time (customer state, policy state)
  - `time_series` — one row per time period for a single or small set of entities
  - `event_log` — timestamped activity stream with free-form event types
  - `survey` — one row per respondent with many categorical/ordinal answers
  - `entity_table` — one row per entity with mostly descriptive attributes
  - `panel_data` — one row per entity per time period (repeated measures)
  - `unknown` — fallback when no shape is confidently detected

### 2. Semantic Role Detection

Each column is assigned one primary semantic role:

| Role | Description |
|------|-------------|
| `metric` | Numeric column representing a quantity to be measured (revenue, units, score) |
| `dimension` | Categorical or low-cardinality column suitable for grouping and slicing |
| `time` | Date, datetime, or time-period column |
| `entity_id` | High-cardinality ID that uniquely identifies a subject (customer_id, user_id) |
| `transaction_id` | High-cardinality ID for an event or transaction (order_id, claim_id) |
| `target` | Likely outcome variable — binary, ordinal, or continuous label for prediction |
| `leakage_candidate` | Column that is suspicious for target leakage (e.g., post-event timestamp, derived metric) |
| `helper_artifact` | System columns, row numbers, import artefacts, date-part extractions |
| `free_text` | Long-string column with high unique rate (comments, notes, descriptions) |
| `geographic` | Country, region, city, postcode, lat/lon |
| `currency_amount` | Numeric column with currency signal in name or values |
| `rate_percentage` | Numeric column representing a rate or percentage (bounded 0–100 or 0–1) |
| `boolean_flag` | Binary column with exactly two distinct values |

A column may carry secondary roles as supplemental signals (e.g., a column could be `metric` with secondary `rate_percentage`).

### 3. Grain and Entity Detection

The grain detector answers the question: **What does one row represent?**

Candidate grain labels:

- `customer` — one row per customer or user
- `order` — one row per order or purchase
- `policy` — one row per insurance or subscription policy
- `transaction` — one row per financial or operational transaction
- `event` — one row per activity event
- `product` — one row per product or SKU
- `employee` — one row per staff member
- `time_period` — one row per day, week, month, or other interval
- `session` — one row per user session
- `survey_response` — one row per survey respondent
- `unknown` — fallback

Detection signals:

- Entity ID column names and cardinality relative to row count
- Presence and dtype of time columns
- Dataset shape from the fingerprint
- Row count vs. unique ID count ratio

The detected grain is stored as `grain_label` (string) and `grain_confidence` (0.0–1.0).

### 4. Analysis Strategy Builder

Given the fingerprint, roles, and grain, the strategy builder produces:

**Recommended analysis types** (in priority order):
- Which detector families are most likely to yield high-quality findings given this dataset shape
- e.g., for `time_series` shape: trend analysis first, then anomaly detection, then correlation

**Analysis types to avoid or deprioritise**:
- Correlation analysis on high-cardinality ID columns
- Trend analysis when no time column is detected
- Segment comparison when all dimensions are free-text

**Recommended comparisons**:
- Which dimension columns should be used for group-by comparisons
- Which metric columns are the strongest candidates for comparison targets

**Recommended segment cuts**:
- Dimension columns with cardinality between 2 and 20 (good segment candidates)

**Recommended trend checks**:
- Time columns paired with each detected metric

**Recommended chart families**:
- Bar/column charts for dimension × metric comparisons
- Line charts for time × metric trends
- Scatter/correlation plots for metric × metric pairs
- Distribution histograms for metric columns

### 5. Risk and Trust Warnings

The risk detector produces a list of named warnings, each with a severity (`low`, `medium`, `high`) and a human-readable description:

| Risk name | Trigger condition |
|-----------|------------------|
| `too_many_id_columns` | More than 20 % of columns detected as `entity_id` or `transaction_id` |
| `sparse_columns` | One or more columns with >60 % missing rate |
| `date_part_artifacts` | Columns whose names match date-part tokens (year, month, week, day) and are derived from another datetime column |
| `possible_leakage` | `leakage_candidate` columns detected alongside a `target` column |
| `target_leakage_risk` | `leakage_candidate` confidence > 0.7 |
| `small_sample` | Row count < 100 |
| `very_small_sample` | Row count < 30 |
| `high_cardinality_dimensions` | Categorical columns with unique rate > 50 % |
| `duplicated_columns` | Two or more columns with identical value distributions |
| `constant_columns` | Columns with exactly one unique value |
| `mixed_grain` | Entity ID cardinality patterns suggest more than one grain is present in the same table |

Warnings feed directly into `analysis_plan_hygiene` suppression logic and are exposed in `result_json` for QA and future frontend display.

### 6. Hypothesis Plan

A lightweight, generic list of natural questions to investigate given the detected grain, roles, and fingerprint. Hypotheses are not domain-specific — they are structural questions that apply to any dataset of the detected shape.

Examples:

- "Do key metrics vary meaningfully across the detected dimension columns?"
- "Do metrics trend upward or downward over the detected time column?"
- "Is missingness concentrated in specific columns, or distributed randomly?"
- "Are high-cardinality ID columns incorrectly driving apparent segment differences?"
- "Do any pairs of metrics exhibit strong correlation or anti-correlation?"
- "Are there anomalous rows that deviate significantly from the bulk distribution?"
- "Is the target variable balanced, or is there a class imbalance that distorts findings?"

Each hypothesis is stored as a short string and is available for narrative and executive panel generation to orient findings.

### 7. Output Schema Proposal

```python
@dataclass
class DatasetFingerprint:
    row_count: int
    column_count: int
    numeric_column_count: int
    categorical_column_count: int
    datetime_column_count: int
    boolean_column_count: int
    free_text_column_count: int
    overall_missing_rate: float          # 0.0–1.0
    duplicate_row_count: int
    overall_data_density: float          # 0.0–1.0
    dataset_shape: str                   # transactional | snapshot | time_series | ...


@dataclass
class ColumnSemanticRole:
    column_name: str
    primary_role: str                    # metric | dimension | time | entity_id | ...
    secondary_roles: list[str]
    role_confidence: float               # 0.0–1.0
    cardinality: int
    missing_rate: float                  # 0.0–1.0
    notes: str | None


@dataclass
class AnalysisStrategy:
    recommended_analysis_types: list[str]
    deprioritised_analysis_types: list[str]
    recommended_metric_columns: list[str]
    recommended_dimension_columns: list[str]
    recommended_time_columns: list[str]
    recommended_chart_families: list[str]


@dataclass
class AnalysisRisk:
    risk_name: str
    severity: str                        # low | medium | high
    affected_columns: list[str]
    description: str


@dataclass
class HypothesisPlan:
    hypotheses: list[str]


@dataclass
class PreAnalysisProfile:
    fingerprint: DatasetFingerprint
    column_roles: list[ColumnSemanticRole]
    grain_label: str
    grain_confidence: float
    strategy: AnalysisStrategy
    risks: list[AnalysisRisk]
    hypothesis_plan: HypothesisPlan
    generated_at: str                    # ISO-8601 timestamp
    planner_version: str                 # e.g. "v2.0-deterministic"
```

---

## Integration Points

| Downstream component | How V2 profile improves it |
|----------------------|---------------------------|
| **Cleaning** | Skip normalisation steps that do not apply to the detected column roles (e.g., date parsing on `entity_id` columns) |
| **`analysis_plan_hygiene`** | Use `AnalysisRisk` list to suppress findings on constant columns, duplicated columns, and ID-driven segments directly — not via name-token matching |
| **Ranking** | Boost findings on `metric` and `target` columns; demote findings on `helper_artifact` and `entity_id` columns |
| **Chart generation** | Use `recommended_chart_families` and `recommended_dimension_columns` to select chart type and axes without heuristic guessing |
| **Narrative** | Orient paragraphs around the `HypothesisPlan` hypotheses; reference the detected grain label for natural language ("each row represents one customer") |
| **Executive panel** | Use `recommended_metric_columns` as the primary signal for opportunities/risks tiles |
| **Report builder** | Include `DatasetFingerprint` and detected grain in the report header section; surface `AnalysisRisk` warnings in a data quality callout |
| **Saved `result_json`** | Persist the full `PreAnalysisProfile` so reopened runs return the same dataset understanding as live runs |

---

## Guardrails

- **No domain packs**: no churn-specific, sales-specific, insurance-specific, or any other vertical-specific logic. All role detection and hypothesis generation must be generic and structurally driven.
- **Deterministic first**: V2 produces the same output for the same dataset on every run. The AI planner extension point is preserved in the schema (`planner_version`) but is not wired in during 90B–90I.
- **Must be testable**: every extractor function returns a plain Python dataclass or dict. No side effects, no I/O. Unit tests cover all classification rules, edge cases (empty dataset, all-missing columns, single-column dataset), and schema shape.
- **Must not break existing `AnalysisPlan` consumers**: the existing `AnalysisPlan` schema and `analysis_plan_hygiene` pipeline remain unchanged. `PreAnalysisProfile` is additive — it feeds into existing consumers as an optional enhancement and is persisted alongside the existing plan.

---

## Suggested Implementation Phases

| Task | Scope |
|------|-------|
| **90B** | Define `PreAnalysisProfile`, `DatasetFingerprint`, `ColumnSemanticRole`, `AnalysisStrategy`, `AnalysisRisk`, and `HypothesisPlan` dataclasses in `app/services/analysis/pre_analysis_schema.py`. Write schema unit tests. |
| **90C** | Build `extract_dataset_fingerprint(df) → DatasetFingerprint` in `app/services/analysis/fingerprint.py`. Cover all shape classifiers and density metrics. Write unit tests. |
| **90D** | Build `classify_column_roles(df, fingerprint) → list[ColumnSemanticRole]` in `app/services/analysis/column_roles.py`. Cover all 13 primary roles with deterministic rules. Write unit tests. |
| **90E** | Build `detect_grain(df, fingerprint, column_roles) → (grain_label, grain_confidence)` in `app/services/analysis/grain_detector.py`. Write unit tests covering each grain label. |
| **90F** | Build `build_analysis_strategy(fingerprint, column_roles, grain_label) → AnalysisStrategy` and `detect_risks(df, fingerprint, column_roles) → list[AnalysisRisk]` and `build_hypothesis_plan(fingerprint, column_roles, grain_label) → HypothesisPlan` in `app/services/analysis/strategy_builder.py`. Write unit tests. |
| **90G** | Wire `PreAnalysisProfile` into the three pipeline paths (sync route, stream route, Celery task). Persist as `pre_analysis_profile` in `result_json`. |
| **90H** | Expose `pre_analysis_profile` in `RunResults` schema (`app/schemas/run_summary.py`) so reopened saved runs return the profile. |
| **90I** | Use `PreAnalysisProfile` signals to improve ranking boost/demote logic, chart axis selection, and `analysis_plan_hygiene` risk suppression. Regression-test that existing passing tests remain green. |
