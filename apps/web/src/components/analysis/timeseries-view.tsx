"use client";

import { useState, useEffect } from "react";
import { getTimeseriesColumns, runTimeseries } from "@/lib/api";
import { TrendingUp, TrendingDown, Minus, AlertCircle, Activity } from "lucide-react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
  ReferenceDot,
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

function StatCard({ label, value, sub }: { label: string; value: React.ReactNode; sub?: string }) {
  return (
    <div className="rounded-xl border border-white/[0.07] bg-white/[0.03] p-3">
      <p className="text-xs text-white/40">{label}</p>
      <p className="mt-1 text-lg font-semibold text-white">{value}</p>
      {sub && <p className="text-xs text-white/30">{sub}</p>}
    </div>
  );
}

export function TimeseriesView({ projectId }: Props) {
  const [cols, setCols] = useState<{ date_columns: string[]; value_columns: string[] } | null>(null);
  const [dateCol, setDateCol] = useState("");
  const [valueCol, setValueCol] = useState("");
  const [result, setResult] = useState<any | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [view, setView] = useState<"main" | "decomposition">("main");

  useEffect(() => {
    getTimeseriesColumns(projectId)
      .then((data) => {
        setCols(data);
        if (data.date_columns.length > 0) setDateCol(data.date_columns[0]);
        if (data.value_columns.length > 0) setValueCol(data.value_columns[0]);
      })
      .catch(() => setError("No datetime columns detected. Try converting date columns."));
  }, [projectId]);

  async function handleRun() {
    if (!dateCol || !valueCol) return;
    setLoading(true);
    setError("");
    try {
      const data = await runTimeseries(projectId, dateCol, valueCol);
      setResult(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Time series analysis failed.");
    } finally {
      setLoading(false);
    }
  }

  const summary = result?.summary;
  const dataPoints: any[] = result?.data_points ?? [];
  const anomalies = dataPoints.filter((p) => p.is_anomaly);

  return (
    <div className="space-y-4">
      <h2 className="font-semibold text-white">Time Series Analysis</h2>

      {error && (
        <div className="flex items-center gap-2 rounded-xl border border-amber-500/20 bg-amber-500/10 px-4 py-3 text-sm text-amber-300">
          <AlertCircle className="h-4 w-4 flex-shrink-0" />
          {error}
        </div>
      )}

      {cols && (
        <div className="flex flex-wrap items-end gap-3">
          <div>
            <label className="mb-1 block text-xs text-white/40">Date column</label>
            <select
              value={dateCol}
              onChange={(e) => setDateCol(e.target.value)}
              className="rounded-lg border border-white/[0.08] bg-white/[0.05] px-3 py-2 text-sm text-white focus:outline-none focus:ring-1 focus:ring-indigo-500"
            >
              {cols.date_columns.map((c) => <option key={c} value={c}>{c}</option>)}
            </select>
          </div>
          <div>
            <label className="mb-1 block text-xs text-white/40">Value column</label>
            <select
              value={valueCol}
              onChange={(e) => setValueCol(e.target.value)}
              className="rounded-lg border border-white/[0.08] bg-white/[0.05] px-3 py-2 text-sm text-white focus:outline-none focus:ring-1 focus:ring-indigo-500"
            >
              {cols.value_columns.map((c) => <option key={c} value={c}>{c}</option>)}
            </select>
          </div>
          <button
            onClick={handleRun}
            disabled={loading || !dateCol || !valueCol}
            className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-500 disabled:opacity-50 transition-colors"
          >
            {loading ? "Analyzing…" : "Analyze"}
          </button>
        </div>
      )}

      {result && summary && (
        <>
          {/* Summary stats */}
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <StatCard
              label="Trend"
              value={
                <span className={`flex items-center gap-1 ${summary.trend === "up" ? "text-green-400" : summary.trend === "down" ? "text-red-400" : "text-white"}`}>
                  {summary.trend === "up" ? <TrendingUp className="h-4 w-4" /> : summary.trend === "down" ? <TrendingDown className="h-4 w-4" /> : <Minus className="h-4 w-4" />}
                  {summary.trend === "up" ? "Upward" : summary.trend === "down" ? "Downward" : "Flat"}
                </span>
              }
              sub={`R²=${summary.trend_r2}`}
            />
            <StatCard
              label="Change"
              value={
                summary.change_pct != null
                  ? <span className={summary.change_pct > 0 ? "text-green-400" : "text-red-400"}>{summary.change_pct > 0 ? "+" : ""}{summary.change_pct}%</span>
                  : "—"
              }
              sub="first → last"
            />
            <StatCard
              label="Stationarity"
              value={
                <span className={summary.is_stationary ? "text-green-400" : "text-amber-400"}>
                  {summary.is_stationary ? "Stationary" : "Non-stationary"}
                </span>
              }
              sub={summary.adf_p != null ? `ADF p=${summary.adf_p}` : undefined}
            />
            <StatCard
              label="Anomalies"
              value={<span className={anomalies.length > 0 ? "text-red-400" : "text-green-400"}>{anomalies.length}</span>}
              sub={`of ${result.n_points} points`}
            />
          </div>

          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <StatCard label="Mean" value={summary.mean} />
            <StatCard label="Std Dev" value={summary.std} />
            <StatCard label="Min" value={summary.min} />
            <StatCard label="Max" value={summary.max} />
          </div>

          {/* View toggle */}
          <div className="flex gap-2">
            {(["main", "decomposition"] as const).map((v) => (
              <button
                key={v}
                onClick={() => setView(v)}
                className={`rounded-lg px-3 py-1.5 text-xs font-medium transition-colors ${view === v ? "bg-indigo-600 text-white" : "bg-white/[0.05] text-white/50 hover:text-white"}`}
              >
                {v === "main" ? "Main Chart" : "Decomposition"}
              </button>
            ))}
          </div>

          {view === "main" && (
            <div className="h-72">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={dataPoints}>
                  <CartesianGrid strokeDasharray="3 3" strokeOpacity={0.1} />
                  <XAxis dataKey="date" tick={{ fill: "#6b7280", fontSize: 11 }} interval="preserveStartEnd" />
                  <YAxis tick={{ fill: "#6b7280", fontSize: 11 }} />
                  <Tooltip {...DARK_TOOLTIP} />
                  <Legend wrapperStyle={{ color: "#9ca3af", fontSize: 12 }} />
                  <Line type="monotone" dataKey="value" stroke="#6366f1" strokeWidth={2} dot={false} name="Value" />
                  <Line type="monotone" dataKey="rolling_short" stroke="#a5b4fc" strokeWidth={1} strokeDasharray="4 2" dot={false} name="Short MA" />
                  <Line type="monotone" dataKey="rolling_long" stroke="#818cf8" strokeWidth={1} strokeDasharray="6 3" dot={false} name="Long MA" />
                  {anomalies.map((pt, i) => (
                    <ReferenceDot key={i} x={pt.date} y={pt.value} r={5} fill="#ef4444" stroke="#fff" strokeWidth={1} />
                  ))}
                </LineChart>
              </ResponsiveContainer>
              {anomalies.length > 0 && (
                <p className="mt-2 text-xs text-white/40">
                  <span className="inline-block h-2 w-2 rounded-full bg-red-500 mr-1.5" />
                  Red dots = anomalous points (residual &gt; 2σ from trend)
                </p>
              )}
            </div>
          )}

          {view === "decomposition" && (
            <div className="space-y-4">
              {[
                { key: "trend_component", label: "Trend", color: "#6366f1" },
                { key: "seasonal_component", label: "Seasonal", color: "#a78bfa" },
                { key: "residual_component", label: "Residual", color: "#f59e0b" },
              ].map(({ key, label, color }) => (
                <div key={key}>
                  <p className="mb-1 text-xs font-medium text-white/50">{label}</p>
                  <div className="h-28">
                    <ResponsiveContainer width="100%" height="100%">
                      <LineChart data={dataPoints}>
                        <CartesianGrid strokeDasharray="3 3" strokeOpacity={0.08} />
                        <XAxis dataKey="date" tick={{ fill: "#6b7280", fontSize: 10 }} interval="preserveStartEnd" />
                        <YAxis tick={{ fill: "#6b7280", fontSize: 10 }} />
                        <Tooltip {...DARK_TOOLTIP} />
                        <Line type="monotone" dataKey={key} stroke={color} strokeWidth={1.5} dot={false} />
                      </LineChart>
                    </ResponsiveContainer>
                  </div>
                </div>
              ))}
            </div>
          )}
        </>
      )}

      {!cols && !error && (
        <p className="text-sm text-white/40">Loading column options…</p>
      )}
    </div>
  );
}
