import type { CompareResult } from "./api";

// ── Demo fixture: Acme Retail – November 2024 Sales ───────────────────────────
// Used by the /demo page to show a fully-populated 6-step workflow without
// requiring a real file upload or live analysis run.

export const DEMO_RESULT = {
  analysis_id: 0,
  run_id: 0,

  dataset_summary: {
    rows: 847,
    columns: 12,
    numeric_cols: 4,
    categorical_cols: 7,
    missing_pct: 2.1,
  },

  // ── Canonical health block ─────────────────────────────────────────────────
  health_result: {
    health_score: {
      total_score: 74,
      grade: "B",
      breakdown: {
        completeness: 78,
        uniqueness: 82,
        consistency: 71,
        validity: 80,
        structure: 59,
      },
    },
    health_warnings: [
      { severity: "medium", message: "8.4% of rows have missing region values" },
      { severity: "low", message: "customer_id has format variations (numeric vs. alphanumeric)" },
    ],
  },

  // Legacy top-level health_score for components that read it directly
  health_score: {
    total: 74,
    score: 74,
    grade: "B",
    label: "Good",
    color: "#4f46e5",
    breakdown: {
      completeness: 78,
      uniqueness: 82,
      consistency: 71,
      validity: 80,
      structure: 59,
    },
    deductions: [
      "8.4% missing values in region column",
      "customer_id format inconsistency",
    ],
  },

  // ── Canonical cleaning block ───────────────────────────────────────────────
  cleaning_result: {
    renamed_columns: [
      { original: "Cust ID", cleaned: "customer_id" },
      { original: "Rev $", cleaned: "revenue" },
    ],
    dropped_columns: [],
    type_fixes: [
      { column: "order_date", to_dtype: "datetime", n_values_converted: 847 },
    ],
    missingness_notes: [
      {
        column: "region",
        missing_count: 71,
        missing_pct: 8.4,
        mechanism: "MCAR",
        strategy_applied: "safe_suggestion",
      },
    ],
    duplicate_notes: {
      duplicate_rows_found: 12,
      duplicate_rows_removed: 12,
      removed: true,
    },
    suspicious_columns: [
      {
        column: "customer_id",
        issue_type: "format_variation",
        detail: "Values mix numeric IDs and alphanumeric codes (e.g. '1042' and 'CUST-1042')",
      },
    ],
    cleaning_summary: { steps_applied: 5 },
  },

  // ── Column profiles ────────────────────────────────────────────────────────
  profile_result: [
    {
      column: "order_date",
      type: "datetime",
      dtype: "datetime",
      missing: 0,
      missing_pct: 0,
      unique: 30,
      unique_pct: 3.5,
      flags: [],
    },
    {
      column: "customer_id",
      type: "text",
      dtype: "text",
      missing: 0,
      missing_pct: 0,
      unique: 148,
      unique_pct: 17.5,
      flags: ["format_variation"],
    },
    {
      column: "revenue",
      type: "numeric",
      dtype: "float",
      missing: 3,
      missing_pct: 0.35,
      unique: 831,
      unique_pct: 98.1,
      flags: [],
      mean: 146.8,
      median: 98.5,
      std: 211.3,
      min: 4.99,
      max: 2840.0,
    },
    {
      column: "region",
      type: "text",
      dtype: "text",
      missing: 71,
      missing_pct: 8.4,
      unique: 6,
      unique_pct: 0.7,
      flags: ["high_missing"],
    },
    {
      column: "discount_pct",
      type: "numeric",
      dtype: "float",
      missing: 0,
      missing_pct: 0,
      unique: 8,
      unique_pct: 0.9,
      flags: [],
      mean: 12.4,
      median: 10.0,
      std: 8.7,
      min: 0.0,
      max: 30.0,
    },
  ],

  // ── Insights (canonical + legacy fields populated for full compatibility) ──
  insights: [
    {
      insight_id: "demo-1",
      title: "Revenue declined 12% vs prior 3-month average",
      category: "trend",
      type: "trend",
      explanation: "Total revenue for November ($124,300) is 12.1% below the Q3 average ($141,400). The decline accelerated in the final week, with the last 7 days contributing only 18% of monthly revenue vs a typical 27%.",
      finding: "Total revenue for November ($124,300) is 12.1% below the Q3 average ($141,400).",
      recommendation: "Investigate Q4 pipeline velocity — check whether deals slipped to December or were lost.",
      action: "Review late-month deal velocity and compare with Q3 close rates.",
      columns_used: ["revenue", "order_date"],
      method_used: "trend_analysis",
      report_safe: true,
      severity: "high",
      confidence: 91,
      evidence: "3-month rolling avg: $141,400 · November: $124,300",
    },
    {
      insight_id: "demo-2",
      title: "Top 3 customers account for 68% of total revenue",
      category: "concentration",
      type: "pattern",
      explanation: "Acme Corp ($42,100), Bright Future LLC ($25,800), and Metro Group ($17,300) together represent 68% of November revenue. Loss of any one account would materially impact the bottom line.",
      finding: "3 customers = 68% of revenue. High concentration risk.",
      recommendation: "Flag in client summary. Review account health and renewal pipeline for the top 3.",
      action: "Add customer concentration chart to report. Confirm renewal status of top accounts.",
      columns_used: ["customer_id", "revenue"],
      method_used: "pareto_analysis",
      report_safe: true,
      severity: "high",
      confidence: 97,
      evidence: "Top 3 revenue: $85,200 / Total: $124,300 = 68.5%",
    },
    {
      insight_id: "demo-3",
      title: "Unusually high order volume on Nov 3rd — possible batch import",
      category: "anomaly",
      type: "anomaly",
      explanation: "November 3rd recorded 87 orders — 4.2× the daily average of 21. No corresponding revenue spike was observed, suggesting possible duplicate entries or a bulk import.",
      finding: "Nov 3rd had 87 orders vs a daily average of 21 — no matching revenue spike.",
      recommendation: "Verify source data for Nov 3rd with the client before including in final report.",
      action: "Ask client: was there a system import or data migration on Nov 3rd?",
      columns_used: ["order_date", "order_id"],
      method_used: "anomaly_detection",
      report_safe: true,
      severity: "medium",
      confidence: 78,
      evidence: "Daily avg: 21 orders · Nov 3rd: 87 orders",
    },
    {
      insight_id: "demo-4",
      title: "8.4% of rows missing region values",
      category: "data_quality",
      type: "data_quality",
      explanation: "71 of 847 rows have no region assigned. This limits geographic segmentation and could skew regional performance breakdowns.",
      finding: "71/847 rows (8.4%) are missing the region column.",
      recommendation: "Ask the client to provide missing region values before running geographic analysis.",
      action: "Send the client a list of order IDs with missing region for backfill.",
      columns_used: ["region"],
      method_used: "missing_value_analysis",
      report_safe: false,
      severity: "medium",
      confidence: 100,
      evidence: "71/847 rows missing region",
    },
    {
      insight_id: "demo-5",
      title: "Higher discounts correlate with smaller orders (r = −0.74)",
      category: "correlation",
      type: "correlation",
      explanation: "A strong negative correlation exists between discount_pct and revenue. Higher discounts consistently appear on smaller orders — counterintuitive and potentially indicating a pricing workflow issue.",
      finding: "Pearson r = −0.74 between discount_pct and revenue. High discounts on low-value orders.",
      recommendation: "Review discount approval workflow to ensure high-value orders aren't being systematically under-discounted.",
      action: "Pull a list of orders over $500 with 0% discount and share with sales manager.",
      columns_used: ["discount_pct", "revenue"],
      method_used: "correlation_analysis",
      report_safe: false,
      severity: "low",
      confidence: 83,
      evidence: "Pearson r = −0.74 across 847 observations",
    },
  ],

  // Canonical insight_results mirrors insights above
  insight_results: [] as unknown[],

  narrative:
    "November sales data shows a 12% revenue decline vs the Q3 average, driven primarily by a weak final week. Customer concentration remains high — three accounts account for two-thirds of revenue. An order volume spike on Nov 3rd requires client verification before the report is finalised.",

  story_result: {
    title: "Acme Retail — November 2024 Sales Review",
    slides: [
      {
        slide_num: 1,
        title: "Executive takeaway",
        narrative:
          "November 2024 revenue landed at $124,300 — 12.1% below the Q3 monthly average of $141,400. Order volume fell 7.1% versus October (847 vs 912 orders). The file is analysis-ready, but 8.4% of rows lack region — flag that before geographic cuts.",
        key_points: [
          "$124,300 revenue — down 12.1% vs Q3 monthly average",
          "847 November orders vs 912 in October",
          "71 rows missing region — limit geo reporting until backfilled",
        ],
      },
      {
        slide_num: 2,
        title: "Data quality & trust",
        narrative:
          "Pipeline scored the dataset at 74/100 (grade B): strong structure with minor completeness gaps. Twelve duplicate rows were removed automatically. The Nov 3 order spike (87 orders vs ~21 daily average) needs client confirmation before citing in a board deck.",
        key_points: [
          "Health score 74/100 (grade B) — good baseline trust",
          "12 duplicate rows removed in cleaning",
          "Nov 3 volume spike flagged for verification",
        ],
      },
      {
        slide_num: 3,
        title: "Biggest opportunity or driver",
        narrative:
          "Revenue softness concentrated in the final week (only ~18% of November revenue vs a typical ~27%). Mid-month performance held closer to plan — the gap is timing and close-rate in the last seven days, not a single category write-down.",
        key_points: [
          "Final week under-contributed vs historical month-end shape",
          "Mid-month (Nov 10–20) tracked near prior months",
          "No one product line explains the full shortfall — investigate pipeline",
        ],
      },
      {
        slide_num: 4,
        title: "Main risk or caveat",
        narrative:
          "Customer concentration remains acute: Acme Corp, Bright Future LLC, and Metro Group drove ~68% of November revenue. Discount usage and revenue show a strong negative association in-row — useful for targeting, but treat as associative until promotion rules are validated.",
        key_points: [
          "Top 3 accounts ≈68% of November revenue — renewal risk",
          "High concentration in `customer_id` tail — monitor churn signals",
          "Discount–revenue pattern is correlational; confirm with finance rules",
        ],
      },
      {
        slide_num: 5,
        title: "Recommended next actions",
        narrative:
          "In the next two weeks: (1) reconcile the Nov 3 order burst with ops, (2) run renewal readiness on the top-three accounts, and (3) backfill region on the 71 incomplete rows so territory dashboards are client-safe.",
        key_points: [
          "Ops validation on Nov 3 spike before external communication",
          "Account plan refresh for top 3 customers ahead of Q1",
          "Region backfill ticket — unblock geographic reporting",
        ],
      },
    ],
  },
} as const;

// ── Demo compare result: October vs November 2024 ─────────────────────────────
export const DEMO_COMPARE_RESULT: CompareResult = {
  compare_id: "demo-compare-oct-nov-2024",
  file_a: {
    file_name: "Acme Retail - October 2024 Sales.xlsx",
    project_id: null,
    row_count: 912,
    column_count: 12,
  },
  file_b: {
    file_name: "Acme Retail - November 2024 Sales.xlsx",
    project_id: null,
    row_count: 847,
    column_count: 12,
  },
  schema_changes: {
    added_columns: [],
    removed_columns: [],
    shared_columns: [
      "order_id", "order_date", "customer_id", "product_sku",
      "product_name", "category", "region", "quantity",
      "unit_price", "revenue", "discount_pct", "sales_rep",
    ],
  },
  row_volume_changes: {
    count_a: 912,
    count_b: 847,
    diff: -65,
    diff_pct: -7.1,
    overlap_count: 0,
    overlap_pct_of_a: null,
  },
  metric_deltas: [
    {
      column: "revenue",
      mean_a: 155.1,
      mean_b: 146.8,
      mean_delta_pct: -5.4,
      median_a: 104.2,
      median_b: 98.5,
      std_a: 198.6,
      std_b: 211.3,
      change_flag: "notable",
    },
    {
      column: "discount_pct",
      mean_a: 11.2,
      mean_b: 12.4,
      mean_delta_pct: 10.7,
      median_a: 10.0,
      median_b: 10.0,
      std_a: 7.9,
      std_b: 8.7,
      change_flag: "stable",
    },
    {
      column: "quantity",
      mean_a: 3.1,
      mean_b: 2.9,
      mean_delta_pct: -6.5,
      median_a: 2.0,
      median_b: 2.0,
      std_a: 1.9,
      std_b: 1.8,
      change_flag: "stable",
    },
  ],
  health_changes: {
    score_a: 78,
    score_b: 74,
    grade_a: "B",
    grade_b: "B",
    delta: -4,
    direction: "declined",
  },
  summary_draft:
    "November shows a 7.1% reduction in order volume (847 vs 912 rows) and a 5.4% decline in average revenue per order ($146.8 vs $155.1) compared to October. Schema is unchanged — all 12 columns are present in both files. Data health held at grade B with a minor 4-point dip. Discount rates edged up 10.7%, which may be contributing to the revenue softness.",
  caution_flags: [
    {
      kind: "volume_decline",
      severity: "medium",
      message: "Order volume declined 7.1% month-over-month (912 → 847 rows)",
      column: null,
    },
  ],
};
