/* eslint-disable @typescript-eslint/no-explicit-any */
"use client";

import { useState, useEffect } from "react";
import { getOutlierColumns, runOutlierAnalysis } from "@/lib/api";
import { ColumnSelect } from "@/components/ui/column-select";
import { AlertCircle } from "lucide-react";
import {
  BarChart,
  Bar,
  Cell,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
} from "recharts";

type Props = { projectId: number };

const DARK_TOOLTIP = {
  contentStyle: {
    background: "#111118",
    border: "1px solid rgba(255,255,255,0.08)",
    borderRadius: 8,
    color: "#fff",
  },
};

export function OutlierView({ projectId }: Props) {
  const [columns, setColumns] = useState<string[]>([]);
  const [column, setColumn] = useState("");
  const [result, setResult] = useState<any | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    getOutlierColumns(projectId)
      .then((data) => {
        setColumns(data.numeric_columns);
        if (data.numeric_columns.length > 0) setColumn(data.numeric_columns[0]);
      })
      .catch(() => setError("Failed to load numeric columns."));
  }, [projectId]);

  async function handleRun() {
    if (!column) return;
    setLoading(true);
    setError("");
    try {
      const data = await runOutlierAnalysis(projectId, column);
      setResult(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Outlier analysis failed.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-4">
      <h2 className="font-semibold text-white">Outlier Explorer</h2>

      {error && (
        <div className="flex items-center gap-2 rounded-xl border border-red-500/20 bg-red-500/10 px-4 py-3 text-sm text-red-400">
          <AlertCircle className="h-4 w-4" />
          {error}
        </div>
      )}

      <div className="flex flex-wrap items-end gap-3">
        <ColumnSelect
          label="Column"
          value={column}
          options={columns}
          onChange={setColumn}
          className="min-w-[180px]"
        />
        <button
          onClick={handleRun}
          disabled={loading || !column}
          className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-500 disabled:opacity-50 transition-colors"
        >
          {loading ? "Analyzing…" : "Detect Outliers"}
        </button>
      </div>

      {result && (
        <>
          {/* Method comparison */}
          <div className="grid grid-cols-3 gap-3">
            {[
              {
                label: "Z-Score (>3σ)",
                count: result.methods?.zscore?.count ?? 0,
                pct: result.methods?.zscore?.pct ?? 0,
                detail: result.methods?.zscore?.threshold,
              },
              {
                label: "IQR Method",
                count: result.methods?.iqr?.count ?? 0,
                pct: result.methods?.iqr?.pct ?? 0,
                detail: `fence: [${result.methods?.iqr?.lower_fence?.toFixed(2)}, ${result.methods?.iqr?.upper_fence?.toFixed(2)}]`,
              },
              {
                label: "Combined",
                count: result.methods?.combined?.count ?? 0,
                pct: result.methods?.combined?.pct ?? 0,
                detail: "flagged by either method",
              },
            ].map(({ label, count, pct, detail }) => (
              <div key={label} className="rounded-xl border border-white/[0.07] bg-white/[0.03] p-3">
                <p className="text-xs text-white/40">{label}</p>
                <p className={`mt-1 text-2xl font-bold ${count > 0 ? "text-amber-400" : "text-green-400"}`}>{count}</p>
                <p className="text-xs text-white/30">{pct}% • {detail}</p>
              </div>
            ))}
          </div>

          {/* Stats */}
          <div className="grid grid-cols-4 gap-2 text-center">
            {[
              { label: "Mean", value: result.stats?.mean },
              { label: "Median", value: result.stats?.median },
              { label: "Std Dev", value: result.stats?.std },
              { label: "IQR", value: result.stats?.iqr },
            ].map(({ label, value }) => (
              <div key={label} className="rounded-lg bg-white/[0.04] py-2 px-3">
                <p className="text-xs text-white/40">{label}</p>
                <p className="mt-0.5 text-sm font-semibold text-white">{value?.toFixed(3) ?? "—"}</p>
              </div>
            ))}
          </div>

          {/* Histogram */}
          {result.histogram?.length > 0 && (
            <div>
              <p className="mb-2 text-xs font-medium text-white/50">Distribution (red bins = outside IQR fences)</p>
              <div className="h-52">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={result.histogram}>
                    <CartesianGrid strokeDasharray="3 3" strokeOpacity={0.1} />
                    <XAxis dataKey="label" tick={{ fill: "#6b7280", fontSize: 9 }} angle={-20} textAnchor="end" height={50} />
                    <YAxis tick={{ fill: "#6b7280", fontSize: 11 }} />
                    <Tooltip {...DARK_TOOLTIP} />
                    <Bar dataKey="value" radius={[4, 4, 0, 0]}>
                      {result.histogram.map((bin: any, i: number) => (
                        <Cell key={i} fill={bin.is_outlier_bin ? "#ef4444" : "#6366f1"} fillOpacity={bin.is_outlier_bin ? 0.8 : 0.6} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>
          )}

          {/* Outlier rows table */}
          {result.outlier_rows?.length > 0 && (
            <div>
              <h3 className="mb-2 text-sm font-semibold text-white/70">
                Outlier Records ({result.outlier_rows.length})
              </h3>
              <div className="overflow-x-auto rounded-xl border border-white/[0.07]">
                <table className="w-full text-left">
                  <thead>
                    <tr className="border-b border-white/[0.07] bg-white/[0.03]">
                      {["Index", "Value", "Z-Score", "IQR Flag", "% Deviation"].map((h) => (
                        <th key={h} className="px-3 py-2 text-xs font-medium text-white/40">{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {result.outlier_rows.slice(0, 30).map((row: any, i: number) => (
                      <tr key={i} className="border-b border-white/[0.04] hover:bg-white/[0.02]">
                        <td className="px-3 py-2 text-xs text-white/50">{row.index}</td>
                        <td className="px-3 py-2 text-xs font-mono text-white">{row.value}</td>
                        <td className={`px-3 py-2 text-xs font-mono ${Math.abs(row.z_score) > 3 ? "text-red-400" : "text-amber-400"}`}>
                          {row.z_score?.toFixed(2)}
                        </td>
                        <td className="px-3 py-2 text-xs">
                          {row.iqr_flag
                            ? <span className="text-red-400">Yes</span>
                            : <span className="text-white/30">No</span>}
                        </td>
                        <td className={`px-3 py-2 text-xs font-mono ${row.pct_deviation != null && Math.abs(row.pct_deviation) > 50 ? "text-red-400" : "text-white/60"}`}>
                          {row.pct_deviation != null ? `${row.pct_deviation > 0 ? "+" : ""}${row.pct_deviation}%` : "—"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
