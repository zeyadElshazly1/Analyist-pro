/* eslint-disable @typescript-eslint/no-explicit-any */
"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { BarChart2, AlertCircle, Loader2, Lock } from "lucide-react";
import { getSharedAnalysis } from "@/lib/api";
import { StatsCards } from "@/components/analysis/stats-cards";
import { HealthScore } from "@/components/analysis/health-score";
import { InsightHighlights } from "@/components/analysis/insight-highlights";
import { InsightsList } from "@/components/analysis/insights-list";
import { CleaningSummaryCards } from "@/components/analysis/cleaning-summary-cards";

type SharedData = {
  project_id: number;
  created_at: string;
  result: Record<string, unknown>;
};

export default function SharePage() {
  const params = useParams();
  const token = Array.isArray(params?.token) ? params.token[0] : (params?.token as string);

  const [data, setData] = useState<SharedData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!token) return;
    getSharedAnalysis(token)
      .then(setData)
      .catch((e) => setError(e instanceof Error ? e.message : "Share link not found."))
      .finally(() => setLoading(false));
  }, [token]);

  return (
    <div className="min-h-screen bg-[#080810] text-white">
      {/* Header */}
      <header className="border-b border-white/[0.06] bg-[#09090f]/80 backdrop-blur-sm">
        <div className="mx-auto flex max-w-5xl items-center justify-between px-6 py-3">
          <Link href="/" className="flex items-center gap-2">
            <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-gradient-to-br from-indigo-500 to-violet-600">
              <BarChart2 className="h-3.5 w-3.5 text-white" strokeWidth={2.5} />
            </div>
            <span className="text-sm font-bold text-white">
              Analyst<span className="text-indigo-400">Pro</span>
            </span>
          </Link>
          <div className="flex items-center gap-2 text-xs text-white/40">
            <Lock className="h-3 w-3" />
            Read-only shared view
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-5xl space-y-6 px-6 py-10">
        {loading && (
          <div className="flex items-center justify-center py-24">
            <Loader2 className="h-6 w-6 animate-spin text-indigo-400" />
          </div>
        )}

        {error && (
          <div className="flex flex-col items-center justify-center gap-4 py-24 text-center">
            <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-red-500/10">
              <AlertCircle className="h-6 w-6 text-red-400" />
            </div>
            <div>
              <h2 className="text-lg font-semibold text-white">Link not found</h2>
              <p className="mt-1 text-sm text-white/50">{error}</p>
            </div>
            <Link
              href="/"
              className="mt-2 rounded-lg bg-indigo-600 px-5 py-2 text-sm font-semibold text-white hover:bg-indigo-500 transition-colors"
            >
              Go to AnalystPro
            </Link>
          </div>
        )}

        {data && !loading && (() => {
          // insight_results replaced insights for new analyses; fall back for old stored results.
          const insights = (data.result.insights ?? data.result.insight_results ?? []) as any;
          return (
          <>
            {/* Meta */}
            <div className="rounded-2xl border border-white/[0.06] bg-white/[0.02] p-6">
              <p className="text-xs text-white/30">Shared analysis · Project #{data.project_id}</p>
              <p className="mt-1 text-xs text-white/20">
                Generated {new Date(data.created_at).toLocaleString()}
              </p>
            </div>

            {/* Stats */}
            <StatsCards summary={data.result.dataset_summary as any} />

            {/* Health + Cleaning */}
            <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
              <div className="rounded-2xl border border-white/[0.07] bg-white/[0.03] p-6">
                <HealthScore score={data.result.health_score as any} />
              </div>
              <div className="rounded-2xl border border-white/[0.07] bg-white/[0.03] p-6">
                <h2 className="mb-4 text-sm font-semibold uppercase tracking-wider text-white/70">
                  Cleaning Summary
                </h2>
                <CleaningSummaryCards summary={data.result.cleaning_summary as any} />
              </div>
            </div>

            {/* Highlights */}
            <div className="rounded-2xl border border-white/[0.07] bg-white/[0.03] p-6">
              <h2 className="mb-4 font-semibold text-white">Top Highlights</h2>
              <InsightHighlights insights={insights} />
            </div>

            {/* All insights */}
            <div className="rounded-2xl border border-white/[0.07] bg-white/[0.03] p-6">
              <h2 className="mb-4 font-semibold text-white">All Insights</h2>
              <InsightsList insights={insights} />
            </div>

            {/* CTA */}
            <div className="rounded-2xl border border-indigo-500/20 bg-indigo-600/8 p-6 text-center">
              <p className="text-sm text-white/60">
                Want to run your own analysis?
              </p>
              <Link
                href="/signup"
                className="mt-3 inline-block rounded-lg bg-indigo-600 px-6 py-2 text-sm font-semibold text-white hover:bg-indigo-500 transition-colors"
              >
                Try AnalystPro free
              </Link>
            </div>
          </>
          );
        })()}
      </main>
    </div>
  );
}
