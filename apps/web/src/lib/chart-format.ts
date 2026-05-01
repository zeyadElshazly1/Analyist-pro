/**
 * Display formatting helpers for backend chart payloads (e.g. financial snapshot
 * percent metadata — Task 74C). Raw `data` values are never mutated.
 */

export type ChartValueFormatKey = "percent" | string;
export type ChartValueScaleKey = "decimal" | "unit" | string;

/** One decimal place + % suffix when format === "percent" (decimal vs unit scale). */
export function formatChartValue(
  value: unknown,
  format?: ChartValueFormatKey | null,
  scale?: ChartValueScaleKey | null,
): string {
  if (value === null || value === undefined) return "—";
  const n = Number(value);
  if (!Number.isFinite(n)) return "—";
  if (format !== "percent") {
    return String(value);
  }
  const sc = scale === "unit" ? "unit" : "decimal";
  if (sc === "decimal") {
    return `${(n * 100).toFixed(1)}%`;
  }
  return `${n.toFixed(1)}%`;
}
