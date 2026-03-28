"use client";

import { useEffect, useState } from "react";
import { getOutlierColumns, runOutlierAnalysis } from "@/lib/api";
import { BarChart, Bar, Cell, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from "recharts";

type Props = { projectId: number };

const TS = { background: "#111113", border: "1px solid rgba(255,255,255,0.08)", borderRadius: "8px", color: "#f5f7fa", fontSize: 12 };

export function OutlierView({ projectId }: Props) {
  const [columns, setColumns] = useState<string[]>([]);
  const [col, setCol] = useState("");
  const [result, setResult] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [colsLoading, setColsLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    getOutlierColumns(projectId)
      .then((d) => { setColumns(d.columns ?? []); if (d.columns?.[0]) setCol(d.columns[0]); })
      .catch(() => setError("Failed to load columns"))
      .finally(() => setColsLoading(false));
  }, [projectId]);

  async function run() {
    setLoading(true); setError("");
    try { setResult(await runOutlierAnalysis(projectId, col)); }
    catch (e) { setError(e instanceof Error ? e.message : "Failed"); }
    finally { setLoading(false); }
  }

  if (colsLoading) return <p className="text-sm text-white/40">Loading columns…</p>;
  if (columns.length === 0) return <p className="text-sm text-white/40">No numeric columns found.</p>;

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-end gap-3">
        <div className="space-y-1">
          <label className="text-xs text-white/40">Numeric column</label>
          <select value={col} onChange={(e) => setCol(e.target.value)}
            className="rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-white">
            {columns.map((c) => <option key={c} value={c}>{c}</option>)}
          </select>
        </div>
        <button onClick={run} disabled={loading}
          className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-500 disabled:opacity-60">
          {loading ? "Running…" : "Explore outliers"}
        </button>
      </div>

      {error && <p className="text-sm text-red-400">{error}</p>}

      {result && (
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            {[
              { label: "Total rows", value: result.total_rows, warn: false },
              { label: "Outliers", value: result.outlier_count, warn: result.outlier_count > 0 },
              { label: "Outlier %", value: `${result.outlier_pct}%`, warn: result.outlier_pct > 5 },
              { label: "Std dev", value: result.stats.std, warn: false },
            ].map((s) => (
              <div key={s.label} className={`rounded-xl border p-4 ${s.warn ? "border-amber-500/20 bg-amber-500/5" : "border-white/[0.07] bg-white/[0.03]"}`}>
                <p className="text-xs text-white/40">{s.label}</p>
                <p className={`mt-1.5 text-xl font-semibold ${s.warn ? "text-amber-400" : "text-white"}`}>{s.value}</p>
              </div>
            ))}
          </div>

          <div className="rounded-xl border border-white/[0.07] bg-white/[0.03] p-4 text-sm">
            <p className="mb-2 text-xs text-white/35 font-medium">Z-score bounds (±3 std)</p>
            <div className="flex flex-wrap gap-5 text-white/60">
              <span>Lower: <span className="text-white">{result.stats.lower_bound}</span></span>
              <span>Upper: <span className="text-white">{result.stats.upper_bound}</span></span>
              <span>Range: <span className="text-white">{result.stats.min} – {result.stats.max}</span></span>
            </div>
          </div>

          <div className="rounded-2xl border border-white/[0.07] bg-white/[0.03] p-5">
            <p className="mb-4 text-sm font-medium text-white/80">
              Distribution — <span className="text-red-400 text-xs">red = outlier bins</span>
            </p>
            <div className="h-[240px]">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={result.histogram} margin={{ bottom: 50 }}>
                  <CartesianGrid strokeDasharray="3 3" strokeOpacity={0.08} />
                  <XAxis dataKey="label" tick={{ fill: "#6b7280", fontSize: 10 }} angle={-35} textAnchor="end" interval={0} />
                  <YAxis tick={{ fill: "#6b7280", fontSize: 11 }} />
                  <Tooltip contentStyle={TS} />
                  <Bar dataKey="count" radius={[3, 3, 0, 0]}>
                    {result.histogram.map((entry: any, i: number) => (
                      <Cell key={i} fill={entry.is_outlier_bin ? "#f87171" : "#6366f1"} fillOpacity={entry.is_outlier_bin ? 0.9 : 0.65} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>

          {result.outlier_rows.length > 0 && (
            <div className="rounded-2xl border border-white/[0.07] bg-white/[0.03] p-5">
              <p className="mb-4 text-sm font-medium text-white/80">Outlier records ({result.outlier_rows.length})</p>
              <div className="overflow-x-auto">
                <table className="min-w-full text-xs">
                  <thead className="border-b border-white/[0.06]">
                    <tr>
                      {["Index", "Value", "Z-score"].map((h) => (
                        <th key={h} className="px-3 py-2 font-medium text-white/35">{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {result.outlier_rows.slice(0, 20).map((row: any, i: number) => (
                      <tr key={i} className="border-b border-white/[0.04]">
                        <td className="px-3 py-2 text-white/50">{row.index}</td>
                        <td className="px-3 py-2 font-medium text-amber-400">{row.value}</td>
                        <td className="px-3 py-2 text-red-400">{row.z_score}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
