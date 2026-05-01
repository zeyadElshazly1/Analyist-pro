# Dataset Intelligence Plan — Analyst Pro

**Status:** Pre-implementation planning document  
**Author:** Senior Data Platform Architect  
**Date:** 2026-05-01  
**Scope:** v1 — financial_markets domain only  

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

The current `analyze_dataset()` pipeline in `orchestrator.py` treats every DataFrame identically. It fires every detector — correlations, anomalies, segments, trends — regardless of what the data actually represents. On a financial markets dataset, this produces findings like:

- "Strong correlation: open & close (r=0.99)" — statistically true, analytically worthless. Of course open and close prices correlate; any financial analyst knows this is a structural property of OHLC data, not an insight.
- "Strong correlation: high & low (r=0.97)" — same problem.
- "Skewed distribution: volume" — volume is always right-skewed in markets. Flagging it as a finding wastes the user's attention.
- "Concentration risk in ticker" — a ticker column with 500 stocks will always look concentrated; this is not risk, it is cardinality.

The ranking function `rank_insights()` in `ranking.py` scores insights by statistical severity (65%) and confidence (35%). It has no concept of domain relevance. A generic high-confidence correlation between two price columns will always outrank a low-confidence but genuinely important cross-asset leading indicator. The user sees noise first.

### 1.2 Charts Are Misleading Without Domain Context

The chart builder (`charting/orchestrator.py`) generates charts in a fixed priority order:

1. Time-series line charts
2. Histograms
3. Correlation heatmap
4. Boxplots
5. Categorical bars
6. Scatter plots

For financial markets data, the scatter plot of `open` vs `close` will rank highly because `_pearson()` returns r≈0.99. This chart will appear prominently in the report despite communicating nothing. Meanwhile, the chart that actually matters — cumulative return over time, drawdown, rolling volatility — will never be built because those computed series are not in the raw DataFrame and the chart builder has no domain awareness.

The same heatmap showing perfect correlation between all OHLC columns actively misleads: a user unfamiliar with finance might conclude the dataset is redundant and drop columns that are structurally necessary.

### 1.3 Reports Are Weak Without Domain Context

`generate_narrative()` in `narrative.py` and `_detect_domain()` perform a simple keyword scan over column names and produce a generic 3-paragraph executive summary. `_detect_domain()` can detect "Finance / Sales" from the word "price" but does nothing with that label — it is returned in `get_dataset_summary()` and never used to alter the narrative or insight selection.

`insight_adapter.py` assigns the same `caveats`, `chart_suggestion`, and `method_used` to every insight of a given category regardless of domain. A "correlation" insight on a financial dataset gets the same caveat ("Correlation does not imply causation") as one on a survey dataset, even though the financial context warrants "OHLC price columns are structurally correlated by market microstructure; exclude from general correlation analysis."

The report builder consumes `InsightResult` objects filtered by `report_safe=True`. With no domain awareness, the report for a financial dataset will be littered with trivially-true OHLC correlations and miss the genuinely actionable signals: volatility clustering, momentum effects, volume-price divergence.

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
┌─────────────────────────────────┐
│  dataset_context.detector       │  ← NEW
│  detect_dataset_context(df)     │
│  → DatasetContext               │
└─────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────┐
│  dataset_context.roles          │  ← NEW
│  resolve_semantic_roles(df,ctx) │
│  → SemanticRoles                │
└─────────────────────────────────┘
        │
        ├─── confidence >= threshold?
        │         YES                        NO
        ▼                                    ▼
┌──────────────────────┐       ┌──────────────────────────┐
│  Domain Insight Pack  │       │  Generic orchestrator    │
│  (e.g. financial_     │       │  (current analyze_       │
│   markets pack)       │       │   dataset() unchanged)   │
└──────────────────────┘       └──────────────────────────┘
        │                                    │
        └────────────────┬───────────────────┘
                         ▼
             ┌─────────────────────┐
             │  Domain-aware        │
             │  rank_insights()     │  ← MODIFIED
             │  + suppression rules │
             └─────────────────────┘
                         │
                         ▼
             ┌─────────────────────┐
             │  insight_adapter.py │  ← MODIFIED
             │  domain context      │
             │  injected into       │
             │  caveats/charts/     │
             │  chart_suggestion    │
             └─────────────────────┘
                         │
                         ▼
             ┌─────────────────────┐
             │  Domain chart        │  ← MODIFIED
             │  strategy            │
             │  build_chart_data()  │
             └─────────────────────┘
                         │
                         ▼
             ┌─────────────────────┐
             │  Domain narrative    │  ← MODIFIED
             │  generate_narrative()│
             └─────────────────────┘
                         │
                         ▼
             canonical InsightResult list
             + domain-aware charts
             + domain narrative
             → frontend / report builder
```

### 2.2 Integration Points

The domain-awareness layer is injected at **five** touch points in the existing stack. No existing public API signatures change in v1.

| Touch Point | Current Behaviour | New Behaviour |
|---|---|---|
| `orchestrator.analyze_dataset(df)` | Always runs all detectors | If context confidence ≥ threshold, runs domain pack first, then optionally generic detectors for gap-fill |
| `ranking.rank_insights()` | Severity + confidence sort only | Domain boost/suppress weights applied before sort |
| `insight_adapter.build_insight_result()` | Category-only caveats/charts | Domain context passed in; domain-specific caveats and chart suggestions injected |
| `charting/orchestrator.build_chart_data()` | Fixed priority order | Domain strategy selects chart types and columns before generic builder runs |
| `narrative.generate_narrative()` | Generic 3-paragraph summary | Domain narrative template used when context confidence ≥ threshold |

---

## 3. DatasetContext Specification

### 3.1 Core Dataclass

```
DatasetContext
├── dataset_type: str
│     The detected domain label. One of the values defined in §4.
│     Default: "generic_tabular"
│
├── confidence: float  [0.0 – 1.0]
│     How confident the detector is in the dataset_type assignment.
│     Computed as: sum(signal_weights_matched) / sum(all_signal_weights_for_type)
│     Threshold for activating domain pack: 0.65 (configurable constant)
│
├── matched_signals: list[str]
│     Human-readable list of the signals that contributed to this detection.
│     Example for financial_markets:
│       ["OHLC column group detected (open, high, low, close)",
│        "volume column detected",
│        "date column with trading-day frequency detected",
│        "ticker/symbol column detected"]
│     Used in: UI debug panel, test assertions, warnings generation
│
├── semantic_roles: dict[str, str]
│     Maps each column name to its semantic role within the detected domain.
│     Key = column name. Value = role label (domain-specific vocabulary).
│     Example for financial_markets:
│       {"date":   "time_index",
│        "open":   "ohlc_open",
│        "high":   "ohlc_high",
│        "low":    "ohlc_low",
│        "close":  "ohlc_close",
│        "volume": "volume",
│        "ticker": "asset_id",
│        "rsi_14": "technical_indicator"}
│     Unmapped columns: role = "unknown"
│     Used in: domain pack selector, chart strategy, narrative, suppression rules
│
└── warnings: list[str]
      Non-fatal issues detected during context resolution that the user
      should know about, but that do not block analysis.
      Examples:
        "open > high detected in 3 rows — possible data quality issue"
        "Missing trading days detected — weekend gaps expected, others may be errors"
        "Ticker column has 500 unique values — per-asset analysis may be slow"
      Used in: report header, narrative paragraph 1
```

### 3.2 Detection Logic (Deterministic, No ML)

Detection is a **signal scoring system** — no machine learning, no LLM calls. Each dataset type has a weighted signal checklist. Signals are deterministic column-name pattern matches, dtype checks, value range checks, and structural checks.

**Why deterministic?**  
- Reproducible: same DataFrame always produces same DatasetContext.
- Testable: each signal can be unit tested in isolation.
- Fast: no model load time, no external API call.
- Auditable: `matched_signals` tells the user exactly what fired.

**Signal types:**
1. **Column name patterns** — regex or keyword match on normalised column names (lowercased, stripped)
2. **Column group patterns** — a set of columns that must co-occur (e.g. `{open, high, low, close}`)
3. **Dtype signals** — e.g. datetime column present
4. **Value range signals** — e.g. values between 0 and 1 suggest rate/probability columns
5. **Frequency signals** — e.g. date column with 5-day-week gaps suggests trading data
6. **Cardinality signals** — e.g. a low-cardinality string column in the presence of OHLC suggests `ticker`

### 3.3 Confidence Calculation

```
For each dataset_type T:
  signal_scores = [weight_i for each signal_i that fires]
  max_possible  = sum(weight_i for all signals_i defined for T)
  confidence(T) = sum(signal_scores) / max_possible

Assigned dataset_type = argmax(confidence(T)) across all T
If max confidence < 0.65 → dataset_type = "generic_tabular", confidence = 1.0
```

Confidence is **not** a probability — it is a normalised match score. A confidence of 0.65 means 65% of the maximum possible signal weight was matched, not that there is a 65% probability of correct classification.

---

## 4. Supported Dataset Types

### 4.1 V1 Scope: `financial_markets`

Full domain pack implemented. All other types below are planned for future versions.

**Detection signals (weighted):**

| Signal | Weight | Description |
|---|---|---|
| OHLC group present | 0.40 | Columns matching open/high/low/close as a co-occurring group |
| Volume column | 0.20 | Column name contains volume, vol, traded |
| Date column with trading frequency | 0.15 | Datetime column; median gap = 1 day, ~5-day week pattern |
| Ticker / symbol column | 0.15 | Low-cardinality string column with names or uppercase codes |
| Price-like numeric range | 0.05 | Numeric columns with values > 1 and right-skewed |
| Return / pct_change column | 0.05 | Column name contains return, ret, pct_chg, change |

Maximum possible confidence = 1.00 (all signals fire). Threshold for activation = 0.65.

**Semantic roles defined for `financial_markets`:**

| Role Label | Description | Example Columns |
|---|---|---|
| `time_index` | The primary date/time axis | date, timestamp, trading_date |
| `asset_id` | Identifier for the financial instrument | ticker, symbol, isin, cusip |
| `ohlc_open` | Opening price | open, open_price |
| `ohlc_high` | Session high price | high, high_price |
| `ohlc_low` | Session low price | low, low_price |
| `ohlc_close` | Closing / settlement price | close, close_price, adj_close |
| `volume` | Trade volume | volume, vol, shares_traded |
| `returns` | Period return | returns, daily_return, ret, pct_change |
| `technical_indicator` | Computed TA signal | rsi, macd, sma, ema, bb_upper, atr |
| `fundamental` | Fundamental ratio | pe_ratio, eps, pb_ratio, roe |
| `unknown` | Not mapped to any role | anything else |

**Insight pack for `financial_markets`:** (detectors to implement)

| Insight | Detector | Priority |
|---|---|---|
| Volatility regime detection | Rolling std-dev on `ohlc_close` or `returns` with change-point detection | HIGH |
| Volume-price divergence | Correlation sign-flip between `volume` and `returns` over rolling windows | HIGH |
| Return distribution fat-tails | Kurtosis + Jarque-Bera on `returns` column | HIGH |
| OHLC integrity check | Validate open ≤ high, low ≤ close, low ≤ high for every row | HIGH |
| Momentum signal | Autocorrelation of `returns` at lag 1–5 | MEDIUM |
| Cross-asset correlation | Pearson on `returns` across tickers (panel aware) | MEDIUM |
| Gap detection | Missing trading days beyond expected weekend/holiday gaps | MEDIUM |
| Outlier session detection | Single-day returns beyond ±3σ with volume confirmation | MEDIUM |

**Suppression rules for `financial_markets`:**

| Suppressed Insight | Reason |
|---|---|
| Correlation between any two `ohlc_*` columns | Structurally correlated by microstructure; not actionable |
| "Skewed distribution" on `volume` | Volume is always right-skewed; not a finding |
| "Concentration risk" on `asset_id` | Ticker cardinality is schema design, not risk |
| "High-cardinality column" on `asset_id` | Same reason |
| Correlations where both columns have role `technical_indicator` | TA indicators are derived from the same price series; correlation is spurious |

---

### 4.2 Future: `customer_churn` (v2+)

**Detection signals:** churned/churn column, tenure/days_since column, customer_id, subscription/plan columns, event counts.

**Key insight pack:** churn rate by segment, tenure-survival curve, feature importance for churn prediction, cohort retention heatmap.

**Suppression:** correlations between derived RFM columns (recency/frequency/monetary are definitionally related).

---

### 4.3 Future: `insurance` (v2+)

**Detection signals:** claim_amount column, policy_id, premium, exposure, loss_ratio, peril/cause columns.

**Key insight pack:** loss ratio by segment, claim frequency vs severity trade-off, large-loss concentration (Pareto on claim_amount), geographic cluster risk.

**Suppression:** correlations between premium and sum_insured (actuarially set relationship, not a discovery).

---

### 4.4 Fallback: `generic_tabular`

**Trigger:** No domain type reaches confidence ≥ 0.65.

**Behaviour:** Current `analyze_dataset()` runs unchanged. No domain pack. No suppression. `DatasetContext` is constructed with `dataset_type="generic_tabular"`, `confidence=1.0`, empty `matched_signals`, all columns with role `"unknown"`.

This is the **zero-regression guarantee**: existing users uploading non-domain datasets see exactly the same output as today.

---

## 5. V1 Implementation Scope

V1 ships exactly one domain: `financial_markets`. Everything else is groundwork that makes adding v2 domains cheap.

**V1 deliverables:**

1. `DatasetContext` dataclass + `detect_dataset_context(df)` function
2. `SemanticRoles` resolver for `financial_markets`
3. `financial_markets` insight pack (5 detectors: volatility regime, volume-price divergence, return fat-tails, OHLC integrity, gap detection)
4. Suppression rules applied in ranking
5. Domain-aware chart strategy for `financial_markets` (price chart, returns distribution, rolling volatility)
6. Domain narrative template for `financial_markets`
7. Domain caveats injected into `InsightResult` via adapter
8. Full test suite (unit + integration)

**V1 explicitly excludes:**

- LLM-based column name inference (pure regex/keyword detection only)
- Customer churn, insurance, or any other domain pack
- Frontend UI changes (the domain label may appear in `dataset_summary` but no new UI components)
- Per-asset (multi-ticker panel) analysis — v1 treats multi-ticker data as a single series
- Backtest / strategy analysis
- Real-time / streaming data

---

## 6. Files to Create and Change

### 6.1 New Files (create from scratch)

```
apps/api/app/services/
└── dataset_context/
    ├── __init__.py
    │     Exports: DatasetContext, detect_dataset_context, resolve_semantic_roles
    │
    ├── schema.py
    │     DatasetContext dataclass (frozen, hashable)
    │     SemanticRoles type alias (dict[str, str])
    │     DATASET_TYPE literals and constants
    │     CONFIDENCE_THRESHOLD constant (0.65)
    │
    ├── detector.py
    │     detect_dataset_context(df: DataFrame) -> DatasetContext
    │     _score_financial_markets(df) -> float, list[str]
    │     _score_customer_churn(df) -> float, list[str]   [stub, always 0.0]
    │     _score_insurance(df) -> float, list[str]        [stub, always 0.0]
    │     _normalise_col_name(col: str) -> str            [lowercase, strip, remove _]
    │
    ├── roles.py
    │     resolve_semantic_roles(df, ctx) -> dict[str, str]
    │     _roles_financial_markets(df) -> dict[str, str]
    │     _roles_generic(df) -> dict[str, str]            [all "unknown"]
    │
    └── signals.py
          OHLC_NAMES: frozenset[str]       [open, high, low, close variants]
          VOLUME_NAMES: frozenset[str]
          TICKER_NAMES: frozenset[str]
          RETURN_NAMES: frozenset[str]
          _is_ohlc_group(cols) -> bool
          _is_trading_frequency(series) -> bool
          _is_ticker_column(series) -> bool

apps/api/app/services/analysis/
└── domain/
    ├── __init__.py
    │     Exports: run_domain_pack
    │
    ├── base.py
    │     Abstract base: DomainInsightPack
    │     run(df, roles) -> list[dict]
    │
    ├── financial_markets.py
    │     FinancialMarketsInsightPack(DomainInsightPack)
    │     Detectors:
    │       _detect_volatility_regime(df, roles)
    │       _detect_volume_price_divergence(df, roles)
    │       _detect_return_fat_tails(df, roles)
    │       _detect_ohlc_integrity(df, roles)
    │       _detect_trading_gaps(df, roles)
    │
    └── registry.py
          DOMAIN_PACKS: dict[str, type[DomainInsightPack]]
          get_domain_pack(dataset_type) -> DomainInsightPack | None

apps/api/tests/
    ├── test_dataset_context.py      [new]
    ├── test_financial_markets_pack.py   [new]
    └── test_domain_ranking.py           [new]
```

### 6.2 Files to Modify (existing files, targeted changes)

```
apps/api/app/services/analysis/orchestrator.py
  CHANGE: analyze_dataset(df) gains an optional ctx parameter.
          If ctx is None, detect_dataset_context(df) is called internally.
          If ctx.confidence >= CONFIDENCE_THRESHOLD and a domain pack exists,
          domain pack insights are prepended to the insight list and suppression
          rules are registered before ranking.
          Existing detector calls are unchanged.
  RISK: Low. The ctx parameter is optional with a None default — all existing
        callers continue to work with zero changes.

apps/api/app/services/analysis/ranking.py
  CHANGE: rank_insights() gains an optional suppression_keys parameter.
          suppression_keys: set[tuple] = set()   (same key shape as _insight_key)
          Insights whose key is in suppression_keys are removed before ranking.
          Domain packs pass their suppression key sets through here.
  RISK: Low. Parameter is optional; existing callers unaffected.

apps/api/app/services/insight_adapter.py
  CHANGE: build_insight_result() gains an optional dataset_context parameter.
          When present and dataset_type == "financial_markets":
            - caveats list gets domain-specific additions
            - chart_suggestion may be overridden by domain chart map
          When absent: current behaviour unchanged.
  RISK: Low. Parameter is optional.

apps/api/app/services/charting/orchestrator.py
  CHANGE: build_chart_data() gains an optional dataset_context parameter.
          When present and dataset_type == "financial_markets":
            - Domain chart strategy runs first (price timeseries, returns distribution,
              rolling volatility chart)
            - Scatter plots of ohlc_* vs ohlc_* columns are skipped
            - Heatmap is suppressed if all numeric columns are ohlc_* (prevents
              the misleading all-green OHLC heatmap)
          When absent: current behaviour unchanged.
  RISK: Low. Parameter is optional.

apps/api/app/services/analysis/narrative.py
  CHANGE: generate_narrative() gains an optional dataset_context parameter.
          When present and dataset_type == "financial_markets":
            - Paragraph 1: mentions the financial domain and the OHLC structure detected
            - Paragraph 2: leads with return-distribution and volatility findings
              rather than correlation findings
            - Paragraph 3: includes financial-context actions
          When absent: current 3-paragraph generic narrative unchanged.
  RISK: Low. Parameter is optional.

apps/api/app/services/analyzer.py
  CHANGE: The thin wrapper calling orchestrator.analyze_dataset() passes
          dataset_context through if it is already computed upstream (e.g. from
          a prior profiling step). No change to public API.
  RISK: Minimal.
```

### 6.3 Files Explicitly Not Changed in V1

```
apps/api/app/schemas/insight.py         ← InsightResult schema unchanged
apps/api/app/routes/analysis.py         ← Route unchanged
apps/api/app/services/cleaning/         ← Cleaning pipeline unchanged
apps/api/app/services/charting/payloads.py  ← Payload builders unchanged
apps/api/app/services/reporting/        ← Report templates unchanged in v1
```

---

## 7. Tests Required

### 7.1 Unit Tests: `tests/test_dataset_context.py`

| Test | What it verifies |
|---|---|
| `test_ohlc_group_detection` | `_is_ohlc_group()` returns True for [open, high, low, close] and variants; False for partial groups |
| `test_trading_frequency_detection` | `_is_trading_frequency()` returns True for daily 5-day-week series; False for monthly or hourly |
| `test_ticker_column_detection` | `_is_ticker_column()` returns True for a low-cardinality uppercase string column; False for free-text |
| `test_full_ohlc_dataset_confidence` | A DataFrame with all 6 signals scores confidence ≥ 0.90 |
| `test_partial_ohlc_confidence` | A DataFrame with OHLC + volume but no ticker scores confidence in [0.65, 0.90) |
| `test_non_financial_dataset` | A customer demographics DataFrame scores confidence < 0.65 → dataset_type = "generic_tabular" |
| `test_semantic_roles_complete` | resolve_semantic_roles() assigns correct role to every column in a reference OHLC dataset |
| `test_semantic_roles_unknown_columns` | Novel columns not in signal lists get role "unknown" |
| `test_matched_signals_are_human_readable` | matched_signals list contains only non-empty strings |
| `test_warnings_ohlc_integrity` | A DataFrame with open > high on some rows produces a DatasetContext warning |
| `test_deterministic` | Calling detect_dataset_context() twice on same df produces identical DatasetContext |
| `test_confidence_threshold_boundary` | A dataset at exactly 0.65 confidence activates the domain pack; at 0.64 it does not |

### 7.2 Unit Tests: `tests/test_financial_markets_pack.py`

| Test | What it verifies |
|---|---|
| `test_volatility_regime_detected` | A DataFrame with two distinct volatility regimes produces a "volatility_regime" insight |
| `test_volatility_regime_single_regime` | A stable-volatility DataFrame produces no regime insight |
| `test_volume_price_divergence_detected` | A DataFrame where volume rises while returns fall produces a divergence insight |
| `test_return_fat_tails_kurtosis` | A returns series with kurtosis > 3 produces a fat-tail insight |
| `test_return_fat_tails_normal` | A normally distributed returns series produces no fat-tail insight |
| `test_ohlc_integrity_violation` | A row with open > high produces an integrity-violation insight at severity="high" |
| `test_ohlc_integrity_clean` | A clean OHLC DataFrame produces no integrity insight |
| `test_gap_detection_missing_days` | A DataFrame with a 5-day gap mid-series (non-holiday) produces a gap insight |
| `test_gap_detection_weekend_ok` | Weekend gaps are not flagged as missing trading days |
| `test_domain_pack_returns_list` | `FinancialMarketsInsightPack.run()` always returns a list (never raises) |
| `test_domain_pack_empty_df` | An empty DataFrame returns an empty insight list without error |

### 7.3 Unit Tests: `tests/test_domain_ranking.py`

| Test | What it verifies |
|---|---|
| `test_ohlc_correlation_suppressed` | A correlation insight between two ohlc_* columns is removed by suppression rules |
| `test_non_ohlc_correlation_not_suppressed` | A correlation between `volume` and `returns` is NOT suppressed |
| `test_domain_insight_ranks_above_generic` | A domain-pack insight with medium severity outranks a generic low-confidence correlation |
| `test_suppression_does_not_affect_generic_path` | When dataset_type = "generic_tabular", no suppression rules apply |
| `test_rank_insights_with_suppression_keys` | rank_insights() with a suppression_keys set removes those insights before sorting |

### 7.4 Integration Tests (added to existing test files or new)

| Test | File | What it verifies |
|---|---|---|
| `test_analyze_dataset_financial_ohlc` | `test_dataset_context.py` | End-to-end: OHLC DataFrame → `analyze_dataset()` → no OHLC-OHLC correlations in output |
| `test_analyze_dataset_generic_unchanged` | `test_dataset_context.py` | Non-domain DataFrame → output identical to current `analyze_dataset()` |
| `test_chart_strategy_no_ohlc_heatmap` | `test_dataset_context.py` | OHLC DataFrame → `build_chart_data()` → no all-OHLC heatmap in output |
| `test_narrative_mentions_domain` | `test_dataset_context.py` | OHLC DataFrame → `generate_narrative()` → narrative mentions financial context |
| `test_insight_adapter_domain_caveats` | `test_dataset_context.py` | InsightResult built with financial_markets context has domain caveats in `.caveats` |
| `test_regression_existing_tests_pass` | (run existing suite) | All pre-existing tests pass without modification |

---

## 8. Acceptance Criteria

### 8.1 Detection Accuracy

- A canonical OHLC dataset (date, open, high, low, close, volume, ticker) must score `confidence ≥ 0.85` and `dataset_type = "financial_markets"`.
- A canonical customer churn dataset (customer_id, tenure, churned, plan, monthly_charges) must score `confidence < 0.65` and `dataset_type = "generic_tabular"` (we have not implemented churn detection yet — it must not false-positive as financial).
- An empty DataFrame must produce `dataset_type = "generic_tabular"` without raising.
- A DataFrame with only 1 column must produce `dataset_type = "generic_tabular"` without raising.

### 8.2 Suppression Correctness

- On a standard OHLC dataset, zero insights of type "correlation" with both `columns_used` values having role `ohlc_*` must appear in the final output.
- On a generic dataset, the count of correlation insights in the output is identical before and after the domain intelligence layer is added.

### 8.3 Domain Pack Coverage

- On an OHLC dataset with a detectable volatility regime, at least one domain insight of type `"volatility_regime"` must appear in the output.
- On an OHLC dataset with a clean integrity check, zero `"ohlc_integrity"` insights must appear.
- On an OHLC dataset with a 5-day non-weekend gap, at least one `"trading_gap"` insight must appear.

### 8.4 Backward Compatibility (Non-Negotiable)

- All existing tests in `tests/` must pass with zero modifications.
- The public signatures of `analyze_dataset(df)`, `build_chart_data(df)`, `generate_narrative(insights, df)`, and `build_insight_result(ins)` must remain callable with their existing argument shapes (new parameters are all optional with safe defaults).
- The `InsightResult` Pydantic schema must not gain any new required fields.

### 8.5 Performance

- `detect_dataset_context(df)` must complete in under 200ms on a DataFrame with up to 1,000,000 rows and 50 columns (pure deterministic signal scoring — no pandas iterrows, no model inference).
- The domain pack detectors for `financial_markets` must complete in under 5 seconds on 500,000 rows.
- Total latency increase for the full `analyze_dataset()` pipeline on a financial dataset must be under 10 seconds versus the current baseline.

### 8.6 Test Coverage

- All new files in `dataset_context/` and `analysis/domain/` must have ≥ 90% line coverage.
- No new file may be introduced with zero tests.

---

## 9. Rollout Strategy

### 9.1 Principles

1. **Generic analysis never regresses.** The current `analyze_dataset()` path is the fallback for all non-domain data. It runs unchanged when `dataset_type = "generic_tabular"`.
2. **Domain insights augment; they do not replace.** In v1, domain pack insights are prepended to the insight list before generic insights run. Both contribute to the final ranked list. Domain suppression rules remove only structurally meaningless generic insights (OHLC-OHLC correlations), not the entire generic analysis.
3. **High-confidence activation only.** The domain pack activates only when `confidence ≥ 0.65`. Below this threshold, behaviour is identical to today. There is no "partial domain mode".
4. **Matched signals are always visible.** The `DatasetContext` object (including `matched_signals` and `warnings`) is attached to the `dataset_summary` response. This allows the analyst to understand why the domain pack fired or did not fire.

### 9.2 Flag-Based Activation (Optional Safety Valve)

If engineering requires a kill switch during initial rollout, a single boolean config flag `ENABLE_DATASET_INTELLIGENCE = True` can be added to `apps/api/app/config.py`. When `False`, `detect_dataset_context()` immediately returns `DatasetContext(dataset_type="generic_tabular", confidence=1.0, ...)` and the rest of the stack sees the generic path. This flag requires no code changes in any other file.

This flag is optional. If the test suite passes and performance benchmarks are met, the flag is not needed.

### 9.3 Phased Rollout

**Phase 0 — Foundation (no user-visible change)**  
Deploy `dataset_context/` module and `analysis/domain/` registry. `detect_dataset_context()` is called in `analyze_dataset()` but domain pack is not activated (threshold set to 1.01, impossible to reach). Run in production for one week; monitor for exceptions.

**Phase 1 — Financial Markets Suppression Only**  
Lower threshold to 0.65. Activate suppression rules for `financial_markets` datasets only. Domain pack insights not yet included. Effect: OHLC users stop seeing trivial correlations. Generic users see no change. Monitor insight-count distribution.

**Phase 2 — Financial Markets Domain Pack**  
Enable the `FinancialMarketsInsightPack` detector output. Domain insights appear in ranked output. Monitor for user feedback on false-positive domain detections.

**Phase 3 — Domain Chart Strategy and Narrative**  
Enable domain-aware chart builder and narrative. Complete the financial markets experience. Gather feedback.

**Phase 4 — V2 Planning**  
Begin signal definition for `customer_churn` and `insurance` based on Phase 1-3 learnings.

---

## 10. Implementation Checklist

Steps are ordered by dependency. Steps within the same group can be parallelised.

### Group A: Schema and Detection Foundation

- [ ] **A1.** Create `apps/api/app/services/dataset_context/schema.py`  
  Define `DatasetContext` dataclass, `CONFIDENCE_THRESHOLD = 0.65`, `DATASET_TYPES` literal, and `SemanticRoles` type alias.

- [ ] **A2.** Create `apps/api/app/services/dataset_context/signals.py`  
  Define `OHLC_NAMES`, `VOLUME_NAMES`, `TICKER_NAMES`, `RETURN_NAMES` frozensets. Implement `_normalise_col_name()`, `_is_ohlc_group()`, `_is_trading_frequency()`, `_is_ticker_column()`.

- [ ] **A3.** Write unit tests for all signal functions in `signals.py`  
  (Before writing detector — validates signal logic in isolation.)

### Group B: Detector and Role Resolver (depends on A)

- [ ] **B1.** Create `apps/api/app/services/dataset_context/detector.py`  
  Implement `_score_financial_markets(df)` using signals from A2. Implement stub scorers for churn and insurance (return 0.0). Implement `detect_dataset_context(df)`.

- [ ] **B2.** Create `apps/api/app/services/dataset_context/roles.py`  
  Implement `_roles_financial_markets(df)` mapping each column to its semantic role. Implement `_roles_generic(df)` (all "unknown"). Implement `resolve_semantic_roles(df, ctx)` dispatcher.

- [ ] **B3.** Create `apps/api/app/services/dataset_context/__init__.py`  
  Export `DatasetContext`, `detect_dataset_context`, `resolve_semantic_roles`.

- [ ] **B4.** Write unit tests for detector and role resolver (`test_dataset_context.py`, detection and roles sections).

### Group C: Domain Insight Pack (depends on B)

- [ ] **C1.** Create `apps/api/app/services/analysis/domain/base.py`  
  Define abstract `DomainInsightPack` with `run(df, roles) -> list[dict]`.

- [ ] **C2.** Create `apps/api/app/services/analysis/domain/financial_markets.py`  
  Implement all 5 detectors: volatility regime, volume-price divergence, return fat-tails, OHLC integrity, gap detection. Each returns a list of insight dicts conforming to the existing insight dict schema.

- [ ] **C3.** Create `apps/api/app/services/analysis/domain/registry.py`  
  Map `"financial_markets"` → `FinancialMarketsInsightPack`. Stubs for future types.

- [ ] **C4.** Create `apps/api/app/services/analysis/domain/__init__.py`  
  Export `run_domain_pack(df, ctx) -> list[dict]`.

- [ ] **C5.** Write unit tests for all domain pack detectors (`test_financial_markets_pack.py`).

### Group D: Ranking with Suppression (depends on B, C)

- [ ] **D1.** Modify `apps/api/app/services/analysis/ranking.py`  
  Add optional `suppression_keys: set[tuple] = None` parameter to `rank_insights()`. Apply suppression filter before ranking sort.

- [ ] **D2.** Define suppression key sets for `financial_markets` (in `financial_markets.py` or `registry.py`).  
  Include keys for all OHLC-OHLC correlation pairs and TA-TA correlations.

- [ ] **D3.** Write unit tests for ranking with suppression (`test_domain_ranking.py`).

### Group E: Orchestrator Integration (depends on B, C, D)

- [ ] **E1.** Modify `apps/api/app/services/analysis/orchestrator.py`  
  Add optional `ctx: DatasetContext | None = None` to `analyze_dataset()`. If ctx is None, call `detect_dataset_context(df)`. If `ctx.confidence >= CONFIDENCE_THRESHOLD` and domain pack exists, run domain pack, prepend insights, pass suppression keys to `rank_insights()`.

- [ ] **E2.** Write integration test: OHLC DataFrame → `analyze_dataset()` → assert no OHLC-OHLC correlations, assert domain insights present.

- [ ] **E3.** Write integration test: generic DataFrame → `analyze_dataset()` → assert output identical to pre-change baseline.

### Group F: Adapter, Charts, Narrative (depends on B; parallel with E)

- [ ] **F1.** Modify `apps/api/app/services/insight_adapter.py`  
  Add optional `dataset_context: DatasetContext | None = None` to `build_insight_result()`. Inject domain caveats and override `chart_suggestion` for financial_markets roles.

- [ ] **F2.** Modify `apps/api/app/services/charting/orchestrator.py`  
  Add optional `dataset_context: DatasetContext | None = None` to `build_chart_data()`. When financial_markets: skip OHLC-OHLC scatters; suppress all-OHLC heatmap; add price timeseries, returns distribution, rolling volatility charts.

- [ ] **F3.** Modify `apps/api/app/services/analysis/narrative.py`  
  Add optional `dataset_context: DatasetContext | None = None` to `generate_narrative()`. When financial_markets: use domain narrative template.

- [ ] **F4.** Write integration tests for F1, F2, F3 (adapter caveats, chart suppression, narrative domain mention).

### Group G: Validation and Cleanup

- [ ] **G1.** Run full existing test suite. Assert zero regressions.

- [ ] **G2.** Run performance benchmark: `detect_dataset_context()` on 1M-row DataFrame must complete < 200ms.

- [ ] **G3.** Run performance benchmark: full `analyze_dataset()` on a 500k-row OHLC DataFrame must not exceed baseline + 10s.

- [ ] **G4.** Code review: verify all new parameters are optional with safe defaults; verify no existing caller is broken.

- [ ] **G5.** Update `CLAUDE.md` / developer docs with the new `dataset_context/` module structure and how to add a future domain pack.

### Group H: Deployment

- [ ] **H1.** Deploy Phase 0 (threshold = 1.01, no activation). Monitor for one week.
- [ ] **H2.** Deploy Phase 1 (suppression only). Monitor insight distribution.
- [ ] **H3.** Deploy Phase 2 (full domain pack). Monitor for user feedback.
- [ ] **H4.** Deploy Phase 3 (charts + narrative). Complete v1.
- [ ] **H5.** Begin v2 signal definition based on learnings.

---

## Appendix A: Key Invariants

1. `DatasetContext` is **immutable** (frozen dataclass). Once detected, it is passed through the pipeline without modification.
2. `semantic_roles` covers every column in the DataFrame. No column is ever absent from the roles dict. Unknown columns get `"unknown"`, never `None` or missing key.
3. `detect_dataset_context()` **never raises**. All exceptions are caught internally; on failure, the function returns `generic_tabular` with a warning in `DatasetContext.warnings`.
4. Domain pack detectors **never raise to the caller**. Each detector wraps its logic in try/except and returns an empty list on failure.
5. Suppression keys are applied **before** ranking, not after. A suppressed insight is gone from the ranked list, not just moved to the bottom.
6. The `generic_tabular` fallback path is **the unchanged current code**. Any regression in the generic path is a bug, not an acceptable trade-off.

## Appendix B: Naming Conventions for New Insight Types

New insight types introduced by domain packs must be added to the `InsightCategory` Literal in `apps/api/app/schemas/insight.py`. V1 additions:

| New Type | Category Label |
|---|---|
| Volatility regime change | `"volatility_regime"` |
| Volume-price divergence | `"volume_price_divergence"` |
| Return fat-tails | `"distribution"` (reuse existing — fat-tail is a distribution finding) |
| OHLC integrity violation | `"data_quality"` (reuse existing — it is a quality issue) |
| Trading day gap | `"missing_pattern"` (reuse existing — gaps are missing data) |

Reusing existing categories where semantically correct avoids schema changes and keeps the `InsightCategory` literal manageable.
