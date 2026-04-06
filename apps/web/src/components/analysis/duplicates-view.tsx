/* eslint-disable @typescript-eslint/no-explicit-any */
"use client";

import { useEffect, useState } from "react";
import { getDuplicates } from "@/lib/api";
import { Copy, AlertCircle } from "lucide-react";

type Props = { projectId: number };

function SummaryCard({ label, value, sub, accent }: { label: string; value: React.ReactNode; sub?: string; accent?: string }) {
  return (
    <div className="rounded-xl border border-white/[0.07] bg-white/[0.03] p-4">
      <p className="text-xs text-white/40">{label}</p>
      <p className={`mt-1 text-2xl font-bold ${accent ?? "text-white"}`}>{value}</p>
      {sub && <p className="mt-0.5 text-xs text-white/30">{sub}</p>}
    </div>
  );
}

function SampleRow({ row, cols }: { row: Record<string, unknown>; cols: string[] }) {
  return (
    <tr className="border-b border-white/[0.04] hover:bg-white/[0.02]">
      {cols.map((col) => (
        <td key={col} className="px-3 py-2 text-xs text-white/70 truncate max-w-[120px]">
          {String(row[col] ?? "—")}
        </td>
      ))}
    </tr>
  );
}

export function DuplicatesView({ projectId }: Props) {
  const [data, setData] = useState<any | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    getDuplicates(projectId)
      .then(setData)
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load duplicate data"))
      .finally(() => setLoading(false));
  }, [projectId]);

  if (loading) {
    return (
      <div className="space-y-3">
        <h2 className="font-semibold text-white">Duplicate Detector</h2>
        <div className="grid grid-cols-3 gap-3">
          {[0, 1, 2].map((i) => (
            <div key={i} className="h-20 rounded-xl bg-white/[0.04] animate-pulse" />
          ))}
        </div>
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

  const exactRows: Record<string, unknown>[] = data.exact?.sample_rows ?? [];
  const cols = exactRows.length > 0 ? Object.keys(exactRows[0]) : [];

  return (
    <div className="space-y-5">
      <h2 className="font-semibold text-white">Duplicate Detector</h2>

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <SummaryCard
          label="Exact Duplicates"
          value={data.exact?.count ?? 0}
          sub={`${data.exact?.pct ?? 0}% of rows`}
          accent={data.exact?.count > 0 ? "text-red-400" : "text-green-400"}
        />
        <SummaryCard
          label="Near Duplicates"
          value={data.near_duplicates?.count ?? 0}
          sub="similar numeric rows"
          accent={data.near_duplicates?.count > 0 ? "text-amber-400" : "text-green-400"}
        />
        <SummaryCard
          label="Total Affected"
          value={data.impact?.total_affected ?? 0}
          sub={`${data.impact?.impact_pct ?? 0}% of dataset`}
        />
        <SummaryCard
          label="Total Rows"
          value={data.total_rows?.toLocaleString() ?? "—"}
        />
      </div>

      {/* Recommendation */}
      {data.impact?.recommendation && (
        <div className="rounded-xl border border-indigo-500/20 bg-indigo-500/10 px-4 py-3 text-sm text-indigo-300">
          {data.impact.recommendation}
        </div>
      )}

      {/* Exact duplicate sample */}
      {exactRows.length > 0 && (
        <div>
          <h3 className="mb-2 text-sm font-semibold text-white/70">Sample Duplicate Rows</h3>
          <div className="overflow-x-auto rounded-xl border border-white/[0.07]">
            <table className="w-full text-left">
              <thead>
                <tr className="border-b border-white/[0.07] bg-white/[0.03]">
                  {cols.slice(0, 8).map((col) => (
                    <th key={col} className="px-3 py-2 text-xs font-medium text-white/40 truncate max-w-[120px]">
                      {col}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {exactRows.slice(0, 10).map((row, i) => (
                  <SampleRow key={i} row={row} cols={cols.slice(0, 8)} />
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Near duplicate groups */}
      {data.near_duplicates?.groups?.length > 0 && (
        <div>
          <h3 className="mb-2 text-sm font-semibold text-white/70">
            Near-Duplicate Groups ({data.near_duplicates.groups.length})
          </h3>
          <div className="space-y-2">
            {data.near_duplicates.groups.slice(0, 8).map((group: any, i: number) => (
              <div key={i} className="flex items-center gap-3 rounded-lg border border-white/[0.05] bg-white/[0.02] px-3 py-2">
                <Copy className="h-3.5 w-3.5 text-white/30" />
                <span className="text-xs text-white/50">
                  Rows {group.indices?.join(", ")} — distance: {group.distance}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {data.exact?.count === 0 && data.near_duplicates?.count === 0 && (
        <div className="rounded-xl border border-green-500/20 bg-green-500/10 px-4 py-3 text-sm text-green-300">
          No duplicates detected. Your dataset looks clean.
        </div>
      )}
    </div>
  );
}
