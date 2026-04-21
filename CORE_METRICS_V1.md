# Core Metrics V1

## Goal
Define the few product metrics that actually tell us whether V1 is working.

## Rule
Do not track vanity metrics first.
Track whether users reach value and whether the product becomes part of a real consulting workflow.

## Primary Success Metrics

### 1. Upload to First Insight Rate
Percentage of users who upload a file and successfully reach the insights step.

### 2. Upload to Export Rate
Percentage of users who upload a file and successfully export a report/output.

### 3. Compare Usage Rate
Percentage of active projects that use file comparison.

### 4. Report Builder Usage Rate
Percentage of projects that add at least one item into a report draft.

### 5. Repeat Project Rate
Percentage of users who return and run another project or another file in the same workspace.

### 6. Paid Conversion Trigger Rate
Percentage of free users who hit a paid wall after reaching real value.

## Trust Metrics

### 7. Analysis Failure Rate
How often core workflow analysis fails.

### 8. Export Failure Rate
How often report export fails.

### 9. Low-Confidence Insight Inclusion Rate
How often weak insights are being included by default or mistakenly surfaced too strongly.

## Product Quality Metrics

### 10. Time to First Value
Time from upload to first useful insight/health result.

### 11. Time to Export
Time from upload to finished client-ready output.

## V1 Principle
If users cannot reliably go:
Upload -> Insight -> Compare -> Report -> Export

then the product is not ready, no matter how many features exist.

---

## Current Measurement Audit

### What You Can Already Measure

**Upload events** — `upload.py:153` fires `log_event(action="upload", category="activation")` on every successful file upload. The detail includes `filename`, `size_bytes`, and `file_hash`. You can query: how many users uploaded a file.

**Analysis completed events** — two routes both fire a completion event:
- `analysis.py:134` fires `action="analysis_completed", category="activation"` with `insight_count` in detail
- `analysis_stream.py:285` fires `action="analysis"` (same semantic, different action string — inconsistency to fix)

From these two you can calculate: how many projects reached the insights step after uploading. Combined with upload events this gives you a proxy for **Metric 1 (Upload to First Insight Rate)** — though it requires joining on `user_id` and accounting for the duplicate action names.

**Export completed events** — `reports.py:68` fires `action="export_completed", category="activation"` with the export `format` in detail. Combined with upload events you can calculate **Metric 2 (Upload to Export Rate)**.

**Compare usage events** — `explore.py:173` fires `action="compare_used", category="activation"` when multifile compare runs. You can calculate **Metric 3 (Compare Usage Rate)** by counting `compare_used` per project.

**Report draft created events** — `reports.py:205` fires `action="report_draft_created", category="activation"`. You can calculate **Metric 4 (Report Builder Usage Rate)** from this.

**All activation events have a common category tag** — all five events above use `category="activation"`, so the query `SELECT action, COUNT(*) FROM audit_logs WHERE category='activation' GROUP BY action` gives you a funnel view immediately.

---

### What You Cannot Measure Yet

**Metric 5 — Repeat Project Rate**
No event is fired when a user creates a second project, runs a second analysis on an existing project, or uploads a new file to the same workspace. You can approximate it by querying `AnalysisResult` rows per `project_id` per `user_id` (via project join), but there is no direct `user_returned` or `repeat_analysis` event.

**Metric 6 — Paid Conversion Trigger Rate**
`middleware/plans.py` raises HTTP 402 when a free user hits a plan wall, but `require_feature()` does not call `log_event`. There is no record of which users hit which plan gates, how many times, or at what point in their session. You cannot calculate what percentage of free users hit a paywall after reaching real value, or which feature triggers upgrades most.

**Metric 7 — Analysis Failure Rate**
`analysis_stream.py:291` catches exceptions and logs them with `logger.error()` — a server log, not an audit event. No `action="analysis_failed"` event is written to the `audit_logs` table. Only successful runs are recorded. You cannot calculate failure rate from the database.

**Metric 8 — Export Failure Rate**
`reports.py:103` raises `HTTPException(status_code=500)` on PDF failure but writes no audit event for the failure. Only `export_completed` on success is logged. Same gap as analysis failures — no failure events in `audit_logs`.

**Metric 9 — Low-Confidence Insight Inclusion Rate**
There is no confidence threshold filtering in `analysis_stream.py` or `analysis.py`. All insights are passed through regardless of their `confidence` value. No event records whether a low-confidence insight was surfaced. There is no concept of "weak insight included" anywhere in the logging layer.

**Metric 10 — Time to First Value**
`AnalysisResult` has a `created_at` (completion timestamp) but no `started_at`. `upload.py` logs an upload event with its own timestamp. Joining those two records would give a rough upload-to-completion time, but it is fragile (two separate event rows, no shared session or request ID to join on). There is no single `duration_seconds` field anywhere.

**Metric 11 — Time to Export**
Same gap as Metric 10 — no `started_at` on the analysis, and no timestamp on when the report builder was opened. You could approximate upload-to-export by joining the `upload` event timestamp to the `export_completed` event timestamp per user per project, but this is a multi-row join with no guaranteed ordering.

---

### What Events and Logging to Add Later

| Missing Signal | Where to Add It | What to Log |
|----------------|-----------------|-------------|
| Analysis failure | `analysis_stream.py` except block at line 291 | `action="analysis_failed"`, `category="trust"`, `detail={"stage": <step name>, "error": str(e)[:200]}` |
| Export failure | `reports.py` except block around PDF/XLSX generation | `action="export_failed"`, `category="trust"`, `detail={"format": fmt, "error": str(e)[:200]}` |
| Plan wall hit | `middleware/plans.py` inside `require_feature()` before raising 402 | `action="plan_gate_hit"`, `category="monetization"`, `detail={"feature": feature, "current_plan": plan}` |
| Repeat analysis | `analysis_stream.py` after writing `AnalysisResult` | `action="repeat_analysis"` when `project` already has ≥1 prior `AnalysisResult` row |
| Analysis started_at | `AnalysisResult` model in `models.py` | Add `started_at = Column(DateTime)` written at pipeline entry, before any processing |
| Analysis duration | `analysis_stream.py` at completion | Add `duration_seconds` to the `analysis` audit event detail |
| Insight confidence summary | `analysis_stream.py` when insights are written | Add `low_confidence_count` (insights with confidence < 0.5) to the `analysis` event detail |
| Action name deduplication | `analysis.py:134` | Change `action="analysis_completed"` to `action="analysis"` to match `analysis_stream.py`, or vice versa — pick one name and use it everywhere |
