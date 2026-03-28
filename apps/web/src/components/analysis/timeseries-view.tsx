"use client";

import { useEffect, useState } from "react";
import { getTimeseriesColumns, runTimeseries } from "@/lib/api";
import {
  LineChart, Line, BarChart, Bar,
  XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid,
} from "recharts";
import { TrendingUp, TrendingDown, Minus } from "lucide-react";

type Props = { projectId: number };

const TS = {
  background: "#111113", border: "1px solid rgba(255,255,255,0.08)",
  borderRadius: "8px", color: "#f5f7fa", fontSize: 12,
};
const tick = { fill: "#6b7280", fontSize: 11 };
const grid = { strokeDasharray: "3 3", strokeOpacity: 0.08 };

export function TimeseriesView({ projectId }: Props) {
  const [dateCols, setDateCols] = useState<string[]>([]);
  const [valueCols, setValueCols] = useState<string[]>([]);
  const [dateCol, setDateCol] = useState("");
  const [valueCol, setValueCol] = useState("");
  const [result, setResult] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [colsLoading, setColsLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    getTimeseriesColumns(projectId)
      .then((d) => {
        setDateCols(d.date_columns ?? []);
        setValueCols(d.value_columns ?? []);
        if (d.date_columns?.[0]) setDateCol(d.date_columns[0]);
        if (d.value_columns?.[0]) setValueCol(d.value_columns[0]);
      })
      .catch(() => setError("Failed to load columns"))
      .finally(() => setColsLoading(false));
  }, [projectId]);

  async function run() {
    setLoading(true); setError("");
    try { setResult(await runTimeseries(projectId, dateCol, valueCol)); }
    catch (e) { setError(e instanceof Error ? e.message : "Failed"); }
    finally { setLoading(false); }
  }

  if (colsLoading) return <p className="text-sm text-white/40">Detecting date columns…</p>;

  if (dateCols.length === 0) {
    return (
      <div className="rounded-xl border border-amber-500/15 bg-amber-500/5 p-5">
        <p className="text-sm text-amber-400">
          No date columns detected. Your dataset needs a column with dates or timestamps.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-end gap-3">
        <Sel label="Date column" value={dateCol} options={dateCols} onChange={setDateCol} />
        <Sel label="Metric" value={valueCol} options={valueCols} onChange={setValueCol} />
        <button onClick={run} disabled={loading}
          className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-500 disabled:opacity-60">
          {loading ? "Analyzing…" : "Analyze"}
        </button>
      </div>

      {error && <p className="text-sm text-red-400">{error}</p>}

      {result && (
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <MiniStat label="First value" value={result.summary.first_value} />
            <MiniStat label="Last value" value={result.summary.last_value} />
            <MiniStat
              label="Change"
              value={`${result.summary.change_pct > 0 ? "+" : ""}${result.summary.change_pct}%`}
              color={result.summary.change_pct > 0 ? "text-emerald-400" : result.summary.change_pct < 0 ? "text-red-400" : "text-white"}
            />
            <MiniStat
              label="Trend"
              value={
                result.summary.trend === "upward"
                  ? <span className="flex items-center gap-1 text-emerald-400"><TrendingUp className="h-4 w-4" />Upward</span>
                  : result.summary.trend === "downward"
                  ? <span className="flex items-center gap-1 text-red-400"><TrendingDown className="h-4 w-4" />Downward</span>
                  : <span className="flex items-center gap-1 text-white/50"><Minus className="h-4 w-4" />Flat</span>
              }
            />
          </div>

          <div className="rounded-2xl border border-white/[0.07] bg-white/[0.03] p-5">
            <p className="mb-4 text-sm font-medium text-white/80">
              {result.value_col} over time <span className="text-white/30">({result.frequency})</span>
            </p>
            <div className="h-[260px]">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={result.data_points}>
                  <CartesianGrid {...grid} />
                  <XAxis dataKey="date" tick={tick} />
                  <YAxis tick={tick} width={50} />
                  <Tooltip contentStyle={TS} />
                  <Line type="monotone" dataKey="value" stroke="#6366f1" strokeWidth={2} dot={false} activeDot={{ r: 4 }} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>

          <div className="rounded-2xl border border-white/[0.07] bg-white/[0.03] p-5">
            <p className="mb-4 text-sm font-medium text-white/80">Bar view</p>
            <div className="h-[200px]">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={result.data_points}>
                  <CartesianGrid {...grid} />
                  <XAxis dataKey="date" tick={tick} />
                  <YAxis tick={tick} width={50} />
                  <Tooltip contentStyle={TS} />
                  <Bar dataKey="value" fill="#6366f1" radius={[3, 3, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function Sel({ label, value, options, onChange }: { label: string; value: string; options: string[]; onChange: (v: string) => void }) {
  return (
    <div className="space-y-1">
      <label className="text-xs text-white/40">{label}</label>
      <select value={value} onChange={(e) => onChange(e.target.value)}
        className="rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-white">
        {options.map((c) => <option key={c} value={c}>{c}</option>)}
      </select>
    </div>
  );
}

function MiniStat({ label, value, color }: { label: string; value: React.ReactNode; color?: string }) {
  return (
    <div className="rounded-xl border border-white/[0.07] bg-white/[0.03] p-4">
      <p className="text-xs text-white/40">{label}</p>
      <p className={`mt-1.5 text-lg font-semibold ${color ?? "text-white"}`}>{value}</p>
    </div>
  );
}
