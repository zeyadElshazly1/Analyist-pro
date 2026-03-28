"use client";

import { useState, type Dispatch, type SetStateAction } from "react";
import { runMultifileCompare } from "@/lib/api";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, Legend } from "recharts";

const TS = { background: "#111113", border: "1px solid rgba(255,255,255,0.08)", borderRadius: "8px", color: "#f5f7fa", fontSize: 12 };

export function MultifileCompare() {
  const [idA, setIdA] = useState("");
  const [idB, setIdB] = useState("");
  const [result, setResult] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function run() {
    const a = parseInt(idA), b = parseInt(idB);
    if (!a || !b) return;
    setLoading(true); setError("");
    try { setResult(await runMultifileCompare(a, b)); }
    catch (e) { setError(e instanceof Error ? e.message : "Comparison failed"); }
    finally { setLoading(false); }
  }

  const projectIdInputs: [string, string, Dispatch<SetStateAction<string>>][] = [
    ["File A project ID", idA, setIdA],
    ["File B project ID", idB, setIdB],
  ];

  return (
    <div className="space-y-5">
      <div className="rounded-xl border border-white/[0.07] bg-white/[0.03] p-5">
        <p className="mb-1 text-sm font-semibold text-white">Compare two datasets</p>
        <p className="mb-4 text-xs text-white/40">Enter the project IDs that each have a file uploaded.</p>
        <div className="flex flex-wrap items-end gap-3">
          {projectIdInputs.map(([label, val, set]) => (
            <div key={label} className="space-y-1">
              <label className="text-xs text-white/40">{label}</label>
              <input type="number" value={val} onChange={(e) => set(e.target.value)} placeholder="e.g. 1"
                className="w-28 rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-white" />
            </div>
          ))}
          <button onClick={run} disabled={loading || !idA || !idB}
            className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-500 disabled:opacity-60">
            {loading ? "Comparing…" : "Compare files"}
          </button>
        </div>
      </div>

      {error && <p className="text-sm text-red-400">{error}</p>}

      {result && (
        <div className="space-y-4">
          <div className="grid gap-3 sm:grid-cols-2">
            {(["file_a", "file_b"] as const).map((key, i) => (
              <div key={key} className="rounded-xl border border-white/[0.07] bg-white/[0.03] p-4">
                <p className="mb-3 text-sm font-semibold text-white">File {i === 0 ? "A" : "B"}</p>
                <div className="grid grid-cols-2 gap-y-2 text-xs">
                  <KV k="Rows" v={result[key].rows.toLocaleString()} />
                  <KV k="Columns" v={result[key].columns} />
                  <KV k="Health score" v={`${result[key].health_score} (${result[key].health_grade})`} />
                </div>
              </div>
            ))}
          </div>

          <div className="rounded-xl border border-white/[0.07] bg-white/[0.03] p-5">
            <p className="mb-4 text-sm font-semibold text-white">Schema</p>
            <div className="grid gap-4 sm:grid-cols-3 text-xs">
              {[
                { label: "Shared", cols: result.schema.shared_columns, color: "bg-emerald-500/10 text-emerald-400" },
                { label: "Only in A", cols: result.schema.only_in_a, color: "bg-indigo-500/10 text-indigo-400" },
                { label: "Only in B", cols: result.schema.only_in_b, color: "bg-amber-500/10 text-amber-400" },
              ].map(({ label, cols, color }) => (
                <div key={label}>
                  <p className="mb-2 text-white/40">{label} ({cols.length})</p>
                  <div className="flex flex-wrap gap-1">
                    {cols.length ? cols.map((c: string) => (
                      <span key={c} className={`rounded px-2 py-0.5 ${color}`}>{c}</span>
                    )) : <span className="text-white/25">—</span>}
                  </div>
                </div>
              ))}
            </div>
            {result.row_overlap !== null && (
              <p className="mt-4 text-xs text-white/40">
                Overlapping rows (inner merge): <span className="text-white">{result.row_overlap.toLocaleString()}</span>
              </p>
            )}
          </div>

          {result.column_comparison.length > 0 && (
            <div className="rounded-xl border border-white/[0.07] bg-white/[0.03] p-5">
              <p className="mb-4 text-sm font-semibold text-white">Numeric stats comparison</p>
              <div className="overflow-x-auto">
                <table className="min-w-full text-xs">
                  <thead className="border-b border-white/[0.06]">
                    <tr>{["Column", "Mean A", "Mean B", "Median A", "Median B", "Std A", "Std B"].map((h) => (
                      <th key={h} className="px-3 py-2 font-medium text-white/35">{h}</th>
                    ))}</tr>
                  </thead>
                  <tbody>
                    {result.column_comparison.map((row: any, i: number) => (
                      <tr key={i} className="border-b border-white/[0.04]">
                        <td className="px-3 py-2 font-medium text-white">{row.column}</td>
                        <td className="px-3 py-2 text-white/65">{row.file_a.mean}</td>
                        <td className="px-3 py-2 text-white/65">{row.file_b.mean}</td>
                        <td className="px-3 py-2 text-white/65">{row.file_a.median}</td>
                        <td className="px-3 py-2 text-white/65">{row.file_b.median}</td>
                        <td className="px-3 py-2 text-white/65">{row.file_a.std}</td>
                        <td className="px-3 py-2 text-white/65">{row.file_b.std}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {Object.entries(result.histograms).map(([col, bins]: [string, any]) => (
            <div key={col} className="rounded-2xl border border-white/[0.07] bg-white/[0.03] p-5">
              <p className="mb-4 text-sm font-medium text-white/80">Distribution overlay: {col}</p>
              <div className="h-[220px]">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={bins} margin={{ bottom: 40 }}>
                    <CartesianGrid strokeDasharray="3 3" strokeOpacity={0.08} />
                    <XAxis dataKey="label" tick={{ fill: "#6b7280", fontSize: 10 }} angle={-35} textAnchor="end" interval={0} />
                    <YAxis tick={{ fill: "#6b7280", fontSize: 11 }} />
                    <Tooltip contentStyle={TS} />
                    <Legend />
                    <Bar dataKey="file_a" fill="#6366f1" radius={[3, 3, 0, 0]} name="File A" />
                    <Bar dataKey="file_b" fill="#a78bfa" radius={[3, 3, 0, 0]} name="File B" />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function KV({ k, v }: { k: string; v: React.ReactNode }) {
  return <div><span className="text-white/40">{k}: </span><span className="text-white">{v}</span></div>;
}
