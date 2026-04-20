# Screen Flow V1

## Main Screens

1. Homepage
2. Pricing
3. Login / Signup
4. Projects Dashboard
5. Project Detail
6. Report Builder
7. Billing
8. Settings

## Project Detail Tabs / Steps

### 1. Upload
Purpose:
- upload CSV/XLSX files
- show file status
- start intake process

### 2. Intake Review
Purpose:
- show detected header row
- show preamble/footer detection
- show parsing warnings
- show structure confidence

### 3. Cleaning & Health
Purpose:
- show cleaning actions
- show missing values
- show duplicates
- show suspicious columns
- show health score

### 4. Insights
Purpose:
- show top findings
- show executive summary
- show best charts
- show important patterns

### 5. Compare
Purpose:
- compare current vs previous file
- show metric deltas
- show schema changes
- show major changes

### 6. Report
Purpose:
- assemble selected insights
- assemble charts
- assemble summary
- export polished output

### 7. Power Tools
Purpose:
- advanced tools only
- AI chat
- SQL
- pivots
- extra analysis tools

## UX Rule
The default user path should be:
Upload -> Intake Review -> Cleaning & Health -> Insights -> Compare -> Report

Power tools must be secondary, not primary.

---

## Current Frontend Mapping

### Main Screens

| Screen | Status | Location |
|--------|--------|----------|
| Homepage | ✅ Exists | `app/(marketing)/page.tsx` |
| Pricing | ✅ Exists | `app/(marketing)/pricing/page.tsx` |
| Login | ✅ Exists | `app/(marketing)/login/page.tsx` |
| Signup | ✅ Exists | `app/(marketing)/signup/page.tsx` |
| Projects Dashboard | ✅ Exists | `app/(app)/projects/page.tsx` |
| Project Detail | ✅ Exists | `app/(app)/projects/[id]/page.tsx` |
| Report Builder | ⚠️ Partly exists | `components/project/report-builder.tsx` — component exists, but lives inside the project detail step, not as a standalone screen. No dedicated route. |
| Billing | ✅ Exists | `app/(app)/billing/page.tsx` |
| Settings | ✅ Exists | `app/(app)/settings/page.tsx` |
| Shared report view | ✅ Exists | `app/share/[token]/page.tsx` |

---

### Project Detail Steps

| V1 Step | Status | Current Implementation |
|---------|--------|------------------------|
| **1. Upload** | ✅ Exists | `components/project/upload-dataset.tsx` — rendered in project detail page |
| **2. Intake Review** | ⚠️ Partly exists | `components/project/intake-review.tsx` — component exists but not prominently wired as a required step; shown conditionally after upload |
| **3. Cleaning & Health** | ⚠️ Partly exists | `components/project/cleaning-review.tsx` — component exists; health score and column profiles exist inside the "Health" tab, but cleaning review and health are currently split across two sub-tabs rather than one unified step |
| **4. Insights** | ✅ Exists | "Insights" tab in `project-tabs.tsx` — top findings, charts, time series, correlations, duplicates, outliers are all present |
| **5. Compare** | ⚠️ Partly exists | "Compare" tab group exists in `project-tabs.tsx` with file compare, column compare, and diff runs — but it is buried as a tab group, not surfaced as a primary step |
| **6. Report** | ⚠️ Partly exists | `components/project/report-builder.tsx` exists; "Report" step in tab flow includes AI summary and client summary — but report builder and export are not yet the clear final destination of the workflow |
| **7. Power Tools** | ⚠️ Needs reorganisation | SQL, AutoML, A/B tests, Segments, Pivot, Join are currently in an "Advanced tools" collapsible drawer at the bottom of `project-tabs.tsx` — correct placement but not yet labelled as "Power Tools" |

---

### Summary

| Status | Count | Items |
|--------|-------|-------|
| ✅ Fully exists | 6 | Homepage, Pricing, Login, Signup, Projects Dashboard, Billing, Settings, Shared view |
| ⚠️ Partly exists / needs reorganisation | 5 | Intake Review, Cleaning & Health, Compare, Report, Power Tools |
| ❌ Does not exist | 0 | — |

**Main gap:** all components and pages exist, but the project detail workflow is structured as a flat tab grid rather than a guided linear sequence. The step order, step labels, and progressive reveal are what needs to be built or reorganised — not the underlying components.
