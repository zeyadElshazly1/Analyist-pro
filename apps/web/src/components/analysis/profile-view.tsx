"use client";

import { useState } from "react";
import { ChevronDown, ChevronRight, AlertTriangle } from "lucide-react";
import { BarChart, Bar, ResponsiveContainer } from "recharts";

type ColProfile = {
  column: string;
  dtype: string;
  type: "numeric" | "categorical" | "datetime";
  missing: number;
  missing_pct: number;
  unique: number;
  unique_pct: number;
  flags: string[];
  // numeric
  mean?: number; median?: number; std?: number;
  min?: number; max?: number; q25?: number; q75?: number;
  skewness?: number; outliers?: number; zeros?: number;
  // categorical
  top_values?: Record<string, number>;
  most_common?: string; most_common_pct?: number;
  // datetime
  range_days?: number;
};

type Props = { profile: ColProfile[] };

function MiniViz({ col }: { col: ColProfile }) {
  if (col.type === "numeric" && col.min !== undefined && col.max !== undefined) {
    const range = col.max - col.min;
    if (range === 0) return <div className="h-3 w-full rounded bg-white/10" />;
    const q25pct = ((col.q25! - col.min) / range) * 100;
    const medpct = ((col.median! - col.min) / range) * 100;
    const iqrw = ((col.q75! - col.min) / range) * 100 - q25pct;
    return (
      <div className="relative h-3 w-full rounded bg-white/5">
        <div className="absolute top-0 h-full rounded bg-indigo-500/25" style={{ left: `${q25pct}%`, width: `${iqrw}%` }} />
        <div className="absolute top-0 h-full w-0.5 bg-indigo-400" style={{ left: `${medpct}%` }} />
      </div>
    );
  }
  if (col.type === "categorical" && col.top_values) {
    const data = Object.entries(col.top_values).slice(0, 6).map(([k, v]) => ({ k, v }));
    return (
      <div className="h-8 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} barSize={6}>
            <Bar dataKey="v" fill="#6366f1" radius={[2, 2, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    );
  }
  return null;
}

function ExpandedDetail({ col }: { col: ColProfile }) {
  return (
    <tr className="border-b border-white/[0.05] bg-white/[0.015]">
      <td colSpan={5} className="px-6 py-4">
        <div className="grid gap-3 text-xs sm:grid-cols-2 lg:grid-cols-4">
          {col.type === "numeric" && (
            <>
              {[
                ["Mean", col.mean], ["Median", col.median], ["Std dev", col.std],
                ["Min", col.min], ["Max", col.max], ["Q25", col.q25], ["Q75", col.q75],
                ["Skewness", col.skewness], ["Outliers", col.outliers], ["Zeros", col.zeros],
              ].map(([label, val]) =>
                val !== undefined ? (
                  <div key={label as string}>
                    <p className="text-white/35">{label}</p>
                    <p className="mt-0.5 font-medium text-white">{val}</p>
                  </div>
                ) : null
              )}
            </>
          )}
          {col.type === "categorical" && col.top_values && (
            <div className="col-span-full">
              <p className="mb-2 text-white/35">Top values</p>
              <div className="flex flex-wrap gap-1.5">
                {Object.entries(col.top_values).map(([k, v]) => (
                  <span key={k} className="rounded-lg bg-white/5 px-2 py-1 text-white/60">
                    {k}: <span className="text-white">{v}</span>
                  </span>
                ))}
              </div>
              {col.most_common && (
                <p className="mt-2 text-white/35">
                  Most common: <span className="text-white">{col.most_common}</span> ({col.most_common_pct}%)
                </p>
              )}
            </div>
          )}
          {col.type === "datetime" && (
            <div>
              <p className="text-white/35">Date range</p>
              <p className="mt-0.5 font-medium text-white">{col.range_days} days</p>
            </div>
          )}
          {col.flags?.length > 0 && (
            <div className="col-span-full">
              <p className="text-amber-400/80">⚠ {col.flags.join(" · ")}</p>
            </div>
          )}
        </div>
      </td>
    </tr>
  );
}

function ColRow({ col }: { col: ColProfile }) {
  const [open, setOpen] = useState(false);
  return (
    <>
      <tr
        className="cursor-pointer border-b border-white/[0.05] transition-colors hover:bg-white/[0.03]"
        onClick={() => setOpen(!open)}
      >
        <td className="px-4 py-2.5">
          <div className="flex items-center gap-2">
            {open
              ? <ChevronDown className="h-3.5 w-3.5 flex-shrink-0 text-white/25" />
              : <ChevronRight className="h-3.5 w-3.5 flex-shrink-0 text-white/25" />}
            <span className="text-sm font-medium text-white">{col.column}</span>
            {col.flags?.length > 0 && <AlertTriangle className="h-3 w-3 text-amber-400" />}
          </div>
        </td>
        <td className="px-4 py-2.5">
          <span className="rounded-full bg-white/5 px-2 py-0.5 text-[11px] text-white/45">
            {col.type ?? col.dtype}
          </span>
        </td>
        <td className="px-4 py-2.5 text-sm text-white/50">
          <span className={col.missing_pct > 10 ? "text-amber-400" : ""}>{col.missing_pct}%</span>
        </td>
        <td className="px-4 py-2.5 text-sm text-white/50">{col.unique}</td>
        <td className="w-36 px-4 py-2.5"><MiniViz col={col} /></td>
      </tr>
      {open && <ExpandedDetail col={col} />}
    </>
  );
}

export function ProfileView({ profile }: Props) {
  if (!profile || profile.length === 0) {
    return <p className="text-sm text-white/40">No profile available.</p>;
  }
  return (
    <div className="overflow-hidden rounded-xl border border-white/[0.07]">
      <div className="overflow-x-auto">
        <table className="min-w-full text-left">
          <thead className="border-b border-white/[0.07] bg-white/[0.03]">
            <tr>
              {["Column", "Type", "Missing", "Unique", "Distribution"].map((h) => (
                <th key={h} className="px-4 py-2.5 text-xs font-medium text-white/35">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {profile.map((col, i) => <ColRow key={i} col={col} />)}
          </tbody>
        </table>
      </div>
    </div>
  );
}
