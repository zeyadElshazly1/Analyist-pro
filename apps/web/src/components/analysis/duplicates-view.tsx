"use client";

import { useEffect, useState } from "react";
import { getDuplicates } from "@/lib/api";
import { Copy, AlertTriangle, CheckCircle2 } from "lucide-react";

type Props = { projectId: number };

export function DuplicatesView({ projectId }: Props) {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    getDuplicates(projectId).then(setData).catch((e) => setError(e.message)).finally(() => setLoading(false));
  }, [projectId]);

  if (loading) return <p className="text-sm text-white/40">Scanning for duplicates…</p>;
  if (error) return <p className="text-sm text-red-400">{error}</p>;
  if (!data) return null;

  return (
    <div className="space-y-5">
      <div className="grid gap-3 sm:grid-cols-3">
        <Card icon={<Copy className="h-4 w-4 text-white/40" />} label="Total rows" value={data.total_rows.toLocaleString()} />
        <Card
          icon={<AlertTriangle className="h-4 w-4 text-amber-400" />}
          label="Exact duplicates"
          value={`${data.exact_duplicates.count} (${data.exact_duplicates.pct}%)`}
          warn={data.exact_duplicates.count > 0}
        />
        <Card
          icon={<AlertTriangle className="h-4 w-4 text-orange-400" />}
          label="Near duplicates"
          value={String(data.near_duplicates.count)}
          warn={data.near_duplicates.count > 0}
        />
      </div>

      <Section title="Exact duplicates" subtitle="Rows identical across all columns.">
        {data.exact_duplicates.count === 0
          ? <Good text="No exact duplicates found." />
          : <SampleTable rows={data.exact_duplicates.sample_rows} />}
      </Section>

      <Section
        title="Near duplicates"
        subtitle={`Numerically similar rows (KNN distance < 0.1). Columns used: ${data.near_duplicates.numeric_cols_used?.join(", ") || "—"}`}
      >
        {data.near_duplicates.count === 0
          ? <Good text="No near duplicates found." />
          : <SampleTable rows={data.near_duplicates.sample_rows} />}
      </Section>
    </div>
  );
}

function Card({ icon, label, value, warn }: { icon: React.ReactNode; label: string; value: string; warn?: boolean }) {
  return (
    <div className={`rounded-xl border p-4 ${warn ? "border-amber-500/20 bg-amber-500/5" : "border-white/[0.07] bg-white/[0.03]"}`}>
      <div className="flex items-center gap-2 mb-2">{icon}<p className="text-xs text-white/40">{label}</p></div>
      <p className={`text-xl font-semibold ${warn ? "text-amber-400" : "text-white"}`}>{value}</p>
    </div>
  );
}

function Good({ text }: { text: string }) {
  return <p className="flex items-center gap-2 text-sm text-emerald-400"><CheckCircle2 className="h-4 w-4" />{text}</p>;
}

function Section({ title, subtitle, children }: { title: string; subtitle: string; children: React.ReactNode }) {
  return (
    <div className="rounded-2xl border border-white/[0.07] bg-white/[0.03] p-5">
      <h3 className="mb-1 text-sm font-semibold text-white">{title}</h3>
      <p className="mb-4 text-xs text-white/40">{subtitle}</p>
      {children}
    </div>
  );
}

function SampleTable({ rows }: { rows: Record<string, any>[] }) {
  if (!rows?.length) return null;
  const cols = Object.keys(rows[0]).slice(0, 6);
  return (
    <div className="overflow-x-auto">
      <table className="min-w-full text-xs">
        <thead className="border-b border-white/[0.06]">
          <tr>{cols.map((c) => <th key={c} className="px-3 py-2 font-medium text-white/35">{c}</th>)}</tr>
        </thead>
        <tbody>
          {rows.slice(0, 10).map((row, i) => (
            <tr key={i} className="border-b border-white/[0.04]">
              {cols.map((c) => <td key={c} className="px-3 py-2 text-white/65">{String(row[c] ?? "—")}</td>)}
            </tr>
          ))}
        </tbody>
      </table>
      {rows.length > 10 && <p className="mt-2 text-xs text-white/30">Showing 10 of {rows.length} rows</p>}
    </div>
  );
}
