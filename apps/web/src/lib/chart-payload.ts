/**
 * Shape of items returned by `POST /charts/suggest` (matches backend chart dicts).
 */

export interface ChartFinanceFormattingMeta {
  value_format?: "percent" | string;
  value_scale?: "decimal" | "unit" | string;
  x_format?: "percent" | string;
  x_scale?: "decimal" | "unit" | string;
  y_format?: "percent" | string;
  y_scale?: "decimal" | "unit" | string;
}

export type SuggestedChartPayload = ChartFinanceFormattingMeta & {
  type: "bar" | "line" | "pie" | "scatter" | "boxplot" | "heatmap";
  title: string;
  description?: string;
  insight?: string;
  x_key: string;
  y_key: string;
  x_label?: string;
  y_label?: string;
  data: Array<Record<string, unknown>>;
  regression?: Array<{ x: number; y_hat: number }>;
  columns?: string[];
  recommended?: boolean;
  /** Server hint: render as horizontal bars (category on Y). */
  horizontal?: boolean;
  /** Numeric 0/1 flag column — prefer short, unrotated category labels. */
  is_binary?: boolean;
  color_key?: string | null;
};

/** True when the payload carries finance percent-display hints (Task 74D). */
export function isFinanceFormattedChart(
  chart: Pick<ChartFinanceFormattingMeta, "value_format" | "x_format" | "y_format">,
): boolean {
  return (
    chart.value_format === "percent" ||
    chart.x_format === "percent" ||
    chart.y_format === "percent"
  );
}
