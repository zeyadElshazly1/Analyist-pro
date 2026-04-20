# Report Builder V1

## Goal
Turn analysis outputs into a polished client-ready deliverable fast.

## Core Principle
The report builder is not just export.
It is a structured deliverable assembly workflow.

## Required Report Sections

### 1. Cover / Title
- client name
- project name
- reporting period
- prepared by

### 2. Executive Summary
- short summary of what matters most
- AI draft editable by user

### 3. Data Health Notes
- important warnings
- missingness
- duplicates
- structural limitations
- assumptions made during cleaning

### 4. Key Findings
- top ranked insights
- each finding should be editable
- each finding should be removable

### 5. Charts
- selected charts only
- title + optional note

### 6. Comparison Summary
- what changed vs previous file
- biggest deltas
- schema changes if relevant

### 7. Recommendations / Next Steps
- optional consultant notes
- AI draft editable by user

## Required User Actions
- add/remove section
- reorder sections
- edit text
- include/exclude insights
- include/exclude charts
- preview report
- export report

## Export Formats
- PDF
- XLSX
- HTML / shareable report

## Trust Rules
- clearly separate AI-generated text from user-edited text before final save
- include data quality notes when relevant
- do not include weak insights by default
- every included chart and finding should feel client-safe

## V1 Rule
A consultant should be able to build a usable client report in minutes, not from scratch.

---

## Current Report System Audit

### What Already Exists

**Backend — Storage**
- `ReportDraft` model with: `title`, `summary`, `selected_insight_ids_json`, `selected_chart_ids_json`, `template`, `analysis_result_id`, timestamps
- `POST /reports/draft/{project_id}` — create/update draft
- `GET /reports/draft/{project_id}` — fetch current draft
- `GET /reports/export/{project_id}?format=html|pdf|xlsx` — export to file
- `GET /reports/preview/{project_id}` — returns raw analysis JSON (not a visual preview)

**Backend — Generation**
- `context.py` — assembles Jinja2 context: title, date, row/col counts, health grade, narrative, insights (up to 10), column profiles, cleaning steps, two chart configs, trust metadata
- `html_report.py` — renders `templates/report.html` with analyst or executive mode
- `excel_report.py` — 6-sheet workbook: Summary, Insights, Column Profiles, Cleaning Report, Data Preview, Report Info (trust labels)
- `pdf_report.py` — WeasyPrint → pdfkit fallback, raises RuntimeError if neither available
- `templates/report.html` — Jinja2 dark-theme HTML template: stats grid, executive summary, data quality charts (2x Chart.js), insights cards, column profiles, cleaning actions
- `charts.py` — builds Chart.js configs for health score breakdown bar and top-missing-columns bar

**Backend — Templates**
- `templates.py` — 3 opinionated templates: `monthly_performance`, `ops_kpi_review`, `finance_summary`
- Each template defines: insight priority order, focus sections, executive summary hint, title prefix
- `apply_template_to_draft()` — auto-selects top 5 insights sorted by template preference

**Frontend**
- `report-builder.tsx` — template picker (3 options), title input (save-on-blur), executive summary textarea labelled "AI-generated — edit freely", insight checkboxes (up to 10), Export PDF + Export Excel buttons
- Draft auto-saves to backend on every change

---

### What Partially Exists

| Feature | What Exists | What's Missing |
|---------|-------------|----------------|
| **Executive Summary** | Textarea + "AI-generated" label in UI; narrative field in context | No button to trigger AI draft generation; narrative is from analysis, not surfaced in the textarea automatically |
| **Key Findings / Insights** | Checkbox selection (stored as index list); severity badge per insight | No reordering UI; limited to 10 shown; no inline text editing per finding; no "weak insight" filter |
| **Charts** | `selected_chart_ids_json` field stored in DB; 2 auto-generated Chart.js charts in HTML/Excel | No chart selection UI; `selected_chart_ids` is saved but never read back into exports; only health and missing charts exist |
| **Trust Labels** | "Report Info" metadata sheet in Excel; trust footer in HTML template | No UI toggle to show/hide trust labels; no "AI-generated" vs "user-edited" visual distinction in builder |
| **Templates** | 3 templates auto-select insights | Templates do not control section visibility, cover metadata, comparison inclusion, or recommendations |
| **Health Notes** | Cleaning steps table in exports; health score displayed | No dedicated editable "health notes" section in the builder or export — cleaning info is always shown in full, not summarised |

---

### What Is Missing for V1

| Gap | Impact |
|-----|--------|
| **Cover / Title section** — no client name, reporting period, or "prepared by" fields | Reports open without a professional cover; feels like a raw export |
| **Comparison Summary section** — no way to include period-over-period delta in the report | Consultants doing monthly reports have no comparison block |
| **Recommendations section** — no editable "next steps" or consultant notes block | Report ends at findings; client-readiness requires a call-to-action section |
| **Add / remove sections toggle** — no UI to show/hide any report section | User cannot control what is in the report |
| **Reorder sections** — no drag-and-drop or up/down ordering | Fixed structure; not adaptable to client preferences |
| **Visual preview** — `/reports/preview` returns raw JSON, not a rendered view | User must export to see what the report looks like |
| **Chart selection UI** — `selected_chart_ids` is stored but no UI exists to choose charts | Charts in export are always the same 2 auto-generated ones |
| **Inline finding editing** — insights can be included/excluded but not edited in place | Consultant cannot rephrase a finding to be more client-safe |
| **AI summary generation trigger** — no button to call the AI and populate the summary field | User must write the executive summary manually |
| **Weak insight filtering** — no threshold or toggle to exclude low-confidence findings | Weak insights appear by default; consultant must manually deselect |
| **"AI vs user-edited" visual distinction** — no clear label once user edits AI text | Trust principle not enforced in the UI |
