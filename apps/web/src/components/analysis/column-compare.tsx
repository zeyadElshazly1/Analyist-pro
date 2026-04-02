"use client";

import { useState, useEffect } from "react";
import { getCompareColumnOptions, runColumnCompare } from "@/lib/api";
import { AlertCircle } from "lucide-react";
import {
  ScatterChart,
  Scatter,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
  Line,
  LineChart,
  BarChart,
  Bar,
  Legend,
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

export function ColumnCompare({ projectId }: Props) {
  const [columns, setColumns] = useState<string[]>([]);
  const [colA, setColA] = useState("");
  const [colB, setColB] = useState("");
  const [result, setResult] = useState<any | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    getCompareColumnOptions(projectId)
      .then((data) => {
        setColumns(data.columns);
        if (data.columns.length >= 2) {
          setColA(data.columns[0]);
          setColB(data.columns[1]);
        }
      })
      .catch(() => setError("Failed to load columns."));
  }, [projectId]);

  async function handleRun() {
    if (!colA || !colB) return;
    setLoading(true);
    setError("");
    try {
      const data = await runColumnCompare(projectId, colA, colB);
      setResult(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Comparison failed.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-4">
      <h2 className="font-semibold text-white">Column Comparison</h2>

      {error && (
        <div className="flex items-center gap-2 rounded-xl border border-red-500/20 bg-red-500/10 px-4 py-3 text-sm text-red-400">
          <AlertCircle className="h-4 w-4" />
          {error}
        </div>
      )}

      <div className="flex flex-wrap items-end gap-3">
        {["A", "B"].map((label, idx) => (
          <div key={label}>
            <p className="mb-1 text-xs text-white/40">Column {label}</p>
            <select
              value={idx === 0 ? colA : colB}
              onChange={(e) => idx === 0 ? setColA(e.target.value) : setColB(e.target.value)}
              className="rounded-lg border border-white/[0.08] bg-white/[0.05] px-3 py-2 text-sm text-white focus:outline-none focus:ring-1 focus:ring-indigo-500"
            >
              {columns.map((c) => (
                <option key={c} value={c} className="bg-white text-black">
                  {c}
                </option>
              ))}
            </select>
          </div>
        ))}
        <button
          onClick={handleRun}
          disabled={loading || !colA || !colB || colA === colB}
          className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-500 disabled:opacity-50 transition-colors"
        >
          {loading ? "Comparing…" : "Compare"}
        </button>
      </div>

      {result && (
        <>
          {/* Interpretation banner */}
          <div className="rounded-xl border border-indigo-500/20 bg-indigo-500/10 px-4 py-3 text-sm text-indigo-200">
            {result.interpretation}
          </div>

          {/* Numeric × Numeric */}
          {result.type === "num_num" && (
            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                {[
                  { label: "Pearson r", value: result.pearson_r?.toFixed(3) },
                  { label: "Pearson p", value: result.pearson_p?.toFixed(5) },
                  { label: "Spearman r", value: result.spearman_r?.toFixed(3) },
                  { label: "n pairs", value: result.n },
                ].map(({ label, value }) => (
                  <div key={label} className="rounded-xl border border-white/[0.07] bg-white/[0.03] p-3 text-center">
                    <p className="text-xs text-white/40">{label}</p>
                    <p className="mt-1 text-lg font-semibold text-white">{value}</p>
                  </div>
                ))}
              </div>
              <div className="h-64">
                <ResponsiveContainer width="100%" height="100%">
                  <ScatterChart>
                    <CartesianGrid strokeDasharray="3 3" strokeOpacity={0.1} />
                    <XAxis dataKey="x" name={result.col_a} tick={{ fill: "#6b7280", fontSize: 11 }} label={{ value: result.col_a, position: "insideBottom", offset: -5, fill: "#9ca3af", fontSize: 11 }} />
                    <YAxis dataKey="y" name={result.col_b} tick={{ fill: "#6b7280", fontSize: 11 }} label={{ value: result.col_b, angle: -90, position: "insideLeft", fill: "#9ca3af", fontSize: 11 }} />
                    <Tooltip {...DARK_TOOLTIP} cursor={{ strokeDasharray: "3 3" }} />
                    <Scatter data={result.scatter ?? []} fill="#6366f1" fillOpacity={0.5} r={3} />
                  </ScatterChart>
                </ResponsiveContainer>
              </div>
            </div>
          )}

          {/* Numeric × Categorical */}
          {result.type === "num_cat" && result.group_stats && (
            <div className="space-y-4">
              {result.anova_p != null && (
                <p className="text-xs text-white/40">
                  ANOVA p={result.anova_p} —{" "}
                  <span className={result.is_significant ? "text-green-400" : "text-amber-400"}>
                    {result.is_significant ? "statistically significant" : "not significant"}
                  </span>
                </p>
              )}
              <div className="h-56">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={result.group_stats}>
                    <CartesianGrid strokeDasharray="3 3" strokeOpacity={0.1} />
                    <XAxis dataKey="category" tick={{ fill: "#6b7280", fontSize: 11 }} />
                    <YAxis tick={{ fill: "#6b7280", fontSize: 11 }} />
                    <Tooltip {...DARK_TOOLTIP} />
                    <Legend wrapperStyle={{ color: "#9ca3af", fontSize: 12 }} />
                    <Bar dataKey="mean" fill="#6366f1" radius={[4, 4, 0, 0]} name={`Mean ${result.num_col}`} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
              <div className="overflow-x-auto rounded-xl border border-white/[0.07]">
                <table className="w-full text-left text-xs">
                  <thead>
                    <tr className="border-b border-white/[0.07] bg-white/[0.03]">
                      {["Category", "Count", "Mean", "Median", "Std Dev", "Min", "Max"].map((h) => (
                        <th key={h} className="px-3 py-2 text-white/40 font-medium">{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {result.group_stats.map((g: any, i: number) => (
                      <tr key={i} className="border-b border-white/[0.04] hover:bg-white/[0.02]">
                        <td className="px-3 py-2 font-medium text-white">{g.category}</td>
                        <td className="px-3 py-2 text-white/60">{g.count}</td>
                        <td className="px-3 py-2 text-white/60">{g.mean?.toFixed(3)}</td>
                        <td className="px-3 py-2 text-white/60">{g.median?.toFixed(3)}</td>
                        <td className="px-3 py-2 text-white/60">{g.std?.toFixed(3)}</td>
                        <td className="px-3 py-2 text-white/60">{g.min?.toFixed(3)}</td>
                        <td className="px-3 py-2 text-white/60">{g.max?.toFixed(3)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Categorical × Categorical */}
          {result.type === "cat_cat" && result.heatmap && (
            <div className="space-y-3">
              {result.chi2_p != null && (
                <p className="text-xs text-white/40">
                  Chi-square p={result.chi2_p} —{" "}
                  <span className={result.is_significant ? "text-green-400" : "text-amber-400"}>
                    {result.is_significant ? "significant association" : "no significant association"}
                  </span>
                </p>
              )}
              <div className="overflow-x-auto">
                <table className="border-separate border-spacing-0.5 text-xs">
                  <thead>
                    <tr>
                      <th className="px-2 py-1 text-white/30 text-left">{result.col_a} \\ {result.col_b}</th>
                      {(result.col_labels ?? []).map((label: string) => (
                        <th key={label} className="px-2 py-1 text-white/50 text-center">{label.slice(0, 10)}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {(result.row_labels ?? []).map((rowLabel: string) => {
                      const rowCells = result.heatmap.filter((c: any) => c.row === rowLabel);
                      const maxInRow = Math.max(...rowCells.map((c: any) => c.value));
                      return (
                        <tr key={rowLabel}>
                          <td className="px-2 py-1 text-white/50 text-right">{rowLabel.slice(0, 12)}</td>
                          {(result.col_labels ?? []).map((colLabel: string) => {
                            const cell = result.heatmap.find((c: any) => c.row === rowLabel && c.col === colLabel);
                            const val = cell?.value ?? 0;
                            const opacity = maxInRow > 0 ? 0.15 + (val / maxInRow) * 0.7 : 0.1;
                            return (
                              <td
                                key={colLabel}
                                className="h-8 w-16 rounded text-center"
                                style={{ background: `rgba(99,102,241,${opacity})`, color: opacity > 0.5 ? "#fff" : "rgba(255,255,255,0.6)" }}
                              >
                                {val}
                              </td>
                            );
                          })}
                        </tr>
                      );
                    })}
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
