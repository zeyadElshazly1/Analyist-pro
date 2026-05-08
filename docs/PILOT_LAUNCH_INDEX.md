# Analyst Pro — Pilot Launch Index

> One document to orient everything. Open this first, then follow the link for your immediate task.

---

## Current Readiness Status

| Item | Status |
|------|--------|
| Pilot-ready | **Yes** — as of 2026-05-07 (82A smoke test) |
| Active P1 launch-hardening items | **0** |
| Active P2 launch-hardening items | **0** |
| Active P3 launch-hardening items | **0** |
| Remaining item | **NR2 only** — non-blocking runtime observation (best-effort DB commit on `finalise_run`; requires infrastructure failure to observe; intentional design) |
| Safe to demo | **Yes** |
| Safe to start outreach | **Yes** |

---

## What to Read First

| Your immediate task | Start here |
|---------------------|-----------|
| Running a demo call | [Pilot Demo Package](./PILOT_DEMO_PACKAGE.md) |
| Finding pilot users | [Pilot Outreach Kit](./PILOT_OUTREACH_KIT.md) |
| Executing week 1 day by day | [Week-1 Pilot Execution Plan](./WEEK_1_PILOT_EXECUTION_PLAN.md) |
| Tracking contacts, demos, and pilots | [Pilot Tracker Template](./PILOT_TRACKER_TEMPLATE.md) |
| Collecting and scoring feedback | [Pilot Feedback System](./PILOT_FEEDBACK_SYSTEM.md) |
| Proving the product is stable | [Final Launch Smoke Test](./FINAL_LAUNCH_SMOKE_TEST.md) |
| Reviewing all resolved hardening items | [Launch Hardening QA Pass](../LAUNCH_HARDENING_QA_PASS.md) |

---

## Launch Hardening Proof

| Document | What it shows |
|----------|--------------|
| [LAUNCH_HARDENING_QA_PASS.md](../LAUNCH_HARDENING_QA_PASS.md) | Full P1/P2/P3 board — every item resolved, with commit evidence. A1–A3 (plan gate fixes), B1–B8 (backend hardening), C1 (UX polish). NR2 documented as intentional non-blocking design. |
| [FINAL_LAUNCH_SMOKE_TEST.md](./FINAL_LAUNCH_SMOKE_TEST.md) | 82A checkpoint: 129 tests passed, 1 skipped by design, exit 0. 21 manual QA rows — all Pass. Pilot-ready verdict recorded. |

---

## Pilot Execution Docs

| Document | Purpose |
|----------|---------|
| [PILOT_DEMO_PACKAGE.md](./PILOT_DEMO_PACKAGE.md) | Product one-liner, 10-step demo flow (7–10 min), recommended datasets, proof points, honest caveats, 6 post-demo feedback questions. |
| [PILOT_OUTREACH_KIT.md](./PILOT_OUTREACH_KIT.md) | Ideal pilot user profile, contact priority list, 5 message templates (cold DM, email, follow-up, LinkedIn, community post), 30-min call agenda, qualification checklist, red flags. |
| [PILOT_FEEDBACK_SYSTEM.md](./PILOT_FEEDBACK_SYSTEM.md) | Async feedback form, interview note template, 5-dimension scoring rubric (max 25), issue labels, severity levels (P0–wontfix), roadmap decision rules, conversion criteria. |
| [PILOT_TRACKER_TEMPLATE.md](./PILOT_TRACKER_TEMPLATE.md) | 6 copy-paste tables for Google Sheets / Notion / Excel: outreach pipeline, demo calls, active pilots, feedback log, roadmap candidates, conversion tracker. |
| [WEEK_1_PILOT_EXECUTION_PLAN.md](./WEEK_1_PILOT_EXECUTION_PLAN.md) | Day-by-day checklist for days 1–5: what to send, when to follow up, how to decide week 2 direction. Success metrics table (fill in Friday). |

---

## Weekly Operating Rhythm

During the active pilot period, run this sequence every Friday (15 minutes):

1. Update outreach pipeline — log any new messages or responses.
2. Update demo calls table — fill in any calls completed this week.
3. Update active pilots — note blockers, workflow steps completed.
4. Update feedback log — add this week's entries with labels and scores.
5. Update roadmap candidates — has any request hit 3+ independent mentions?
6. Flag any P0/P1 bug for immediate fix before next demo.
7. Check conversion status — is any pilot ready for the paid ask?
8. Decide: continue outreach / pause / expand to new sources.

Full checklist: [Pilot Tracker Template — Weekly Friday Review](./PILOT_TRACKER_TEMPLATE.md#weekly-friday-review-checklist)

---

## Remaining Non-Blocking Item

**NR2 — `finalise_run` best-effort commit**

`finalise_run` uses a best-effort DB commit. A simultaneous DB + Redis failure during result persistence would swallow the error. This is an intentional design decision for pipeline resilience; it requires an infrastructure failure to observe and has no impact on normal operation. It is documented and will be revisited post-pilot if infrastructure scale warrants it.

No action required before outreach.

---

## Do-Not-Start-Yet List

These items are explicitly out of scope for the pilot phase. Do not build, promise, or scope any of the following until real pilot feedback provides independent corroboration (3+ pilots, per the roadmap decision rules).

| Item | Why not yet |
|------|------------|
| Domain packs (sales, insurance, telco, HR, etc.) | Wait for 3+ independent pilot requests before building any domain pack |
| Enterprise compliance claims (SOC 2, HIPAA, GDPR) | Not compliant; advise pilots not to upload regulated data |
| SSO / SAML | Not supported; on long-term roadmap only |
| Live database connections / API connectors | File upload only in current version |
| White-label version | Not available; product is Analyst Pro branded |
| New features during week 1 | No new features unless a P0/P1 bug blocks the core upload → analyze → export workflow |
| Pricing changes | No pricing changes during pilot phase |

---

*Index created: 2026-05-08*
