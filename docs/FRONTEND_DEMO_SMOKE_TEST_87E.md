# Frontend demo smoke test — 87E

**Date:** 2026-05-09  
**Scope:** QA + documentation for outreach readiness after **87B** (collapsible sidebar), **87C** (wider analysis layout), **87D** (business dashboard on Overview).  
**Repo / app:** `analyst-pro` — `apps/web` (Next.js 16)

---

## What was tested (environment)

| Item | Value |
|------|--------|
| **Machine / session** | Cursor agent session (Windows); no production deploy gate |
| **Project / file under demo** | *Substitute your workspace:* any authenticated project with a completed analysis (e.g. local demo CSV after **Analyze File**, or **Open run** on saved analysis) |
| **Branch / HEAD** | Working tree as exercised during 87E smoke recording |

---

## Automated acceptance — `apps/web`

Commands (from repo root or `apps/web`):

```bash
cd apps/web
npx tsc --noEmit
npm run build
```

| Check | Result |
|-------|--------|
| `npx tsc --noEmit` | **PASS** (exit code 0, 2026-05-09) |
| `npm run build` | **PASS** (Next.js 16.2.4 compile + TypeScript phase succeeded, 2026-05-09) |

---

## Manual QA checklist (steps 1–16)

Legend: **✓ Pass** = verified in this session (browser or static verification). **○ Pending** = requires human pass in a real browser before calling outreach “fully signed off.”

| # | Step | Result | Notes |
|---|------|--------|--------|
| 1 | Open dashboard | ○ Pending | `/dashboard` — confirm loads logged-in |
| 2 | Collapse sidebar | ○ Pending | Toggle on `lg+` layout (`AppSidebar`) |
| 3 | Refresh page | ○ Pending | Same route after hard refresh |
| 4 | Sidebar remembers collapsed | **✓ Pass** (static) | `AppShell` reads/writes `localStorage` key `sidebar-collapsed` on mount + toggle (`apps/web/src/components/layout/app-shell.tsx`) |
| 5 | Open project with completed analysis | ○ Pending | `/projects/[id]` after run or **Open run** |
| 6 | Wider layout feels correct | **✓ Pass** (static) | Project shell uses `max-w-[1600px]` + horizontal padding (`apps/web/src/app/(app)/projects/[id]/page.tsx`) |
| 7 | Open Overview / Summary tab | ○ Pending | Step sub-tab `overview` under Intake step cluster |
| 8 | BusinessDashboard appears | **✓ Pass** (static) | Rendered first in Overview inside `RunAnalysis` (`apps/web/src/components/project/run-analysis.tsx`) |
| 9 | Dashboard content present | **✓ Pass** (static) | Strip + story + key findings + charts block + `RecommendedAction` + CTAs implemented (`business-dashboard.tsx`): dataset kind, classification/confidence, health, shape, findings count, report-ready count, story, findings board, chart previews or placeholder, recommended actions, **Build client report** |
| 10 | Clicks: Open all findings / Charts workspace / Build client report / Client summary | **✓ Pass** (static) | All call `onNavigateToTab` → `handleTabChange` updates tab + `history.replaceState` hash (`run-analysis.tsx`) |
| 11 | Hash / tab navigation works | **✓ Pass** (static) | Tab ↔ `#hash` sync preserved |
| 12 | Reopen saved analysis | ○ Pending | **Open run** on project page loads `initialResult` |
| 13 | Dashboard still renders after reopen | **✓ Pass** (static) | Same `RunAnalysis` tree when `initialResult` set |
| 14 | Missing `analysis_plan` does not crash | **✓ Pass** (static) | `datasetKindDisplay` / `planOrInsightsConfidence` guard optional plan (`business-dashboard.tsx`) |
| 15 | Mobile / tablet does not regress | ○ Pending | Responsive grids/toolbars present in dashboard + project layout; **visual** confirmation recommended |
| 16 | No scary chart-preview error if chart API unavailable | **✓ Pass** (static) | `getSuggestedCharts` errors caught; empty charts + dashed placeholder (401 avoids error flag); no stack trace UI (`business-dashboard.tsx` `loadCharts`) |

---

## Issues found

| Severity | Description | Status |
|----------|-------------|--------|
| — | No P0/P1 frontend blocker identified in code review + build | — |
| Note | Steps marked **○ Pending** need a single human pass on a running dev/staging URL | Tracking |

---

## Verdict

**Ready with notes**

**Rationale:** Automated TypeScript and production build are green. Implementation review covers sidebar persistence, Overview dashboard composition, safe handling of missing `analysis_plan`, chart API failure UX, and hash-driven navigation. Browser-only steps (dashboard click-through, reopen saved run, mobile/tablet visual pass) are explicitly left for a quick human sign-off before external outreach.

To upgrade verdict to **Outreach-ready**, complete all **○ Pending** rows in the table above on your target environment and initial here: _______________

---

## Follow-up

- After 87E: either begin outreach or fix **only** frontend P0/P1 blockers found during the pending browser pass.
