/* eslint-disable @typescript-eslint/no-explicit-any */
"use client";

import { useState } from "react";
import { runMultifileCompare } from "@/lib/api";
import type { CompareResult, CompareMetricDelta } from "@/lib/api";
import { AlertCircle, AlertTriangle, Info } from "lucide-react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
  Legend,
} from "recharts";

type Props = { currentProjectId: number; onCompareResult?: (cr: CompareResult) => void };

const DARK_TOOLTIP = {
  contentStyle: {
    background: "#111118",
    border: "1px solid rgba(255,255,255,0.08)",
    borderRadius: 8,
    color: "#fff",
  },
};

const CAUTION_STYLE: Record<string, { icon: typeof AlertTriangle; badge: string; row: string }> = {
  high:   { icon: AlertTriangle, badge: "border-red-500/20 bg-red-500/10 text-red-300",    row: "border-red-500/10 bg-red-500/5" },
  medium: { icon: AlertTriangle, badge: "border-amber-500/20 bg-amber-500/10 text-amber-300", row: "border-amber-500/10 bg-amber-500/5" },
  low:    { icon: Info,          badge: "border-white/10 bg-white/5 text-white/50",           row: "border-white/[0.05] bg-white/[0.02]" },
};

const CHANGE_FLAG_COLOR: Record<string, string> = {
  significant: "text-red-400",
  notable:     "text-amber-400",
  stable:      "text-white/60",
  no_data:     "text-white/30",
};

function classifyDelta(pct: number | null): CompareMetricDelta["change_flag"] {
  if (pct == null) return "no_data";
  const abs = Math.abs(pct);
  if (abs > 20) return "significant";
  if (abs >= 5)  return "notable";
  return "stable";
}

export function MultifileCompare({ currentProjectId, onCompareResult }: Props) {
  const [otherProjectId, setOtherProjectId] = useState("");
  const [result, setResult] = useState<(Record<string, any> & { compare_result?: CompareResult }) | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function handleCompare() {
    const otherId = parseInt(otherProjectId);
    if (isNaN(otherId)) {
      setError("Please enter a valid project ID.");
      return;
    }
    setLoading(true);
    setError("");
    try {
      const data = await runMultifileCompare(currentProjectId, otherId);
      setResult(data);
      if (data.compare_result) onCompareResult?.(data.compare_result);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Comparison failed.");
    } finally {
      setLoading(false);
    }
  }

  // ── Canonical-first data extraction ──────────────────────────────────────
  const cr = result?.compare_result ?? null;

  const labelA = cr?.file_a.file_name ?? result?.label_a ?? "File A";
  const labelB = cr?.file_b.file_name ?? result?.label_b ?? "File B";

  const rowVol = cr?.row_volume_changes;
  const countA = rowVol?.count_a ?? result?.rows?.a;
  const countB = rowVol?.count_b ?? result?.rows?.b;
  const rowDiff = rowVol?.diff ?? result?.rows?.diff;
  const diffPct = rowVol?.diff_pct ?? null;

  const schema = cr?.schema_changes;
  const sharedCols:  string[] = schema?.shared_columns  ?? result?.schema?.shared   ?? [];
  const removedCols: string[] = schema?.removed_columns ?? result?.schema?.only_a   ?? [];
  const addedCols:   string[] = schema?.added_columns   ?? result?.schema?.only_b   ?? [];

  const healthChg = cr?.health_changes;
  const scoreA = healthChg?.score_a ?? result?.health_scores?.a?.total;
  const gradeA = healthChg?.grade_a ?? result?.health_scores?.a?.grade;
  const scoreB = healthChg?.score_b ?? result?.health_scores?.b?.total;
  const gradeB = healthChg?.grade_b ?? result?.health_scores?.b?.grade;
  const healthDirection = healthChg?.direction;

  // Normalize metric rows: prefer canonical (has change_flag), fallback to raw
  const metricRows: CompareMetricDelta[] = cr?.metric_deltas?.length
    ? cr.metric_deltas
    : (result?.stats_comparison ?? []).map((row: any) => ({
        column:         row.column,
        mean_a:         row.a_mean ?? null,
        mean_b:         row.b_mean ?? null,
        mean_delta_pct: row.mean_diff_pct ?? null,
        median_a:       row.a_median ?? null,
        median_b:       row.b_median ?? null,
        std_a:          row.a_std ?? null,
        std_b:          row.b_std ?? null,
        change_flag:    classifyDelta(row.mean_diff_pct),
      }));

  const overlapCount = rowVol?.overlap_count ?? result?.row_overlap?.count;
  const overlapPct   = rowVol?.overlap_pct_of_a ?? result?.row_overlap?.pct_of_a;

  const cautionFlags = cr?.caution_flags ?? [];
  const summaryDraft = cr?.summary_draft ?? null;

  const healthDirColor =
    healthDirection === "improved" ? "text-emerald-400" :
    healthDirection === "declined" ? "text-red-400" :
    "text-white/60";

  return (
    <div className="space-y-4">
      <h2 className="font-semibold text-white">Compare Files</h2>
      <p className="text-sm text-white/40">
        Compare this project&apos;s dataset with another project&apos;s uploaded file.
      </p>

      {error && (
        <div className="flex items-center gap-2 rounded-xl border border-red-500/20 bg-red-500/10 px-4 py-3 text-sm text-red-400">
          <AlertCircle className="h-4 w-4" />
          {error}
        </div>
      )}

      <div className="flex items-end gap-3">
        <div>
          <label className="mb-1 block text-xs text-white/40">Other Project ID</label>
          <input
            type="number"
            value={otherProjectId}
            onChange={(e) => setOtherProjectId(e.target.value)}
            placeholder="e.g. 2"
            className="rounded-lg border border-white/[0.08] bg-white/[0.05] px-3 py-2 text-sm text-white placeholder-white/20 focus:outline-none focus:ring-1 focus:ring-indigo-500 w-32"
          />
        </div>
        <button
          onClick={handleCompare}
          disabled={loading || !otherProjectId}
          className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-500 disabled:opacity-50 transition-colors"
        >
          {loading ? "Comparing…" : "Compare"}
        </button>
      </div>

      {result && (
        <div className="space-y-5">

          {/* ── Summary draft (canonical only) ───────────────────────────── */}
          {summaryDraft && (
            <div className="rounded-xl border border-indigo-500/15 bg-indigo-500/5 px-4 py-3">
              <p className="mb-1 text-[10px] font-medium uppercase tracking-wider text-indigo-400/60">Comparison Summary</p>
              <p className="text-sm leading-relaxed text-white/75">{summaryDraft}</p>
            </div>
          )}

          {/* ── Caution flags (canonical only) ───────────────────────────── */}
          {cautionFlags.length > 0 && (
            <div className="space-y-1.5">
              <p className="text-[10px] font-medium uppercase tracking-wider text-white/30">Flags to review</p>
              {cautionFlags.map((flag, i) => {
                const style = CAUTION_STYLE[flag.severity] ?? CAUTION_STYLE.low;
                const Icon = style.icon;
                return (
                  <div key={i} className={`flex items-start gap-2.5 rounded-lg border px-3 py-2.5 ${style.row}`}>
                    <Icon className={`mt-0.5 h-3.5 w-3.5 flex-shrink-0 ${flag.severity === "high" ? "text-red-400" : flag.severity === "medium" ? "text-amber-400" : "text-white/40"}`} />
                    <p className="flex-1 text-xs leading-relaxed text-white/65">{flag.message}</p>
                    <span className={`flex-shrink-0 rounded-full border px-1.5 py-0.5 text-[10px] font-medium ${style.badge}`}>
                      {flag.severity}
                    </span>
                  </div>
                );
              })}
            </div>
          )}

          {/* ── Row/col overview ─────────────────────────────────────────── */}
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            {[
              { label: `${labelA} Rows`, value: countA?.toLocaleString() },
              { label: `${labelB} Rows`, value: countB?.toLocaleString() },
              {
                label: "Row Difference",
                value: rowDiff != null
                  ? `${rowDiff > 0 ? "+" : ""}${rowDiff.toLocaleString()}${diffPct != null ? ` (${diffPct > 0 ? "+" : ""}${diffPct.toFixed(1)}%)` : ""}`
                  : "—",
              },
              { label: "Shared Columns", value: sharedCols.length },
            ].map(({ label, value }) => (
              <div key={label} className="rounded-xl border border-white/[0.07] bg-white/[0.03] p-3 text-center">
                <p className="text-xs text-white/40">{label}</p>
                <p className="mt-1 text-xl font-bold text-white">{value}</p>
              </div>
            ))}
          </div>

          {/* ── Health score comparison ───────────────────────────────────── */}
          <div className="grid grid-cols-2 gap-3">
            {([
              { label: labelA, score: scoreA, grade: gradeA },
              { label: labelB, score: scoreB, grade: gradeB },
            ] as const).map(({ label, score, grade }) => (
              <div key={label} className="rounded-xl border border-white/[0.07] bg-white/[0.03] p-4">
                <p className="text-xs text-white/40 mb-1">{label}</p>
                <div className="flex items-baseline gap-2">
                  <span className="text-3xl font-bold text-white">{typeof score === "number" ? Math.round(score) : score ?? "—"}</span>
                  <span className="text-lg font-semibold text-white/50">{grade ?? ""}</span>
                </div>
              </div>
            ))}
          </div>
          {healthDirection && healthDirection !== "unchanged" && (
            <p className={`text-xs font-medium ${healthDirColor}`}>
              Quality {healthDirection} between files
              {healthChg ? ` (${healthChg.delta > 0 ? "+" : ""}${healthChg.delta.toFixed(1)} pts)` : ""}.
            </p>
          )}

          {/* ── Schema diff ──────────────────────────────────────────────── */}
          {(sharedCols.length > 0 || removedCols.length > 0 || addedCols.length > 0) && (
            <div>
              <h3 className="mb-2 text-sm font-semibold text-white/70">Schema Differences</h3>
              <div className="flex flex-wrap gap-1.5">
                {sharedCols.map((col) => (
                  <span key={col} className="rounded-full border border-green-500/30 bg-green-500/10 px-2.5 py-0.5 text-xs text-green-300">
                    {col}
                  </span>
                ))}
                {removedCols.map((col) => (
                  <span key={col} className="rounded-full border border-red-500/30 bg-red-500/10 px-2.5 py-0.5 text-xs text-red-300">
                    {col} (removed)
                  </span>
                ))}
                {addedCols.map((col) => (
                  <span key={col} className="rounded-full border border-purple-500/30 bg-purple-500/10 px-2.5 py-0.5 text-xs text-purple-300">
                    {col} (added)
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* ── Metric deltas table ───────────────────────────────────────── */}
          {metricRows.length > 0 && (
            <div>
              <h3 className="mb-2 text-sm font-semibold text-white/70">Numeric Statistics Comparison</h3>
              <div className="overflow-x-auto rounded-xl border border-white/[0.07]">
                <table className="w-full text-left text-xs">
                  <thead>
                    <tr className="border-b border-white/[0.07] bg-white/[0.03]">
                      {["Column", `${labelA} Mean`, `${labelB} Mean`, "Mean Δ %", `${labelA} Std`, `${labelB} Std`].map((h) => (
                        <th key={h} className="px-3 py-2 text-white/40 font-medium whitespace-nowrap">{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {metricRows.map((row, i) => {
                      const flagColor = CHANGE_FLAG_COLOR[row.change_flag] ?? "text-white/60";
                      return (
                        <tr key={i} className="border-b border-white/[0.04] hover:bg-white/[0.02]">
                          <td className="px-3 py-2 font-medium text-white">{row.column}</td>
                          <td className="px-3 py-2 text-white/60 font-mono">{row.mean_a?.toFixed(3) ?? "—"}</td>
                          <td className="px-3 py-2 text-white/60 font-mono">{row.mean_b?.toFixed(3) ?? "—"}</td>
                          <td className={`px-3 py-2 font-mono ${flagColor}`}>
                            {row.mean_delta_pct != null
                              ? `${row.mean_delta_pct > 0 ? "+" : ""}${row.mean_delta_pct.toFixed(1)}%`
                              : "—"}
                          </td>
                          <td className="px-3 py-2 text-white/60 font-mono">{row.std_a?.toFixed(3) ?? "—"}</td>
                          <td className="px-3 py-2 text-white/60 font-mono">{row.std_b?.toFixed(3) ?? "—"}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* ── Overlay histograms (raw field — no canonical equivalent) ──── */}
          {result.histograms?.length > 0 && (
            <div>
              <h3 className="mb-3 text-sm font-semibold text-white/70">Distribution Overlays</h3>
              <div className="space-y-5">
                {result.histograms.map((hist: any, i: number) => (
                  <div key={i}>
                    <p className="mb-1 text-xs text-white/40">{hist.column}</p>
                    <div className="h-40">
                      <ResponsiveContainer width="100%" height="100%">
                        <BarChart data={hist.bins}>
                          <CartesianGrid strokeDasharray="3 3" strokeOpacity={0.1} />
                          <XAxis dataKey="label" tick={{ fill: "#6b7280", fontSize: 9 }} angle={-15} textAnchor="end" height={40} />
                          <YAxis tick={{ fill: "#6b7280", fontSize: 10 }} />
                          <Tooltip {...DARK_TOOLTIP} />
                          <Legend wrapperStyle={{ color: "#9ca3af", fontSize: 11 }} />
                          <Bar dataKey="a_count" name={labelA} fill="#6366f1" fillOpacity={0.7} radius={[3, 3, 0, 0]} />
                          <Bar dataKey="b_count" name={labelB} fill="#a78bfa" fillOpacity={0.7} radius={[3, 3, 0, 0]} />
                        </BarChart>
                      </ResponsiveContainer>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* ── Row overlap ───────────────────────────────────────────────── */}
          {overlapCount != null && (
            <div className="rounded-xl border border-white/[0.07] bg-white/[0.03] p-4">
              <p className="text-sm text-white/60">
                Row overlap:{" "}
                <span className="font-semibold text-white">{Number(overlapCount).toLocaleString()}</span>{" "}
                identical rows
                {overlapPct != null && ` (${Number(overlapPct).toFixed(1)}% of ${labelA})`}
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
