# Power Tools Boundary

## Goal
Keep advanced features available without letting them dilute the core product.

## Problem
If advanced tools are treated like the main product, the app feels scattered and harder to trust.

## Rule
Power tools should support the core workflow, not compete with it.

## Core Workflow Comes First
1. Upload
2. Intake Review
3. Cleaning & Health
4. Insights
5. Compare
6. Report

## Power Tools
- AI chat
- SQL query
- pivots
- feature engineering
- advanced joins
- extra explore tools
- stats tools
- AutoML tools

## Product Rule
A new user should understand the product before they ever need Power Tools.

## UX Rule
Power Tools should be:
- secondary in navigation
- visually separated
- optional
- framed as advanced extensions

## Build Rule
No Power Tool should be improved before the core workflow is trustworthy and polished.

## Decision Filter
For each advanced feature, ask:
- does it help the consultant finish client work faster?
- does it improve trust?
- does it improve report delivery?
- does it improve compare workflow?
- does it improve monetization?

If not, it should stay low priority.

---

## Current Power Tools Audit

### Which Features Belong in Power Tools

These features are correctly classified as advanced extensions and currently live inside the "Advanced tools" collapsible drawer in `project-tabs.tsx` (`ADVANCED_TABS` array, lines 69–76):

| Feature | Tab ID | Backend Route |
|---------|--------|---------------|
| SQL query | `query` | `POST /query/execute`, `GET /query/schema` |
| AutoML | `predictions` | `POST /ml/train`, `POST /ml/predict/{id}`, `GET /ml/model-info/{id}` |
| A/B tests | `ab-tests` | *(no dedicated route — rendered client-side)* |
| Segments | `segments` | `POST /cohorts/rfm`, `POST /cohorts/retention` |
| Pivot table | `pivot` | `POST /pivot/run`, `GET /pivot/columns` |
| Join datasets | `join` | *(dataset merge — rendered client-side)* |

These belong in Power Tools and are already behind the drawer. They do not need to move.

**Also belongs in Power Tools but not yet listed in the drawer:**
- Feature engineering (`POST /features/create`, `GET /features/suggest`) — exists as a backend route and frontend component (`features.py`, imported in `run-analysis.tsx` as implied by the route) but has no tab in `ADVANCED_TABS`. It is either orphaned or accessed by direct navigation only.
- Statistical tests (`POST /stats/test`, `POST /stats/power`, `GET /stats/columns`) — `stats.py` route exists with no plan gate and no tab entry in the drawer. It is accessible via API but has no UI surface — effectively hidden by accident, not by design.

---

### Which Ones Are Accidentally Too Prominent Right Now

**Time series, Correlations, Duplicates, Outliers** — these four are sub-tabs under the Insights step (`STEPS[2].tabs`, `project-tabs.tsx` lines 37–45). They sit at the same visual level as "Top findings" and "Charts," which are the primary insight outputs a consultant needs. A new user opening the Insights step sees six sub-tabs at once. Time series, correlations, duplicates, and outliers are exploratory tools — useful when the user wants to dig deeper, not as front-line outputs in a consultant workflow.

**Compare columns** (`compare-cols`) — sits as a peer sub-tab alongside "Compare files" and "Diff runs" in the Compare step (`STEPS[3].tabs`, lines 51–55). Column-vs-column statistical comparison (Pearson, Spearman, ANOVA, Chi-square) is an analyst tool, not a consultant deliverable tool. It is prominently positioned next to the compare features a consultant actually needs.

**Ask AI / Copilot** is the `primaryTab` of the Report step (`STEPS[4]`, line 61) — meaning clicking "Report" in the step bar drops the user directly into the AI chat view, not a report builder. A consultant clicking "Report" expects to build a report, not open a chat window. The chat is a power tool framed as the primary report experience.

---

### Which Ones Should Stay Visible but Secondary

**AI chat (`ask-ai`)** — useful for consultants who want to ask follow-up questions about the data after reviewing findings. Should stay accessible within the Report step but should not be the `primaryTab`. The report draft builder should be the landing view; AI chat should be a secondary sub-tab.

**Diff runs** (`diff`) — comparing two analysis run outputs (health delta, new/resolved insights, column changes) is relevant to recurring client work. It belongs in the Compare step as a sub-tab, where it already is. It should stay visible but is correctly secondary to "Compare files."

**Client summary** (`story`) — the AI-generated 5-slide narrative. Useful as a supporting output inside the Report step. Should stay as a sub-tab there. Not a replacement for the report builder, but a valid secondary action.

**Charts** (`charts`) — the chart recommendations panel within the Insights step. Stays visible as a sub-tab. Consultants who want to pick charts for their report need it. It is correctly positioned behind "Top findings."

---

### Which Ones Should Be Hidden for Now

**A/B tests** (`ab-tests`) — no backend route exists for this. The frontend renders a view but there is no `ab_tests.py` route file and no plan gate. It is either a stub or routes through a generic endpoint. It does not serve the consultant workflow, has no clear paid value, and should not be surfaced to users until there is a real implementation behind it.

**AutoML** (`predictions`) — `ml.py` is fully implemented (train, predict, model info), but the feature requires understanding of ML concepts (target column selection, model type, feature importance) that most consultants do not have. It is the feature least aligned with the consultant-workflow target audience. It is already in the drawer, but should also be de-emphasized within the drawer — listed last, not first.

**Cohorts / Segments** (`segments`) — RFM cohort analysis and retention cohorts are marketing-analytics tools. Useful for e-commerce and product teams, not for the general-purpose consultant file review workflow. Already in the drawer, correctly hidden from primary navigation. No change needed, but no investment should go here before core workflow is solid.

**Statistical tests** (`stats`) — `POST /stats/test` and `POST /stats/power` are exposed on the backend with no plan gate and no UI tab. They are effectively invisible to users. This is fine for now — they should stay invisible until there is a clear use case for consultants that cannot be served by the health score and insight outputs.

**Feature engineering** (`features`) — `POST /features/create` and `GET /features/suggest` exist on the backend with no plan gate. There is no tab entry in `ADVANCED_TABS` in `project-tabs.tsx`. Like stats, the feature is accessible via API but has no UI surface. It should stay hidden until the core pipeline's cleaning and profiling outputs are fully trusted by users — building on top of a pipeline users don't yet trust will not drive adoption.
