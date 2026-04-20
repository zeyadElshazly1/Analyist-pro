# Pricing Plan Alignment

## Goal
Use one consistent plan structure across:
- frontend
- backend
- Stripe
- middleware
- pricing page
- upgrade prompts

## Recommended Plans

### Free
For trying the product.

### Consultant
Main paid plan for solo consultants and freelancers.

### Studio
Plan for small teams/agencies.

## Rule
Do not mix names like:
- Pro
- Team
- Consultant
- Studio

Pick one system and use it everywhere.

## Current Recommended Naming
- Free
- Consultant
- Studio

## What Must Match
- pricing page labels
- backend plan enums/constants
- Stripe product names
- access-control middleware
- feature gates
- account/billing screens
- upgrade CTAs
- onboarding copy

## Why This Matters
Inconsistent pricing names make the product feel unfinished and lower trust.

---

## Current Usage Audit

### "free"
Already consistent. Used everywhere as the default/free tier.

| File | Lines | Context |
|------|-------|---------|
| `apps/api/app/middleware/auth.py` | 137 | New user created with `plan="free"` |
| `apps/api/app/middleware/plans.py` | 35, 85, 105, 126 | `PLAN_LIMITS["free"]` key + fallback |
| `apps/api/app/models.py` | 33 | `User.plan` column default + comment |
| `apps/api/app/routes/billing.py` | 117 | Subscription cancelled → reset to `"free"` |
| `apps/api/app/routes/upload.py` | 68 | Error response `current_plan` fallback |
| `apps/api/tests/conftest.py` | 138 | `pro_auth_headers` fixture upgrades from free |
| `apps/api/tests/test_health_and_projects.py` | 22 | `assert body["plan"] == "free"` |
| `apps/api/tests/test_ml_cohorts_pivot_reports.py` | 407 | `assert u.plan == "free"` after webhook |
| `apps/web/src/app/(app)/billing/page.tsx` | 13, 100, 131, 134, 289 | Plan id, copy, conditional UI |
| `apps/web/src/app/(app)/settings/page.tsx` | 198 | `user?.plan === "free"` upgrade banner |
| `apps/web/src/components/layout/app-sidebar.tsx` | 77 | Sidebar upgrade banner condition |

---

### "pro" — INCONSISTENT: should be "consultant"

| File | Lines | Context |
|------|-------|---------|
| `apps/api/app/middleware/plans.py` | 43 | `PLAN_LIMITS["pro"]` key |
| `apps/api/app/models.py` | 33 | Comment `free \| pro \| team` |
| `apps/api/app/routes/billing.py` | 35, 109, 123, 137, 152 | Stripe price map, default plan fallback, env var `STRIPE_PRO_PRICE_ID` |
| `apps/api/tests/conftest.py` | 138 | `user.plan = "pro"` in `pro_auth_headers` fixture |
| `apps/api/tests/test_ml_cohorts_pivot_reports.py` | 386 | `u.plan = "pro"` direct DB write |
| `apps/web/src/app/(app)/billing/page.tsx` | 29, 87 | Plan `id: "pro"`, checkout guard `planId !== "pro"` |
| `apps/web/src/lib/api.ts` | 944 | `createCheckoutSession(plan: "pro" \| "team")` type |

---

### "team" — INCONSISTENT: should be "studio"

| File | Lines | Context |
|------|-------|---------|
| `apps/api/app/middleware/plans.py` | 51 | `PLAN_LIMITS["team"]` key |
| `apps/api/app/models.py` | 33 | Comment `free \| pro \| team` |
| `apps/api/app/routes/billing.py` | 36, 138, 152 | Stripe price map, env var `STRIPE_TEAM_PRICE_ID`, type annotation |
| `apps/api/app/routes/team.py` | 26, 31, 32 | `user.plan != "team"` gate |
| `apps/api/tests/test_ml_cohorts_pivot_reports.py` | 386, 407 | Billing webhook plan reset test |
| `apps/web/src/app/(app)/billing/page.tsx` | 48, 87, 247 | Plan `id: "team"`, checkout guard, CTA branch |
| `apps/web/src/app/(app)/team/page.tsx` | 144, 199 | `user?.plan === "team"` gate |
| `apps/web/src/components/layout/app-sidebar.tsx` | 52 | Team nav link condition |

---

### "Consultant" — marketing page only (correct name, wrong scope)

| File | Lines | Context |
|------|-------|---------|
| `apps/web/src/app/(marketing)/pricing/page.tsx` | 25, 28, 51, 76, 141 | Pricing page plan label and copy |

---

### "Studio" — marketing page only (correct name, wrong scope)

| File | Lines | Context |
|------|-------|---------|
| `apps/web/src/app/(marketing)/pricing/page.tsx` | 43 | Pricing page plan label |

---

## Summary of Work Needed

The marketing pricing page already uses `Consultant` / `Studio`. Every other layer still uses `pro` / `team`. To fully align:

1. Rename `"pro"` → `"consultant"` in `plans.py`, `models.py`, `billing.py`, `billing/page.tsx`, `api.ts`, tests
2. Rename `"team"` → `"studio"` in `plans.py`, `models.py`, `billing.py`, `team.py`, `team/page.tsx`, `billing/page.tsx`, `app-sidebar.tsx`, `api.ts`, tests
3. Update Stripe env var names: `STRIPE_PRO_PRICE_ID` → `STRIPE_CONSULTANT_PRICE_ID`, `STRIPE_TEAM_PRICE_ID` → `STRIPE_STUDIO_PRICE_ID`
4. Add a DB migration to rename existing user plan values
