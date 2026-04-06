/* eslint-disable @typescript-eslint/no-explicit-any */
"use client";

import { useState } from "react";
import { runMultifileCompare } from "@/lib/api";
import { AlertCircle } from "lucide-react";
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

type Props = { currentProjectId: number };

const DARK_TOOLTIP = {
  contentStyle: {
    background: "#111118",
    border: "1px solid rgba(255,255,255,0.08)",
    borderRadius: 8,
    color: "#fff",
  },
};

export function MultifileCompare({ currentProjectId }: Props) {
  const [otherProjectId, setOtherProjectId] = useState("");
  const [result, setResult] = useState<any | null>(null);
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
    } catch (err) {
      setError(err instanceof Error ? err.message : "Comparison failed.");
    } finally {
      setLoading(false);
    }
  }

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
          {/* Row/col overview */}
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            {[
              { label: `${result.label_a} Rows`, value: result.rows?.a?.toLocaleString() },
              { label: `${result.label_b} Rows`, value: result.rows?.b?.toLocaleString() },
              { label: "Row Difference", value: result.rows?.diff != null ? (result.rows.diff > 0 ? `+${result.rows.diff}` : String(result.rows.diff)) : "—" },
              { label: "Shared Columns", value: result.schema?.shared_count },
            ].map(({ label, value }) => (
              <div key={label} className="rounded-xl border border-white/[0.07] bg-white/[0.03] p-3 text-center">
                <p className="text-xs text-white/40">{label}</p>
                <p className="mt-1 text-xl font-bold text-white">{value}</p>
              </div>
            ))}
          </div>

          {/* Health score comparison */}
          <div className="grid grid-cols-2 gap-3">
            {[
              { label: result.label_a, score: result.health_scores?.a },
              { label: result.label_b, score: result.health_scores?.b },
            ].map(({ label, score }) => (
              <div key={label} className="rounded-xl border border-white/[0.07] bg-white/[0.03] p-4">
                <p className="text-xs text-white/40 mb-1">{label}</p>
                <div className="flex items-baseline gap-2">
                  <span className="text-3xl font-bold text-white">{score?.total}</span>
                  <span className="text-lg font-semibold text-white/50">{score?.grade}</span>
                  <span className="text-sm text-white/40">{score?.label}</span>
                </div>
              </div>
            ))}
          </div>

          {/* Schema diff */}
          <div>
            <h3 className="mb-2 text-sm font-semibold text-white/70">Schema Differences</h3>
            <div className="flex flex-wrap gap-1.5">
              {(result.schema?.shared ?? []).map((col: string) => (
                <span key={col} className="rounded-full border border-green-500/30 bg-green-500/10 px-2.5 py-0.5 text-xs text-green-300">
                  {col}
                </span>
              ))}
              {(result.schema?.only_a ?? []).map((col: string) => (
                <span key={col} className="rounded-full border border-indigo-500/30 bg-indigo-500/10 px-2.5 py-0.5 text-xs text-indigo-300">
                  {col} (A only)
                </span>
              ))}
              {(result.schema?.only_b ?? []).map((col: string) => (
                <span key={col} className="rounded-full border border-purple-500/30 bg-purple-500/10 px-2.5 py-0.5 text-xs text-purple-300">
                  {col} (B only)
                </span>
              ))}
            </div>
          </div>

          {/* Stats comparison table */}
          {result.stats_comparison?.length > 0 && (
            <div>
              <h3 className="mb-2 text-sm font-semibold text-white/70">Numeric Statistics Comparison</h3>
              <div className="overflow-x-auto rounded-xl border border-white/[0.07]">
                <table className="w-full text-left text-xs">
                  <thead>
                    <tr className="border-b border-white/[0.07] bg-white/[0.03]">
                      {["Column", `${result.label_a} Mean`, `${result.label_b} Mean`, "Mean Diff %", `${result.label_a} Std`, `${result.label_b} Std`].map((h) => (
                        <th key={h} className="px-3 py-2 text-white/40 font-medium whitespace-nowrap">{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {result.stats_comparison.map((row: any, i: number) => (
                      <tr key={i} className="border-b border-white/[0.04] hover:bg-white/[0.02]">
                        <td className="px-3 py-2 font-medium text-white">{row.column}</td>
                        <td className="px-3 py-2 text-white/60 font-mono">{row.a_mean?.toFixed(3)}</td>
                        <td className="px-3 py-2 text-white/60 font-mono">{row.b_mean?.toFixed(3)}</td>
                        <td className={`px-3 py-2 font-mono ${row.mean_diff_pct != null && Math.abs(row.mean_diff_pct) > 10 ? "text-amber-400" : "text-white/60"}`}>
                          {row.mean_diff_pct != null ? `${row.mean_diff_pct > 0 ? "+" : ""}${row.mean_diff_pct}%` : "—"}
                        </td>
                        <td className="px-3 py-2 text-white/60 font-mono">{row.a_std?.toFixed(3)}</td>
                        <td className="px-3 py-2 text-white/60 font-mono">{row.b_std?.toFixed(3)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Overlay histograms */}
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
                          <Bar dataKey="a_count" name={result.label_a} fill="#6366f1" fillOpacity={0.7} radius={[3, 3, 0, 0]} />
                          <Bar dataKey="b_count" name={result.label_b} fill="#a78bfa" fillOpacity={0.7} radius={[3, 3, 0, 0]} />
                        </BarChart>
                      </ResponsiveContainer>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Row overlap */}
          {result.row_overlap?.count != null && (
            <div className="rounded-xl border border-white/[0.07] bg-white/[0.03] p-4">
              <p className="text-sm text-white/60">
                Row overlap: <span className="font-semibold text-white">{result.row_overlap.count}</span> identical rows
                ({result.row_overlap.pct_of_a}% of {result.label_a})
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
