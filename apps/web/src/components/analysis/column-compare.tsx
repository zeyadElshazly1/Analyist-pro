"use client";

import { useEffect, useState, type Dispatch, type SetStateAction } from "react";
import { getCompareColumns, runColumnCompare } from "@/lib/api";
import {
  ScatterChart, Scatter, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, BarChart, Bar,
} from "recharts";

type Props = { projectId: number };

const TS = { background: "#111113", border: "1px solid rgba(255,255,255,0.08)", borderRadius: "8px", color: "#f5f7fa", fontSize: 12 };
const tick = { fill: "#6b7280", fontSize: 11 };
const grid = { strokeDasharray: "3 3", strokeOpacity: 0.08 };

export function ColumnCompare({ projectId }: Props) {
  const [columns, setColumns] = useState<string[]>([]);
  const [colA, setColA] = useState("");
  const [colB, setColB] = useState("");
  const [result, setResult] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [colsLoading, setColsLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    getCompareColumns(projectId)
      .then((d) => {
        const cols = d.columns ?? [];
        setColumns(cols);
        if (cols[0]) setColA(cols[0]);
        if (cols[1]) setColB(cols[1]);
      })
      .catch(() => setError("Failed to load columns"))
      .finally(() => setColsLoading(false));
  }, [projectId]);

  async function run() {
    if (!colA || !colB || colA === colB) return;
    setLoading(true); setError("");
    try { setResult(await runColumnCompare(projectId, colA, colB)); }
    catch (e) { setError(e instanceof Error ? e.message : "Failed"); }
    finally { setLoading(false); }
  }

  if (colsLoading) return <p className="text-sm text-white/40">Loading columns…</p>;

  const columnSelectors: [string, string, Dispatch<SetStateAction<string>>][] = [
    ["Column A", colA, setColA],
    ["Column B", colB, setColB],
  ];

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-end gap-3">
        {columnSelectors.map(([label, val, set]) => (
          <div key={label} className="space-y-1">
            <label className="text-xs text-white/40">{label}</label>
            <select value={val} onChange={(e) => set(e.target.value)}
              className="rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-white">
              {columns.map((c) => <option key={c} value={c}>{c}</option>)}
            </select>
          </div>
        ))}
        <button onClick={run} disabled={loading || colA === colB}
          className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-500 disabled:opacity-60">
          {loading ? "Comparing…" : "Compare"}
        </button>
        {colA === colB && <p className="text-xs text-white/30">Select two different columns</p>}
      </div>

      {error && <p className="text-sm text-red-400">{error}</p>}
      {result && <CompareResult result={result} />}
    </div>
  );
}

function CompareResult({ result }: { result: any }) {
  if (result.type === "numeric_vs_numeric") {
    return (
      <div className="space-y-4">
        <div className="grid gap-3 sm:grid-cols-3">
          <Stat label="Pearson r" value={result.correlation} color={Math.abs(result.correlation) > 0.5 ? "text-indigo-400" : "text-white"} />
          <Stat label="P-value" value={result.p_value} />
          <Stat label="Significant" value={result.significant ? "Yes (p < 0.05)" : "No (p ≥ 0.05)"} color={result.significant ? "text-emerald-400" : "text-white/50"} />
        </div>
        <div className="rounded-2xl border border-white/[0.07] bg-white/[0.03] p-5">
          <p className="mb-4 text-sm font-medium text-white/80">Scatter plot: {result.col_a} vs {result.col_b}</p>
          <div className="h-[300px]">
            <ResponsiveContainer width="100%" height="100%">
              <ScatterChart>
                <CartesianGrid {...grid} />
                <XAxis dataKey={result.col_a} name={result.col_a} tick={tick} />
                <YAxis dataKey={result.col_b} name={result.col_b} tick={tick} />
                <Tooltip contentStyle={TS} />
                <Scatter data={result.scatter_data} fill="#6366f1" fillOpacity={0.6} />
              </ScatterChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>
    );
  }

  if (result.type === "numeric_vs_categorical") {
    return (
      <div className="space-y-4">
        <div className="rounded-2xl border border-white/[0.07] bg-white/[0.03] p-5">
          <p className="mb-4 text-sm font-medium text-white/80">Mean {result.num_col} by {result.cat_col}</p>
          <div className="h-[260px]">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={result.group_stats}>
                <CartesianGrid {...grid} />
                <XAxis dataKey="category" tick={tick} />
                <YAxis tick={tick} />
                <Tooltip contentStyle={TS} />
                <Bar dataKey="mean" fill="#6366f1" radius={[4, 4, 0, 0]} name="Mean" />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
        <div className="overflow-x-auto rounded-xl border border-white/[0.07]">
          <table className="min-w-full text-left text-xs">
            <thead className="border-b border-white/[0.06] bg-white/[0.03]">
              <tr>{["Category", "Mean", "Median", "Std", "Count"].map((h) => (
                <th key={h} className="px-4 py-2 font-medium text-white/35">{h}</th>
              ))}</tr>
            </thead>
            <tbody>
              {result.group_stats.map((row: any, i: number) => (
                <tr key={i} className="border-b border-white/[0.04]">
                  <td className="px-4 py-2 font-medium text-white">{row.category}</td>
                  <td className="px-4 py-2 text-white/65">{row.mean}</td>
                  <td className="px-4 py-2 text-white/65">{row.median}</td>
                  <td className="px-4 py-2 text-white/65">{row.std}</td>
                  <td className="px-4 py-2 text-white/65">{row.count}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    );
  }

  if (result.type === "categorical_vs_categorical") {
    const { heatmap_data, col_a_values, col_b_values } = result;
    return (
      <div className="rounded-2xl border border-white/[0.07] bg-white/[0.03] p-5">
        <p className="mb-4 text-sm font-medium text-white/80">Cross-tabulation (row %)</p>
        <div className="overflow-x-auto">
          <table className="text-xs">
            <thead>
              <tr>
                <th className="px-2 py-1 text-white/30" />
                {col_b_values.map((v: string) => (
                  <th key={v} className="px-2 py-1 font-medium text-white/40">{v}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {col_a_values.map((rowVal: string) => (
                <tr key={rowVal}>
                  <td className="pr-3 py-1 text-right font-medium text-white/50">{rowVal}</td>
                  {col_b_values.map((colVal: string) => {
                    const cell = heatmap_data.find((d: any) => d.y === rowVal && d.x === colVal);
                    const val = cell?.value ?? 0;
                    return (
                      <td key={colVal} className="p-0.5">
                        <div className="flex h-8 w-14 items-center justify-center rounded text-[11px] font-semibold text-white"
                          style={{ background: `rgba(99,102,241,${val * 0.9 + 0.05})` }}>
                          {(val * 100).toFixed(0)}%
                        </div>
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    );
  }

  return null;
}

function Stat({ label, value, color }: { label: string; value: React.ReactNode; color?: string }) {
  return (
    <div className="rounded-xl border border-white/[0.07] bg-white/[0.03] p-4">
      <p className="text-xs text-white/40">{label}</p>
      <p className={`mt-1.5 text-lg font-semibold ${color ?? "text-white"}`}>{value}</p>
    </div>
  );
}
