# Core Workflow

## Primary User Journey

### Step 1: Create Project
User creates a client project/workspace.

### Step 2: Upload Files
User uploads one or more messy client CSV/XLSX files.

### Step 3: Intake Detection
System detects:
- header row
- preamble rows
- footer rows
- encoding issues
- delimiter issues
- likely column names
- file quality warnings

### Step 4: Cleaning Review
System shows:
- renamed columns
- dropped empty columns
- type fixes
- missing value warnings
- duplicate warnings
- suspicious columns
- confidence / assumptions made

### Step 5: Data Health + Profile
User sees:
- row count
- column count
- missingness
- duplicates
- type distribution
- key columns
- semantic column types
- overall health score

### Step 6: Insights + Charts
System generates:
- top findings
- chart suggestions
- trend summaries
- anomalies
- important comparisons
- executive summary draft

### Step 7: File Comparison
User compares:
- current vs previous file
- schema changes
- row count changes
- metric changes
- major deltas

### Step 8: AI Follow-Up
User asks:
- what changed?
- what matters most?
- what should I tell the client?
- what charts should I include?

### Step 9: Report Builder
User selects insights/charts/summary blocks and creates a client-ready report.

### Step 10: Export
User exports:
- PDF
- XLSX
- HTML/shareable report

## Product Rule
Everything in the app should support or strengthen this workflow.
Anything outside this flow is secondary.
