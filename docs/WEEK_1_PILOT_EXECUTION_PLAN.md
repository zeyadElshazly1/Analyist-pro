# Analyst Pro — Week 1 Pilot Execution Plan

> References: [Demo Package](./PILOT_DEMO_PACKAGE.md) · [Outreach Kit](./PILOT_OUTREACH_KIT.md) · [Feedback System](./PILOT_FEEDBACK_SYSTEM.md) · [Tracker](./PILOT_TRACKER_TEMPLATE.md)

---

## Week-1 Objective

By end of day 5:

- **20–30 qualified prospects** contacted
- **≥ 20% reply rate** (4–6 responses)
- **3 demo calls booked**
- **1–2 active pilots started**
- **0 bad-fit users accepted** (no enterprise/compliance/DB-integration asks)

---

## Rules for the Entire Week

1. **Do not pitch enterprise compliance, SSO, or SAML** — if someone asks, say it is on the long-term roadmap and move on.
2. **Do not promise unsupported integrations** — file upload only; no live database connections, no API connectors.
3. **Do not build new features this week** unless a P0 or P1 bug blocks a demo or the core upload → analyze → export workflow.
4. **Record every response in the tracker the same day** — do not batch at end of week.
5. **One follow-up per non-responder**, then mark `deferred` and move on.
6. **Qualify before booking a demo** — use the checklist in `PILOT_OUTREACH_KIT.md`. Do not book calls with bad-fit users.

---

## Day 1 — Prepare and Send Warm DMs

**Goal:** Tracker ready. First 5 messages sent before end of day.

### Morning (~1 hour)

- [ ] Open `PILOT_TRACKER_TEMPLATE.md` → paste all 6 tables into Google Sheets / Notion / Excel.
- [ ] Name the file: `Analyst Pro Pilot Tracker — [Month] [Year]`.
- [ ] Set up columns, freeze headers, set status dropdown to the 10 status codes.

### Afternoon (~1–2 hours)

- [ ] Shortlist 10 warm contacts: people you know personally who work with data regularly.
  - Think: ex-colleagues, freelance contacts, anyone who has ever complained about Excel reports.
- [ ] Apply the qualification checklist (from Outreach Kit) mentally — remove obvious bad fits.
- [ ] Write personalised versions of the **Short Cold DM** template for your top 5.
  - Add one specific detail about their role or company to each.
- [ ] Send 5 DMs (LinkedIn, Slack, email — wherever you have a warm connection).
- [ ] Log each in Section 1 (Outreach Pipeline) with status `sent` and today's date.

**End of day check:**
- [ ] 5 messages sent and logged
- [ ] Tracker is live and usable

---

## Day 2 — LinkedIn Outreach to Target Roles

**Goal:** 10 additional messages sent. First replies handled.

### Morning

- [ ] Check for Day 1 replies — respond within 2 hours.
  - If interested: send demo booking link or propose a time.
  - If not interested: mark `not-interested`, move on.
  - Update tracker status for all responses.

### Afternoon (~1–2 hours)

- [ ] Search LinkedIn for: `freelance data analyst`, `business consultant`, `marketing analyst`, `finance analyst`.
  - Filter to: 1st and 2nd degree, open to messages.
- [ ] Shortlist 10 profiles. Apply qualification checklist mentally.
- [ ] Send **LinkedIn Connection Request Note** template to 5 new contacts.
- [ ] Send **Short Cold DM** to 5 existing 1st-degree connections who fit the profile.
- [ ] Log all 10 in Outreach Pipeline with status `sent`.

**End of day check:**
- [ ] Total sent: ~15
- [ ] Any replies? → Book demos immediately, do not delay.

---

## Day 3 — Community Posts and Targeted DMs

**Goal:** Broader reach. Community post live. 5 more targeted DMs sent.

### Morning

- [ ] Check all replies from Day 1–2. Respond and update tracker.
- [ ] Prepare the **Community Post** template from Outreach Kit.
  - Personalise slightly for each community's tone.

### Afternoon (~1–2 hours)

- [ ] Post in 1–2 relevant communities:
  - Reddit: r/dataanalysis, r/consulting, or r/freelance
  - Slack: any analytics, freelance, or small-business workspace you are in
  - LinkedIn: post on your own feed (wider reach than DMs)
- [ ] Send 5 more targeted DMs — target: accounting/finance analysts, operations analysts, or marketing consultants you have not reached yet.
- [ ] Log community posts as single entries in Outreach Pipeline (source: `community-post`).
- [ ] Log all new DMs.

**End of day check:**
- [ ] Total sent: ~20–25
- [ ] Community post live
- [ ] Demo calls: target ≥ 1 booked by now

---

## Day 4 — Follow-Ups and Demo Booking

**Goal:** Close the gap. Follow up with non-responders. Confirm booked demos.

### Morning

- [ ] Review Outreach Pipeline — identify everyone with status `sent` and contacted ≥ 2 days ago.
- [ ] Send the **Follow-Up Message** template to non-responders (one follow-up only).
  - Offer a 2-minute video as an alternative to a call if they are time-constrained.
- [ ] Update tracker status to `deferred` for anyone who has now been messaged twice with no response.

### Afternoon

- [ ] For anyone who replied positively: confirm demo time, send calendar link.
- [ ] Check community post comments/replies — respond to every comment.
- [ ] Run the **qualification checklist** on any new leads before booking.
  - If they ask about enterprise compliance, SSO, or DB integrations: do not book. Respond honestly and mark `not-a-fit`.
- [ ] Send 3–5 final targeted outreach messages if pipeline count is below 25.

**End of day check:**
- [ ] Follow-ups sent to all Day-1/2 non-responders
- [ ] Demos: ≥ 2 confirmed, target 3
- [ ] Tracker fully up to date

---

## Day 5 — Pipeline Review and Week-2 Decision

**Goal:** Close the week cleanly. Know your numbers. Decide what changes for week 2.

### Morning

- [ ] Run all outstanding demos if scheduled today.
- [ ] Fill in Section 2 (Demo Calls) for any calls completed this week.
- [ ] Send any remaining reply messages from community posts.

### Afternoon — Weekly Review (15 minutes)

Run the Friday review checklist from `PILOT_TRACKER_TEMPLATE.md`:

- [ ] Count total contacts sent — hit 20–30?
- [ ] Count replies — hit 20%+?
- [ ] Count demo calls booked — hit 3?
- [ ] Count active pilots started — hit 1–2?
- [ ] Any P0/P1 bugs found during demos? → Create task immediately.
- [ ] Any repeated feedback (2+ people)? → Log in Roadmap Candidates.
- [ ] Any conversion-ready pilots? → Send conversion ask.

### Week-2 Decision (Stop / Continue / Adjust)

| Signal | Decision |
|--------|----------|
| 3+ demos booked, 1–2 pilots active | **Continue** — same outreach channels, shift focus to pilot support and feedback collection |
| < 3 demos booked but good replies | **Adjust** — try a different message or community; re-examine qualification bar |
| Low reply rate and low demos | **Adjust** — go warmer; try in-person outreach or referrals instead of cold DMs |
| Multiple bad-fit users (enterprise, compliance) | **Adjust** — refine targeting; remove enterprise-sounding language from posts |
| P0/P1 bug blocking demo | **Fix first** — do not continue outreach until core workflow is stable again |

---

## Demo Call Quick-Reference

When a demo call is booked:

1. Confirm the 30-minute slot and send a calendar invite.
2. Prepare a demo dataset if they do not have one (use the recommended dataset from Demo Package).
3. Follow the 10-step demo flow in `PILOT_DEMO_PACKAGE.md`.
4. Fill in Section 2 (Demo Calls) immediately after.
5. If fit score ≥ 3: invite them to the pilot the same day.
6. Send pilot invite with: a brief next-steps message, how to access the product, and what you are asking from them (4 weeks, 30-min feedback call).

---

## Week-1 Success Metrics

| Metric | Target | Result (fill in Friday) |
|--------|--------|------------------------|
| Total contacts sent | 20–30 | |
| Reply rate | ≥ 20% | |
| Demo calls booked | 3 | |
| Active pilots started | 1–2 | |
| Bad-fit users accepted | 0 | |
| P0/P1 bugs discovered | 0 | |
| Roadmap candidates (3+ mentions) | TBD | |

---

## What Not to Do This Week

- **Do not build new features** — product is pilot-ready. Feedback comes first.
- **Do not accept bad-fit users** to hit a number — they produce noise, not signal.
- **Do not promise a roadmap item** to close a demo — say "we're tracking that" at most.
- **Do not deprioritise logging** — untracked feedback is lost signal.
- **Do not chase one loud user** — wait for 3+ independent mentions before scheduling any feature.
- **Do not expand scope** — no domain packs, no new integrations, no pricing changes this week.

---

*Plan created: 2026-05-08*
