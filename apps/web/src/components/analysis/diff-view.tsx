"use client";

import { useState, useEffect } from "react";
import { getAnalysisHistory, getAnalysisDiff, ApiError } from "@/lib/api";
import type { AnalysisDiff } from "@/lib/api";
import { GitCompare, TrendingUp, TrendingDown, Minus, AlertCircle, CheckCircle, Plus, Trash2 } from "lucide-react";

type HistoryItem = { id: number; created_at: string | null; file_hash: string | null };

function fmt(date: string | null) {
  if (!date) return "Unknown";
  return new Date(date).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
}

function DeltaBadge({ delta, direction }: { delta: number; direction: "up" | "down" | "unchanged" }) {
  if (direction === "unchanged") {
    return <span className="text-white/40 text-xs">no change</span>;
  }
  const positive = delta > 0;
  return (
    <span className={`inline-flex items-center gap-0.5 text-xs font-medium ${positive ? "text-emerald-400" : "text-red-400"}`}>
      {positive ? <TrendingUp className="h-3 w-3" /> : <TrendingDown className="h-3 w-3" />}
      {positive ? "+" : ""}{typeof delta === "number" ? (Number.isInteger(delta) ? delta : delta.toFixed(1)) : delta}
    </span>
  );
}

type Props = { projectId: number };

export function DiffView({ projectId }: Props) {
  const [history, setHistory] = useState<HistoryItem[]>([]);
  const [loadingHistory, setLoadingHistory] = useState(true);
  const [runA, setRunA] = useState<number | "">("");
  const [runB, setRunB] = useState<number | "">("");
  const [diff, setDiff] = useState<AnalysisDiff | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    setLoadingHistory(true);
    getAnalysisHistory(projectId, 20)
      .then(setHistory)
      .catch(() => {})
      .finally(() => setLoadingHistory(false));
  }, [projectId]);

  async function handleCompare() {
    if (!runA || !runB || runA === runB) {
      setError("Select two different runs to compare.");
      return;
    }
    setLoading(true);
    setError("");
    setDiff(null);
    try {
      const result = await getAnalysisDiff(Number(runA), Number(runB));
      setDiff(result);
    } catch (e) {
      setError(e instanceof ApiError ? e.userMessage : "Comparison failed. Please try again.");
    } finally {
      setLoading(false);
    }
  }

  if (loadingHistory) {
    return <div className="space-y-3">{[0, 1, 2].map(i => <div key={i} className="h-10 rounded-lg bg-white/[0.04] animate-pulse" />)}</div>;
  }

  if (history.length < 2) {
    return (
      <div className="flex flex-col items-center justify-center py-20 text-center space-y-3">
        <GitCompare className="h-10 w-10 text-white/20" />
        <h3 className="text-base font-medium text-white">No runs to compare yet</h3>
        <p className="text-sm text-white/40 max-w-xs">
          Run analysis at least twice (e.g. after cleaning or re-uploading data) to compare results.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-lg font-semibold text-white mb-1 flex items-center gap-2">
          <GitCompare className="h-5 w-5 text-indigo-400" /> Compare Runs
        </h2>
        <p className="text-sm text-white/50">Select two analysis runs to see what changed between them.</p>
      </div>

      {/* Run selectors */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        {([["Baseline (A)", runA, setRunA], ["Comparison (B)", runB, setRunB]] as const).map(
          ([label, value, setter]) => (
            <div key={label}>
              <label className="block text-xs font-medium text-white/50 mb-1.5">{label}</label>
              <select
                value={value}
                onChange={(e) => setter(e.target.value ? Number(e.target.value) : "")}
                className="w-full rounded-lg border border-white/[0.08] bg-white/[0.04] px-3 py-2 text-sm text-white focus:outline-none focus:border-indigo-500/50"
              >
                <option value="">Select a run…</option>
                {history.map((r) => (
                  <option key={r.id} value={r.id}>
                    Run #{r.id} — {fmt(r.created_at)}
                    {r.file_hash ? ` (${r.file_hash.slice(0, 7)})` : ""}
                  </option>
                ))}
              </select>
            </div>
          )
        )}
      </div>

      {error && (
        <div className="flex items-center gap-2 rounded-lg border border-red-500/20 bg-red-500/10 px-4 py-3 text-sm text-red-400">
          <AlertCircle className="h-4 w-4 flex-shrink-0" />
          {error}
        </div>
      )}

      <button
        onClick={handleCompare}
        disabled={!runA || !runB || runA === runB || loading}
        className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-500 disabled:opacity-50 transition-colors"
      >
        {loading ? "Comparing…" : "Compare"}
      </button>

      {/* Diff results */}
      {diff && (
        <div className="space-y-6">
          {/* Header */}
          <div className="rounded-xl border border-white/[0.07] bg-white/[0.02] p-4 text-sm">
            <div className="flex items-center justify-between flex-wrap gap-2">
              <span className="text-white/60">
                Run <span className="text-white font-medium">#{diff.run_a.id}</span> → Run{" "}
                <span className="text-white font-medium">#{diff.run_b.id}</span>
              </span>
              {diff.same_file ? (
                <span className="text-xs text-amber-400 bg-amber-500/10 border border-amber-500/20 px-2 py-0.5 rounded-full">
                  Same file — different analysis run
                </span>
              ) : (
                <span className="text-xs text-indigo-400 bg-indigo-500/10 border border-indigo-500/20 px-2 py-0.5 rounded-full">
                  Different files
                </span>
              )}
            </div>
          </div>

          {/* Metrics */}
          {diff.metrics.length > 0 && (
            <div>
              <h3 className="text-sm font-semibold text-white/70 mb-3 uppercase tracking-wider text-xs">Metric Changes</h3>
              <div className="rounded-xl border border-white/[0.07] overflow-hidden">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-white/[0.07] bg-white/[0.02]">
                      <th className="px-4 py-2.5 text-left text-xs font-medium text-white/50">Metric</th>
                      <th className="px-4 py-2.5 text-right text-xs font-medium text-white/50">Baseline</th>
                      <th className="px-4 py-2.5 text-right text-xs font-medium text-white/50">Current</th>
                      <th className="px-4 py-2.5 text-right text-xs font-medium text-white/50">Change</th>
                    </tr>
                  </thead>
                  <tbody>
                    {diff.metrics.map((m) => (
                      <tr key={m.name} className="border-b border-white/[0.04] last:border-0">
                        <td className="px-4 py-2.5 text-white/80">{m.name}</td>
                        <td className="px-4 py-2.5 text-right text-white/50 tabular-nums">
                          {m.a ?? "—"}
                        </td>
                        <td className="px-4 py-2.5 text-right text-white tabular-nums">
                          {m.b ?? "—"}
                        </td>
                        <td className="px-4 py-2.5 text-right">
                          <DeltaBadge delta={m.delta} direction={m.direction} />
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Insights diff */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className="rounded-xl border border-emerald-500/20 bg-emerald-500/5 p-4">
              <div className="flex items-center gap-2 mb-3">
                <Plus className="h-4 w-4 text-emerald-400" />
                <h3 className="text-sm font-semibold text-emerald-400">
                  New Insights ({diff.insights.new.length})
                </h3>
              </div>
              {diff.insights.new.length === 0 ? (
                <p className="text-xs text-white/30">None</p>
              ) : (
                <ul className="space-y-2">
                  {diff.insights.new.slice(0, 5).map((ins, i) => (
                    <li key={i} className="text-xs text-white/70 border-l-2 border-emerald-500/40 pl-2">
                      {String((ins as Record<string, unknown>).finding ?? "").slice(0, 120)}
                    </li>
                  ))}
                  {diff.insights.new.length > 5 && (
                    <li className="text-xs text-white/40">+{diff.insights.new.length - 5} more</li>
                  )}
                </ul>
              )}
            </div>

            <div className="rounded-xl border border-white/[0.07] bg-white/[0.02] p-4">
              <div className="flex items-center gap-2 mb-3">
                <CheckCircle className="h-4 w-4 text-white/40" />
                <h3 className="text-sm font-semibold text-white/50">
                  Resolved ({diff.insights.resolved.length})
                </h3>
              </div>
              {diff.insights.resolved.length === 0 ? (
                <p className="text-xs text-white/30">None</p>
              ) : (
                <ul className="space-y-2">
                  {diff.insights.resolved.slice(0, 5).map((ins, i) => (
                    <li key={i} className="text-xs text-white/40 line-through border-l-2 border-white/10 pl-2">
                      {String((ins as Record<string, unknown>).finding ?? "").slice(0, 120)}
                    </li>
                  ))}
                  {diff.insights.resolved.length > 5 && (
                    <li className="text-xs text-white/30">+{diff.insights.resolved.length - 5} more</li>
                  )}
                </ul>
              )}
            </div>
          </div>

          {/* Column changes */}
          {(diff.columns.added.length > 0 || diff.columns.removed.length > 0 || diff.columns.changed.length > 0) && (
            <div>
              <h3 className="text-sm font-semibold text-white/70 mb-3 uppercase tracking-wider text-xs">Column Changes</h3>
              <div className="space-y-2">
                {diff.columns.added.map((c, i) => (
                  <div key={i} className="flex items-center gap-2 text-xs text-emerald-400">
                    <Plus className="h-3 w-3" />
                    <span className="font-mono">{String((c as Record<string, unknown>).name ?? "")}</span>
                    <span className="text-white/30">added</span>
                  </div>
                ))}
                {diff.columns.removed.map((c, i) => (
                  <div key={i} className="flex items-center gap-2 text-xs text-red-400">
                    <Trash2 className="h-3 w-3" />
                    <span className="font-mono">{String((c as Record<string, unknown>).name ?? "")}</span>
                    <span className="text-white/30">removed</span>
                  </div>
                ))}
                {diff.columns.changed.map((c) => (
                  <div key={c.name} className="text-xs">
                    <span className="font-mono text-white/70">{c.name}</span>
                    <span className="text-white/30 ml-2">
                      {Object.entries(c.changes).map(([field, { a, b }]) =>
                        `${field}: ${a} → ${b}`
                      ).join(", ")}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Unchanged summary */}
          {diff.insights.unchanged_count > 0 && (
            <p className="text-xs text-white/30">
              {diff.insights.unchanged_count} insight{diff.insights.unchanged_count !== 1 ? "s" : ""} unchanged between runs.
            </p>
          )}
        </div>
      )}
    </div>
  );
}
