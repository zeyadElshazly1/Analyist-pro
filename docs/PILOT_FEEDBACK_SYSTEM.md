# Analyst Pro — Pilot Feedback System

> Companion to: [docs/PILOT_OUTREACH_KIT.md](./PILOT_OUTREACH_KIT.md) · [docs/PILOT_DEMO_PACKAGE.md](./PILOT_DEMO_PACKAGE.md)

---

## Goals

1. Capture feedback consistently so every pilot call produces comparable signal.
2. Classify issues immediately (bug / friction / feature request / domain gap).
3. Score by severity and frequency — not by who was loudest.
4. Convert feedback into a prioritised task queue, not a random wish list.
5. Know when a pilot user is ready to convert to a paying customer.

---

## Feedback Collection Form

Send this to each pilot user after 1–2 weeks of use (async, no call needed).
Copy/paste into a Google Form, Notion, or email.

---

**Analyst Pro — Pilot Feedback Form**

*Takes 5–10 minutes. Be honest — critical feedback is more useful than polite feedback.*

**1. What type of data did you upload?**
(e.g. sales, finance, HR, operations, marketing, research)

**2. Which steps of the workflow did you actually use?**
☐ Upload / Intake  ☐ Cleaning Review  ☐ Health Score  ☐ Findings  ☐ Report Builder  ☐ Export  ☐ Reopen saved run

**3. Did anything break or confuse you? Describe it.**
(Be specific — what did you click, what did you expect, what happened?)

**4. What was the most useful thing the tool did?**

**5. What is the most important thing that is missing?**

**6. Did you trust the findings enough to share them with a client or manager? (1 = No / 5 = Yes, immediately)**
☐ 1  ☐ 2  ☐ 3  ☐ 4  ☐ 5

**7. How much time did it save you compared to doing this manually? (rough estimate)**
☐ No time saved  ☐ < 30 min  ☐ 30 min – 2 hrs  ☐ 2–5 hrs  ☐ More than 5 hrs

**8. Would you pay for this? If yes, what feels like a fair monthly price for the Consultant plan?**

**9. Anything else?**

---

## Interview Note Template

Use during or immediately after a 30-minute pilot call.

```
Pilot: [Name]
Role:  [Title / company type]
Date:  [YYYY-MM-DD]
Dataset type: [sales / finance / HR / ops / other]

--- What they used ---
Steps completed: [ ]
Dataset size: ~[N] rows × [N] columns

--- What worked ---
- 

--- What broke or confused ---
- 

--- What's missing ---
- 

--- Trust / findings quality ---
Score (1–5): [ ]
Quote: "

--- Time saved ---
Estimate: 

--- Willingness to pay ---
Score (1–5): [ ]
Price mentioned: 

--- Would they recommend? ---
[ ] Yes  [ ] Maybe  [ ] No

--- Immediate follow-up needed? ---
[ ] Bug fix  [ ] Clarification  [ ] Nothing

--- Raw notes ---

```

---

## Scoring Rubric

Score each pilot session on five dimensions (1–5 each).

| Dimension | 1 | 3 | 5 |
|-----------|---|---|---|
| **Pain intensity** | Mild inconvenience | Regular friction | Blocks their workflow entirely |
| **Product fit** | Wrong tool for them | Partially fits | Replaces a real workflow step |
| **Willingness to pay** | Would not pay | Maybe $10–20/mo | Would pay current Consultant price immediately |
| **Urgency** | Nice to have someday | Would use in next month | Needs it for active client work right now |
| **Trust in findings** | Would not share with anyone | Would share internally | Would share directly with a paying client |

**Total score = sum of 5 dimensions (max 25).**

| Total | Interpretation |
|-------|---------------|
| 20–25 | Strong signal — high-fit pilot, prioritise their feedback |
| 13–19 | Moderate fit — useful signal, weight equally with others |
| 5–12 | Low fit — note domain gaps but do not let this drive roadmap alone |

---

## Issue Classification

For every piece of feedback, assign one label:

| Label | Definition | Example |
|-------|------------|---------|
| `bug` | Something broke or produced wrong output | Export downloaded empty file |
| `friction` | Works but is confusing or takes too many steps | Couldn't find the export button |
| `feature-request` | Works fine but something is missing | "I want to filter findings by column" |
| `domain-gap` | The tool works but misses their specific domain context | "It didn't recognise my currency format" |
| `expectation-gap` | The tool works but they expected something different | "I thought it would write the whole report for me" |
| `not-a-fit` | The user's workflow doesn't match the product's scope | "I need live database connections" |

---

## Severity Labels

| Severity | Definition | Response time |
|----------|------------|---------------|
| `P0` | Blocks upload, analysis, or export entirely | Fix before next demo |
| `P1` | Severely degrades the core workflow | Fix within current sprint |
| `P2` | Noticeable friction but workaround exists | Schedule in next sprint |
| `P3` | Polish / copy / minor UX | Batch with other P3s |
| `defer` | Valid but out of scope for pilot phase | Document, revisit post-pilot |
| `wontfix` | Enterprise-only, compliance, or not-a-fit | Explicitly decline |

---

## Roadmap Decision Rules

These rules prevent random feature creep and premature domain-pack expansion.

| Trigger | Decision |
|---------|----------|
| Blocks upload / analysis / report / export for any pilot | **Fix immediately (P0/P1)** |
| 2 pilots mention the same friction | **Schedule as P2** |
| 3+ pilots mention the same missing feature | **Add to near-term roadmap as a task** |
| 1 pilot wants an enterprise feature (SSO, SAML, compliance) | **Decline for pilot scope — log for later** |
| 1 pilot wants a domain-specific pack (e.g. insurance, telco) | **Do not build yet — wait for 3+ independent requests** |
| Feature request from a non-paying, low-score pilot | **Log but do not prioritise** |
| A bug is reproducible | **Fix it regardless of who reported it** |
| A request aligns with a known planned feature | **Accelerate the planned feature, not a one-off** |

**The "one loud user" rule:** Do not build a feature because one pilot user asked loudly or repeatedly. Wait for independent corroboration from at least 2 other users before scheduling it.

---

## Weekly Pilot Review Ritual

Run this every Friday during the active pilot period.

**15-minute review:**

1. Update the feedback tracker table with any new entries from the week.
2. Count issue mentions by label and severity.
3. Apply roadmap decision rules — convert any 3+ mentions to a task.
4. Flag any P0/P1 bugs for immediate fix.
5. Note any low-fit users and deprioritise their requests.
6. Update conversion status for each pilot.

**Questions to answer each week:**
- Is anyone blocked from completing the core workflow?
- Has any feature been mentioned by 3+ pilots this week?
- Is any pilot ready to convert to a paid user?
- Should the next outreach wave continue or pause?

---

## Conversion Criteria — Pilot → Paid User

A pilot user is ready to convert when:

- [ ] They completed at least one full workflow (upload → analysis → export)
- [ ] They rated trust in findings ≥ 3/5
- [ ] They mentioned a specific client or project they would use it for
- [ ] They said they would pay (any price) without being prompted
- [ ] They have not hit an unresolved P0 or P1 bug

**Conversion ask script:**
> "Based on your feedback, it sounds like this fits your workflow. We're moving to paid plans soon — the Consultant plan is [price]/month and covers unlimited workspaces, AI features, and polished exports. Want to be one of the first paid users?"

---

## Example Filled-In Feedback Entry

| Field | Value |
|-------|-------|
| Pilot name | Jordan T. |
| Role | Freelance marketing analyst |
| Dataset type | Ad campaign performance (CSV, 800 rows) |
| Workflow stages used | Upload, Cleaning, Findings, Report Builder, Export HTML |
| Issue / request | "Export button was hard to find — I looked for 2 minutes" |
| Category | `friction` |
| Severity | `P3` |
| Pain score | 2 |
| Product fit score | 4 |
| WTP score | 4 |
| Urgency score | 3 |
| Trust score | 4 |
| Total score | 17 (Moderate fit) |
| Follow-up needed | Move export button to a more prominent location |
| Roadmap decision | Log — promote to P2 if 2 more pilots mention it |
| Task ID | — (pending corroboration) |

---

## Feedback Tracker Table

Maintain one row per issue/request per pilot. Multiple rows per pilot are expected.

| Pilot | Role | Dataset | Stage | Issue / Request | Label | Severity | Pain | Fit | WTP | Urgency | Trust | Total | Follow-up | Decision | Task ID |
|-------|------|---------|-------|-----------------|-------|----------|------|-----|-----|---------|-------|-------|-----------|----------|---------|
| | | | | | | | | | | | | | | | |
| | | | | | | | | | | | | | | | |

**Columns:**
- **Stage:** Upload / Intake / Cleaning / Health / Findings / Report Builder / Export / Reopen
- **Label:** bug / friction / feature-request / domain-gap / expectation-gap / not-a-fit
- **Severity:** P0 / P1 / P2 / P3 / defer / wontfix
- **Pain / Fit / WTP / Urgency / Trust:** 1–5
- **Total:** sum of 5 scores (max 25)
- **Decision:** Fix now / Schedule / Log / Decline / Wait for corroboration

---

*Document created: 2026-05-07*
