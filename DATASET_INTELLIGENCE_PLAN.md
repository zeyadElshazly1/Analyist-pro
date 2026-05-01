# Dataset Intelligence Plan — Analyst Pro

**Status:** Revised pre-implementation planning document  
**Author:** Senior Data Platform Architect  
**Date:** 2026-05-01  
**Scope:** V1 — financial_markets_snapshot (Yahoo global markets cross-sectional data)  
**Revision note:** Split original `financial_markets` type into `financial_markets_snapshot`
(cross-sectional, per-asset metrics) and `financial_markets_timeseries` (OHLC price history).
V1 targets snapshot only. OHLC/time-series detectors moved to V1.5/V2.

---

## Table of Contents

1. [Problem Statement](#1-problem-statement)
2. [Target Architecture](#2-target-architecture)
3. [DatasetContext Specification](#3-datasetcontext-specification)
4. [Supported Dataset Types](#4-supported-dataset-types)
5. [V1 Implementation Scope](#5-v1-implementation-scope)
6. [Files to Create and Change](#6-files-to-create-and-change)
7. [Tests Required](#7-tests-required)
8. [Acceptance Criteria](#8-acceptance-criteria)
9. [Rollout Strategy](#9-rollout-strategy)
10. [Implementation Checklist](#10-implementation-checklist)

---

## 1. Problem Statement

### 1.1 Generic Correlations Dominate and Mislead

The current `analyze_dataset()` pipeline in `orchestrator.py` treats every DataFrame identically. It fires every detector — correlations, anomalies, segments, trends — regardless of what the data actually represents. On a Yahoo global markets snapshot dataset this produces findings like:

- "Strong correlation: ytd_return & one_year_return (r=0.91)" — true but trivially expected; multi-period return columns are constructed from the same price series. Not an insight.
- "Strong correlation: composite_score & sharpe_ratio (r=0.88)" — composite scores are typically *built from* constituent metrics; flagging this is circular.
- "Skewed distribution: market_cap" — market cap is always right-skewed across a broad asset universe. Flagging it as a finding wastes attention.
- "High-cardinality column: ticker" — tickers are identifiers, not a data quality problem.
- "Concentration risk in sector" — a snapshot with 10 sectors will always look concentrated; this is schema design, not risk.

The ranking function `rank_insights()` scores by statistical severity and confidence. It has no concept of domain relevance. A high-confidence but trivially-expected correlation between two return columns will outrank a genuinely important Sharpe/return divergence across asset classes. The user sees noise first.

### 1.2 Charts Are Misleading Without Domain Context

The generic chart builder produces charts in a fixed priority order: time-series lines, histograms, heatmaps, boxplots, bar charts, scatter plots. On a snapshot dataset there are no datetime columns, so time-series charts are skipped. What the builder does produce:

- **Histogram of composite_score** — marginally useful but not the first thing an analyst needs.
- **Scatter: ytd_return vs one_year_return** — ranks highly because r≈0.9. Tells the analyst nothing they do not already know.
- **Heatmap** — all return and score columns light up as correlated. The heatmap actively misleads by suggesting redundancy rather than confirming multi-period structure.
- **Bar: sector counts** — counts assets per sector, not returns per sector. Wrong aggregation.

The charts the analyst actually wants — top 10 returns, risk vs. return scatter, volatility by asset class, analyst upside leaders — are never built because they require domain-aware column selection and computed aggregations.

### 1.3 Reports and Narratives Are Weak Without Domain Context

`generate_narrative()` produces a generic 3-paragraph summary that leads with correlations and anomalies. For a finance snapshot, the executive summary should lead with performance leaders and laggards, risk-adjusted standings, and cross-asset comparisons. The word "finance" may appear in the domain label returned by `_detect_domain()` but it is never used to change the narrative structure or content.

`insight_adapter.py` assigns identical caveats to all insights of a given category. A "correlation" insight on a snapshot dataset gets "Correlation does not imply causation" — generically correct but domain-useless. The finance-aware caveat would be: "Multi-period return columns are constructed from overlapping price series; their correlation is structural, not informative."

Mixed-asset-class datasets (equities + ETFs + bonds + crypto in one snapshot) require an explicit caveat in every insight: risk metrics, Sharpe ratios, and volatility figures are not directly comparable across asset classes with different return profiles.

---

## 2. Target Architecture

### 2.1 Pipeline Diagram

```
Raw upload (CSV/Excel/etc.)
        │
        ▼
  cleaning/pipeline.py → cleaned df
        │
        ▼
┌──────────────────────────────────────┐
│  dataset_context/detector.py          │  ← NEW (V1A)
│  detect_dataset_context(df)           │
│  → DatasetContext                     │
│    .dataset_type                      │
│    .confidence                        │
│    .matched_signals                   │
│    .semantic_roles                    │
│    .warnings                          │
└──────────────────────────────────────┘
        │
        ├─── confidence >= 0.65?
        │         YES                          NO
        ▼                                      ▼
┌────────────────────────┐       ┌──────────────────────────────┐
│  Domain Insight Pack   │       │  Generic orchestrator         │
│  (V1B snapshot pack)   │       │  analyze_dataset() unchanged  │
└────────────────────────┘       └──────────────────────────────┘
        │                                      │
        └──────────────────┬────────────────────┘
                           ▼
               ┌─────────────────────────┐
               │  Domain-aware ranking    │  ← MODIFIED (V1C)
               │  + suppression rules     │
               └─────────────────────────┘
                           │
                           ▼
               ┌─────────────────────────┐
               │  insight_adapter.py      │  ← MODIFIED (V1E)
               │  domain caveats injected │
               └─────────────────────────┘
                           │
                           ▼
               ┌─────────────────────────┐
               │  Domain chart strategy   │  ← MODIFIED (V1D)
               │  build_chart_data()      │
               └─────────────────────────┘
                           │
                           ▼
               ┌─────────────────────────┐
               │  Domain narrative        │  ← MODIFIED (V1E)
               │  generate_narrative()    │
               └─────────────────────────┘
                           │
                           ▼
               canonical InsightResult list
               + domain charts
               + finance executive summary
               → frontend / report builder
```

### 2.2 V1 Sub-Phases

| Phase | Label | Deliverable |
|---|---|---|
| V1A | Dataset context detector | `detect_dataset_context()` returning `financial_markets_snapshot`, `financial_markets_timeseries` (stub), or `generic_tabular` |
| V1B | Snapshot finance insight pack | 8 domain-specific insight detectors for snapshot data |
| V1C | Ranking and suppression | Suppress repetitive return correlations, fake time-series, ID/name chart noise |
| V1D | Finance chart strategy | 5 domain-aware charts replacing generic defaults |
| V1E | Finance report summary | Domain narrative template + domain caveats in InsightResult |

### 2.3 Integration Points

No existing public API signatures change. All new parameters are optional with safe defaults.

| Touch Point | Current Behaviour | New Behaviour |
|---|---|---|
| `orchestrator.analyze_dataset(df)` | Always runs all generic detectors | If snapshot context detected, runs domain pack; generic detectors fill remaining slots |
| `ranking.rank_insights()` | Severity + confidence sort only | Domain suppression keys applied before sort |
| `insight_adapter.build_insight_result()` | Category-only caveats | Domain caveats and mixed-asset-class caveat injected |
| `charting/orchestrator.build_chart_data()` | Fixed priority order | Domain strategy runs first; ID/name charts and structural-correlation scatters suppressed |
| `narrative.generate_narrative()` | Generic 3-paragraph summary | Finance executive summary template used when snapshot context fires |

---

## 3. DatasetContext Specification

### 3.1 Core Dataclass

```
DatasetContext
├── dataset_type: str
│     Detected domain. One of:
│       "financial_markets_snapshot"   ← V1, fully implemented
│       "financial_markets_timeseries" ← V1 stub; detects but defers to generic
│       "generic_tabular"              ← always-available fallback
│
├── confidence: float  [0.0 – 1.0]
│     Normalised signal match score.
│     confidence = sum(matched_signal_weights) / sum(all_signal_weights_for_type)
│     Domain pack activates only when confidence >= 0.65.
│     generic_tabular is always assigned confidence = 1.0 (it is the fallback, not detected).
│
├── matched_signals: list[str]
│     Human-readable list of signals that fired.
│     Example for financial_markets_snapshot:
│       ["Return column detected (ytd_return)",
│        "Volatility column detected (volatility)",
│        "Sharpe ratio column detected (sharpe_ratio)",
│        "Asset class column detected (asset_class)",
│        "Sector column detected (sector)",
│        "Analyst upside column detected (analyst_upside)",
│        "52-week position column detected (week_52_position)"]
│     Used in: debug panel, test assertions, warning generation.
│
├── semantic_roles: dict[str, str]
│     Maps every column name to its semantic role in the detected domain.
│     Columns not matched to any role get role "unknown".
│     Example for financial_markets_snapshot:
│       {"ticker":            "asset_id",
│        "name":              "asset_label",
│        "asset_class":       "asset_class",
│        "sector":            "sector",
│        "ytd_return":        "return_period",
│        "one_year_return":   "return_period",
│        "three_year_return": "return_period",
│        "volatility":        "volatility",
│        "sharpe_ratio":      "sharpe_ratio",
│        "analyst_upside":    "analyst_upside",
│        "week_52_position":  "position_52w",
│        "composite_score":   "composite_score",
│        "market_cap":        "size_metric"}
│
└── warnings: list[str]
      Non-fatal issues detected during context resolution.
      Examples for snapshot:
        "Mixed asset classes detected (Equity, ETF, Bond, Crypto) — risk metrics
         are not directly comparable across these classes."
        "Sharpe ratio column contains values > 10 — verify annualisation basis."
        "Analyst upside column has 40% missing values — upside insights will
         cover a partial universe."
      Injected into: report header, narrative paragraph 1, InsightResult caveats.
```

### 3.2 Detection Logic (Deterministic, No ML)

Detection is a **signal scoring system** — pure deterministic column-name pattern matching, dtype checks, and value-range checks. No machine learning, no LLM calls.

**Why deterministic:**
- Reproducible: same DataFrame always produces the same DatasetContext.
- Testable: every signal is a unit-testable function.
- Fast: no model load, no API call. Target < 200ms on 1M rows.
- Auditable: `matched_signals` gives the user an exact reason for every classification.

**Signal types used in V1:**
1. **Column name patterns** — regex / keyword match on normalised names (lowercase, stripped, underscores removed for matching)
2. **Column group patterns** — a set of columns that co-occur (e.g. return + volatility + sharpe together strongly signal a snapshot)
3. **Dtype signals** — presence or absence of datetime columns (timeseries has them; snapshot does not)
4. **Value range signals** — volatility columns contain values in [0, 5]; return columns contain values in [-1, 10] for annual returns
5. **Cardinality signals** — a low-cardinality string column in the presence of return columns is likely `asset_class` or `sector`

### 3.3 Snapshot vs. Timeseries Disambiguation

The two financial_markets types are disambiguated by a **datetime column check** run before signal scoring:

| Condition | Assigned Type |
|---|---|
| No datetime column AND return/volatility/Sharpe signals present | `financial_markets_snapshot` |
| Datetime column present AND OHLC group present | `financial_markets_timeseries` |
| Datetime column present but no OHLC signals | `financial_markets_timeseries` (deferred to generic in V1) |
| Neither condition met | `generic_tabular` |

This avoids false classification of a timeseries dataset as a snapshot simply because it also has computed return columns.

### 3.4 Confidence Calculation

```
For each candidate type T:
  matched_weight = sum(weight_i for each signal_i that fires for T)
  max_weight     = sum(weight_i for all signals_i defined for T)
  confidence(T)  = matched_weight / max_weight

Assigned type = argmax over all T
If max confidence < 0.65 → dataset_type = "generic_tabular"

financial_markets_timeseries in V1: even if confidence >= 0.65, the domain
pack is not activated — timeseries is detected but falls through to generic.
A DatasetContext.warnings entry is added: "Time-series financial data detected;
domain-specific analysis for this type is available in a future version."
```

---

## 4. Supported Dataset Types

### 4.1 V1 Full Implementation: `financial_markets_snapshot`

**Reference dataset:** Yahoo Finance global markets cross-sectional snapshot — one row per asset, columns covering returns across multiple periods, risk metrics, analyst consensus, and composite scores.

**Canonical column vocabulary:**

| Column Pattern | Semantic Role | Weight |
|---|---|---|
| ytd_return, one_year_return, three_year_return, five_year_return, return_* | `return_period` | 0.25 |
| volatility, vol, std_dev, annualised_vol | `volatility` | 0.20 |
| sharpe, sharpe_ratio, risk_adjusted_return | `sharpe_ratio` | 0.15 |
| asset_class, type, instrument_type | `asset_class` | 0.15 |
| sector, industry, gics_sector | `sector` | 0.10 |
| analyst_upside, price_target_upside, consensus_upside | `analyst_upside` | 0.08 |
| week_52_position, position_52w, pct_of_52w_high | `position_52w` | 0.07 |
| composite_score, overall_score, rating | `composite_score` | — (no weight; derived, not detected) |
| ticker, symbol, isin | `asset_id` | — (no weight alone; confirms snapshot shape) |
| name, company_name, asset_name | `asset_label` | — |
| market_cap, aum, fund_size | `size_metric` | — |

Minimum for activation: return + volatility + (sharpe OR asset_class) → confidence ≥ 0.65.  
Maximum possible confidence = 1.00 (all weighted signals fire).

**No datetime column required or expected.** If a datetime column is present this dataset is reclassified as timeseries.

---

### 4.2 V1 Stub: `financial_markets_timeseries`

Detected but not acted on in V1. Assigned when an OHLC group or price-history pattern is found alongside a datetime column. Falls through to the generic analysis path with a warning. Full implementation in V1.5.

**V1.5 planned detectors (not in scope now):**
- Volatility regime detection
- Volume-price divergence
- Return distribution fat-tails
- OHLC integrity check
- Trading day gap detection
- Rolling momentum autocorrelation

---

### 4.3 Fallback: `generic_tabular`

Triggered when no domain type reaches confidence ≥ 0.65, or when `financial_markets_timeseries` is detected in V1. The current `analyze_dataset()` runs without modification. Zero regression guarantee.

---

### 4.4 Future: `customer_churn` (V2+)

Signals: churned/churn column, tenure, customer_id, subscription/plan columns, event counts.  
Key pack: churn rate by segment, tenure-survival curve, feature importance.

### 4.5 Future: `insurance` (V2+)

Signals: claim_amount, policy_id, premium, exposure, loss_ratio, peril.  
Key pack: loss ratio by segment, large-loss Pareto, geographic cluster risk.

---

## 5. V1 Implementation Scope

### 5.1 V1A — Dataset Context Detector

Implement `detect_dataset_context(df)` returning one of three types. All signal logic lives in `dataset_context/signals.py`. Detector is purely deterministic. `financial_markets_timeseries` is detected and returned but the domain pack is not activated.

### 5.2 V1B — Snapshot Finance Insight Pack

Eight domain-specific detectors operating on columns with roles defined in §4.1. Each returns a list of insight dicts in the existing insight dict schema (same fields as generic detectors: type, title, finding, severity, confidence, evidence, action).

| Detector | Output Insight Type | Description |
|---|---|---|
| `_detect_return_leaders` | `"segment"` | Top N assets by best return column; shows outperformers with evidence |
| `_detect_return_laggards` | `"segment"` | Bottom N assets by return; flags underperformers |
| `_detect_volatility_leaders` | `"concentration"` | Assets with highest volatility; flags outliers vs. peer median |
| `_detect_sharpe_leaders` | `"segment"` | Top N assets by Sharpe ratio; risk-adjusted performance ranking |
| `_detect_asset_class_comparison` | `"segment"` | Median return and volatility per asset class; flags divergent classes |
| `_detect_sector_comparison` | `"segment"` | Median return per sector; flags best and worst performing sectors |
| `_detect_analyst_upside` | `"segment"` | Top N assets by analyst upside; flags high-conviction buys |
| `_detect_52w_position` | `"distribution"` | Distribution of assets near 52-week high vs. low; market breadth signal |

**Mixed-asset-class caveat detector (not an insight — a warning):**  
If `asset_class` column contains ≥ 2 distinct classes, add to `DatasetContext.warnings`:  
"This dataset contains mixed asset classes. Volatility, Sharpe ratio, and return comparisons across classes (e.g. Equity vs. Bond vs. Crypto) should be interpreted with caution."  
This warning is injected into every domain insight's caveats list via the adapter.

### 5.3 V1C — Ranking and Suppression

Three suppression rule sets applied in `rank_insights()`:

**1. Return-column structural correlations:**  
Suppress any correlation insight where both `columns_used` values have role `return_period`. Multi-period return columns are built from overlapping price series — their correlation is a construction artefact.

**2. Composite-score correlations:**  
Suppress any correlation insight where either column has role `composite_score`. Composite scores are built from the same constituent metrics as the other columns; their correlations are definitional.

**3. ID / label columns:**  
Suppress any insight where a column with role `asset_id` or `asset_label` is the primary column. These are identifier strings; statistical tests on them are meaningless. This also prevents the chart builder from producing frequency bar charts of ticker names.

**Fake time-series suppression:**  
If `dataset_type = "financial_markets_snapshot"` (no datetime column), suppress all insights of type `"trend"` — the generic trend detector may fire on the row-index order, which has no temporal meaning in a snapshot.

### 5.4 V1D — Finance Chart Strategy

Five domain-aware charts are built first when `financial_markets_snapshot` is detected. They replace, not supplement, the generic defaults for this dataset type.

| Chart | Type | Columns | Description |
|---|---|---|---|
| Top 10 Returns | Horizontal bar | `asset_label` or `asset_id`, best available `return_period` role | Top 10 assets by return, labelled, sorted descending |
| Risk vs. Return Scatter | Scatter | `volatility` role (x), best `return_period` role (y), coloured by `asset_class` | The canonical risk/return plot; each dot is one asset |
| Asset Class Returns | Grouped bar | `asset_class` role (x), median of `return_period` columns (y) | Median return per asset class, one bar per class |
| Volatility by Asset Class | Boxplot | `asset_class` role (x), `volatility` role (y) | Spread and median volatility per asset class |
| Analyst Upside Top 10 | Horizontal bar | `asset_label` or `asset_id`, `analyst_upside` role | Top 10 assets by analyst consensus upside, labelled |

If any required column role is absent (e.g. no `analyst_upside` column), that chart is silently skipped. The chart builder falls back to the next generic chart in the priority queue.

Generic charts suppressed for snapshot data:
- Scatter plots between any two `return_period` columns (structural correlation, not informative)
- Correlation heatmap when ≥ 50% of numeric columns are `return_period` or `composite_score` roles
- Bar charts of `asset_id` or `asset_label` columns (ticker name frequency — meaningless)
- Time-series line charts (no datetime index in a snapshot)

### 5.5 V1E — Finance Executive Summary and Report Integration

**Narrative template** (replaces generic 3-paragraph structure when `financial_markets_snapshot` fires):

- **Paragraph 1 — Universe and data quality:** Number of assets, asset classes covered, date context if present, missing-value summary for key metrics, mixed-asset-class warning if applicable.
- **Paragraph 2 — Performance landscape:** Return leaders and laggards by name, best and worst asset class median returns, best sector, Sharpe ratio leaders (risk-adjusted standout).
- **Paragraph 3 — Analyst view and positioning:** Analyst upside leaders, 52-week position distribution (breadth signal — "X% of assets within 5% of 52-week high"), and the single highest-priority recommended action from the domain insights.

**Domain caveats injected into InsightResult:**

| Insight Type | Additional Domain Caveat |
|---|---|
| All insights on a mixed-asset-class dataset | "Risk and return metrics are not directly comparable across asset classes (e.g. Equity vs. Bond vs. Crypto)." |
| Any insight using `return_period` columns | "Return figures may use different calculation bases (price return vs. total return). Verify before comparing." |
| Any insight using `sharpe_ratio` role | "Sharpe ratio comparability requires consistent annualisation and risk-free rate assumptions." |
| Any insight using `analyst_upside` role | "Analyst consensus reflects a point-in-time view; upside figures become stale quickly." |

---

## 6. Files to Create and Change

### 6.1 New Files

```
apps/api/app/services/
└── dataset_context/
    ├── __init__.py
    │     Exports: DatasetContext, detect_dataset_context, resolve_semantic_roles
    │
    ├── schema.py
    │     DatasetContext (frozen dataclass)
    │     CONFIDENCE_THRESHOLD = 0.65
    │     DATASET_TYPE literals
    │
    ├── detector.py
    │     detect_dataset_context(df) -> DatasetContext
    │     _score_snapshot(df) -> tuple[float, list[str]]
    │     _score_timeseries(df) -> tuple[float, list[str]]
    │     _has_datetime_column(df) -> bool
    │     _normalise_col(col: str) -> str
    │
    ├── roles.py
    │     resolve_semantic_roles(df, ctx) -> dict[str, str]
    │     _roles_snapshot(df) -> dict[str, str]
    │     _roles_generic(df) -> dict[str, str]
    │
    └── signals.py
          RETURN_NAMES: frozenset[str]
          VOLATILITY_NAMES: frozenset[str]
          SHARPE_NAMES: frozenset[str]
          ASSET_CLASS_NAMES: frozenset[str]
          SECTOR_NAMES: frozenset[str]
          ANALYST_UPSIDE_NAMES: frozenset[str]
          POSITION_52W_NAMES: frozenset[str]
          OHLC_NAMES: frozenset[str]          ← for timeseries detection
          ASSET_ID_NAMES: frozenset[str]
          ASSET_LABEL_NAMES: frozenset[str]
          SIZE_METRIC_NAMES: frozenset[str]

apps/api/app/services/analysis/
└── domain/
    ├── __init__.py
    │     Exports: run_domain_pack
    │
    ├── base.py
    │     Abstract DomainInsightPack
    │     run(df, roles) -> list[dict]
    │     suppression_keys(roles) -> set[tuple]
    │
    ├── snapshot_finance.py
    │     SnapshotFinanceInsightPack(DomainInsightPack)
    │     _detect_return_leaders(df, roles)
    │     _detect_return_laggards(df, roles)
    │     _detect_volatility_leaders(df, roles)
    │     _detect_sharpe_leaders(df, roles)
    │     _detect_asset_class_comparison(df, roles)
    │     _detect_sector_comparison(df, roles)
    │     _detect_analyst_upside(df, roles)
    │     _detect_52w_position(df, roles)
    │
    └── registry.py
          DOMAIN_PACKS: dict[str, type[DomainInsightPack]]
            "financial_markets_snapshot" → SnapshotFinanceInsightPack
          get_domain_pack(dataset_type) -> DomainInsightPack | None

apps/api/tests/
    ├── test_dataset_context.py           ← new
    ├── test_snapshot_finance_pack.py     ← new
    └── test_domain_ranking.py            ← new
```

### 6.2 Files to Modify (targeted, minimal changes)

```
apps/api/app/services/analysis/orchestrator.py
  ADD optional ctx: DatasetContext | None = None to analyze_dataset().
  If ctx is None, call detect_dataset_context(df) internally.
  If ctx.dataset_type in DOMAIN_PACKS and ctx.confidence >= CONFIDENCE_THRESHOLD:
    - run domain pack, prepend insights
    - pass suppression_keys to rank_insights()
  All existing detector calls unchanged.
  LINES CHANGED: ~15 (import + ctx block at top of function).

apps/api/app/services/analysis/ranking.py
  ADD optional suppression_keys: set[tuple] | None = None to rank_insights().
  Apply filter before sort.
  LINES CHANGED: ~8.

apps/api/app/services/insight_adapter.py
  ADD optional dataset_context: DatasetContext | None = None to build_insight_result().
  When financial_markets_snapshot: inject domain caveats from a new lookup table.
  LINES CHANGED: ~20 (new lookup table + conditional block).

apps/api/app/services/charting/orchestrator.py
  ADD optional dataset_context: DatasetContext | None = None to build_chart_data().
  When financial_markets_snapshot: build 5 domain charts first; apply suppression
  list for structural-correlation scatters, ID bar charts, and heatmap.
  LINES CHANGED: ~50 (new domain chart builder block at top of function).

apps/api/app/services/analysis/narrative.py
  ADD optional dataset_context: DatasetContext | None = None to generate_narrative().
  When financial_markets_snapshot: use 3-paragraph domain template.
  LINES CHANGED: ~40 (new template function + conditional dispatch).
```

### 6.3 Files Explicitly Not Changed

```
apps/api/app/schemas/insight.py          ← InsightResult schema unchanged
apps/api/app/routes/analysis.py          ← Route unchanged
apps/api/app/services/cleaning/          ← Cleaning pipeline unchanged
apps/api/app/services/charting/payloads.py   ← Individual payload builders unchanged
apps/api/app/services/reporting/         ← Report templates unchanged in V1
```

The only schema change in V1 is adding new `InsightCategory` literals for any truly new insight types. Given §5.2 reuses existing types (`"segment"`, `"concentration"`, `"distribution"`), **no schema change is needed in V1**.

---

## 7. Tests Required

### 7.1 `tests/test_dataset_context.py`

**Detector tests:**

| Test | What it verifies |
|---|---|
| `test_snapshot_all_signals_high_confidence` | DataFrame with return + vol + sharpe + asset_class + sector + upside + 52w scores ≥ 0.85 |
| `test_snapshot_minimum_signals` | DataFrame with return + vol + sharpe (only) scores ≥ 0.65 → activates |
| `test_snapshot_below_threshold` | DataFrame with return column only scores < 0.65 → generic_tabular |
| `test_timeseries_detected_by_ohlc_and_date` | OHLC + datetime column → financial_markets_timeseries |
| `test_timeseries_does_not_activate_domain_pack` | financial_markets_timeseries context → run_domain_pack returns empty list |
| `test_generic_tabular_no_signals` | Demographics DataFrame → generic_tabular, confidence = 1.0 |
| `test_no_false_positive_churn_dataset` | tenure + churned + customer_id → generic_tabular (not snapshot) |
| `test_deterministic` | Same DataFrame called twice → identical DatasetContext |
| `test_empty_dataframe` | Empty df → generic_tabular, no raise |
| `test_single_column` | df with one column → generic_tabular, no raise |
| `test_mixed_asset_class_warning` | asset_class column with 3 distinct values → warning in DatasetContext.warnings |
| `test_matched_signals_human_readable` | All matched_signals are non-empty strings |

**Semantic role tests:**

| Test | What it verifies |
|---|---|
| `test_roles_return_period_assigned` | ytd_return, one_year_return → role "return_period" |
| `test_roles_asset_id_assigned` | ticker, symbol → role "asset_id" |
| `test_roles_unknown_for_novel_column` | "widget_count" → role "unknown" |
| `test_roles_complete_no_missing_columns` | Every column in df appears in returned roles dict |

### 7.2 `tests/test_snapshot_finance_pack.py`

| Test | What it verifies |
|---|---|
| `test_return_leaders_detected` | Top-return assets appear in leaders insight, names correct |
| `test_return_laggards_detected` | Bottom-return assets appear in laggards insight |
| `test_volatility_leaders_vs_median` | Assets with vol > 1.5× median appear in volatility insight |
| `test_sharpe_leaders_ranking` | Top Sharpe assets appear, ranked correctly |
| `test_asset_class_comparison_multi_class` | Insight produced when ≥ 2 asset classes present |
| `test_asset_class_comparison_single_class` | No asset_class insight when only 1 class present |
| `test_sector_comparison_multi_sector` | Insight produced when ≥ 2 sectors present, best/worst named |
| `test_analyst_upside_top10` | Top-upside assets named in insight; missing upside column → no insight |
| `test_52w_position_distribution` | Insight produced; pct near high/low reported in evidence |
| `test_pack_returns_list_always` | run() always returns list, never raises |
| `test_pack_empty_dataframe` | Empty df → empty list, no raise |
| `test_all_insights_have_required_fields` | Every returned dict has type, title, finding, severity, confidence, evidence, action |
| `test_mixed_asset_caveat_in_warnings` | Mixed-asset df → DatasetContext.warnings contains caveat string |

### 7.3 `tests/test_domain_ranking.py`

| Test | What it verifies |
|---|---|
| `test_return_period_correlation_suppressed` | Correlation between two return_period columns removed by suppression |
| `test_composite_score_correlation_suppressed` | Correlation involving composite_score column removed |
| `test_asset_id_insight_suppressed` | Insight with asset_id as primary column removed |
| `test_trend_insight_suppressed_on_snapshot` | Trend insight suppressed when dataset_type = financial_markets_snapshot |
| `test_non_suppressed_insight_survives` | Sharpe-return correlation (mixed roles) is NOT suppressed |
| `test_suppression_does_not_affect_generic_path` | generic_tabular context → no suppression applied |
| `test_rank_insights_signature_unchanged` | rank_insights(insights) with no extra args works as before |

### 7.4 Integration Tests

| Test | File | What it verifies |
|---|---|---|
| `test_analyze_dataset_snapshot_end_to_end` | `test_dataset_context.py` | Yahoo snapshot df → no return-return correlations in output, ≥ 1 domain insight |
| `test_analyze_dataset_generic_unchanged` | `test_dataset_context.py` | Non-domain df → output identical to pre-change baseline |
| `test_chart_strategy_snapshot` | `test_dataset_context.py` | Snapshot df → top-returns bar chart present; no ticker-name bar chart |
| `test_chart_strategy_risk_return_scatter` | `test_dataset_context.py` | Snapshot with vol + return + asset_class → risk/return scatter in output |
| `test_narrative_snapshot_leads_with_performance` | `test_dataset_context.py` | Snapshot narrative paragraph 2 mentions return leaders/laggards |
| `test_insight_result_has_domain_caveats` | `test_dataset_context.py` | InsightResult on mixed-asset snapshot has mixed-asset caveat in .caveats |
| `test_regression_all_existing_tests_pass` | (run existing suite) | All pre-existing tests pass, zero changes required |

---

## 8. Acceptance Criteria

### 8.1 Detection Accuracy

- A Yahoo global markets snapshot with ytd_return, volatility, sharpe_ratio, asset_class, sector, analyst_upside, and week_52_position columns must score `confidence ≥ 0.85` and `dataset_type = "financial_markets_snapshot"`.
- A snapshot with only ytd_return, volatility, and sharpe_ratio (minimum) must score `confidence ≥ 0.65`.
- A dataset with one return column and nothing else must score `confidence < 0.65` → `generic_tabular`.
- An OHLC dataset with a datetime column must classify as `financial_markets_timeseries`, not `financial_markets_snapshot`.
- A customer churn dataset (tenure, churned, plan, monthly_charges) must not false-positive as any financial type.
- An empty DataFrame must produce `generic_tabular` without raising.

### 8.2 Insight Pack Output

- On a canonical Yahoo snapshot, at least 5 of the 8 domain detectors must produce at least one insight.
- Every domain insight dict must contain: `type`, `title`, `finding`, `severity`, `confidence`, `evidence`, `action`.
- `confidence` values must be in [0, 100] (pipeline convention; adapter divides by 100).
- On a single-asset-class snapshot, `_detect_asset_class_comparison` must return an empty list (no false comparison).
- On a snapshot with no `analyst_upside` column, `_detect_analyst_upside` must return an empty list (no crash).

### 8.3 Suppression Correctness

- On a canonical Yahoo snapshot, zero `"correlation"` insights with both `columns_used` values having role `return_period` must appear in the final ranked output.
- On a snapshot, zero `"trend"` insights must appear (no datetime column).
- On a snapshot, zero insights whose `columns_used[0]` has role `asset_id` must appear.
- On a generic dataset, the count of correlation insights is identical before and after the domain intelligence layer.

### 8.4 Charts

- On a canonical Yahoo snapshot, the output of `build_chart_data()` must include a horizontal bar chart (top 10 returns) and a scatter chart (risk vs. return).
- On a canonical Yahoo snapshot, the output must NOT include a scatter chart where both axes are `return_period` columns.
- On a generic dataset, `build_chart_data()` output is identical before and after.

### 8.5 Backward Compatibility (Non-Negotiable)

- All existing tests pass with zero modifications.
- `analyze_dataset(df)`, `build_chart_data(df)`, `generate_narrative(insights, df)`, and `build_insight_result(ins)` remain callable with their existing positional-only argument shapes.
- `InsightResult` gains no new required fields in V1.

### 8.6 Performance

- `detect_dataset_context(df)` completes in < 200ms on a 1M-row, 50-column DataFrame.
- Snapshot domain pack completes in < 3 seconds on 10,000-row snapshot (typical Yahoo global snapshot size).
- Full `analyze_dataset()` on a snapshot must not increase total latency by more than 5 seconds over baseline.

### 8.7 Test Coverage

- All new files in `dataset_context/` and `analysis/domain/` must have ≥ 90% line coverage.
- No new file introduced with zero tests.

---

## 9. Rollout Strategy

### 9.1 Principles

1. **Generic analysis never regresses.** `generic_tabular` runs the current unchanged `analyze_dataset()`. Any regression in the generic path is a bug, not an acceptable trade-off.
2. **Confidence gate is strict.** The domain pack activates only at confidence ≥ 0.65. Below this, behaviour is identical to today.
3. **Timeseries detected but deferred in V1.** `financial_markets_timeseries` is classified and the classification is surfaced to the user (via `dataset_summary.domain_context`), but the domain pack is not activated. The user knows we detected it; they get a note that OHLC-specific analysis is coming.
4. **Domain insights augment generic insights.** Domain pack insights are prepended; generic detectors still run. Suppression removes only structurally meaningless generic output, not all generic output.
5. **Matched signals are always visible.** `DatasetContext.matched_signals` and `.warnings` appear in the `dataset_summary` API response, making every classification auditable.

### 9.2 Kill Switch

A single boolean `ENABLE_DATASET_INTELLIGENCE = True` in `apps/api/app/config.py` allows instant rollback. When `False`, `detect_dataset_context()` returns `generic_tabular` immediately. No other file changes needed.

### 9.3 Phased Deployment

**Phase 0 — Inert deploy (no user-visible change):**  
Deploy all new code with `CONFIDENCE_THRESHOLD = 1.01` (impossible to reach). Monitor for exceptions for several days.

**Phase 1 — Suppression only (V1C):**  
Lower threshold to 0.65. Activate suppression rules for snapshot datasets only. Domain pack insights not yet shown. Effect: Yahoo snapshot users stop seeing trivial return correlations. Generic users see no change.

**Phase 2 — Full V1 (V1A through V1E):**  
Enable domain pack insights, domain charts, and domain narrative. Monitor user feedback. Watch for false-positive snapshot detections on non-financial data.

**Phase 3 — V1.5:**  
Activate `financial_markets_timeseries` domain pack (OHLC detectors, trading gap detection, volatility regime).

**Phase 4 — V2:**  
Add `customer_churn` and `insurance` domain packs using the registry pattern already in place.

---

## 10. Implementation Checklist

Steps are ordered by dependency. Steps within the same group can be parallelised.

### Group A — Schema and Signal Definitions

- [ ] **A1.** Create `dataset_context/schema.py` — `DatasetContext` frozen dataclass, `CONFIDENCE_THRESHOLD`, `DATASET_TYPE` literals.
- [ ] **A2.** Create `dataset_context/signals.py` — all `frozenset` name lists for each semantic role; `_normalise_col()` helper.
- [ ] **A3.** Write unit tests for `_normalise_col()` and every frozenset membership check.

### Group B — Detector and Role Resolver (depends on A)

- [ ] **B1.** Create `dataset_context/detector.py` — `_has_datetime_column()`, `_score_snapshot()`, `_score_timeseries()`, `detect_dataset_context()`.
- [ ] **B2.** Create `dataset_context/roles.py` — `_roles_snapshot()`, `_roles_generic()`, `resolve_semantic_roles()`.
- [ ] **B3.** Create `dataset_context/__init__.py` — exports.
- [ ] **B4.** Write unit tests: detection accuracy tests (§7.1 detector tests), semantic role tests (§7.1 role tests).

### Group C — Domain Pack Infrastructure (depends on B)

- [ ] **C1.** Create `analysis/domain/base.py` — abstract `DomainInsightPack` with `run()` and `suppression_keys()`.
- [ ] **C2.** Create `analysis/domain/registry.py` — `DOMAIN_PACKS` dict, `get_domain_pack()`.
- [ ] **C3.** Create `analysis/domain/__init__.py` — `run_domain_pack(df, ctx)` dispatcher.

### Group D — Snapshot Finance Pack (depends on B, C)

- [ ] **D1.** Create `analysis/domain/snapshot_finance.py` — implement all 8 detectors.
- [ ] **D2.** Register `SnapshotFinanceInsightPack` in `registry.py`.
- [ ] **D3.** Write unit tests for all 8 detectors (§7.2).

### Group E — Ranking with Suppression (depends on B, D)

- [ ] **E1.** Modify `analysis/ranking.py` — add `suppression_keys` parameter to `rank_insights()`.
- [ ] **E2.** Implement suppression key sets in `snapshot_finance.py` (`suppression_keys()` method).
- [ ] **E3.** Write unit tests for suppression (§7.3).

### Group F — Orchestrator Integration (depends on B, D, E)

- [ ] **F1.** Modify `analysis/orchestrator.py` — add optional `ctx` parameter; insert domain pack call and suppression.
- [ ] **F2.** Write integration tests: snapshot end-to-end, generic unchanged baseline (§7.4).

### Group G — Adapter, Charts, Narrative (depends on B; parallel with F)

- [ ] **G1.** Modify `insight_adapter.py` — add `dataset_context` parameter; domain caveat lookup table; mixed-asset caveat injection.
- [ ] **G2.** Modify `charting/orchestrator.py` — add `dataset_context` parameter; implement 5 domain charts; apply suppression list.
- [ ] **G3.** Modify `analysis/narrative.py` — add `dataset_context` parameter; implement 3-paragraph finance narrative template.
- [ ] **G4.** Write integration tests: chart strategy (§7.4 chart tests), narrative content, adapter caveats.

### Group H — Validation

- [ ] **H1.** Run full existing test suite. Assert zero regressions.
- [ ] **H2.** Benchmark: `detect_dataset_context()` < 200ms on 1M-row DataFrame.
- [ ] **H3.** Benchmark: full `analyze_dataset()` on 10k-row snapshot < baseline + 5s.
- [ ] **H4.** Code review: verify all new parameters are optional with safe defaults; no caller broken.

### Group I — Deployment

- [ ] **I1.** Deploy Phase 0 (threshold = 1.01). Monitor.
- [ ] **I2.** Deploy Phase 1 (suppression only). Monitor insight distribution.
- [ ] **I3.** Deploy Phase 2 (full V1). Monitor for false positives and user feedback.
- [ ] **I4.** Begin V1.5 planning (timeseries pack).

---

## Appendix A: Key Invariants

1. `DatasetContext` is **immutable** (frozen dataclass). Passed through the pipeline without modification.
2. `semantic_roles` covers every column. No column is absent. Unknown → `"unknown"`, never `None`.
3. `detect_dataset_context()` **never raises**. Exceptions are caught; failure returns `generic_tabular` with a warning.
4. Domain pack detectors **never raise to the caller**. Each wraps in try/except; returns empty list on failure.
5. `financial_markets_timeseries` in V1 **always falls through to generic**. Detection fires, domain pack does not.
6. Suppression is applied **before ranking**, not after. Suppressed insights are gone, not merely demoted.
7. The `generic_tabular` fallback path is **the unchanged current code**. Any regression there is a bug.

---

## Appendix B: Scope Boundaries

### In V1

- `financial_markets_snapshot` detection and full domain pack
- `financial_markets_timeseries` detection (stub only, no pack)
- 8 snapshot insight detectors
- 5 domain charts
- Finance executive summary narrative
- Domain caveats in InsightResult
- Ranking suppression for structural correlations, composite scores, ID columns, fake trends

### In V1.5

- `financial_markets_timeseries` full domain pack (OHLC detectors, volatility regime, gap detection, momentum, volume-price divergence)

### In V2

- `customer_churn` domain pack
- `insurance` domain pack

### Never in scope

- LLM-based column name inference
- Real-time / streaming data
- Frontend UI changes (domain label surfaced via existing `dataset_summary` field only)
- Per-asset panel analysis for multi-ticker timeseries
- Backtest or strategy analysis
