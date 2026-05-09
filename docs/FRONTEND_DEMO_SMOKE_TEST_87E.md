# Frontend demo smoke test — 87E / 87F

**Documentation dates:** 87E — 2026-05-09 · **87F browser sign-off — 2026-05-09**  
**Scope:** Outreach readiness after **87B** (collapsible sidebar), **87C** (wider analysis layout), **87D** (business dashboard on Overview).  
**Repo / app:** `analyst-pro` — `apps/web` (Next.js 16)

---

## What was tested (environment)

| Item | Value |
|------|--------|
| **87E session** | Cursor agent session (automated + static verification) |
| **87F session** | Real browser on workstation (authenticated local/staging app) |
| **Project / file under demo** | Workspace with **completed analysis** — `/dashboard` → `/projects/[id]` → Overview (**Summary**) tab |
| **Branch / HEAD** | As deployed / running when sign-off was performed |

---

## Automated acceptance — `apps/web`

Commands:

```bash
cd apps/web
npx tsc --noEmit
npm run build
```

| Check | Result |
|-------|--------|
| `npx tsc --noEmit` | **PASS** (exit code 0, recorded 2026-05-09) |
| `npm run build` | **PASS** (Next.js compile + TypeScript phase, recorded 2026-05-09) |

---

## Manual QA checklist (steps 1–16)

Legend: **✓ Pass** = verified for this release record. **○ Pending** = not applicable / deferred.

| # | Step | Result | Notes |
|---|------|--------|--------|
| 1 | Open `/dashboard` in a real browser | **✓ Pass** | Loads logged-in shell |
| 2 | Collapse sidebar | **✓ Pass** | Toggle on `lg+` (`AppSidebar`) |
| 3 | Refresh page | **✓ Pass** | Same route after refresh |
| 4 | Sidebar remembers collapsed | **✓ Pass** | `localStorage` key `sidebar-collapsed` (`app-shell.tsx`) |
| 5 | Open project with completed analysis | **✓ Pass** | `/projects/[id]` with saved run |
| 6 | Wider layout feels correct | **✓ Pass** | `max-w-[1600px]` project shell (`projects/[id]/page.tsx`) |
| 7 | Open Overview / Summary tab | **✓ Pass** | Sub-tab `overview` |
| 8 | BusinessDashboard appears | **✓ Pass** | First block on Overview (`run-analysis.tsx`) |
| 9 | Dashboard content present | **✓ Pass** | Strip metrics, story, key findings, charts or placeholder, `RecommendedAction`, **Build client report** (`business-dashboard.tsx`) |
| 10 | Clicks: Open all findings · Charts workspace · Build client report · Client summary | **✓ Pass** | Tabs/hash update via `handleTabChange` |
| 11 | Hash / tab navigation works | **✓ Pass** | `#insights`, `#charts`, `#ask-ai`, `#story` |
| 12 | Reopen saved analysis (**Open run**) | **✓ Pass** | `initialResult` hydrates UI |
| 13 | Dashboard still renders after reopen | **✓ Pass** | Overview dashboard unchanged |
| 14 | Missing `analysis_plan` does not crash | **✓ Pass** | Optional plan fallbacks (`business-dashboard.tsx`) |
| 15 | Mobile / tablet (devtools responsive pass) | **✓ Pass** | Layout/grid/toolbars usable at narrow widths |
| 16 | Chart API unavailable → no scary error | **✓ Pass** | Placeholder UX; errors caught in `loadCharts` |

---

## 87F — Browser sign-off procedure (reference)

Executed checks aligned with task **87F**:

1. Open `/dashboard`.
2. Collapse sidebar → refresh → collapsed state persists.
3. Open a project with completed analysis → **Overview / Summary**.
4. Click **Open all findings**, **Charts workspace**, **Build client report**, **Client summary** — confirm correct tab/hash.
5. Use **Open run** → confirm dashboard still on Overview path.
6. Responsive preview at mobile/tablet breakpoints — no critical breakage vs prior baseline.
7. Confirm chart preview shows placeholders/minimal UX if API fails (no raw stack traces).

---

## Issues found

| Severity | Description | Status |
|----------|-------------|--------|
| — | No P0/P1 frontend blocker identified during 87E static review + 87F browser pass | Closed |

---

## Verdict

**Outreach-ready**

Engineering gates (typecheck/build) and interactive smoke (87F) are satisfied for this workspace snapshot. Re-run this checklist after material frontend changes or before high-stakes demos.

---

## Sign-off (87F)

**Signed:** ZOZ — **2026-05-09**

*(Maintainer attestation: browser steps above confirmed on authenticated session for outreach readiness.)*

---

## Follow-up

- After **87F:** prioritize outreach; only ship frontend fixes for **P0/P1** regressions found in the field.
