"use client";

import { useEffect, useState } from "react";
import { getCorrelations } from "@/lib/api";

type Props = { projectId: number };

function heatColor(v: number): string {
  const a = Math.abs(v);
  if (v >= 0) {
    const r = Math.round(99 + (10 - 99) * a);
    const g = Math.round(102 + (10 - 102) * a);
    return `rgba(${r},${g},241,${0.15 + a * 0.75})`;
  }
  return `rgba(248,${Math.round(70 * (1 - a))},${Math.round(113 * (1 - a))},${0.15 + a * 0.75})`;
}

export function CorrelationMatrix({ projectId }: Props) {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    getCorrelations(projectId).then(setData).catch((e) => setError(e.message)).finally(() => setLoading(false));
  }, [projectId]);

  if (loading) return <p className="text-sm text-white/40">Computing correlations…</p>;
  if (error) return <p className="text-sm text-red-400">{error}</p>;
  if (!data || data.columns.length < 2) {
    return <p className="text-sm text-white/40">Need at least 2 numeric columns.</p>;
  }

  return (
    <div className="space-y-6">
      {/* Heatmap */}
      <div className="rounded-2xl border border-white/[0.07] bg-white/[0.03] p-5">
        <h3 className="mb-4 text-sm font-semibold text-white/80">Pearson correlation heatmap</h3>
        <div className="overflow-x-auto">
          <table className="text-[11px]">
            <thead>
              <tr>
                <th className="w-28 p-1" />
                {data.columns.map((c: string) => (
                  <th key={c} className="p-1 align-bottom">
                    <div className="font-medium text-white/40" style={{ writingMode: "vertical-rl", transform: "rotate(180deg)", maxHeight: 80, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                      {c}
                    </div>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {data.matrix.map((row: any) => (
                <tr key={row.column}>
                  <td className="pr-2 py-0.5 text-right text-[11px] text-white/40 truncate max-w-[112px]">{row.column}</td>
                  {data.columns.map((c: string) => {
                    const val: number = row[c];
                    const isDiag = row.column === c;
                    return (
                      <td key={c} className="p-0.5">
                        <div
                          title={`${row.column} × ${c}: ${val}`}
                          className="flex h-9 w-12 items-center justify-center rounded text-[10px] font-semibold text-white"
                          style={{ background: isDiag ? "rgba(255,255,255,0.04)" : heatColor(val) }}
                        >
                          {isDiag ? "—" : val?.toFixed(2)}
                        </div>
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="mt-4 flex items-center gap-3">
          <span className="text-xs text-white/30">−1</span>
          <div className="h-2 flex-1 rounded-full" style={{ background: "linear-gradient(to right, rgba(248,70,113,0.9), rgba(255,255,255,0.05), rgba(99,102,241,0.9))" }} />
          <span className="text-xs text-white/30">+1</span>
        </div>
      </div>

      {/* Ranked pairs */}
      <div className="rounded-2xl border border-white/[0.07] bg-white/[0.03] p-5">
        <h3 className="mb-4 text-sm font-semibold text-white/80">Ranked pairs</h3>
        <div className="space-y-2">
          {data.pairs.map((p: any, i: number) => (
            <div key={i} className="flex items-center justify-between rounded-lg border border-white/[0.05] bg-white/[0.02] px-3 py-2.5">
              <div className="flex flex-wrap items-center gap-2">
                <span className="w-5 text-xs text-white/25">{i + 1}</span>
                <span className="text-sm text-white/80">
                  <span className="font-medium text-white">{p.col_a}</span>
                  <span className="mx-1.5 text-white/25">×</span>
                  <span className="font-medium text-white">{p.col_b}</span>
                </span>
                <span className={`rounded-full border px-2 py-0.5 text-[11px] font-medium ${
                  p.strength === "Very strong" ? "border-indigo-500/20 bg-indigo-500/10 text-indigo-400" :
                  p.strength === "Strong"      ? "border-blue-500/20 bg-blue-500/10 text-blue-400" :
                  p.strength === "Moderate"    ? "border-amber-500/20 bg-amber-500/10 text-amber-400" :
                                                 "border-white/10 bg-white/5 text-white/35"
                }`}>{p.strength}</span>
                {!p.significant && <span className="text-[11px] text-white/25">not significant</span>}
              </div>
              <div className="text-right flex-shrink-0 ml-3">
                <p className={`text-sm font-bold ${p.r > 0 ? "text-indigo-400" : "text-rose-400"}`}>
                  {p.r > 0 ? "+" : ""}{p.r}
                </p>
                <p className="text-[11px] text-white/30">p={p.p_value}</p>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
