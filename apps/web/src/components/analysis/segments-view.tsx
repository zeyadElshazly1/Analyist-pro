"use client";

import { useState, useEffect } from "react";
import { getCohortColumns, runRfm, runRetention } from "@/lib/api";
import { Loader2, Users } from "lucide-react";
import { Button } from "@/components/ui/button";

type Props = { projectId: number };

const SEGMENT_COLORS: Record<string, string> = {
  Champions: "#10b981",
  Loyal: "#6366f1",
  "Potential Loyalist": "#8b5cf6",
  "At Risk": "#f59e0b",
  Lost: "#ef4444",
  "New Customer": "#06b6d4",
  Promising: "#94a3b8",
};

function RetentionHeatmap({ matrix, rowLabels, colLabels }: { matrix: (number | null)[][], rowLabels: string[], colLabels: string[] }) {
  if (!matrix?.length) return null;

  function cellColor(val: number | null): string {
    if (val == null) return "transparent";
    const r = Math.round(255 * (1 - val));
    const g = Math.round(180 * val);
    return `rgba(${r}, ${g}, 80, 0.7)`;
  }

  return (
    <div className="overflow-auto">
      <table className="text-xs border-collapse">
        <thead>
          <tr>
            <th className="px-3 py-2 text-left text-white/50 font-medium">Cohort</th>
            {colLabels.map((cl, ci) => (
              <th key={ci} className="px-2 py-2 text-center text-white/50 min-w-[60px] font-medium">P{ci}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {matrix.map((row, ri) => (
            <tr key={ri}>
              <td className="px-3 py-1.5 text-white/70 font-medium whitespace-nowrap">{rowLabels[ri]}</td>
              {row.map((val, ci) => (
                <td key={ci} className="px-2 py-1.5 text-center text-white font-medium rounded" style={{ background: cellColor(val), fontSize: "10px" }}>
                  {val != null ? `${(val * 100).toFixed(0)}%` : "—"}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function SegmentsView({ projectId }: Props) {
  const [allCols, setAllCols] = useState<string[]>([]);
  const [numCols, setNumCols] = useState<string[]>([]);
  const [dtCols, setDtCols] = useState<string[]>([]);

  const [customerCol, setCustomerCol] = useState("");
  const [dateCol, setDateCol] = useState("");
  const [revenueCol, setRevenueCol] = useState("");
  const [rfmResult, setRfmResult] = useState<any>(null);
  const [rfmLoading, setRfmLoading] = useState(false);

  const [cohortCol, setCohortCol] = useState("");
  const [periodCol, setPeriodCol] = useState("");
  const [userCol, setUserCol] = useState("");
  const [retentionResult, setRetentionResult] = useState<any>(null);
  const [retentionLoading, setRetentionLoading] = useState(false);

  const [error, setError] = useState("");
  const [mode, setMode] = useState<"rfm" | "retention">("rfm");

  useEffect(() => {
    getCohortColumns(projectId)
      .then((data: any) => {
        const all: string[] = data.all_columns || [];
        const num: string[] = data.numeric_columns || [];
        const dt: string[] = data.datetime_columns || [];
        setAllCols(all);
        setNumCols(num);
        setDtCols(dt);
        if (all.length > 0) setCustomerCol(all[0]);
        const dateSuggestion = dt.length > 0 ? dt[0] : all.find((c) => /date|time|day|month|year/i.test(c)) || "";
        setDateCol(dateSuggestion);
        if (num.length > 0) setRevenueCol(num[0]);
        if (all.length > 0) { setCohortCol(all[0]); setPeriodCol(all[Math.min(1, all.length - 1)]); setUserCol(all[0]); }
      })
      .catch(() => setError("Failed to load columns."));
  }, [projectId]);

  async function handleRfm() {
    if (!customerCol || !dateCol || !revenueCol) { setError("Fill all RFM fields."); return; }
    setRfmLoading(true); setError("");
    try {
      const data = await runRfm(projectId, customerCol, dateCol, revenueCol);
      setRfmResult(data);
    } catch (e: any) {
      try { const p = JSON.parse(e.message); setError(p.detail || e.message); }
      catch { setError(e.message || "RFM failed."); }
    } finally { setRfmLoading(false); }
  }

  async function handleRetention() {
    if (!cohortCol || !periodCol || !userCol) { setError("Fill all retention fields."); return; }
    setRetentionLoading(true); setError("");
    try {
      const data = await runRetention(projectId, cohortCol, periodCol, userCol);
      setRetentionResult(data);
    } catch (e: any) {
      try { const p = JSON.parse(e.message); setError(p.detail || e.message); }
      catch { setError(e.message || "Retention failed."); }
    } finally { setRetentionLoading(false); }
  }

  const dateOptions = dtCols.length > 0 ? dtCols : allCols;

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-lg font-semibold text-white mb-1 flex items-center gap-2">
          <Users className="h-5 w-5 text-indigo-400" /> Segments
        </h2>
        <p className="text-sm text-white/50">RFM segmentation and cohort retention analysis.</p>
      </div>

      <div className="flex gap-2">
        {(["rfm", "retention"] as const).map((m) => (
          <button key={m} onClick={() => setMode(m)}
            className={`rounded-lg px-4 py-2 text-sm font-medium transition-colors ${mode === m ? "bg-indigo-600 text-white" : "text-white/50 hover:text-white bg-white/[0.04]"}`}>
            {m === "rfm" ? "RFM Segmentation" : "Retention Matrix"}
          </button>
        ))}
      </div>

      {error && <div className="rounded-lg border border-red-500/20 bg-red-500/10 px-4 py-3 text-sm text-red-400">{error}</div>}

      {mode === "rfm" && (
        <div className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            {[
              { label: "Customer ID Column", val: customerCol, set: setCustomerCol, opts: allCols },
              { label: "Date Column", val: dateCol, set: setDateCol, opts: dateOptions },
              { label: "Revenue Column", val: revenueCol, set: setRevenueCol, opts: numCols.length > 0 ? numCols : allCols },
            ].map(({ label, val, set, opts }) => (
              <div key={label}>
                <label className="block text-xs text-white/50 mb-1">{label}</label>
                <select value={val} onChange={(e) => set(e.target.value)}
                  className="w-full rounded-lg bg-white/[0.05] border border-white/10 px-3 py-2 text-sm text-white focus:outline-none focus:ring-1 focus:ring-indigo-500">
                  {opts.length === 0 && <option value="">Loading…</option>}
                  {opts.map((c) => <option key={c} value={c}>{c}</option>)}
                </select>
              </div>
            ))}
          </div>
          <Button onClick={handleRfm} disabled={rfmLoading} className="bg-indigo-600 hover:bg-indigo-500 text-white gap-2">
            {rfmLoading ? <><Loader2 className="h-4 w-4 animate-spin" />Analyzing…</> : "Run RFM Analysis"}
          </Button>

          {rfmResult && (
            <div className="space-y-4">
              <div className="grid grid-cols-3 gap-3">
                <div className="rounded-lg bg-white/[0.03] border border-white/[0.07] p-4 text-center">
                  <div className="text-2xl font-bold text-indigo-400">{(rfmResult.total_customers || 0).toLocaleString()}</div>
                  <div className="text-xs text-white/50 mt-1">Total Customers</div>
                </div>
                <div className="rounded-lg bg-white/[0.03] border border-white/[0.07] p-4 text-center">
                  <div className="text-2xl font-bold text-indigo-400">${(rfmResult.total_revenue || 0).toLocaleString()}</div>
                  <div className="text-xs text-white/50 mt-1">Total Revenue</div>
                </div>
                <div className="rounded-lg bg-white/[0.03] border border-white/[0.07] p-4 text-center">
                  <div className="text-xl font-bold text-indigo-400">{rfmResult.analysis_date || "—"}</div>
                  <div className="text-xs text-white/50 mt-1">Analysis Date</div>
                </div>
              </div>

              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                {Object.entries(rfmResult.segment_counts || {}).map(([seg, count]) => (
                  <div key={seg} className="rounded-lg bg-white/[0.03] border border-white/[0.07] p-3">
                    <div className="flex items-center gap-2 mb-1">
                      <div className="w-2 h-2 rounded-full flex-shrink-0" style={{ background: SEGMENT_COLORS[seg] || "#94a3b8" }} />
                      <span className="text-xs text-white/60 font-medium truncate">{seg}</span>
                    </div>
                    <div className="text-xl font-bold text-white">{String(count)}</div>
                    {rfmResult.segment_stats?.[seg] && (
                      <div className="text-xs text-white/40 mt-1">
                        Avg ${(rfmResult.segment_stats[seg].avg_monetary || 0).toFixed(0)}
                      </div>
                    )}
                  </div>
                ))}
              </div>

              <div className="rounded-xl border border-white/[0.07] bg-white/[0.03] overflow-auto max-h-[300px]">
                <table className="w-full text-xs">
                  <thead className="sticky top-0 bg-[#0f172a]">
                    <tr>
                      {["Customer", "Recency (days)", "Frequency", "Monetary", "R", "F", "M", "Segment"].map((h) => (
                        <th key={h} className="px-3 py-2 text-left text-white/50 font-medium border-b border-white/[0.07] whitespace-nowrap">{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {(rfmResult.customers || []).slice(0, 100).map((c: any, i: number) => (
                      <tr key={i} className="border-b border-white/[0.04] hover:bg-white/[0.02]">
                        <td className="px-3 py-2 text-white/70">{c.customer_id}</td>
                        <td className="px-3 py-2 text-white/70">{c.recency_days}</td>
                        <td className="px-3 py-2 text-white/70">{c.frequency}</td>
                        <td className="px-3 py-2 text-white/70">${(c.monetary || 0).toFixed(2)}</td>
                        <td className="px-3 py-2 text-white/70">{c.r_score}</td>
                        <td className="px-3 py-2 text-white/70">{c.f_score}</td>
                        <td className="px-3 py-2 text-white/70">{c.m_score}</td>
                        <td className="px-3 py-2">
                          <span className="px-2 py-0.5 rounded-full text-xs font-medium" style={{ background: `${SEGMENT_COLORS[c.segment] || "#94a3b8"}22`, color: SEGMENT_COLORS[c.segment] || "#94a3b8" }}>
                            {c.segment}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      )}

      {mode === "retention" && (
        <div className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            {[
              { label: "Cohort Column", val: cohortCol, set: setCohortCol },
              { label: "Period Column", val: periodCol, set: setPeriodCol },
              { label: "User Column", val: userCol, set: setUserCol },
            ].map(({ label, val, set }) => (
              <div key={label}>
                <label className="block text-xs text-white/50 mb-1">{label}</label>
                <select value={val} onChange={(e) => set(e.target.value)}
                  className="w-full rounded-lg bg-white/[0.05] border border-white/10 px-3 py-2 text-sm text-white focus:outline-none focus:ring-1 focus:ring-indigo-500">
                  {allCols.length === 0 && <option value="">Loading…</option>}
                  {allCols.map((c) => <option key={c} value={c}>{c}</option>)}
                </select>
              </div>
            ))}
          </div>
          <Button onClick={handleRetention} disabled={retentionLoading} className="bg-indigo-600 hover:bg-indigo-500 text-white gap-2">
            {retentionLoading ? <><Loader2 className="h-4 w-4 animate-spin" />Analyzing…</> : "Build Retention Matrix"}
          </Button>

          {retentionResult && (
            <div className="rounded-xl border border-white/[0.07] bg-white/[0.03] p-4">
              <RetentionHeatmap matrix={retentionResult.matrix} rowLabels={retentionResult.row_labels} colLabels={retentionResult.col_labels} />
            </div>
          )}
        </div>
      )}
    </div>
  );
}
