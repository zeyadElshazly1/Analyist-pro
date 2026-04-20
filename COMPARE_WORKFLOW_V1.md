# Compare Workflow V1

## Goal
Help consultants quickly understand what changed between two client files.

## Core Use Case
A consultant receives a new monthly/weekly file and needs to know:
- what changed
- what matters
- what should be mentioned to the client

## Required Compare Outputs

### 1. File Match Summary
- file A name
- file B name
- compare status
- comparable or not comparable
- confidence of match

### 2. Schema Changes
- columns added
- columns removed
- renamed/suspected renamed columns
- type changes

### 3. Row / Volume Changes
- row count change
- duplicate count change
- missingness change
- key entity count change if possible

### 4. Metric Changes
- biggest increases
- biggest decreases
- important grouped changes
- trend shifts if date column exists

### 5. Data Quality Changes
- better or worse data health
- new missingness issues
- new suspicious columns
- new structural issues

### 6. Client Summary Draft
- plain-English explanation of what changed
- top 3 things worth mentioning
- caution flags

## UX Rules
- the product should not dump raw diffs only
- comparison should surface what matters first
- schema and quality changes should be visible, not hidden
- user should be able to add compare findings into the report builder

## V1 Rule
Comparison must feel like "monthly client review assistant," not a technical diff tool.

---

## Current Compare Audit

### What Already Exists

**Multifile Compare (backend — `services/multifile_compare.py`)**
- `compare_files(path_a, path_b)` returns: schema diff (shared/added/removed columns), health scores for both files, row counts and delta, numeric stats comparison (mean, median, std, mean change %), distribution histograms for top 3 numeric columns, row overlap count and percent
- Feature-gated at `POST /explore/multifile` behind `file_compare` plan check

**Diff Runs (backend — `routes/analysis.py`)**
- `GET /analysis/diff?run_a=X&run_b=Y` diffs two stored analysis runs from the same project
- Produces: metric deltas with direction (up/down/unchanged) for health score, row count, missing %, columns, cleaning steps; insight diff classified as new/resolved/unchanged; column diff showing added/removed/changed columns with field-level changes

**Column Compare (backend — `services/column_compare/`)**
- Compares two columns within a single dataset
- Num × Num: Pearson, Spearman, Kendall, R², scatter plot, distribution overlap, plus a full English interpretation string
- Num × Cat: ANOVA or Welch's t-test, effect size, group stats, box plots, English interpretation
- Cat × Cat: Chi-square, Cramér's V, heatmap, English interpretation
- All three comparators produce a plain-English `interpretation` field

**Frontend**
- `multifile-compare.tsx` — project ID input, row count cards, health score badges, schema pills (color-coded shared/A-only/B-only), numeric stats table with mean % change highlighted in amber if >10%, overlay bar charts for top 3 columns
- `column-compare.tsx` — column selectors, results rendered by type, English interpretation banner displayed prominently
- `diff-view.tsx` — run selectors, metric delta table with up/down icons, new/resolved insights lists, column change pills
- All three live under the Compare step (step 4) in the project detail tab flow

---

### What Is Useful for Consultant Workflows

- Schema drift is immediately visible — added/removed columns shown as colour-coded pills, not buried in a table
- Row count delta shown with +/- prefix and absolute numbers
- Health score comparison side by side — consultant can see at a glance if data quality improved or degraded
- Mean % change highlighted in amber when >10% — draws attention to significant metric shifts without requiring manual calculation
- Diff runs insight tracking — "new" and "resolved" findings surface what the analysis engine thinks changed, useful for checking if known data problems were fixed
- Column compare interpretation strings — the only place in the current compare system where the output is plain English; these are consultant-ready sentences

---

### What Is Missing for V1

| Gap | Why It Matters |
|-----|---------------|
| **No plain-English comparison narrative** | Every output is raw numbers. No sentence like "Revenue mean dropped 38% and 3 new columns appeared — confirm the file source is correct before sending to client." Consultant must interpret everything manually. |
| **No "comparable or not comparable" signal** | Multifile compare runs regardless of how different the files are. A consultant needs to know upfront: are these the same dataset refreshed, or completely different files? |
| **No data quality risk flagging** | Missing % changes, new NULL columns, and type changes are buried in stats tables. There is no "⚠️ Column X went from 2% to 47% NULL — investigate before using" warning. |
| **No caution flags for abnormal changes** | A mean change of 300% or a row overlap drop from 90% to 10% is shown the same as a 5% change. Nothing escalates genuinely suspicious results. |
| **No "top 3 things to mention to the client" summary** | The closest thing is the diff runs insight list, but it classifies findings as new/resolved — it does not rank by client relevance or suggest what to actually say. |
| **No comparison block that feeds into the report builder** | Comparison results exist in a separate tab. There is no way to select compare findings and include them in a report draft. The two workflows are disconnected. |
| **No "file match confidence" indicator** | The system does not assess how likely the two files are to be the same dataset (same columns, similar volumes, overlapping row hashes). It just runs the diff blind. |
| **No historical context** | Each comparison is isolated. There is no "Row overlap has averaged 85% over the last 4 runs — today's 40% is unusual" signal. |
| **No client-safe language filter** | Column names and technical stat terms appear verbatim. A consultant would need to manually rephrase before sharing. |
| **Comparison is hard to find** | It lives as a sub-tab in the project detail page, not as a natural next step after uploading a new file. There is no "Compare with previous" prompt shown to the user on upload. |
