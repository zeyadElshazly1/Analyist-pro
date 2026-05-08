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
| 1 | auto_insurance_data.xlsx | Auto insurance / risk | ~1k | ~20 | Excel | Upload, intake, health score, findings list, export all completed without error | Cleaning Review grade shown as raw Python object: `Grade {'score': 70, 'grade': 'B', 'label': 'Good'}` instead of formatted label | Yes | No | No | No | P2 | **85E — Fix Cleaning Review grade formatting** — in `cleaning_adapter.py:98` replace `str(summary.get("confidence_grade", "F"))` with `summary.get("confidence_grade", {}).get("grade", "F")` | **Build now** — confirmed universal: `score_to_grade()` always returns a `dict`; `str()` on it always produces raw object text on every file; not file-specific (85D code audit 2026-05-08) |
| 2 | auto_insurance_data.xlsx | Auto insurance / risk | ~1k | ~20 | Excel | — | Date-derived findings dominate ranking: `effective_date_month`, `effective_date_quarter`, `effective_date_year`, weekend flag findings ranked above business-relevant correlations | No | No | Yes | No | P2 | Suppress or down-rank low-value date-part feature correlations (month/quarter/year/weekday extracted from a single date column) in finding ranker | Defer — log; schedule as generic engine improvement when a second file confirms the same over-ranking pattern |
| 3 | auto_insurance_data.xlsx | Auto insurance / risk | ~1k | ~20 | Excel | — | Spreadsheet artifact columns not removed: `avg S`, `avg P`, `Unnamed: X`, `severity per payment` — these are helper/formula columns, not data columns | No | Yes | No | No | P2 | Improve mostly-empty and helper-column detection in cleaning pipeline; flag columns that are >80% empty or appear to be row-level formula residues | Defer — schedule as generic cleaning improvement when a second file produces similar artifact columns |
| 4 | auto_insurance_data.xlsx | Auto insurance / risk | ~1k | ~20 | Excel | Charts render and export without error | Chart selection is technically valid but does not surface the strongest business story; distributions are generic rather than focused on high-signal numeric fields (e.g. claim amount vs premium vs risk tier) | No | No | No | Yes | P2/P3 | Improve generic chart ranking to prioritise numeric fields that correlate with a likely target variable; deprioritise uniform or near-constant distributions | Defer — P3 polish; revisit after findings-ranker improvement is in place |

---

## Issue #1 — Reproduction Audit (85D, 2026-05-08)

**Method:** Static code trace — no additional file upload needed.

**Finding:** `score_to_grade()` in `apps/api/app/services/cleaning/quality_score.py:58` always returns a `dict` (`{"score": int, "grade": str, "label": str}`). In `cleaning_adapter.py:98` this dict is passed through `str()`, producing a raw Python object string on every file without exception. The bug is in the adapter, not the data.

**Verdict:** Confirmed reproducible universally — not file-shape-specific.

**Root cause:** `str(summary.get("confidence_grade", "F"))` — the default `"F"` is a string but the real value is always a dict, so `str()` stringifies the dict.

**Fix location:** `apps/api/app/services/cleaning_adapter.py:98`

**Fix:** Replace `str(summary.get("confidence_grade", "F"))` with `summary.get("confidence_grade", {}).get("grade", "F")`

**Next task:** 85E — Fix Cleaning Review grade formatting.

---

## Domain Pack Decision Gate

| Domain | Files tested | Pilot requests | Decision |
|--------|-------------|----------------|----------|
| Auto insurance | 1 | 0 | Do not build — log only |
| Telco / churn | — | 0 | Do not build — log only |
| Sales | 1 (demo dataset) | 0 | Do not build — log only |
| HR / attrition | — | 0 | Do not build — log only |
| Finance | — | 0 | Do not build — log only |

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
| 1 | #1 | **85E** — Fix `cleaning_adapter.py:98` — extract `.grade` from dict instead of `str(dict)` | **Confirmed — build now** (85D code audit) |
| 2 | #3 | Improve helper/mostly-empty column detection in cleaning | Second file with artifact columns |
| 3 | #2 | Suppress date-part feature correlations in finding ranker | Second file with same over-ranking |
| 4 | #4 | Improve generic chart ranking toward high-signal fields | After findings ranker improvement lands |

---

*Log started: 2026-05-08*
