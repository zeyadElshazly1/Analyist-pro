"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { AppShell } from "@/components/layout/app-shell";
import { getProjectsWithLatestRun, ApiError } from "@/lib/api";
import {
  BarChart2,
  Clock,
  ArrowRight,
  FileText,
  Loader2,
  FolderOpen,
  AlertCircle,
} from "lucide-react";

type ProjectRow = {
  id: number;
  name: string;
  status: string;
  created_at: string;
  latest_run_at: string | null;
  latest_run_id: number | null;
};

export default function ReportsPage() {
  const [items, setItems] = useState<ProjectRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    getProjectsWithLatestRun()
      .then(setItems)
      .catch((e) => {
        setError(e instanceof ApiError ? e.userMessage : "Failed to load reports. Please try again.");
      })
      .finally(() => setLoading(false));
  }, []);

  return (
    <AppShell>
      <div className="min-h-full bg-[#080810]">
        <div className="mx-auto max-w-4xl space-y-6 p-6 lg:p-10">

          {/* Header */}
          <div>
            <h1 className="text-2xl font-bold tracking-tight text-white">Reports</h1>
            <p className="mt-1 text-sm text-white/40">
              Browse analysis reports for each project.
            </p>
          </div>

          {loading && (
            <div className="flex items-center justify-center py-20">
              <Loader2 className="h-6 w-6 animate-spin text-indigo-400" />
            </div>
          )}

          {!loading && error && (
            <div className="flex flex-col items-center gap-3 py-16 text-center">
              <AlertCircle className="h-8 w-8 text-red-400" />
              <p className="text-sm text-white/60">{error}</p>
            </div>
          )}

          {!loading && !error && items.length === 0 && (
            <div className="flex flex-col items-center gap-3 py-20 text-center">
              <FolderOpen className="h-10 w-10 text-white/20" />
              <p className="text-sm text-white/40">No projects yet. Create one to get started.</p>
              <Link
                href="/projects"
                className="mt-2 rounded-lg bg-indigo-600 px-5 py-2 text-sm font-semibold text-white hover:bg-indigo-500 transition-colors"
              >
                New project
              </Link>
            </div>
          )}

          {!loading && !error && items.length > 0 && (
            <div className="divide-y divide-white/[0.06] rounded-2xl border border-white/[0.06] bg-white/[0.02] overflow-hidden">
              {items.map((item) => (
                <div
                  key={item.id}
                  className="group flex items-center justify-between p-5 hover:bg-white/[0.02] transition-colors"
                >
                  <div className="flex items-center gap-4 min-w-0">
                    <div className="flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-xl bg-indigo-600/10">
                      <BarChart2 className="h-4 w-4 text-indigo-400" strokeWidth={1.75} />
                    </div>
                    <div className="min-w-0">
                      <p className="truncate text-sm font-medium text-white">{item.name}</p>
                      {item.latest_run_at ? (
                        <p className="mt-0.5 flex items-center gap-1 text-xs text-white/35">
                          <Clock className="h-3 w-3 flex-shrink-0" />
                          Last run {new Date(item.latest_run_at).toLocaleString()}
                        </p>
                      ) : (
                        <p className="mt-0.5 text-xs text-white/25 italic">No analysis yet</p>
                      )}
                    </div>
                  </div>

                  <div className="ml-4 flex items-center gap-3 flex-shrink-0">
                    {item.latest_run_at ? (
                      <Link
                        href={`/reports/${item.id}`}
                        className="flex items-center gap-1.5 rounded-lg bg-indigo-600/15 px-3 py-1.5 text-xs font-medium text-indigo-300 hover:bg-indigo-600/25 transition-colors"
                      >
                        <FileText className="h-3.5 w-3.5" />
                        View report
                      </Link>
                    ) : (
                      <Link
                        href={`/projects/${item.id}`}
                        className="text-xs text-white/30 hover:text-indigo-400 transition-colors"
                      >
                        Run analysis →
                      </Link>
                    )}
                    <ArrowRight className="h-4 w-4 text-white/15 group-hover:text-white/30 transition-colors" />
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </AppShell>
  );
}
