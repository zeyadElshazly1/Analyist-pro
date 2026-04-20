# Monetization Readiness

## Goal
Define exactly what users are paying for in V1.

## Core Paid Value
Users should pay because the product helps them:
- clean messy client files faster
- find important changes faster
- generate client-ready insights faster
- export polished deliverables faster
- reduce risk before sending work to clients

## Free Plan Should Prove
- the product can ingest files
- the product can detect structure
- the product can show cleaning + health
- the product can generate limited insights

## Paid Plan Should Unlock
- full report builder
- PDF/XLSX/HTML export
- file comparison
- AI Q&A
- AI executive summaries
- larger file limits
- more projects/history
- reusable templates
- branded outputs later

## What Makes It Worth Paying Monthly
- saves hours on recurring reporting work
- reduces manual cleanup effort
- makes deliverables more polished
- increases confidence in client-facing analysis

## Main Monetization Risk
If the product feels broad but not reliably useful, people will not pay.
If it feels focused and repeatable, people will pay.

## V1 Monetization Principle
Charge for workflow completion, not for random advanced features.

---

## Current Monetization Audit

### What Is Already Monetizable

**Report export (PDF / XLSX / HTML)** — gated behind `report_export` feature flag (Consultant plan)
The export pipeline fully works: HTML report with insights, charts, and health score; 6-sheet Excel workbook with column profiles, cleaning log, data preview, and trust metadata; PDF via WeasyPrint/pdfkit. This is a real, polished deliverable a consultant would actually send to a client. It is the strongest paid hook in the codebase today.

**File comparison** — gated behind `file_compare` feature flag (Consultant plan)
Schema diff, health score delta, numeric metric changes, row overlap, and column-level distribution overlays all work. Diff runs can surface new/resolved insights between two analysis runs. Useful for recurring monthly reporting workflows.

**AI executive summary / data story** — gated behind `ai_story` feature flag (Consultant plan)
`POST /analysis/story/{id}` generates a 5-slide structured narrative with title, per-slide narrative, and key points. Backed by Anthropic Claude API. Works when API key is configured.

**AI Q&A / chat** — gated behind `ai_chat` feature flag (Consultant plan)
`POST /chat/query` lets users ask natural language questions about the dataset. Backed by Claude API. Works when API key is configured.

**Plan enforcement infrastructure** — fully wired
`middleware/plans.py` correctly blocks free users from `report_export`, `file_compare`, `ai_story`, `ai_chat`. `check_project_limit` enforces 3-project cap on free plan. Stripe checkout session creation works (`POST /billing/checkout`). Webhook handles subscription activated, updated, and deleted events to set/reset user plan in DB.

**Billing UI** — exists and functional
`/billing` page shows current plan, usage bars (projects used, analyses run), and plan cards with upgrade CTAs that call the Stripe checkout session endpoint.

---

### What Paid Value Is Weak Right Now

**Report builder is half-built as a paid experience**
The export endpoint works, but the report builder UI only offers: template picker, title field, executive summary textarea, and insight checkboxes. There is no cover section, no comparison block, no recommendations editor, no section reorder, and no visual preview. A user paying for "polished exports" opens the report builder and sees a minimal form — the export itself is good, the assembly experience is not.

**File comparison is disconnected from the report**
Comparison results live in a separate tab. There is no way to pull a compare finding into a report draft. A consultant doing a monthly report would want "what changed" inside the deliverable — right now they have to do it manually.

**AI features require a working API key — no fallback experience**
If `ANTHROPIC_API_KEY` is not set, AI chat and AI story return errors. There is no graceful degraded mode. In demo or trial environments this means the paid AI features are invisible.

**The "free plan proves value" loop is too short**
Free users get: upload, health score, profiling, insights. But the insights are shown in the same tabbed interface as the locked features. There is no clear moment where the free experience says "you've seen what this can do — here's what you unlock." The upgrade prompt exists in the sidebar but is not triggered at the natural friction point.

**Plan naming is inconsistent** (detailed in `PRICING_PLAN_ALIGNMENT.md`)
The marketing pricing page says "Consultant / Studio" but every backend system, billing page, and API call says "pro / team." A user upgrading via Stripe to "Consultant" will see their plan displayed as "pro" in the app. This erodes trust.

**AutoML, A/B testing, cohorts, SQL, and pivot are ungated**
These features are accessible to free users. They are not the core consultant workflow and are not in `V1_SCOPE.md` as primary features — yet they are freely available while the core paid value (export, compare, AI) is gated. This creates an odd incentive: the complex advanced tools are free, the practical deliverable tools are paid.

---

### What Should Be the Main Paid Hook

**"Export a polished client-ready report"** is the clearest paid hook.

This is a workflow-completion feature. The free experience shows the user what the analysis found. The paid experience lets them package it into something they can hand to a client. That is a natural, high-value gate:
- free: "here is what your data looks like"
- paid: "here is a polished PDF/Excel you can send to your client today"

Second strongest hook: **file comparison for recurring clients.** A consultant who has the same client every month will immediately see the value — run the new file, compare with last month, get a change summary, put it in the report. That is repeatable monthly value that justifies a subscription.

---

### What Should Not Be Sold as the Main Reason to Buy

**AutoML** — complex, slow, requires understanding of ML concepts. Most consultants do not need it. Selling this as a headline feature attracts the wrong audience and sets wrong expectations.

**AI Q&A chat** — useful but not the hook. Consultants do not primarily want to chat with data. They want to produce a deliverable. Chat is a supporting tool, not the reason to pay.

**"Unlimited projects"** — weak hook by itself. The free 3-project limit is invisible until a user hits it. Paying to unlock more projects is not emotionally motivating; paying to unlock a better deliverable is.

**Advanced analytics** (pivot, SQL, cohorts, segment builder, A/B) — these are analyst tools, not consultant-workflow tools. They are in the product but should not be front-and-center in paid plan messaging. Consultants will not upgrade for pivot tables.
