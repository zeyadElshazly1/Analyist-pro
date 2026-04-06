/* eslint-disable @typescript-eslint/no-explicit-any */
"use client";

import { useEffect, useState } from "react";
import { getCorrelations } from "@/lib/api";
import { AlertCircle } from "lucide-react";

type Props = { projectId: number };

function heatColor(v: number | null): string {
  if (v === null || v === undefined) return "transparent";
  const a = Math.abs(v);
  const opacity = Math.round(a * 80 + 10);
  if (v > 0) return `rgba(99, 102, 241, ${opacity / 100})`;
  return `rgba(239, 68, 68, ${opacity / 100})`;
}

function strengthBadge(strength: string) {
  const styles: Record<string, string> = {
    "Very strong": "bg-indigo-500/30 text-indigo-200",
    Strong: "bg-indigo-400/20 text-indigo-300",
    Moderate: "bg-purple-400/20 text-purple-300",
    Weak: "bg-white/10 text-white/50",
    Negligible: "bg-white/5 text-white/30",
  };
  return (
    <span className={`rounded-full px-2 py-0.5 text-xs ${styles[strength] ?? "bg-white/10 text-white/50"}`}>
      {strength}
    </span>
  );
}

export function CorrelationMatrix({ projectId }: Props) {
  const [data, setData] = useState<any | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [view, setView] = useState<"matrix" | "ranked">("matrix");

  useEffect(() => {
    getCorrelations(projectId)
      .then(setData)
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load correlations"))
      .finally(() => setLoading(false));
  }, [projectId]);

  if (loading) {
    return (
      <div className="space-y-3">
        <h2 className="font-semibold text-white">Correlation Matrix</h2>
        <div className="h-48 rounded-xl bg-white/[0.04] animate-pulse" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center gap-2 rounded-xl border border-red-500/20 bg-red-500/10 px-4 py-3 text-sm text-red-400">
        <AlertCircle className="h-4 w-4" />
        {error}
      </div>
    );
  }

  if (!data) return null;

  const cols: string[] = data.columns ?? [];
  const matrix: Record<string, Record<string, number>> = data.pearson_matrix ?? {};

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="font-semibold text-white">Correlation Matrix</h2>
        <div className="flex items-center gap-1">
          <span className="text-xs text-white/30">indigo = positive &nbsp; red = negative</span>
        </div>
      </div>

      <div className="flex gap-2">
        {(["matrix", "ranked"] as const).map((v) => (
          <button
            key={v}
            onClick={() => setView(v)}
            className={`rounded-lg px-3 py-1.5 text-xs font-medium transition-colors ${view === v ? "bg-indigo-600 text-white" : "bg-white/[0.05] text-white/50 hover:text-white"}`}
          >
            {v === "matrix" ? "Heatmap" : "Ranked Pairs"}
          </button>
        ))}
      </div>

      {view === "matrix" && cols.length > 0 && (
        <div className="overflow-x-auto">
          <table className="border-separate border-spacing-0.5 text-xs">
            <thead>
              <tr>
                <th className="w-24" />
                {cols.map((c) => (
                  <th key={c} className="w-14 text-center">
                    <div className="origin-bottom rotate-[-45deg] whitespace-nowrap text-white/40 text-[10px] h-16 flex items-end justify-center pb-1">
                      {c.slice(0, 10)}
                    </div>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {cols.map((rowCol) => (
                <tr key={rowCol}>
                  <td className="pr-2 text-right text-white/50 text-[10px] whitespace-nowrap">{rowCol.slice(0, 14)}</td>
                  {cols.map((colCol) => {
                    const v = matrix[rowCol]?.[colCol];
                    const isIdentity = rowCol === colCol;
                    return (
                      <td
                        key={colCol}
                        title={`${rowCol} × ${colCol}: ${v != null ? v.toFixed(3) : "N/A"}`}
                        className="h-8 w-14 rounded text-center text-[10px] font-mono cursor-default transition-opacity hover:opacity-80"
                        style={{
                          background: isIdentity ? "rgba(255,255,255,0.08)" : heatColor(v ?? null),
                          color: isIdentity ? "rgba(255,255,255,0.5)" : Math.abs(v ?? 0) > 0.5 ? "#fff" : "rgba(255,255,255,0.6)",
                        }}
                      >
                        {isIdentity ? "1.00" : v != null ? v.toFixed(2) : "—"}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {view === "ranked" && (
        <div className="space-y-2">
          <p className="text-xs text-white/40">
            {data.n_significant ?? 0} significant pairs (BH-corrected p &lt; 0.05)
          </p>
          {(data.pairs ?? []).slice(0, 20).map((pair: any, i: number) => (
            <div
              key={i}
              className={`flex items-center gap-3 rounded-xl border px-4 py-3 ${pair.is_significant ? "border-white/[0.1] bg-white/[0.04]" : "border-white/[0.04] bg-white/[0.01] opacity-60"}`}
            >
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-medium text-white truncate">
                    {pair.col_a} × {pair.col_b}
                  </span>
                  {strengthBadge(pair.strength)}
                  {pair.is_significant && (
                    <span className="rounded-full bg-green-500/20 px-2 py-0.5 text-xs text-green-300">sig.</span>
                  )}
                </div>
                <div className="mt-0.5 flex gap-3 text-xs text-white/40">
                  <span>Pearson r={pair.pearson_r}</span>
                  <span>Spearman r={pair.spearman_r}</span>
                  <span>adj. p={pair.adj_p}</span>
                  <span>n={pair.n}</span>
                </div>
              </div>
              <div className="flex-shrink-0 w-16 text-right">
                <span className={`text-lg font-bold ${pair.pearson_r > 0 ? "text-indigo-400" : "text-red-400"}`}>
                  {pair.pearson_r > 0 ? "+" : ""}{pair.pearson_r?.toFixed(2)}
                </span>
              </div>
            </div>
          ))}

          {(!data.pairs || data.pairs.length === 0) && (
            <p className="text-sm text-white/40">No correlations found between numeric columns.</p>
          )}
        </div>
      )}
    </div>
  );
}
