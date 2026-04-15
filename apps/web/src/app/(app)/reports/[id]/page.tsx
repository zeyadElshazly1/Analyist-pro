/* eslint-disable @typescript-eslint/no-explicit-any */
"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { AppShell } from "@/components/layout/app-shell";
import { getProject, getAnalysisHistory, getAnalysisResult, shareAnalysis, exportReport, ApiError } from "@/lib/api";
import { StatsCards } from "@/components/analysis/stats-cards";
import { HealthScore } from "@/components/analysis/health-score";
import { InsightHighlights } from "@/components/analysis/insight-highlights";
import { InsightsList } from "@/components/analysis/insights-list";
import { CleaningReport } from "@/components/analysis/cleaning-report";
import { CleaningSummaryCards } from "@/components/analysis/cleaning-summary-cards";
import { ProfileView } from "@/components/analysis/profile-view";
import { ExecutivePanel } from "@/components/analysis/executive-panel";
import {
  ArrowLeft,
  Loader2,
  AlertCircle,
  Share2,
  Download,
  Copy,
  Check,
  Clock,
  RefreshCw,
} from "lucide-react";

type HistoryEntry = { id: number; project_id: number; created_at: string };


export default function ReportDetailPage() {
  const params = useParams();
  const rawId = params?.id;
  const projectId = Array.isArray(rawId) ? Number(rawId[0]) : Number(rawId);

  const [projectName, setProjectName] = useState<string | null>(null);
  const [result, setResult] = useState<Record<string, unknown> | null>(null);
  const [history, setHistory] = useState<HistoryEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [shareToken, setShareToken] = useState<string | null>(null);
  const [sharing, setSharing] = useState(false);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    if (!projectId || isNaN(projectId)) return;

    async function load() {
      try {
        // Load project name and analysis history in parallel
        const [project, hist] = await Promise.all([
          getProject(projectId).catch(() => null),
          getAnalysisHistory(projectId, 5).catch(() => [] as HistoryEntry[]),
        ]);
        if (project) setProjectName(project.name);
        setHistory(hist);

        if (hist.length === 0) {
          setError("No analysis found for this project. Run an analysis first.");
          return;
        }

        // Fetch the stored result for the latest run (no re-running)
        const stored = await getAnalysisResult(hist[0].id);
        setResult(stored.result);
      } catch (e) {
        setError(e instanceof ApiError ? e.userMessage : "Failed to load report. Please try again.");
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [projectId]);

  async function handleShare() {
    setSharing(true);
    try {
      const { share_token } = await shareAnalysis(projectId);
      setShareToken(share_token);
    } finally {
      setSharing(false);
    }
  }

  function handleCopy() {
    if (!shareToken) return;
    navigator.clipboard.writeText(`${window.location.origin}/share/${shareToken}`).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  }

  if (!projectId || isNaN(projectId)) {
    return (
      <AppShell>
        <div className="p-10">
          <p className="text-red-400">Invalid project ID.</p>
        </div>
      </AppShell>
    );
  }

  return (
    <AppShell>
      <div className="min-h-full bg-[#080810]">
        <div className="mx-auto max-w-5xl space-y-6 p-6 lg:p-10">

          {/* Breadcrumb */}
          <div>
            <Link
              href="/reports"
              className="mb-3 inline-flex items-center gap-1.5 text-xs text-white/35 hover:text-white/60 transition-colors"
            >
              <ArrowLeft className="h-3 w-3" />
              Reports
            </Link>
            <div className="flex flex-wrap items-center justify-between gap-4">
              <div>
                <p className="text-xs text-white/30">Project #{projectId}</p>
                <h1 className="text-xl font-bold tracking-tight text-white">
                  {projectName ?? "Loading…"}
                </h1>
              </div>

              {/* Actions */}
              {result && (
                <div className="flex flex-wrap items-center gap-2">
                  <button
                    onClick={() => exportReport(projectId, "html")}
                    className="flex items-center gap-1.5 rounded-lg border border-white/10 px-3 py-1.5 text-xs text-white/60 hover:text-white hover:border-white/20 transition-colors"
                  >
                    <Download className="h-3.5 w-3.5" />
                    Export HTML
                  </button>

                  <button
                    onClick={() => exportReport(projectId, "xlsx")}
                    className="flex items-center gap-1.5 rounded-lg border border-emerald-500/30 bg-emerald-500/10 px-3 py-1.5 text-xs text-emerald-400 hover:bg-emerald-500/20 transition-colors"
                  >
                    <Download className="h-3.5 w-3.5" />
                    Export Excel
                  </button>

                  {!shareToken ? (
                    <button
                      onClick={handleShare}
                      disabled={sharing}
                      className="flex items-center gap-1.5 rounded-lg border border-white/10 px-3 py-1.5 text-xs text-white/60 hover:text-white hover:border-white/20 transition-colors disabled:opacity-50"
                    >
                      {sharing ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Share2 className="h-3.5 w-3.5" />}
                      Share
                    </button>
                  ) : (
                    <button
                      onClick={handleCopy}
                      className="flex items-center gap-1.5 rounded-lg border border-indigo-500/30 bg-indigo-500/10 px-3 py-1.5 text-xs text-indigo-300 hover:bg-indigo-500/20 transition-colors"
                    >
                      {copied ? <Check className="h-3.5 w-3.5 text-emerald-400" /> : <Copy className="h-3.5 w-3.5" />}
                      {copied ? "Copied!" : "Copy link"}
                    </button>
                  )}

                  <Link
                    href={`/projects/${projectId}`}
                    className="flex items-center gap-1.5 rounded-lg bg-indigo-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-indigo-500 transition-colors"
                  >
                    <RefreshCw className="h-3.5 w-3.5" />
                    Re-run
                  </Link>
                </div>
              )}
            </div>
          </div>

          {/* History timeline */}
          {history.length > 0 && (
            <div className="flex items-center gap-3 overflow-x-auto">
              {history.map((h, i) => (
                <div
                  key={h.id}
                  className={`flex items-center gap-1.5 rounded-full px-3 py-1 text-xs whitespace-nowrap ${
                    i === 0
                      ? "bg-indigo-600/20 text-indigo-300 border border-indigo-500/30"
                      : "bg-white/[0.04] text-white/35 border border-white/[0.06]"
                  }`}
                >
                  <Clock className="h-3 w-3" />
                  {i === 0 ? "Latest · " : ""}
                  {new Date(h.created_at).toLocaleString()}
                </div>
              ))}
            </div>
          )}

          {/* Loading */}
          {loading && (
            <div className="flex items-center justify-center py-24">
              <div className="space-y-3 text-center">
                <Loader2 className="mx-auto h-6 w-6 animate-spin text-indigo-400" />
                <p className="text-sm text-white/40">Loading analysis…</p>
              </div>
            </div>
          )}

          {/* Error */}
          {error && !loading && (
            <div className="flex flex-col items-center gap-4 py-16 text-center">
              <AlertCircle className="h-8 w-8 text-red-400" />
              <p className="text-sm text-white/60">{error}</p>
              <Link
                href={`/projects/${projectId}`}
                className="rounded-lg bg-indigo-600 px-5 py-2 text-sm font-semibold text-white hover:bg-indigo-500 transition-colors"
              >
                Go to project →
              </Link>
            </div>
          )}

          {/* Report body */}
          {result && !loading && (
            <div className="space-y-6">
              {/* Stats */}
              <StatsCards summary={result.dataset_summary as any} />

              {/* Executive Panel — above insights */}
              {!!result.executive_panel && (
                <div className="space-y-3">
                  <h2 className="font-semibold text-white">Executive Summary</h2>
                  <ExecutivePanel panel={result.executive_panel as any} />
                </div>
              )}

              {/* Health + Cleaning */}
              <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
                <div className="rounded-2xl border border-white/[0.07] bg-white/[0.03] p-6">
                  <HealthScore score={result.health_score as any} />
                </div>
                <div className="rounded-2xl border border-white/[0.07] bg-white/[0.03] p-6">
                  <h2 className="mb-4 text-sm font-semibold uppercase tracking-wider text-white/70">
                    Cleaning Summary
                  </h2>
                  <CleaningSummaryCards summary={result.cleaning_summary as any} />
                </div>
              </div>

              {/* Highlights */}
              <div className="rounded-2xl border border-white/[0.07] bg-white/[0.03] p-6">
                <h2 className="mb-4 font-semibold text-white">Top Highlights</h2>
                <InsightHighlights insights={result.insights as any} />
              </div>

              {/* Column profile */}
              <div className="rounded-2xl border border-white/[0.07] bg-white/[0.03] p-6">
                <h2 className="mb-4 font-semibold text-white">Column Profiles</h2>
                <ProfileView profile={result.profile as any} />
              </div>

              {/* All insights */}
              <div className="rounded-2xl border border-white/[0.07] bg-white/[0.03] p-6">
                <h2 className="mb-4 font-semibold text-white">All Insights</h2>
                <InsightsList insights={result.insights as any} />
              </div>

              {/* Cleaning report */}
              <div className="rounded-2xl border border-white/[0.07] bg-white/[0.03] p-6">
                <h2 className="mb-4 font-semibold text-white">Cleaning Report</h2>
                <CleaningReport items={result.cleaning_report as any} />
              </div>
            </div>
          )}
        </div>
      </div>
    </AppShell>
  );
}
