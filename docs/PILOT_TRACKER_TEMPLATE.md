# Analyst Pro — Pilot Tracker Template

> Links: [Demo Package](./PILOT_DEMO_PACKAGE.md) · [Outreach Kit](./PILOT_OUTREACH_KIT.md) · [Feedback System](./PILOT_FEEDBACK_SYSTEM.md)

Copy each table below into Google Sheets, Excel, or Notion. One file, six tabs/sections.

---

## Operating Rules

- **Update after every message or call** — do not batch updates to end of week.
- **Review every Friday** — 15 minutes, apply roadmap decision rules.
- **Do not promote feedback to a task** until the rules in `PILOT_FEEDBACK_SYSTEM.md` are met (3+ independent mentions for features; reproducible for bugs).
- **One loud user does not make a roadmap.** Wait for corroboration.

---

## Status Codes

| Code | Meaning |
|------|---------|
| `not-contacted` | Identified but not yet reached |
| `sent` | First message sent |
| `replied` | They responded |
| `demo-scheduled` | Call booked |
| `demo-done` | Call completed |
| `pilot-active` | Using the product during trial period |
| `feedback-received` | Post-pilot feedback collected |
| `converted` | Moved to paying plan |
| `not-interested` | Declined or unresponsive after 2 follow-ups |
| `deferred` | Good fit but wrong timing — follow up in 4–6 weeks |

---

## Section 1 — Outreach Pipeline

Track every prospect from first contact through demo booking.

| # | Name | Role / Company | Source | Contact type | Contacted | Status | Follow-up date | Demo booked? | Notes |
|---|------|---------------|--------|-------------|-----------|--------|----------------|--------------|-------|
| 1 | | | | | | | | | |
| 2 | | | | | | | | | |
| 3 | | | | | | | | | |
| 4 | | | | | | | | | |
| 5 | | | | | | | | | |
| 6 | | | | | | | | | |
| 7 | | | | | | | | | |
| 8 | | | | | | | | | |
| 9 | | | | | | | | | |
| 10 | | | | | | | | | |

**Column guide:**
- **Source:** personal-network / LinkedIn / Reddit / Slack / referral / cold-email / other
- **Contact type:** DM / email / LinkedIn / community-post / in-person
- **Status:** use status codes above
- **Demo booked?** Yes / No / Scheduled [date]

---

## Section 2 — Demo Calls

One row per demo call. Fill in during or immediately after the call.

| # | Name | Date | Dataset type | Current workflow (how do they do this today?) | Pain level (1–5) | Fit score (1–5) | Key quote | Next step |
|---|------|------|-------------|-----------------------------------------------|-----------------|-----------------|-----------|-----------|
| 1 | | | | | | | | |
| 2 | | | | | | | | |
| 3 | | | | | | | | |
| 4 | | | | | | | | |
| 5 | | | | | | | | |

**Column guide:**
- **Dataset type:** sales / finance / HR / marketing / ops / research / other
- **Pain level:** 1 = mild inconvenience · 5 = major time sink
- **Fit score:** 1 = wrong tool · 5 = replaces a real workflow step
- **Next step:** invite to pilot / send follow-up / not a fit / schedule another call

---

## Section 3 — Active Pilots

One row per active pilot user. Update weekly.

| # | Pilot | Start date | End date | Dataset type | Workflow steps completed | Blockers | Feedback call booked? | Conversion status |
|---|-------|-----------|---------|-------------|--------------------------|----------|-----------------------|-------------------|
| 1 | | | | | | | | |
| 2 | | | | | | | | |
| 3 | | | | | | | | |
| 4 | | | | | | | | |
| 5 | | | | | | | | |

**Column guide:**
- **Workflow steps completed:** check all that apply — Upload / Intake / Cleaning / Health / Findings / Report Builder / Export / Reopen
- **Blockers:** describe any P0/P1 issue stopping them
- **Feedback call booked?** Yes / No / Scheduled [date]
- **Conversion status:** not-ready / ready / ask-sent / converted / not-interested

---

## Section 4 — Feedback Log

One row per distinct issue or request per pilot. Multiple rows per pilot expected.
See `PILOT_FEEDBACK_SYSTEM.md` for label/severity definitions and scoring rubric.

| # | Pilot | Stage | Issue / Request | Label | Severity | Pain | Fit | WTP | Urgency | Trust | Total | Decision | Task ID |
|---|-------|-------|-----------------|-------|----------|------|-----|-----|---------|-------|-------|----------|---------|
| 1 | | | | | | | | | | | | | |
| 2 | | | | | | | | | | | | | |
| 3 | | | | | | | | | | | | | |
| 4 | | | | | | | | | | | | | |
| 5 | | | | | | | | | | | | | |
| 6 | | | | | | | | | | | | | |
| 7 | | | | | | | | | | | | | |
| 8 | | | | | | | | | | | | | |
| 9 | | | | | | | | | | | | | |
| 10 | | | | | | | | | | | | | |

**Column guide:**
- **Stage:** Upload / Intake / Cleaning / Health / Findings / Report-Builder / Export / Reopen / Billing / Other
- **Label:** bug / friction / feature-request / domain-gap / expectation-gap / not-a-fit
- **Severity:** P0 / P1 / P2 / P3 / defer / wontfix
- **Pain / Fit / WTP / Urgency / Trust:** 1–5 (see scoring rubric in Feedback System doc)
- **Total:** sum of 5 scores, max 25
- **Decision:** fix-now / schedule / log / decline / wait-for-corroboration
- **Task ID:** fill in once a dev task is created

---

## Section 5 — Roadmap Candidates

Aggregate repeated feedback here. A candidate becomes a task only when the decision rules are met.

| # | Request | Mentions | Pilot names | Category | Decision | Build now / later / decline | Next task |
|---|---------|---------|-------------|----------|----------|-----------------------------|-----------|
| 1 | | | | | | | |
| 2 | | | | | | | |
| 3 | | | | | | | |
| 4 | | | | | | | |
| 5 | | | | | | | |

**Column guide:**
- **Mentions:** number of independent pilots who raised this (not how many times one person asked)
- **Category:** ux-polish / core-workflow / new-feature / domain-pack / billing / performance / other
- **Decision rules (from Feedback System):**
  - Bug reproducible → fix regardless of mention count
  - 2 pilots mention same friction → schedule as P2
  - 3+ pilots mention same feature → add to roadmap
  - 1 pilot wants enterprise/compliance → decline for pilot scope
  - Domain pack → wait for 3+ independent pilot requests before building

---

## Section 6 — Conversion Tracker

Track readiness to convert each pilot to a paying plan.

| # | Pilot | Trust score (1–5) | Time saved (hrs) | WTP score (1–5) | Price mentioned | Ready to convert? | Ask sent? | Outcome |
|---|-------|------------------|-----------------|-----------------|-----------------|-------------------|-----------|---------|
| 1 | | | | | | | | |
| 2 | | | | | | | | |
| 3 | | | | | | | | |
| 4 | | | | | | | | |
| 5 | | | | | | | | |

**Column guide:**
- **Trust score:** from feedback form Q6 (1 = would not share · 5 = share directly with client)
- **Time saved:** rough hours per week or per project, from feedback form Q7
- **WTP score:** 1 = would not pay · 5 = would pay current price immediately
- **Price mentioned:** what they said unprompted, if anything
- **Ready to convert?** Yes / Not yet / No — apply conversion criteria from Feedback System doc
- **Ask sent?** Yes / No
- **Outcome:** converted / deferred / not-interested

---

## Weekly Friday Review Checklist

- [ ] All new messages/calls added to Outreach Pipeline and Demo Calls
- [ ] Active Pilots table updated — any new blockers?
- [ ] Feedback Log updated with this week's entries
- [ ] Roadmap Candidates updated — any request now at 3+ mentions?
- [ ] Any P0/P1 bug flagged for immediate fix?
- [ ] Any pilot ready for conversion ask?
- [ ] Next week outreach: continue, pause, or expand to new sources?

---

*Template created: 2026-05-07*
