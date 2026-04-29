# Launch Hardening QA Pass

## Goal
Run a focused QA and hardening pass on the consultant workflow before demo mode and pilot outreach.

## Rule
Do not add major new features in this phase.
Fix breakage, tighten trust, and remove launch-risk.

## QA Areas

### 1. Upload + Intake
Check:
- file upload succeeds
- intake_result renders correctly
- warnings display correctly
- preview sample renders correctly
- low-confidence parse is visible

### 2. Cleaning Review
Check:
- cleaning_result renders correctly
- grouped sections show correctly
- suspicious columns appear
- duplicate/missingness notes appear
- empty states do not look broken

### 3. Health Check
Check:
- health_result renders correctly
- grade/verdict match score
- warnings group correctly
- affected columns render correctly
- client-readiness notes make sense

### 4. Findings
Check:
- insight_results render correctly
- report-safe findings are separated correctly
- review-needed findings are separated correctly
- informational findings collapse correctly
- recommendations and caveats render correctly

### 5. Compare
Check:
- compare_result renders correctly
- summary draft appears
- caution flags appear
- row delta, schema changes, and metric deltas render correctly
- compare data flows into report builder

### 6. Build Report
Check:
- report draft loads correctly
- autosave works
- selected findings persist
- summary edits persist
- report prep summary is accurate
- weak-report guidance appears only when appropriate

### 7. Export
Check:
- HTML export works
- Excel export works
- PDF success/failure is honest
- PDF unavailable state is understandable
- export history strip updates correctly
- preview structure matches export structure

### 8. Reopen Flow
Check:
- latest_run resolves correctly
- previous analysis opens without rerun
- stored results populate all major tabs
- profile tab works on reopened runs
- report builder loads stored content correctly

### 9. Run Lifecycle
Check:
- run created on sync analysis
- run created on streaming analysis
- statuses update correctly
- failed runs store error_summary
- latest-run resolver picks the correct run

### 10. Pricing / Billing
Check:
- pricing page labels are canonical
- upgrade prompts use canonical names
- checkout only accepts canonical plans
- middleware gates behave correctly
- team/studio gating text is correct

## Bug Triage Labels
- P0 = blocks demo / pilot
- P1 = hurts trust or core workflow
- P2 = polish issue
- P3 = cleanup later

## Output Format
For each issue found, log:
- area
- issue
- severity
- repro steps
- expected behavior
- actual behavior
- fix needed
- status

## Exit Condition
We should finish this pass knowing:
- what is safe for demo
- what must be fixed before pilot users
- what can wait until after first customer feedback

---

## Issues Log

<!-- Issues will be filled in during the QA pass -->

