# Plan Name Refactor Checklist

## Goal
Convert all plan naming to one canonical system without breaking billing or access control.

## Canonical Names
- Free
- Consultant
- Studio

## Checklist

### 1. Frontend Labels
- [ ] pricing page updated
- [ ] upgrade modals updated
- [ ] billing/settings screens updated
- [ ] onboarding copy updated
- [ ] any badge/tag/CTA copy updated

### 2. Backend Constants / Enums
- [ ] canonical plan constants defined
- [ ] old names mapped or removed
- [ ] feature gates updated
- [ ] middleware checks updated
- [ ] default/fallback plan logic reviewed

### 3. Billing / Stripe
- [ ] Stripe product names mapped
- [ ] checkout plan mapping reviewed
- [ ] webhook handling reviewed
- [ ] billing portal display names reviewed

### 4. Database / Stored Values
- [ ] check whether old plan names are persisted
- [ ] decide migration strategy if needed
- [ ] define backward-compat handling if needed

### 5. QA Checks
- [ ] free user sees correct limits
- [ ] Consultant user gets correct access
- [ ] Studio user gets correct access
- [ ] upgrade prompts show correct names
- [ ] checkout sends user to correct paid plan

## Risk Notes
- do not break existing paid access
- do not mismatch UI names and backend names
- do not rename things in copy only while leaving logic unchanged

---

## Recommended Update Order

1. **Write and run the Alembic DB migration first**
   Before any code change, update stored plan values in the `users` table:
   ```sql
   UPDATE users SET plan = 'consultant' WHERE plan = 'pro';
   UPDATE users SET plan = 'studio' WHERE plan = 'team';
   ```
   This must happen before the new code is deployed. If the migration runs after, any existing paid user with `plan = "pro"` will fall through to the free-tier fallback in `PLAN_LIMITS` the moment the renamed middleware goes live. File: create a new migration in `apps/api/alembic/versions/`.

2. **Update `apps/api/app/middleware/plans.py`** (lines 43, 51)
   Rename `PLAN_LIMITS["pro"]` → `PLAN_LIMITS["consultant"]` and `PLAN_LIMITS["team"]` → `PLAN_LIMITS["studio"]`. This is the single enforcement point for all feature gates and project limits. Updating it second — immediately after the DB migration — means the new code matches the newly migrated DB values from the first request onward. No user will see a gap.

3. **Update `apps/api/app/routes/billing.py` + `team.py` + `models.py` + env vars**
   Rename all remaining backend `"pro"` and `"team"` strings atomically in the same commit as Step 2:
   - `billing.py` lines 35–36: Stripe price map keys `"pro"` → `"consultant"`, `"team"` → `"studio"`
   - `billing.py` lines 109, 123, 137, 138, 152: plan string defaults and fallbacks
   - `billing.py` env var references: `STRIPE_PRO_PRICE_ID` → `STRIPE_CONSULTANT_PRICE_ID`, `STRIPE_TEAM_PRICE_ID` → `STRIPE_STUDIO_PRICE_ID`
   - `team.py` lines 26, 31, 32: gate `user.plan != "team"` → `user.plan != "studio"`
   - `models.py` line 33: update the comment `free | pro | team` → `free | consultant | studio`
   - `.env` and `.env.example`: rename the two Stripe env var keys
   Steps 2 and 3 should ship in one commit so middleware and billing are never out of sync with each other.

4. **Update frontend: `billing/page.tsx`, `team/page.tsx`, `app-sidebar.tsx`, `api.ts`**
   With backend enforcement already correct, frontend is display-only at this point — a mismatch here is cosmetic, not a billing or access failure. Update plan `id` strings in `billing/page.tsx` (lines 29, 48, 87, 247), gate conditions in `team/page.tsx` (lines 144, 199) and `app-sidebar.tsx` (line 52), and the TypeScript type annotation in `api.ts` (line 944). Verify the billing page now shows "Consultant" and "Studio" labels end-to-end.

5. **Update tests and run the full test suite**
   Update `conftest.py` line 138 (`user.plan = "pro"` → `"consultant"`), `test_ml_cohorts_pivot_reports.py` lines 386 and 407 (`"pro"` → `"consultant"`, `"team"` → `"studio"`). Run `pytest` to confirm all plan-gated tests pass with the new names. Verify the billing webhook test correctly resets to `"free"` and the pro fixture correctly grants `"consultant"` access. This is the final gate before shipping.
