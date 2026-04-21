# Event Tracking Plan

## Goal
Define the minimum event tracking needed to understand whether V1 is working.

## Rule
Track the core workflow first.
Do not start with bloated analytics.

## Core Events

### Project / Workspace
- project_created
- project_opened

### Upload / Intake
- file_uploaded
- intake_started
- intake_completed
- intake_failed

### Cleaning / Health
- cleaning_completed
- cleaning_review_opened
- health_generated

### Insights
- insights_generated
- insight_opened
- insight_added_to_report
- insight_removed_from_report

### Compare
- compare_started
- compare_completed
- compare_failed
- compare_finding_added_to_report

### AI
- ai_summary_generated
- ai_question_asked
- ai_answer_used_in_report

### Reports / Exports
- report_draft_created
- report_section_added
- report_export_started
- report_export_completed
- report_export_failed

### Billing / Monetization
- paywall_seen
- upgrade_clicked
- checkout_started
- checkout_completed

## Event Properties To Capture
Where relevant, include:
- user id
- project id
- run id
- file id(s)
- plan
- timestamp
- success/failure
- failure reason if any
- duration if available

## V1 Principle
If we cannot measure the core workflow, we cannot manage the product properly.

---

## Current Event Audit

### What Events You Already Have

The backend has a working `audit_logs` table and a `log_event()` service (`services/audit.py`) that writes asynchronously to it. Five activation events are already instrumented:

| Existing Event | Action String | Location | Maps To Plan Event |
|----------------|---------------|----------|--------------------|
| File uploaded | `upload` | `routes/upload.py:153` | `file_uploaded` |
| Analysis completed (non-streaming) | `analysis_completed` | `routes/analysis.py:134` | `insights_generated` |
| Analysis completed (streaming) | `analysis` | `routes/analysis_stream.py:285` | `insights_generated` (duplicate action name — should be unified) |
| Compare used | `compare_used` | `routes/explore.py:173` | `compare_completed` |
| Report draft created | `report_draft_created` | `routes/reports.py:205` | `report_draft_created` |
| Export completed | `export_completed` | `routes/reports.py:68` | `report_export_completed` |

All six fire with `category="activation"` and a `user_id` + `resource_id`. No frontend analytics library exists — all tracking is server-side only.

---

### What Is Missing

**No frontend tracking at all.** There is no analytics client (PostHog, Mixpanel, Amplitude, or equivalent) in `apps/web/`. Every event in this plan that originates on the client — paywall seen, upgrade clicked, insight opened, tab viewed, cleaning review opened — is completely invisible. Server-side events only capture successful API calls; they cannot capture navigation, UI interactions, or abandoned flows.

| Missing Event | Why It Matters |
|---------------|----------------|
| `project_created` | No audit event fires in `routes/projects.py` `POST ""` endpoint. Cannot measure workspace creation rate. |
| `project_opened` | No event fires when a project page loads. Cannot measure return visits. |
| `intake_started` | No event fires when analysis begins. The streaming route logs completion only. |
| `intake_failed` | Failures go to `logger.error()` only — never to `audit_logs`. |
| `cleaning_completed` | Cleaning runs as part of the analysis pipeline; no separate event is emitted for it. |
| `cleaning_review_opened` | Frontend-only interaction — no backend event possible without a frontend tracker. |
| `health_generated` | Health score runs inside the analysis pipeline; no separate event. |
| `insight_opened` | Frontend-only tab interaction — invisible without a frontend tracker. |
| `insight_added_to_report` | No event fires when insights are selected in the report builder. |
| `insight_removed_from_report` | Same gap. |
| `compare_started` | `compare_used` fires on completion only. A started-but-abandoned compare is invisible. |
| `compare_failed` | No failure event. Errors return HTTP 4xx/5xx but are never written to `audit_logs`. |
| `compare_finding_added_to_report` | Compare is disconnected from the report builder — this action does not exist yet. |
| `ai_summary_generated` | `POST /analysis/story/{id}` returns a result but fires no audit event. |
| `ai_question_asked` | `POST /chat/query` fires no audit event. |
| `ai_answer_used_in_report` | No mechanism exists for this action yet. |
| `report_section_added` | No event fires when sections are added to a draft. |
| `report_export_started` | Only `export_completed` exists. A started-but-failed export is partially visible via failure logs, not audit events. |
| `report_export_failed` | `routes/reports.py:103` raises HTTPException with no audit event. |
| `paywall_seen` | `require_feature()` in `middleware/plans.py` raises HTTP 402 silently — no log event. |
| `upgrade_clicked` | Frontend-only interaction — no backend event possible without a frontend tracker. |
| `checkout_started` | `POST /billing/create-checkout-session` fires no audit event. |
| `checkout_completed` | Stripe webhook at `routes/billing.py:76` handles `subscription.activated` but fires no audit event — the plan update happens in DB only. |

---

### Which Events to Implement First

Priority is ordered by how directly each event feeds the metrics that determine whether V1 is working.

**Tier 1 — Implement immediately (backend-only, low effort)**

These are single `log_event()` calls in routes that already handle the action:

1. **`analysis_failed`** — add to `analysis_stream.py` except block. Needed for Metric 7 (Analysis Failure Rate). Without it you cannot detect a broken pipeline from the DB.
2. **`report_export_failed`** — add to `reports.py` except block. Needed for Metric 8 (Export Failure Rate). The export is the main paid hook — silent failures erode trust with no data.
3. **`paywall_seen`** — add to `middleware/plans.py` inside `require_feature()` before raising 402. Needed for Metric 6 (Paid Conversion Trigger Rate). Tells you which feature gates users hit and in what plan state.
4. **`project_created`** — add to `routes/projects.py` `POST ""` endpoint after `db.commit()`. Needed for Metric 5 (Repeat Project Rate) — you need a creation event to count projects per user over time.
5. **`checkout_started`** — add to `routes/billing.py` `POST /create-checkout-session`. Needed to measure the billing funnel. Combine with existing `checkout_completed` (once added to the webhook handler) to calculate drop-off between intent and payment.
6. **Unify action names** — `analysis.py` uses `"analysis_completed"` and `analysis_stream.py` uses `"analysis"` for the same event. Pick one (`"analysis_completed"`) and update both. Required before any funnel query will produce correct numbers.

**Tier 2 — Implement with the run model (medium effort, requires model changes)**

These events need the `started_at` field on `AnalysisResult` or a run stub record (from the canonical run model work) before they can carry `duration`:

7. **`intake_started`** — fire at the beginning of `analysis_stream.py` before processing begins. Gives you a started vs completed ratio and enables duration calculation once `started_at` is stored.
8. **`compare_started`** — fire at the beginning of `routes/explore.py` multifile compare before the diff runs. Compare started vs completed rate tells you whether the compare workflow completes reliably.
9. **`ai_summary_generated`** — add to `routes/analysis.py` `POST /analysis/story/{id}`. Needed to measure whether the AI feature is being used and whether it succeeds.

**Tier 3 — Implement after frontend analytics is set up**

These events originate in the browser and require a client-side analytics library (PostHog recommended — open-source, self-hostable, supports session replay and funnels):

10. **`paywall_seen`** (frontend complement) — fire when the upgrade wall renders in the UI, not just when the API 402 fires. Captures users who see the wall before they attempt the action.
11. **`upgrade_clicked`** — fire when the upgrade CTA button is clicked. Measures intent before the Stripe redirect.
12. **`insight_opened`** — fire when a user expands or clicks on an individual insight. Tells you which insights drive engagement.
13. **`cleaning_review_opened`** — fire when the cleaning log tab is opened. Measures whether users actually look at the cleaning output or skip past it.
14. **`project_opened`** — fire on project page load. Enables return-visit measurement without querying analysis history.
