# Analyst Pro — Pilot Demo Package

> Checkpoint: 82A final smoke test — **Pilot-ready** (2026-05-07)  
> Branch: `claude/backend-chart-export-context-culfe`

---

## Product One-Liner

**Analyst Pro is an AI data analyst for consultants, freelancers, and small teams. Upload a dataset, review cleaning/health/findings, build a client-ready report, and export it.**

---

## Target User

- Independent data consultants and freelancers
- Small analytics teams serving external clients
- Anyone who regularly hands off data insights to a non-technical audience

---

## Problem Analyst Pro Solves

Consultants spend hours cleaning data, writing narrative, and formatting reports in Excel or slides — work that is repetitive and error-prone. Analyst Pro automates the data pipeline (cleaning → profiling → insight generation) and gives the consultant a structured review UI so they can focus on judgment, not mechanics. The output is a client-ready HTML or Excel report, not a raw notebook.

---

## Recommended Demo Dataset

Use a small, readable business dataset with mixed column types. Good options:

- **Sales by region/product/month** (~200–500 rows, 6–10 columns) — shows trend analysis and correlation findings naturally.
- **HR attrition** — shows categorical/numeric mix, health warnings, missingness.
- **Client revenue/churn** — shows business-relevant findings the audience will relate to.

Avoid: very wide datasets (>50 columns), datasets with no numeric columns, or files >10 MB (free plan limit during demo).

---

## Demo Flow (7–10 minutes)

### 0. Setup (before the call, ~1 min)

- Log in, confirm a clean project list.
- Have a demo CSV ready to upload (pre-tested).
- Open the demo workspace as a fallback if upload takes time.

---

### 1. Create Workspace (30 sec)

> *"Each client or project gets its own workspace."*

- Click **New workspace**.
- Name it something recognisable: `"Q2 Sales Review"` or `"[Client] Dataset"`.
- Workspace appears in the list immediately.

---

### 2. Upload Dataset (30 sec)

> *"Drop in any CSV or Excel file. The platform detects column types and previews the structure before you run anything."*

- Drag and drop the demo CSV.
- Show the **Intake Review** tab: column types, parse confidence, sample rows.
- Point out any low-confidence parse warnings if present.

---

### 3. Run Analysis (1–2 min)

> *"One click runs the full pipeline — cleaning, health scoring, and insight generation."*

- Click **Run analysis**.
- Watch the SSE progress bar: Reading → Checking quality → Finding patterns → Building brief.
- While it runs: *"This runs cleaning, correlation analysis, anomaly detection, and trend analysis in one pass."*

---

### 4. Review Cleaning (1 min)

> *"The cleaning review shows exactly what was fixed and why."*

- Show the **Cleaning Review** tab.
- Point out any removed duplicates, type corrections, or suspicious columns.
- *"Nothing is hidden — every change is auditable before you sign off."*

---

### 5. Review Health (30 sec)

> *"The health score gives an instant read on data quality before you build anything on top of it."*

- Show the grade (A–F) and breakdown.
- Point out top warnings if any.

---

### 6. Review Findings (1–2 min)

> *"Findings are ranked by strength and business relevance, not just statistical significance."*

- Browse 3–5 findings.
- Show confidence badges, the narrative, and the executive panel summary.
- Select 2–3 findings to include in the report.

---

### 7. Build Report (1–2 min)

> *"The Report Builder lets you choose which findings and charts go into the client deliverable."*

- Open **Build Report**.
- Show selected findings panel.
- Reorder a chart in the chart selector — *"Preview updates live in the order you choose."*
- Edit the executive summary draft if time allows.
- Show autosave indicator: *"Drafts are saved automatically."*

---

### 8. Export (30 sec)

> *"One-click export to HTML for browser viewing or Excel for client handoff."*

- Export HTML — file downloads instantly.
- Export Excel.
- *"PDF is supported in environments with a headless browser installed. HTML is the reliable fallback."*

---

### 9. Reopen Saved Analysis (30 sec, optional)

> *"Saved analyses are instant to reopen. History tracks every run for each workspace."*

- Navigate away and reopen the project.
- Show the **Saved analysis available** banner.
- Click **Open run** — results rehydrate in under a second.

---

### 10. Wrap / Billing Mention (optional, 30 sec)

If relevant to the audience:

> *"Free plan supports up to 3 workspaces and 10 MB files. Consultant plan unlocks AI chat, AI story, file compare, and polished exports. Studio adds team management."*

---

## Key Proof Points

| Area | Evidence |
|------|----------|
| Launch hardening | All P1/P2/P3 items resolved — A1–A3, B1–B8, C1 |
| Final smoke test | 82A: 129 tests passed, 1 skipped by design, exit 0 |
| Plan gates | Free users blocked from diff/export/team; Consultant/Studio tested |
| Run history | Cache-hit analyses create new history entries (80A) |
| Stored result safety | Malformed insight items filtered on reopen (81B) |
| Status validation | Invalid run statuses raise `ValueError` at development time (81C) |
| Report Builder | Selected chart order respected in live preview (75P) |
| Large Dataset Mode | Methodology note shown for datasets >250k rows (77D) |
| Team management | Studio-only gates verified and tested (81F) |
| Autosave safety | Timer cleared on component unmount — no React warnings (79B) |

---

## Known Limitations / Honest Caveats

| Item | Detail |
|------|--------|
| PDF export | Requires a headless browser (e.g. Chromium) in the server environment. HTML and Excel exports are always available. |
| Frontend build | `next build` requires `node_modules` installed. Not available in the current CI sandbox; works normally in a standard dev or production environment. |
| NR2 | `finalise_run` uses best-effort DB commit — a DB or Redis failure during result persistence would be swallowed. Intentional design for resilience; real impact requires infrastructure failure to observe. Non-blocking for pilot. |
| Scale | Tested with typical consultant datasets (<100k rows). Very large files (>250k rows) trigger Large Dataset Mode with a representative sample. |
| AI features | AI Chat and AI Story require a valid Anthropic API key configured in the environment. |
| This is pilot-ready | Not enterprise-compliance-ready (no SOC 2, no SSO, no audit log export). Appropriate for consultants and small teams evaluating the product. |

---

## Suggested Pilot Ask

> *"We're looking for 3–5 consultants or small teams willing to use Analyst Pro on a real client project over the next 4 weeks. In exchange for early access, we'd ask for 30 minutes of feedback at the end of the trial."*

Ideal pilot profile:
- Uses CSV/Excel data regularly
- Produces client reports
- Not currently using an automated analysis tool
- Willing to share honest feedback, including what didn't work

---

## Post-Demo Feedback Questions

1. What part of the demo resonated most with how you actually work?
2. Is there a step in your current process this would replace? Which one?
3. What's the first thing you'd want to change or add?
4. Would you feel confident sharing the exported report directly with a client?
5. What would make you willing to pay for this? What plan/price feels right?
6. Anything in the demo that felt confusing or unfinished?

---

*Document created: 2026-05-07 — post 82A pilot-ready checkpoint.*
