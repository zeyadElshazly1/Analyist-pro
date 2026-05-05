# Report Builder — Chart Selection QA Checkpoint

Tasks 75K–75O added end-to-end chart selection and reordering to the
Report Builder: auto-selected finance charts, interactive add/remove
toggles, Up/Down reorder controls, and persistence of
`selected_chart_ids` (including order) through HTML and Excel exports.

No frontend test framework (Jest/Vitest) is currently configured.  Run
these scenarios manually when reviewing chart-selection changes, or add
them to a CI test suite when one is introduced.

---

## TypeScript contract (static, verifiable with `npx tsc --noEmit`)

| Symbol | Location | Expected |
|--------|----------|----------|
| `AvailableChart` | `apps/web/src/lib/api.ts` | `export interface` with `chart_id`, `chart_type`, `title`, `selected: boolean` |
| `DraftResponse.available_charts` | same file | `AvailableChart[]` |
| `DraftResponse.selected_chart_ids` | same file | `string[]` |
| `SaveDraftPayload.selected_chart_ids` | same file | `string[] \| undefined` |
| `availableCharts` state | `report-builder.tsx` | `useState<AvailableChart[]>` |
| `selectedChartIds` state | `report-builder.tsx` | `useState<string[]>` |
| `toggleChart` | `report-builder.tsx` | `(chartId: string) => void` |
| `moveChart` | `report-builder.tsx` | `(chartId: string, direction: "up" \| "down") => void` |
| `persistDraft` payload | `report-builder.tsx` | reads `selectedChartIdsRef.current` — never hardcoded `[]` |

Run: `cd apps/web && npx tsc --noEmit` — expect only the pre-existing
`TS5101 baseUrl` deprecation warning, no errors.

---

## Scenario 1 — Finance snapshot: default selected charts appear checked

**Setup:** open or create a project whose analysis run includes a
`charts` block with finance-aware chart IDs (`c_top`, `c_rr`, `c_cls`,
`c_sector`).

**Steps:**
1. Navigate to the project → Report Builder tab.
2. Look at "Charts to include" section.

**Expected:**
- Count row shows `4 / 8 selected` (or the actual auto-selected count).
- `Top assets by return`, `Risk vs return`, `Average return by asset
  class`, `Average return by sector` have the indigo checkbox filled.
- Remaining charts have the dim unchecked checkbox.

---

## Scenario 2 — Uncheck one chart and save

**Steps:**
1. Click `Risk vs return` (currently checked).
2. Checkbox toggles to unchecked; indigo row style returns to dim.
3. Count row updates immediately: `3 / 8 selected`.
4. Saving… / Draft saved indicator fires.

**Expected:**
- `saveDraftReport` is called with `selected_chart_ids: ["c_top", "c_cls", "c_sector"]`
  (or whatever remains after the toggle).
- Live Preview "Selected Charts" section updates instantly to show only
  the three remaining charts.

---

## Scenario 3 — Reopen draft: unchecked chart stays unselected

**Steps:**
1. Refresh the page (or navigate away and back to Report Builder).
2. `GET /reports/draft/{project_id}` is called on mount.

**Expected:**
- `c_rr` (`Risk vs return`) is still unchecked.
- Count row still shows `3 / 8 selected`.
- Backend `available_charts[].selected` for `c_rr` is `false`.

---

## Scenario 4 — Re-check chart and save

**Steps:**
1. Click `Risk vs return` again (currently unchecked).
2. Checkbox fills; count row updates to `4 / 8 selected`.
3. Saving… / Draft saved fires.

**Expected:**
- `saveDraftReport` called with `c_rr` back in `selected_chart_ids`.
- Live Preview re-adds the chart.

---

## Scenario 5 — HTML export includes only selected charts

**Steps:**
1. With `c_rr` deselected (Scenario 2 state), click **Export HTML**.
2. Open the downloaded `.html` file in a browser.

**Expected:**
- "Chart Gallery" section present.
- `Top assets by return`, `Average return by asset class`,
  `Average return by sector` canvases are present.
- `Risk vs return` canvas is **absent**.
- PDF fallback metadata blocks present for selected charts only.

---

## Scenario 6 — XLSX export: Selected Charts sheet reflects selection

**Steps:**
1. Same `c_rr`-deselected state. Click **Export Excel**.
2. Open the workbook → `Selected Charts` sheet.

**Expected:**
- Sheet lists three rows (the selected charts).
- `Risk vs return` row is **absent**.
- "Data Status" column shows `available` for charts that have
  `data.datasets`.

---

## Scenario 7 — Generic dataset with no charts: empty state

**Setup:** a project whose analysis result has no `charts`,
`chart_results`, `suggested_charts`, or `chart_gallery` block.

**Expected:**
- "Charts to include" section shows:
  > No chart suggestions are available for this run yet.
- No checkboxes rendered.
- HTML export has no "Chart Gallery" section.
- XLSX workbook has no "Selected Charts" sheet.

---

## Scenario 8 — Existing insight selection unaffected

**Steps:**
1. Toggle a finding off in "Select findings to include".
2. Toggle a chart in "Charts to include".

**Expected:**
- Both save payloads include the correct `selected_insight_ids` **and**
  `selected_chart_ids` simultaneously.
- Neither toggle clobbers the other's state.

---

## Scenario 9 — Reorder: move second chart above first

**Setup:** two or more charts selected (e.g., `c_top` at position 1,
`c_rr` at position 2).

**Steps:**
1. In "Charts to include", locate the `c_rr` row (second selected chart).
2. Click the **▲ (Move up)** button on that row.

**Expected:**
- `c_rr` jumps to position 1; `c_top` moves to position 2.
- The ▲ button on the new top row (`c_rr`) is now disabled (greyed out).
- The ▼ button on the new bottom row (`c_top`) is disabled if it was last.
- Live Preview "Selected Charts" section reorders immediately.
- Saving… / Draft saved fires.
- `saveDraftReport` called with `selected_chart_ids: ["c_rr", "c_top", ...]`.

---

## Scenario 10 — Reorder: move chart down

**Steps:**
1. Click **▼ (Move down)** on the first selected chart.

**Expected:**
- Chart moves to position 2.
- ▲ button on the new first chart is disabled.
- Draft saves with updated order.

---

## Scenario 11 — Reorder persists through save and reopen

**Steps:**
1. Reorder charts so `c_rr` is first, `c_top` is second.
2. Refresh the page.

**Expected:**
- `GET /reports/draft` returns `selected_chart_ids: ["c_rr", "c_top", ...]`.
- `available_charts[].selected` marks correct entries.
- The "Charts to include" section shows `c_rr` first with ▲ disabled,
  `c_top` second.

---

## Scenario 12 — Reordered charts appear in correct order in HTML export

**Steps:**
1. Set order: `c_rr` first, `c_top` second.
2. Export HTML.

**Expected:**
- "Chart Gallery" section shows `c_rr` canvas **before** `c_top` canvas.

---

## Scenario 13 — Reordered charts appear in correct order in XLSX export

**Steps:**
1. Same `c_rr`-first order. Export Excel.

**Expected:**
- "Selected Charts" sheet row 2 is `c_rr`, row 3 is `c_top`.

---

## Scenario 14 — Boundary: first chart ▲ disabled, last chart ▼ disabled

**Expected:**
- The ▲ button on the first selected row has `disabled` attribute.
- The ▼ button on the last selected row has `disabled` attribute.
- Clicking a disabled button has no effect.

---

## Backend API contract (verifiable with pytest)

```bash
cd apps/api
pytest -q tests/test_default_report_draft.py tests/test_report_draft_export.py
```

Key assertions covered by the existing suite:

| Test class | Behavior locked |
|---|---|
| `TestAvailableCharts` | `available_charts` in draft response, order, `selected` flag |
| `TestApplyDraftSelectedChartIds` | `apply_draft_to_result` stores `selected_chart_ids` |
| `TestResolveSelectedChartPayloads` | Resolution from string/int/dict slots |
| `TestBuildContextSelectedChartPayloads` | Context builder exposes payloads |
| `TestHtmlExportChartGallery` | HTML gallery only shows selected charts |
| `TestExcelChartManifestSheet` | Excel "Selected Charts" sheet content |
| `TestReportBuilderExportParity` | Full pipeline: toggle → draft → HTML + XLSX |
