# Task 77E — Large Dataset Mode End-to-End QA Checkpoint

**Purpose:** Final confidence pass that Large Dataset Mode is transparent, safe, and non-regressive across the full consultant journey—without changing sampling, ranking, finance time-series logic, charts, or adding domain packs.

**Related:** General launch QA lives in [`LAUNCH_HARDENING_QA_PASS.md`](./LAUNCH_HARDENING_QA_PASS.md). This checkpoint is **narrow**: large-dataset transparency, metadata carry-through, and report surfaces only.

## Out of scope (do not change for 77E)

- Sampling thresholds, strategies, or frame preparation
- Insight ranking or selection heuristics
- Finance time-series domain logic (ordering, premium titles)
- Chart generation / chart payload budgets
- New sales / churn / insurance (or other) domain packs

## Automation acceptance (record results below)

Run from repo root (or adjust paths):

```bash
cd apps/web
npx tsc --noEmit
npm run build
```

```bash
cd apps/api
pytest -q tests/test_large_dataset_mode.py tests/test_report_draft_export.py tests/test_financial_timeseries_domain.py
```

On environments where `pytest` is not on `PATH` (common on Windows), use:

```bash
python -m pytest -q tests/test_large_dataset_mode.py tests/test_report_draft_export.py tests/test_financial_timeseries_domain.py
```

| Check | Result / notes |
|-------|------------------|
| `apps/web` — `npx tsc --noEmit` | **Pass** (2026-05-07; zero errors) |
| `apps/web` — `npm run build` | **Pass** (2026-05-07; Next.js 16.2.4 production build) |
| `apps/api` — targeted `pytest` (3 files) | **Pass** — `75 passed` in ~16s (2026-05-07; via `python -m pytest`) |

**Automation is not a substitute for the manual UI checklist below.** Fill the Result / Notes columns after exercising the app in a browser.

## Manual QA checklist

Record **Pass / Fail / N/A**, environment (browser, plan), and any screenshots or ticket links in the notes column.

### 1. Small dataset

| # | Expectation | Result | Notes |
|---|-------------|--------|-------|
| 1.1 | No large-dataset banner (or large-dataset callout) after analysis | | |
| 1.2 | Reports (preview, HTML, shared views) do **not** show a large-dataset methodology block | | |

### 2. Large generic dataset

| # | Expectation | Result | Notes |
|---|-------------|--------|-------|
| 2.1 | Banner / transparency appears after analysis completes | | |
| 2.2 | Full rows vs analyzed / sample rows are clearly shown | | |
| 2.3 | Sample strategy text is human-readable | | |
| 2.4 | Health / stats cards still describe full-upload metadata where applicable (row/column context honest vs sample) | | |

### 3. Large financial time-series dataset

| # | Expectation | Result | Notes |
|---|-------------|--------|-------|
| 3.1 | Banner appears | | |
| 3.2 | Symbols covered shown when API provides `symbol_count` (or equivalent) | | |
| 3.3 | Date range shown when `date_range_start` / `date_range_end` (or equivalent) present | | |
| 3.4 | Finance-first findings stay in the expected order (no regression vs pre–large-dataset UX) | | |
| 3.5 | No change in chart selection behavior or report “selection” UX beyond transparency copy | | |

### 4. Report Builder & exports

| # | Expectation | Result | Notes |
|---|-------------|--------|-------|
| 4.1 | Compact methodology note in **preview** | | |
| 4.2 | **HTML** export includes the large-dataset block (consistent with preview) | | |
| 4.3 | **Excel** export completes successfully | | |
| 4.4 | **PDF** path: if PDF is unavailable or degraded, messaging stays honest; fallback (e.g. HTML/Excel) still usable | | |

### 5. Reopen, share, report detail

| # | Expectation | Result | Notes |
|---|-------------|--------|-------|
| 5.1 | Reopened run: large-dataset metadata still visible in workflow UI | | |
| 5.2 | Shared analysis link: same metadata visible to reader | | |
| 5.3 | Report detail / report routes: metadata still visible where product promises it | | |

## Regression spot-checks (optional but recommended)

- Upload → analyze → Build Report → export HTML **without** large dataset mode: unchanged UX.
- Compare tab / multifile flow: no new errors when large dataset mode was active on a run.

## Completion criteria for 77E

Mark **77E complete** only when all are true:

1. This doc exists (or `LAUNCH_HARDENING_QA_PASS.md` explicitly incorporates the same checklist).
2. Frontend typecheck passed (`tsc --noEmit`).
3. Frontend production build passed (`npm run build`).
4. Targeted backend tests passed (three files above).
5. Manual QA table above is filled (Pass/Fail + short notes); any failures have owner/ticket.

## Sign-off log

| Date | Role | Automation | Manual QA | Sign-off |
|------|------|------------|-----------|----------|
| 2026-05-07 | Agent (checkpoint setup) | Pass (tsc, build, 75 pytest) | Pending — see tables §1–§5 | — |
| _YYYY-MM-DD_ | _Human QA / owner_ | _confirm_ | _Pass/Fail_ | _initials_ |

---

_This checkpoint is documentation and process only; code changes belong to separate tasks unless a P0 regression is found._
