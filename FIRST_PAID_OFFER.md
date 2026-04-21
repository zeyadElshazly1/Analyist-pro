# First Paid Offer

## Goal
Define the simplest sellable offer for the first paying users.

## Rule
Sell a focused outcome, not a broad platform dream.

## Recommended First Paid Offer
A consultant reporting toolkit that helps turn messy client spreadsheets into trustworthy, client-ready reports faster.

## Best First Buyers
- freelance analysts
- small agencies
- consultants doing recurring monthly/weekly reporting
- operators who receive spreadsheet exports from clients

## Main Pain To Sell
"I waste too much time cleaning ugly client files, figuring out what changed, and turning it into something presentable."

## What The Paid Product Must Deliver
- reliable file upload and intake
- cleaning review
- health score
- key insights
- file comparison
- report builder
- export

## Main Outcome
Faster client delivery with less manual cleanup and more confidence.

## What Not To Sell First
- enterprise analytics
- broad AI platform claims
- AutoML
- advanced experimentation
- too many technical features

## Offer Angle
This is a client-delivery workflow for spreadsheet-based consultants.

## Suggested Starting Price
Pick one working hypothesis and test it:
- $39/month
or
- $49/month

## Success Condition
The user should feel that one recurring client project can justify the subscription.

---

## Offer Audit

### What the Product Can Already Support for This Offer

**File upload and intake** — fully working. CSV and Excel (`.xlsx`, `.xls`) upload with automatic structure detection, preamble skipping, header inference, delimiter detection, and encoding handling. Files up to the plan size limit are processed reliably.

**Cleaning review** — the backend pipeline applies 15+ rules (type coercion, duplicate removal, whitespace normalization, null handling, date standardization) and returns a per-step cleaning report with before/after counts. The cleaning log tab in the Health step surfaces this to the user.

**Health score** — produces a 0–100 score with an A–F grade, dimensional breakdown (completeness, consistency, validity, uniqueness), per-column health flags, deductions list, and fix suggestions. This is consultant-credible output — it gives a user something concrete to say to a client about data quality.

**Key insights** — the analysis engine produces ranked findings with type, severity, title, finding text, evidence, and a recommended action. Insights cover correlations, anomalies, distributions, and data quality issues. An executive panel with opportunities, risks, and an action plan is also generated.

**File comparison** — schema diff (added/removed/renamed columns shown as colour-coded pills), row count delta, health score comparison, numeric metric changes with mean % highlighted in amber when >10%, and row overlap count. This is gated behind the `file_compare` plan feature. Diff runs also compare two stored analysis results for insight-level change tracking.

**Report builder backend** — `POST /reports/draft` creates and updates a `ReportDraft` record with title, executive summary, selected insight IDs, selected chart IDs, and template. Three template configs exist: `monthly_performance`, `ops_kpi_review`, and `finance_summary`.

**Export pipeline** — fully working and polished:
- **HTML** — styled report with insights, charts, health score, and metadata
- **XLSX** — 6-sheet Excel workbook: cover, insights, column profiles, cleaning log, data preview, trust metadata
- **PDF** — generated via WeasyPrint/pdfkit from the HTML report

All three export formats are gated behind the `report_export` plan feature.

**Plan enforcement and billing** — Stripe checkout session creation works. Webhook handles `subscription.activated`, `subscription.updated`, and `subscription.deleted` to set and reset user plan in the DB. The `require_feature()` middleware correctly blocks free users from `report_export`, `file_compare`, `ai_story`, and `ai_chat`.

**The core workflow is end-to-end functional.** A consultant can upload a file, get a health score and insights, compare with a previous file, create a report draft, and export a PDF or Excel file — all in one session.

---

### What Would Make This Offer Hard to Sell Right Now

**The report builder assembly experience undersells the export quality.**
The export output (PDF, Excel) is polished and client-ready. But the report builder page (`/reports/[id]/page.tsx`) only offers two export buttons (HTML and XLSX — no PDF button is wired up despite the API supporting it) and a share link. There is no template picker, no insight selection, no visual preview, no section editor. A consultant paying for "polished exports" opens the report builder and sees three buttons. The product can produce a great PDF, but the experience before clicking export does not feel like a premium workflow.

**Plan naming is inconsistent — a paying user will see the wrong plan name.**
The marketing page and pricing page say "Consultant plan." The backend, billing page, API responses, and every DB record use `"pro"`. A user who upgrades to the "Consultant" plan will see their plan displayed as "pro" in the app UI and in Stripe metadata. This erodes trust at the moment of conversion and looks like a technical error to someone who just paid.

**Compare results do not connect to the report builder.**
File comparison lives in the Compare step. There is no way to take a compare finding — a schema change, a metric delta, a health score drop — and pull it into a report draft. A consultant doing a monthly report needs "what changed" inside the deliverable. Right now they must manually copy findings from the compare tab into the report summary textarea. The two most important paid features (compare and export) are disconnected from each other.

**The Report step in the navigation defaults to AI chat, not the report builder.**
`project-tabs.tsx` sets the Report step's `primaryTab` to `"ask-ai"`. Clicking "Report" in the step bar drops the user into an AI chat window. A consultant clicking "Report" expects to build a report, not open a chat interface. The report builder (`/reports/[id]`) is accessible via a separate link in the page header, but it is not the natural destination of the core workflow step.

**AI features silently fail without an API key.**
`ai_story` and `ai_chat` are gated paid features. If `ANTHROPIC_API_KEY` is not configured, both endpoints return errors. There is no graceful degraded mode. In a demo or early-customer environment this means the AI features — which are part of the paid pitch — are invisible or broken.

**No PDF button on the report page.**
The API client supports `exportReport(id, "pdf")` but the report detail page (`reports/[id]/page.tsx:129–143`) only renders HTML and XLSX export buttons. PDF is the most client-presentable format and is missing from the UI despite the backend fully supporting it.

---

### 3 Things That Must Be Improved Before Pitching Confidently

**1. Fix the report builder experience to match the export quality**
The PDF and Excel exports are good enough to sell. The experience of building a report before exporting is not. At minimum: add the PDF export button to the report page, add a simple template picker, and add a list of insights the user can select to include. A consultant needs to feel like they assembled something, not just clicked a button on a blank form. This single change would make the paid export hook tangible during a demo.

**2. Fix the plan naming inconsistency**
A paying customer who upgrades to "Consultant" and sees "pro" in the app will assume something went wrong. This is a one-day fix — rename all backend `"pro"` references to `"consultant"` and `"team"` to `"studio"`, update `PLAN_LIMITS` in `middleware/plans.py`, and align the billing page display. Until this is fixed, every paying customer has a broken first impression. (Exact file list and line numbers are in `PRICING_PLAN_ALIGNMENT.md`.)

**3. Connect the compare step to the report builder**
The second strongest paid hook — monthly file comparison — produces findings that currently cannot enter a report. This creates a gap where the consultant must manually bridge the two most important paid features. The fix does not require a full integration: add a "Add to report" button on each compare finding in the Compare step that writes the finding text into the current `ReportDraft.summary` or a new `comparison_notes` field. Even a clipboard copy button with a prompt ("Paste this into your report summary") would reduce the friction enough to make the workflow feel complete.
