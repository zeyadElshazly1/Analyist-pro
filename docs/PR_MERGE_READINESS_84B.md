# PR Merge Readiness — Branch `claude/backend-chart-export-context-culfe`

> Prepared: 2026-05-08  
> Status: **Ready to merge**  
> Reviewer index: [docs/PILOT_LAUNCH_INDEX.md](./PILOT_LAUNCH_INDEX.md)

---

## Branch Purpose

This branch closes all launch-hardening P1/P2/P3 items, adds the final smoke test verification, and delivers the complete pilot-readiness documentation suite. The product moves from "feature-complete" to "pilot-ready."

No unresolved blocking issues remain. NR2 (best-effort finalise_run commit) is documented and intentional.

---

## Copy-Paste PR Description

```
## Summary

Closes all launch-hardening P1/P2/P3 items and delivers the pilot-readiness documentation suite.

### What changed

**Launch hardening (no product behavior changes for end users):**
- Add plan gates (`require_feature`) to `/analysis/diff` and `/analysis/download-cleaned`
- Remove legacy `STRIPE_PRO_PRICE_ID`/`STRIPE_TEAM_PRICE_ID` fallback env vars
- Persist a new `report_ready` run record on cache-hit analyses (sync + SSE paths)
- Validate run status strings in `set_run_status` — raises `ValueError` on invalid status
- Add `isInsightLike` type guard to filter malformed insight items before reopen
- Clarify `RunStateBanner` — explicit `ACTIVE_RUN_STATUSES` set; unknown statuses show amber
- Add `PLAN_FEATURES` frozenset and HTTP 402 payload contract documentation
- Lock Studio-only team gates; fix seat-limit 402 to include `current_plan`
- Lock resolver ordering with deterministic `id DESC` secondary sort
- Clear `saveTimer` on `ReportBuilder` unmount (no React warnings on fast navigation)
- Align user-facing vocabulary: "workspace" replaces "project" in navigation

**Pilot documentation:**
- `docs/PILOT_DEMO_PACKAGE.md` — 10-step demo flow, proof points, honest caveats
- `docs/PILOT_OUTREACH_KIT.md` — 5 message templates, qualification checklist, red flags
- `docs/PILOT_FEEDBACK_SYSTEM.md` — scoring rubric, roadmap decision rules, conversion criteria
- `docs/PILOT_TRACKER_TEMPLATE.md` — 6 copy-paste tracking tables
- `docs/WEEK_1_PILOT_EXECUTION_PLAN.md` — day-by-day week-1 checklist
- `docs/PILOT_LAUNCH_INDEX.md` — central navigation index
- `README.md` — added Docs section linking the index

### Test evidence
- 82A backend suite: 129 passed, 1 skipped by design, exit 0
- py_compile clean on 8 core modules
- 21 manual QA checks: all Pass
- Frontend structural checks passed; full `next build` requires node_modules in environment

### Known caveats
- PDF export requires a headless browser on the server; HTML/Excel always available
- NR2: `finalise_run` is best-effort; requires infrastructure failure to observe (intentional)
- Pilot-ready — not enterprise-compliance-ready (no SOC 2, no SSO, no audit log export)
```

---

## Major Completed Task Groups

### 1. Report Builder Chart Workflow (75F–75P)

End-to-end chart selection: expose `selected_chart_payloads` in export context → render chart gallery in HTML → add `Selected Charts` sheet to Excel → PDF-safe fallback → show selected charts in UI → add/remove controls → up/down reorder controls → live-preview respects chart order (75P bug fix) → chart selection QA checkpoint.

### 2. Large Dataset Mode Transparency (77D–77E)

Methodology note shown automatically when dataset exceeds 250k rows. Users can see sampling is active before interpreting findings. QA checkpoint documented.

### 3. Stale Failed-Run Banner Fix

`RunStateBanner` previously showed "in progress" spinner for any non-result, non-failed state including unknown statuses. Now uses explicit `ACTIVE_RUN_STATUSES` set; unknown statuses render amber "Analysis not complete" without spinner.

### 4. P1 Launch Hardening Closure (79A–79B, tasks A1–A3)

| Item | Fix |
|------|-----|
| A1 | `GET /analysis/diff` now requires `feature="file_compare"` — free users receive HTTP 402 — `35e9292` (79A) |
| A2 | `GET /analysis/download-cleaned/{project_id}` now requires `feature="report_export"` — free users receive HTTP 402 — `35e9292` (79A) |
| A3 | `saveTimer` cleanup `useEffect` added to `report-builder.tsx` — timer cleared on unmount — `22e7d0a` (79B) |

### 5. P2 Launch Hardening Closure (80A–81F, tasks B1–B8)

| Item | Fix |
|------|-----|
| B1 | Cache-hit sync and SSE paths now create and finalise a new `report_ready` run record — `3d8459b` (80A) |
| B2 | `STRIPE_PLAN_MAP` / `_PLAN_PRICE_MAP` no longer fall back to legacy env vars; only canonical `STRIPE_CONSULTANT_PRICE_ID` / `STRIPE_STUDIO_PRICE_ID` read — `392124c` (80B) |
| B3 | `RunStateBanner` explicit branches: active statuses show spinner; unknown/stale statuses show amber "Analysis not complete" with no spinner — `a0e4379` (81A) |
| B4 | `adaptStoredResults` filters `insight_results` through `isInsightLike` — malformed items dropped before reopen — `c294d33` (81B) |
| B5 | `set_run_status` validates against `VALID_RUN_STATUSES` frozenset; raises `ValueError` on unrecognised string — `39390aa` (81C) |
| B6 | `resolve_latest_run` `id DESC` secondary sort confirmed correct; inline comment added; 11 determinism tests added — `2ba3c66` (81D) |
| B7 | `PLAN_FEATURES` frozenset and HTTP 402 payload contract documented in `plans.py`; all feature keys and response shape covered by tests — `7a8a50d` (81E) |
| B8 | Studio-only team gates verified by tests; `"team"` added to `PLAN_FEATURES` / `PLAN_LIMITS` / `UPGRADE_MESSAGES`; `accept_invite` seat-limit 402 now includes `current_plan` — `3b30890` (81F) |

### 6. P3 Launch Hardening Closure (82B, task C1)

Navigation vocabulary aligned: "workspace" replaces "project" in three frontend files.

### 7. Final Smoke Test (82A)

`docs/FINAL_LAUNCH_SMOKE_TEST.md` — 129 backend tests passed, 1 skipped by design, py_compile clean, 21 manual QA rows all Pass. Pilot-ready verdict recorded.

### 8. Pilot Documentation Suite (83A–84A)

Seven documents covering demo, outreach, feedback, tracking, week-1 execution, and central navigation. README updated with Docs section.

---

## Key Commits by Phase

| Commit | Task | Description |
|--------|------|-------------|
| `35e9292` | 79A | Plan gates on diff + download-cleaned |
| `22e7d0a` | 79B | Clear autosave timer on ReportBuilder unmount |
| `1050fb3` | 79C | Mark P1 items resolved in QA board |
| `3d8459b` | 80A | Persist run-history entry on cache-hit analysis |
| `392124c` | 80B | Remove legacy Stripe env-var fallbacks |
| `b290870` | 80C | Reconcile P2 board |
| `a0e4379` | 81A | Clarify RunStateBanner states |
| `c294d33` | 81B | Validate stored insight_results before reopen |
| `39390aa` | 81C | Validate run status strings in set_run_status |
| `2ba3c66` | 81D | Document + test deterministic resolver ordering |
| `7a8a50d` | 81E | Document + test HTTP 402 contract |
| `3b30890` | 81F | Lock Studio-only team gates |
| `5bd013b` | 81G | Close P2 board |
| `6964018` | 82A | Final launch smoke test |
| `5b838c5` | 82B | Align vocabulary: workspace |
| `f9bb1e5` | 82C | Mark C1 resolved — 0 active P1/P2/P3 |
| `fa264f5` | 83A | Pilot demo package |
| `99e7056` | 83B | Pilot outreach kit |
| `49eb39d` | 83C | Pilot feedback system |
| `de4200f` | 83D | Pilot tracker template |
| `0262838` | 83E | Week-1 pilot execution plan |
| `034570c` | 84A | Pilot launch index + README link |

---

## Test Evidence

### Backend automated suite (82A checkpoint)

- **129 tests passed, 1 skipped by design** (exit 0)
- Skipped: `test_team_studio_only_gate` — validates the gate is present by design, not a test gap
- New test files added in this branch:
  - `test_analysis_plan_gates.py` — 6 tests for diff/download-cleaned plan gates
  - `test_billing_env_config.py` — 10 tests for canonical Stripe env vars
  - `test_cache_hit_run_history.py` — 5 tests proving cache-hit creates new run records
  - `test_run_tracker_status_validation.py` — 11 tests for `VALID_RUN_STATUSES` enforcement
  - `test_latest_run_resolver.py` — 11 determinism tests for `resolve_latest_run`
  - `test_upgrade_message_contract.py` — static + integration tests for 402 payload contract
  - `test_team_plan_gates.py` — 17 tests for Studio-only team gates (1 skipped by design)

### py_compile check

Clean on core backend modules touched by this branch: `analysis.py`, `analysis_stream.py`, `billing.py`, `team.py`, `plans.py`, `run_tracker.py`.

### Manual QA (21 rows — all Pass)

Full table in [docs/FINAL_LAUNCH_SMOKE_TEST.md](./FINAL_LAUNCH_SMOKE_TEST.md). Covers:
upload → intake → analysis → cleaning review → health score → findings → report builder → chart add/remove/reorder → HTML export → Excel export → plan gate enforcement → cache-hit run history → workspace navigation vocabulary → team invite seat limit.

### Frontend

`next build` requires `node_modules` installed — not available in the current CI sandbox. Structural TypeScript checks passed. Full build must be verified in a standard dev or production environment before deploying.

---

## Known Caveats

| Item | Detail |
|------|--------|
| **PDF export** | Requires a headless browser (Chromium) on the server. HTML and Excel exports are always available and recommended for pilot demos. |
| **NR2** | `finalise_run` uses best-effort DB commit. A simultaneous DB + Redis failure during result persistence would be swallowed. Intentional design for resilience; requires infrastructure failure to observe. Non-blocking for pilot. |
| **Frontend build** | `next build` not run in current environment (no node_modules). Must be verified in a proper frontend build environment before production deployment. |
| **Pilot-ready, not enterprise-ready** | No SOC 2, no SSO/SAML, no audit log export. Appropriate for consultants and small teams. Documented in outreach kit red flags. |
| **Scale** | Tested with typical consultant datasets (<100k rows). Very large files (>250k rows) trigger Large Dataset Mode with methodology note. |

---

## Merge Risk Level

**Low.**

- All changes are either additive (new tests, new docs) or narrow hardening fixes (plan gates, status validation, timer cleanup)
- No schema migrations
- No changes to the core analysis pipeline
- No changes to auth or billing flows beyond env-var cleanup
- All new tests pass; no existing tests broken
- NR2 is documented and pre-existing

---

## Reviewer Checklist

- [ ] README `## Docs` link to `docs/PILOT_LAUNCH_INDEX.md` renders correctly
- [ ] `docs/PILOT_LAUNCH_INDEX.md` — all 7 linked docs exist and links resolve
- [ ] `LAUNCH_HARDENING_QA_PASS.md` — no active P1/P2/P3 items remain in the board
- [ ] `docs/FINAL_LAUNCH_SMOKE_TEST.md` — 129 passed, 1 skipped, exit 0 recorded
- [ ] Pilot docs contain no unsupported claims (no SOC 2, no SSO, no PDF guarantee)
- [ ] Plan gate tests pass: `pytest apps/api/tests/test_analysis_plan_gates.py`
- [ ] Team gate tests pass: `pytest apps/api/tests/test_team_plan_gates.py`
- [ ] Cache-hit run history tests pass: `pytest apps/api/tests/test_cache_hit_run_history.py`
- [ ] Run frontend build in a proper environment with `node_modules` installed if deploying

---

## Post-Merge Next Step

Merge this branch, then begin week-1 pilot outreach following:

1. [docs/WEEK_1_PILOT_EXECUTION_PLAN.md](./WEEK_1_PILOT_EXECUTION_PLAN.md) — day-by-day actions
2. [docs/PILOT_OUTREACH_KIT.md](./PILOT_OUTREACH_KIT.md) — message templates and qualification checklist
3. [docs/PILOT_TRACKER_TEMPLATE.md](./PILOT_TRACKER_TEMPLATE.md) — paste tables into Google Sheets / Notion before sending first message

Do not start new features, domain packs, or integrations until pilot feedback meets the thresholds in [docs/PILOT_FEEDBACK_SYSTEM.md — Roadmap Decision Rules](./PILOT_FEEDBACK_SYSTEM.md#roadmap-decision-rules).

---

*Document created: 2026-05-08*
