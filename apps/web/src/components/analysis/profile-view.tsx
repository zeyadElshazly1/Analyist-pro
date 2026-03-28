"use client";

import { useState } from "react";
import { ChevronDown, ChevronRight, AlertTriangle } from "lucide-react";
import {
  BarChart,
  Bar,
  ResponsiveContainer,
  Tooltip,
} from "recharts";

type ColProfile = {
  column: string;
  type: string;
  dtype: string;
  missing: number;
  missing_pct: number;
  unique: number;
  unique_pct: number;
  flags: string[];
  // numeric
  mean?: number;
  median?: number;
  std?: number;
  min?: number;
  max?: number;
  q25?: number;
  q75?: number;
  skewness?: number;
  kurtosis?: number;
  is_normal?: boolean;
  outliers_iqr?: number;
  // categorical
  top_values?: Record<string, number>;
  most_common?: string;
  most_common_pct?: number;
  // chart suggestion
  recommended_chart?: string;
};

type Props = {
  profile: ColProfile[];
};

function TypeBadge({ type }: { type: string }) {
  const styles: Record<string, string> = {
    numeric: "bg-indigo-500/20 text-indigo-300",
    categorical: "bg-purple-500/20 text-purple-300",
    datetime: "bg-teal-500/20 text-teal-300",
  };
  return (
    <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${styles[type] ?? "bg-white/10 text-white/60"}`}>
      {type}
    </span>
  );
}

function MiniBar({ value, max }: { value: number; max: number }) {
  const pct = max > 0 ? (value / max) * 100 : 0;
  return (
    <div className="flex items-center gap-2">
      <div className="h-1.5 w-20 rounded-full bg-white/10">
        <div
          className="h-full rounded-full bg-indigo-500"
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}

function NumericMiniViz({ col }: { col: ColProfile }) {
  const { mean = 0, median = 0, q25 = 0, q75 = 0, min = 0, max = 0 } = col;
  const range = max - min;
  if (range === 0) return null;

  const pct = (v: number) => `${Math.max(0, Math.min(100, ((v - min) / range) * 100)).toFixed(1)}%`;

  return (
    <div className="mt-3">
      <p className="mb-2 text-xs text-white/40">Distribution (IQR box)</p>
      <div className="relative h-6 w-full rounded bg-white/5">
        {/* IQR box */}
        <div
          className="absolute top-1 h-4 rounded bg-indigo-500/40 border border-indigo-500/60"
          style={{ left: pct(q25), width: `calc(${pct(q75)} - ${pct(q25)})` }}
        />
        {/* Median line */}
        <div
          className="absolute top-0 h-full w-0.5 bg-indigo-300"
          style={{ left: pct(median) }}
        />
        {/* Mean marker */}
        <div
          className="absolute top-1 h-4 w-0.5 bg-amber-400"
          style={{ left: pct(mean) }}
        />
      </div>
      <div className="mt-1 flex justify-between text-xs text-white/30">
        <span>{min?.toFixed(2)}</span>
        <span className="text-white/50">median={median?.toFixed(2)}</span>
        <span>{max?.toFixed(2)}</span>
      </div>
    </div>
  );
}

function CategoricalMiniViz({ col }: { col: ColProfile }) {
  if (!col.top_values) return null;
  const entries = Object.entries(col.top_values).slice(0, 5);
  const maxCount = Math.max(...entries.map(([, v]) => v));
  const data = entries.map(([k, v]) => ({ name: k.slice(0, 12), value: v }));

  return (
    <div className="mt-3">
      <p className="mb-1 text-xs text-white/40">Top values</p>
      <div className="h-20">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} margin={{ top: 0, right: 0, bottom: 0, left: 0 }}>
            <Bar dataKey="value" fill="#6366f1" radius={[3, 3, 0, 0]} />
            <Tooltip
              contentStyle={{ background: "#1a1a2e", border: "1px solid rgba(255,255,255,0.1)", borderRadius: 8 }}
              labelStyle={{ color: "#fff", fontSize: 11 }}
              itemStyle={{ color: "#a5b4fc", fontSize: 11 }}
            />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

function ColRow({ col }: { col: ColProfile }) {
  const [open, setOpen] = useState(false);
  const hasFlags = col.flags && col.flags.length > 0;

  return (
    <div className="border-b border-white/[0.05] last:border-0">
      <button
        className="flex w-full items-center gap-3 py-3 px-2 text-left hover:bg-white/[0.03] transition-colors rounded-lg"
        onClick={() => setOpen((v) => !v)}
      >
        <span className="text-white/30 flex-shrink-0">
          {open ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
        </span>
        <span className="flex-1 text-sm font-medium text-white truncate">{col.column}</span>
        <TypeBadge type={col.type} />
        {hasFlags && (
          <AlertTriangle className="h-3.5 w-3.5 text-amber-400 flex-shrink-0" />
        )}
        <span className="text-xs text-white/40 w-16 text-right">{col.missing_pct}% null</span>
        <span className="text-xs text-white/40 w-20 text-right">{col.unique.toLocaleString()} unique</span>
      </button>

      {open && (
        <div className="px-4 pb-4 space-y-3">
          {/* Flags */}
          {hasFlags && (
            <div className="flex flex-wrap gap-1.5">
              {col.flags.map((f, i) => (
                <span
                  key={i}
                  className="rounded-full border border-amber-400/30 bg-amber-400/10 px-2 py-0.5 text-xs text-amber-300"
                >
                  {f}
                </span>
              ))}
            </div>
          )}

          {col.type === "numeric" && (
            <>
              <div className="grid grid-cols-3 gap-3 sm:grid-cols-6">
                {[
                  { label: "Mean", value: col.mean?.toFixed(3) },
                  { label: "Median", value: col.median?.toFixed(3) },
                  { label: "Std Dev", value: col.std?.toFixed(3) },
                  { label: "Min", value: col.min?.toFixed(3) },
                  { label: "Max", value: col.max?.toFixed(3) },
                  { label: "IQR Outliers", value: col.outliers_iqr },
                ].map(({ label, value }) => (
                  <div key={label} className="rounded-lg bg-white/[0.04] p-2 text-center">
                    <p className="text-xs text-white/40">{label}</p>
                    <p className="mt-0.5 text-sm font-semibold text-white">{value ?? "—"}</p>
                  </div>
                ))}
              </div>

              <div className="flex items-center gap-3 text-xs">
                <span className="text-white/40">Skewness: <span className="text-white/70">{col.skewness?.toFixed(3)}</span></span>
                <span className="text-white/40">Kurtosis: <span className="text-white/70">{col.kurtosis?.toFixed(3)}</span></span>
                <span className={`rounded-full px-2 py-0.5 ${col.is_normal ? "bg-green-500/20 text-green-300" : "bg-amber-500/20 text-amber-300"}`}>
                  {col.is_normal ? "Normal" : "Non-normal"}
                </span>
              </div>

              <NumericMiniViz col={col} />
            </>
          )}

          {col.type === "categorical" && (
            <>
              <div className="grid grid-cols-2 gap-3">
                <div className="rounded-lg bg-white/[0.04] p-2">
                  <p className="text-xs text-white/40">Most Common</p>
                  <p className="mt-0.5 text-sm font-semibold text-white truncate">{col.most_common}</p>
                </div>
                <div className="rounded-lg bg-white/[0.04] p-2">
                  <p className="text-xs text-white/40">Most Common %</p>
                  <p className="mt-0.5 text-sm font-semibold text-white">{col.most_common_pct}%</p>
                </div>
              </div>
              <CategoricalMiniViz col={col} />
            </>
          )}

          {col.type === "datetime" && (
            <div className="grid grid-cols-2 gap-3">
              {[
                { label: "Min Date", value: (col as any).min },
                { label: "Max Date", value: (col as any).max },
                { label: "Range (days)", value: (col as any).range_days },
              ].map(({ label, value }) => (
                <div key={label} className="rounded-lg bg-white/[0.04] p-2">
                  <p className="text-xs text-white/40">{label}</p>
                  <p className="mt-0.5 text-sm font-semibold text-white">{value ?? "—"}</p>
                </div>
              ))}
            </div>
          )}

          {/* Completeness bar */}
          <div className="flex items-center gap-3 text-xs text-white/40">
            <span>Completeness</span>
            <div className="flex-1 h-1.5 rounded-full bg-white/10">
              <div
                className="h-full rounded-full bg-indigo-500"
                style={{ width: `${100 - col.missing_pct}%` }}
              />
            </div>
            <span>{(100 - col.missing_pct).toFixed(1)}%</span>
          </div>
        </div>
      )}
    </div>
  );
}

export function ProfileView({ profile }: Props) {
  if (!profile || profile.length === 0) {
    return <p className="text-sm text-white/40">No column profiles available.</p>;
  }

  const flaggedCount = profile.filter((c) => c.flags && c.flags.length > 0).length;

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-3 text-sm text-white/50">
        <span>{profile.length} columns</span>
        {flaggedCount > 0 && (
          <span className="flex items-center gap-1 text-amber-400">
            <AlertTriangle className="h-3.5 w-3.5" />
            {flaggedCount} flagged
          </span>
        )}
      </div>

      {/* Column header */}
      <div className="flex items-center gap-3 px-2 text-xs text-white/30 font-medium uppercase tracking-wider">
        <span className="w-4" />
        <span className="flex-1">Column</span>
        <span className="w-20">Type</span>
        <span className="w-4" />
        <span className="w-16 text-right">Null %</span>
        <span className="w-20 text-right">Unique</span>
      </div>

      <div className="rounded-xl border border-white/[0.07] bg-white/[0.02] overflow-hidden">
        {profile.map((col) => (
          <ColRow key={col.column} col={col} />
        ))}
      </div>
    </div>
  );
}
