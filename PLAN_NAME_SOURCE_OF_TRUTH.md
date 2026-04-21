# Plan Name Source of Truth

## Goal
Define one canonical plan system used everywhere.

## Final Decision
Choose one system only.

Recommended:
- Free
- Consultant
- Studio

## Rule
These exact names must be used consistently in:
- frontend labels
- backend enums/constants
- Stripe product names
- billing logic
- middleware / access control
- pricing page
- onboarding / upgrade copy

## Mapping Format

### Canonical Plan Names
- Free
- Consultant
- Studio

## Existing Names Found

| Name | Where Used | Status |
|------|-----------|--------|
| `"free"` | Backend middleware, models, billing reset, frontend billing page, settings page, sidebar, tests | Consistent everywhere — no change needed |
| `"pro"` | `middleware/plans.py`, `models.py` comment, `billing.py` (Stripe map + env var), `billing/page.tsx`, `api.ts` type annotation, test fixtures | Inconsistent — must rename to `"consultant"` |
| `"team"` | `middleware/plans.py`, `models.py` comment, `billing.py` (Stripe map + env var), `team.py` gate, `billing/page.tsx`, `team/page.tsx`, `app-sidebar.tsx`, test fixtures | Inconsistent — must rename to `"studio"` |
| `"Consultant"` | `apps/web/src/app/(marketing)/pricing/page.tsx` only | Correct name, used only on marketing page — needs to propagate to all other layers |
| `"Studio"` | `apps/web/src/app/(marketing)/pricing/page.tsx` only | Correct name, used only on marketing page — needs to propagate to all other layers |

---

## Final Mapping

- `"pro"` → `"consultant"`
- `"team"` → `"studio"`
- `"free"` → `"free"` (no change)
- `STRIPE_PRO_PRICE_ID` → `STRIPE_CONSULTANT_PRICE_ID`
- `STRIPE_TEAM_PRICE_ID` → `STRIPE_STUDIO_PRICE_ID`

---

## Files To Update

### Backend

| File | Lines | Change |
|------|-------|--------|
| `apps/api/app/middleware/plans.py` | 43 | Rename `PLAN_LIMITS["pro"]` key → `PLAN_LIMITS["consultant"]` |
| `apps/api/app/middleware/plans.py` | 51 | Rename `PLAN_LIMITS["team"]` key → `PLAN_LIMITS["studio"]` |
| `apps/api/app/models.py` | 33 | Update comment `free \| pro \| team` → `free \| consultant \| studio` |
| `apps/api/app/routes/billing.py` | 35 | Rename Stripe price map key `"pro"` → `"consultant"` |
| `apps/api/app/routes/billing.py` | 36 | Rename Stripe price map key `"team"` → `"studio"` |
| `apps/api/app/routes/billing.py` | 109, 123 | Update plan string fallback and default from `"pro"` → `"consultant"` |
| `apps/api/app/routes/billing.py` | 137, 138, 152 | Update `"team"` references → `"studio"` |
| `apps/api/app/routes/billing.py` | env vars | Rename `STRIPE_PRO_PRICE_ID` → `STRIPE_CONSULTANT_PRICE_ID` and `STRIPE_TEAM_PRICE_ID` → `STRIPE_STUDIO_PRICE_ID` in both `billing.py` and `.env`/`.env.example` |
| `apps/api/app/routes/team.py` | 26, 31, 32 | Change `user.plan != "team"` → `user.plan != "studio"` |

### Frontend

| File | Lines | Change |
|------|-------|--------|
| `apps/web/src/app/(app)/billing/page.tsx` | 29 | Plan object `id: "pro"` → `id: "consultant"` |
| `apps/web/src/app/(app)/billing/page.tsx` | 48 | Plan object `id: "team"` → `id: "studio"` |
| `apps/web/src/app/(app)/billing/page.tsx` | 87 | Checkout guard `planId !== "pro"` → `planId !== "consultant"`, `planId` team branch → `"studio"` |
| `apps/web/src/app/(app)/billing/page.tsx` | 247 | CTA branch for `"team"` → `"studio"` |
| `apps/web/src/app/(app)/team/page.tsx` | 144, 199 | `user?.plan === "team"` → `user?.plan === "studio"` |
| `apps/web/src/components/layout/app-sidebar.tsx` | 52 | Team nav link condition `"team"` → `"studio"` |
| `apps/web/src/lib/api.ts` | 944 | `createCheckoutSession(plan: "pro" \| "team")` → `createCheckoutSession(plan: "consultant" \| "studio")` |

### Tests

| File | Lines | Change |
|------|-------|--------|
| `apps/api/tests/conftest.py` | 138 | `user.plan = "pro"` → `user.plan = "consultant"` |
| `apps/api/tests/test_ml_cohorts_pivot_reports.py` | 386 | `u.plan = "pro"` → `u.plan = "consultant"` |
| `apps/api/tests/test_ml_cohorts_pivot_reports.py` | 386, 407 | `"team"` references in billing webhook test → `"studio"` |

### Database Migration

Add an Alembic migration that runs:
```sql
UPDATE users SET plan = 'consultant' WHERE plan = 'pro';
UPDATE users SET plan = 'studio' WHERE plan = 'team';
```

---

## Risks

- **mismatched gates** — if any `require_feature()` check or `PLAN_LIMITS` lookup still references `"pro"` after the rename, free users will be incorrectly blocked or paid users will be incorrectly allowed through
- **wrong upgrade prompts** — billing page checkout call passes plan ID to Stripe; if the ID string is renamed in the frontend but not the Stripe price map in `billing.py`, checkout sessions will fail silently
- **wrong checkout mapping** — `STRIPE_PRO_PRICE_ID` env var must be renamed in both the app config and the deployment environment; a stale env var will cause the Stripe checkout to use the wrong price
- **confusing pricing UI** — if the billing app page still shows `"pro"` while the marketing pricing page says `"Consultant"`, a user who just paid will not recognise their own plan
- **DB migration order** — the Alembic migration must run before the updated application code is deployed; deploying renamed middleware before migrating existing `"pro"` rows will cause those users to fall through to the free-tier fallback until the migration completes
