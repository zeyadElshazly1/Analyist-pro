/**
 * Demo / snapshot fixtures mirroring `getSuggestedCharts` payloads.
 * Use in design review or future Storybook; not wired into production routes.
 */
export type ChartFixture = {
  type: "bar" | "line" | "pie" | "scatter" | "boxplot" | "heatmap";
  title: string;
  description?: string;
  insight?: string;
  x_key: string;
  y_key: string;
  x_label?: string;
  y_label?: string;
  data: Array<Record<string, unknown>>;
  recommended?: boolean;
  horizontal?: boolean;
  is_binary?: boolean;
};

/** Telco-style tenure histogram (integer-like bin labels). */
export const FIXTURE_TENURE_HISTOGRAM: ChartFixture = {
  type: "bar",
  title: "Distribution of tenure",
  insight: "Typical customer tenure spread for sanity-checking bins.",
  x_key: "label",
  y_key: "value",
  x_label: "tenure",
  y_label: "Count",
  data: [
    { label: "1–9", value: 210, density: 0.07, is_anomaly_bin: false },
    { label: "10–18", value: 318, density: 0.11, is_anomaly_bin: false },
    { label: "19–28", value: 402, density: 0.13, is_anomaly_bin: false },
    { label: "29–37", value: 287, density: 0.1, is_anomaly_bin: false },
    { label: "38–46", value: 265, density: 0.09, is_anomaly_bin: false },
    { label: "47–55", value: 190, density: 0.06, is_anomaly_bin: false },
    { label: "56–64", value: 178, density: 0.06, is_anomaly_bin: false },
    { label: "65–72", value: 150, density: 0.05, is_anomaly_bin: false },
  ],
  recommended: true,
};

export const FIXTURE_MONTHLY_CHARGES_HISTOGRAM: ChartFixture = {
  type: "bar",
  title: "Distribution of MonthlyCharges",
  x_key: "label",
  y_key: "value",
  x_label: "MonthlyCharges",
  y_label: "Count",
  data: [
    { label: "18.2–28.4", value: 42, density: 0.21 },
    { label: "28.4–38.6", value: 55, density: 0.28 },
    { label: "38.6–48.8", value: 38, density: 0.19 },
    { label: "48.8–59", value: 30, density: 0.15 },
    { label: "59–69.2", value: 18, density: 0.09 },
    { label: "69.2–79.4", value: 10, density: 0.05 },
    { label: "79.4–89.6", value: 5, density: 0.02 },
    { label: "89.6–99.8", value: 2, density: 0.01 },
  ],
};

export const FIXTURE_TOTAL_CHARGES_HISTOGRAM: ChartFixture = {
  type: "bar",
  title: "Distribution of TotalCharges",
  x_key: "label",
  y_key: "value",
  x_label: "TotalCharges",
  y_label: "Count",
  data: [
    { label: "0–500", value: 120, density: 0.24 },
    { label: "500–1000", value: 98, density: 0.2 },
    { label: "1000–2000", value: 152, density: 0.3 },
    { label: "2000–4000", value: 88, density: 0.18 },
    { label: "4000–8000", value: 42, density: 0.08 },
  ],
};

/** customerID must be suppressed server-side; this documents the expectation only. */
export const FIXTURE_CUSTOMER_ID_SUPPRESSED_NOTE =
  "customerID / CustomerID columns are excluded in build_chart_data — no fixture chart.";

export const FIXTURE_SENIOR_CITIZEN_BINARY: ChartFixture = {
  type: "bar",
  title: "Breakdown of SeniorCitizen",
  insight: "Roughly four fifths of customers are not senior; remainder are senior.",
  x_key: "label",
  y_key: "value",
  x_label: "SeniorCitizen",
  y_label: "Count",
  is_binary: true,
  horizontal: false,
  data: [
    { label: "Not senior", value: 4731, pct: 67.6 },
    { label: "Senior", value: 2269, pct: 32.4 },
  ],
};

export const TELCO_CHART_FIXTURES: ChartFixture[] = [
  FIXTURE_TENURE_HISTOGRAM,
  FIXTURE_MONTHLY_CHARGES_HISTOGRAM,
  FIXTURE_TOTAL_CHARGES_HISTOGRAM,
  FIXTURE_SENIOR_CITIZEN_BINARY,
];
