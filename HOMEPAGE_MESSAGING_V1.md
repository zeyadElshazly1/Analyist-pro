# Homepage Messaging V1

## Goal
Make the homepage instantly communicate what the product does and who it is for.

## Rule
The homepage should sell the workflow, not the feature list.

## Recommended Headline
Turn messy client spreadsheets into client-ready reports.

## Recommended Subheadline
Analyst Pro helps consultants and freelancers clean messy CSV/XLSX files, uncover key insights, compare changes over time, and export polished reports fast.

## Top 3 Value Promises
1. Clean ugly client files automatically
2. Find what changed and what matters
3. Deliver polished client-ready output faster

## Target Users
- freelance analysts
- marketing consultants
- operations consultants
- finance/accounting freelancers
- small agencies

## Core Workflow To Communicate
Upload -> Clean -> Review -> Compare -> Report -> Export

## What Not To Lead With
- AutoML
- A/B testing
- advanced statistics
- generic AI hype
- too many technical terms

## Social Proof Direction
Use proof like:
- saves hours on recurring client reports
- catches issues before client delivery
- turns raw files into polished deliverables fast

## CTA Direction
Primary CTA:
- Try it on a sample file
or
- Upload your first client file

Secondary CTA:
- View demo workflow

---

## Current Homepage Audit

### What the Homepage Currently Says

**Headline** (`page.tsx:39–43`)
> "Turn messy client spreadsheets into client-ready analysis"

**Subheadline** (`page.tsx:46–49`)
> "Upload CSV or Excel files, auto-clean the data, spot issues and trends, compare versions, and export polished reports — without rebuilding everything in Excel."

**Badge** (`page.tsx:32–35`)
> "Built for consultants who live in spreadsheets"

**Primary CTA** (`page.tsx:57`): "Start for free"
**Secondary CTA** (`page.tsx:62`): "View pricing"

**Outcome proofs section** (`page.tsx:145–156`): Three proof points:
1. "Upload messy client files — Auto-detected structure, cleaned and ready in seconds"
2. "Compare month vs month — See exactly what changed between two client exports in one click"
3. "Export a polished report — PDF and Excel output ready to send — no reformatting required"

**Features section** (`page.tsx:332–375`): Six cards:
1. Upload any format
2. AI-powered insights — "Automatically detects correlations, anomalies, skewed distributions, and segment gaps."
3. Smart chart generation
4. Time series analysis — "Detect trends, seasonality, anomalies, and stationarity across date-based data."
5. Data quality scoring
6. Export-ready reports — "Share insights, charts, and cleaning reports with your team or clients."

**How it works section** (`page.tsx:377–390`): Three steps:
1. Upload your dataset
2. Run the analysis
3. "Explore and share — Dive into 11 analysis tabs: correlations, outliers, time series, duplicates, column comparisons, and more."

**Compare section** (`page.tsx:202–270`): Dedicated section showing month-over-month revenue comparison with a visual mock and four bullet points.

**CTA banner** (`page.tsx:279`): "Get from messy file to client-ready brief today"

---

### What Matches This Positioning

**Headline is mostly right.** "Turn messy client spreadsheets into client-ready analysis" is close to the recommendation. It leads with the pain (messy spreadsheets), names the audience (implicit consultant framing), and ends with a consultant-relevant outcome. The only weak word is "analysis" — the recommended version ends with "reports," which is more concrete and deliverable-oriented.

**Subheadline is well-aligned.** Mentions the full workflow in sequence (clean → spot issues → compare → export polished reports), includes "without rebuilding everything in Excel" as a strong objection handler, and avoids technical jargon.

**The badge is good.** "Built for consultants who live in spreadsheets" is audience-specific and concise. It sets the right framing before the headline.

**Outcome proofs section matches the top 3 value promises exactly.** Upload / Compare / Export maps directly to "Clean ugly client files", "Find what changed", and "Deliver polished output". This section is correctly positioned and correctly written.

**The compare section is strong.** It names a specific use case (March vs April), uses real-sounding numbers, calls out exactly what the feature produces (row-level diff, metric delta, health comparison, AI summary), and has a consultant-relevant CTA ("Try file comparison free"). This is the best-written section on the page.

**The CTA banner is well-framed.** "Get from messy file to client-ready brief today" is specific, action-oriented, and consultant-focused. The supporting copy ("Upload a client CSV or Excel file and see the health score, top findings, and a report draft in under 2 minutes") sets a clear time expectation.

**No fake social proof.** The previous fake stats section ("2M+ datasets analyzed", "98% accuracy rate", "50K+ analysts") has been replaced with the outcome proofs. This is correct.

---

### What Should Be Rewritten

**Headline: "analysis" → "reports"** (`page.tsx:42`)
"Client-ready analysis" is slightly weaker than "client-ready reports." Analysis describes the process; a report is the deliverable. Consultants sell reports to clients, not analysis sessions.

> Recommended: "Turn messy client spreadsheets into client-ready reports."

**Feature card: "AI-powered insights"** (`page.tsx:342–346`)
"Automatically detects correlations, anomalies, skewed distributions, and segment gaps." — every term here is analyst vocabulary, not consultant vocabulary. A consultant does not care about "skewed distributions" or "segment gaps." They care about findings they can put in a report.

> Recommended: "Surface the findings that matter — revenue drops, data quality issues, unusual patterns, and what changed since last time."

**Feature card: "Export-ready reports"** (`page.tsx:369–374`)
"Share insights, charts, and cleaning reports with your team or clients." — "or your team" broadens the target to internal analysts. The product is for consultants delivering to clients, not team sharing. "Cleaning reports" is also internal language, not client-delivery language.

> Recommended: "Export a polished PDF or Excel report your client can receive directly — no reformatting, no rebuilding in Excel."

**How it works — Step 3** (`page.tsx:386–389`)
"Explore and share — Dive into 11 analysis tabs: correlations, outliers, time series, duplicates, column comparisons, and more." This is the worst line on the page. "11 analysis tabs" is cockpit-selling language. "Correlations, outliers, time series" are technical terms that signal complexity, not value. The step should describe the consultant outcome, not the feature count.

> Recommended: "Build a report and export — Pick your top findings, add a comparison, and export a polished PDF or Excel report ready to send."

**Primary CTA: "Start for free" → more action-specific** (`page.tsx:57`)
"Start for free" is generic. Every SaaS product says this. The recommended CTAs ("Try it on a sample file" / "Upload your first client file") are more specific to the product's core action and reduce friction by naming exactly what the user does next.

> Recommended: "Upload your first client file" or "Try it free — upload a file"

**Secondary CTA: "View pricing" → "See how it works"** (`page.tsx:62`)
The secondary CTA sends visitors to the pricing page before they have seen the workflow. A visitor who is not yet convinced of the value will leave from the pricing page. The secondary CTA should extend the demo, not ask for money.

> Recommended: "See how it works" (scroll to how-it-works section) or "View demo workflow"

---

### What Should Be Removed or De-Emphasized

**Feature card: "Time series analysis"** (`page.tsx:355–360`)
"Detect trends, seasonality, anomalies, and stationarity across date-based data." — "stationarity" is a statistics term that will mean nothing to the target audience. Time series is a useful capability but it is a secondary insight tool, not a core consultant workflow step. It should not occupy one of six headline feature slots. If it stays, the copy must be rewritten to remove "stationarity" and frame the output as a deliverable finding ("Spot revenue trends, seasonality patterns, and unusual spikes before your client asks about them").

**How it works — "11 analysis tabs"** (`page.tsx:388`)
This phrase should be removed entirely. It is the most prominent signal that the product is a tool for power analysts, not a workflow for consultants. Telling a consultant there are 11 tabs to explore is the opposite of the simplicity message the product needs to convey.

**The floating badge: "+34% correlation / Revenue × Ad Spend"** (`page.tsx:127–137`)
This decorative badge on the dashboard mock shows a correlation stat. Correlation is an analyst metric. A consultant-facing badge would show something like "Report ready to send" or "3 issues found before client delivery." The badge is cosmetic but contributes to the analyst-tool framing.
