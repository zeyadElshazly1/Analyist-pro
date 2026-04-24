/* eslint-disable @typescript-eslint/no-explicit-any */
"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { AppShell } from "@/components/layout/app-shell";
import { UploadDataset } from "@/components/project/upload-dataset";
import { RunAnalysis, type AnalysisResult } from "@/components/project/run-analysis";
import {
  getProject,
  getAnalysisHistory,
  getRunResults,
  type LatestRun,
  type ProjectDetail,
  type RunResultsResponse,
} from "@/lib/api";
import {
  ArrowLeft,
  CheckCircle2,
  Clock,
  Database,
  FileText,
  Loader2,
  XCircle,
  Zap,
} from "lucide-react";

// ── Types ─────────────────────────────────────────────────────────────────────

type HistoryEntry = { id: number; project_id: number; created_at: string; file_hash: string | null };

// ── Cleaning items from canonical CleaningResult ──────────────────────────────

type CleaningItem = { step: string; detail: string; impact: "high" | "medium" | "low" };

function cleaningItemsFromCanonical(cr: Record<string, any> | null): CleaningItem[] {
  if (!cr) return [];
  const items: CleaningItem[] = [];

  for (const r of cr.renamed_columns ?? []) {
    items.push({ step: `Rename: ${r.original} → ${r.cleaned}`, detail: "Column name normalised", impact: "low" as const });
  }
  for (const col of cr.dropped_columns ?? []) {
    items.push({ step: `Drop column: ${col}`, detail: "Removed — high missingness or no content", impact: "medium" as const });
  }
  for (const fix of cr.type_fixes ?? []) {
    const count = fix.n_values_converted > 0 ? ` (${fix.n_values_converted} values)` : "";
    items.push({ step: `Type fix: ${fix.column}`, detail: `Converted to ${fix.to_dtype}${count}`, impact: "medium" as const });
  }
  for (const note of cr.missingness_notes ?? []) {
    const isSuggestion = note.strategy_applied === "safe_suggestion";
    const prefix = isSuggestion ? "[SUGGESTION] Impute missing" : "Impute missing";
    items.push({ step: `${prefix}: ${note.column}`, detail: `${note.missing_count} missing (${note.missing_pct}%), mechanism: ${note.mechanism}`, impact: (isSuggestion ? "low" : "medium") as "low" | "medium" });
  }
  const dn = cr.duplicate_notes;
  if (dn?.duplicate_rows_removed > 0) {
    items.push({ step: "Remove duplicate rows", detail: `Removed ${dn.duplicate_rows_removed} of ${dn.duplicate_rows_found} duplicates`, impact: "medium" as const });
  }
  for (const susp of cr.suspicious_columns ?? []) {
    items.push({ step: `[FLAG] ${susp.column}`, detail: susp.detail, impact: "medium" as const });
  }
  return items;
}

// ── Adapter: canonical RunResults → RunAnalysis shape ─────────────────────────

function adaptStoredResults(stored: RunResultsResponse): AnalysisResult {
  const hr = stored.health_result;
  const cr = stored.cleaning_result;
  const ir = stored.insight_results ?? [];
  const pr = stored.profile_result ?? [];
  const ms = hr?.missingness_stats ?? {};
  const cs = cr?.cleaning_summary;

  const numeric_cols = pr.filter((c: any) => c.type === "numeric").length;
  const categorical_cols = pr.filter((c: any) => c.type === "categorical").length;

  // Canonical InsightResult has confidence 0.0–1.0; UI expects 0–100.
  const insights = ir.map((i: any) =>
    typeof i.confidence === "number" && i.confidence <= 1
      ? { ...i, confidence: Math.round(i.confidence * 100) }
      : i
  );

  return {
    run_id: stored.run_id,
    analysis_id: stored.run_id,
    dataset_summary: {
      rows: hr?.row_count ?? 0,
      columns: hr?.column_count ?? 0,
      numeric_cols,
      categorical_cols,
      missing_pct: ms.missing_cell_pct ?? 0,
    },
    // health_result passes the canonical block directly — HealthScore reads from it
    health_result: hr ?? null,
    // cleaning_result passes the canonical block directly — CleaningReview reads from it
    cleaning_result: cr ?? null,
    // cleaning_summary mapped from canonical CleaningSummary for CleaningSummaryCards
    cleaning_summary: cs ? {
      original_rows: cs.original_rows,
      original_cols: cs.original_cols,
      final_rows: cs.final_rows,
      final_cols: cs.final_cols,
      rows_removed: cs.rows_removed,
      steps: cs.steps_applied,          // canonical uses steps_applied, cards expect steps
      confidence_score: cs.confidence_score,
      time_saved_estimate: cs.time_saved_estimate,
      suspicious_issues_remaining: (cr?.suspicious_columns ?? []).map((s: any) => ({
        type: s.issue_type,
        column: s.column,
        detail: s.detail,
      })),
    } : null,
    insights,
    profile: pr,
    // cleaning_report reconstructed from canonical sub-structures
    cleaning_report: cleaningItemsFromCanonical(cr),
    narrative: stored.narrative ?? undefined,
    executive_panel: stored.executive_panel ?? undefined,
    // story_result: pre-populate DataStoryView so reopening shows stored story
    story_result: stored.story_result ?? undefined,
  };
}

// ── HistoryPanel ──────────────────────────────────────────────────────────────

function HistoryPanel({ projectId }: { projectId: number }) {
  const [history, setHistory] = useState<HistoryEntry[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getAnalysisHistory(projectId, 8)
      .then(setHistory)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [projectId]);

  if (loading) return null;
  if (history.length === 0) return null;

  return (
    <section className="rounded-2xl border border-white/[0.06] bg-white/[0.02] p-6">
      <div className="mb-4 flex items-center justify-between">
        <div className="flex items-center gap-2.5">
          <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-white/[0.05]">
            <Clock className="h-3.5 w-3.5 text-white/50" strokeWidth={1.75} />
          </div>
          <h2 className="text-sm font-semibold text-white">Analysis history</h2>
        </div>
        <Link
          href={`/reports/${projectId}`}
          className="flex items-center gap-1 text-xs text-indigo-400 hover:text-indigo-300 transition-colors"
        >
          <FileText className="h-3.5 w-3.5" />
          View full report
        </Link>
      </div>

      <div className="space-y-1">
        {history.map((entry, i) => (
          <div
            key={entry.id}
            className={`flex items-center justify-between rounded-lg px-3 py-2.5 ${
              i === 0 ? "bg-indigo-600/10 border border-indigo-500/20" : "hover:bg-white/[0.02]"
            } transition-colors`}
          >
            <div className="flex items-center gap-2.5">
              <div className={`h-2 w-2 rounded-full flex-shrink-0 ${i === 0 ? "bg-indigo-400" : "bg-white/20"}`} />
              <span className="text-xs text-white/60">
                {new Date(entry.created_at).toLocaleString()}
              </span>
              {i === 0 && (
                <span className="rounded-full bg-indigo-600/20 px-2 py-0.5 text-[10px] font-medium text-indigo-400">
                  Latest
                </span>
              )}
            </div>
            {entry.file_hash && (
              <span className="font-mono text-[10px] text-white/20" title="File hash">
                #{entry.file_hash.slice(0, 8)}
              </span>
            )}
          </div>
        ))}
      </div>
    </section>
  );
}

// ── RunStateBanner ────────────────────────────────────────────────────────────

function RunStateBanner({
  run,
  onOpenPrevious,
  loadingPrevious,
}: {
  run: LatestRun;
  onOpenPrevious: () => void;
  loadingPrevious: boolean;
}) {
  const finishedAt = run.finished_at
    ? new Date(run.finished_at).toLocaleString()
    : null;

  if (run.has_result) {
    return (
      <div className="flex items-start justify-between gap-4 rounded-xl border border-emerald-500/20 bg-emerald-500/5 px-4 py-3">
        <div className="flex items-start gap-3">
          <CheckCircle2 className="mt-0.5 h-4 w-4 flex-shrink-0 text-emerald-400" strokeWidth={1.75} />
          <div>
            <p className="text-sm font-medium text-white">Previous analysis ready</p>
            <p className="mt-0.5 text-xs text-white/40">
              {run.filename && <span className="text-white/60">{run.filename}</span>}
              {run.filename && finishedAt && <span className="mx-1.5 text-white/20">·</span>}
              {finishedAt && <span>{finishedAt}</span>}
            </p>
          </div>
        </div>
        <button
          onClick={onOpenPrevious}
          disabled={loadingPrevious}
          className="flex shrink-0 items-center gap-1.5 rounded-lg bg-emerald-600/20 px-3 py-1.5 text-xs font-medium text-emerald-300 hover:bg-emerald-600/30 disabled:opacity-60 transition-colors"
        >
          {loadingPrevious && <Loader2 className="h-3 w-3 animate-spin" />}
          Open previous analysis
        </button>
      </div>
    );
  }

  if (run.status === "failed") {
    return (
      <div className="rounded-xl border border-red-500/20 bg-red-500/5 px-4 py-3">
        <div className="flex items-start gap-3">
          <XCircle className="mt-0.5 h-4 w-4 flex-shrink-0 text-red-400" strokeWidth={1.75} />
          <div>
            <p className="text-sm font-medium text-white">Last run failed</p>
            {run.error_summary && (
              <p className="mt-0.5 text-xs text-red-300/70">{run.error_summary}</p>
            )}
            <p className="mt-1 text-xs text-white/35">
              Run the analysis again below to retry.
            </p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex items-center gap-3 rounded-xl border border-indigo-500/20 bg-indigo-500/5 px-4 py-3">
      <Loader2 className="h-4 w-4 flex-shrink-0 animate-spin text-indigo-400" strokeWidth={1.75} />
      <div>
        <p className="text-sm font-medium text-white">Analysis in progress</p>
        <p className="mt-0.5 text-xs text-white/40 capitalize">
          {run.status.replace(/_/g, " ")}…
        </p>
      </div>
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function ProjectPage() {
  const params = useParams();
  const rawId = params?.id;
  const projectId = Array.isArray(rawId) ? Number(rawId[0]) : Number(rawId);

  const [project, setProject] = useState<ProjectDetail | null>(null);
  const [storedResult, setStoredResult] = useState<AnalysisResult | null>(null);
  const [loadingPrevious, setLoadingPrevious] = useState(false);
  const [openError, setOpenError] = useState<string | null>(null);

  useEffect(() => {
    if (!projectId || isNaN(projectId)) return;
    getProject(projectId)
      .then(setProject)
      .catch(() => {});
  }, [projectId]);

  async function handleOpenPrevious() {
    const runId = project?.latest_run?.run_id;
    if (!runId) return;
    setLoadingPrevious(true);
    setOpenError(null);
    try {
      const stored = await getRunResults(runId);
      setStoredResult(adaptStoredResults(stored));
    } catch {
      setOpenError("Could not load the previous analysis. Please try again.");
    } finally {
      setLoadingPrevious(false);
    }
  }

  if (!projectId || isNaN(projectId)) {
    return (
      <AppShell>
        <div className="min-h-full bg-[#080810] p-10">
          <h1 className="text-2xl font-bold text-white">Invalid project</h1>
          <p className="mt-2 text-sm text-white/50">The project ID is missing or invalid.</p>
        </div>
      </AppShell>
    );
  }

  return (
    <AppShell>
      <div className="min-h-full bg-[#080810]">
        <div className="mx-auto max-w-4xl space-y-6 p-6 lg:p-10">

          {/* Breadcrumb + header */}
          <div>
            <Link
              href="/projects"
              className="mb-3 inline-flex items-center gap-1.5 text-xs text-white/35 hover:text-white/60 transition-colors"
            >
              <ArrowLeft className="h-3 w-3" />
              Workspaces
            </Link>
            <div className="flex items-center justify-between gap-3">
              <div className="flex items-center gap-3">
                <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-indigo-600/15">
                  <Database className="h-4.5 w-4.5 text-indigo-400" strokeWidth={1.75} />
                </div>
                <div>
                  <p className="text-[11px] text-white/30">Workspace #{projectId}</p>
                  <h1 className="text-xl font-bold tracking-tight text-white">
                    {project?.name ?? "Loading…"}
                  </h1>
                </div>
              </div>
              <Link
                href={`/reports/${projectId}`}
                className="hidden items-center gap-1.5 rounded-lg border border-white/10 px-3 py-1.5 text-xs text-white/50 hover:border-white/20 hover:text-white/70 transition-colors sm:flex"
              >
                <FileText className="h-3.5 w-3.5" />
                View report
              </Link>
            </div>
          </div>

          {/* Latest-run state banner */}
          {project?.latest_run && (
            <RunStateBanner
              run={project.latest_run}
              onOpenPrevious={handleOpenPrevious}
              loadingPrevious={loadingPrevious}
            />
          )}

          {/* Error loading previous */}
          {openError && (
            <div className="rounded-xl border border-red-500/20 bg-red-500/10 px-4 py-3 text-xs text-red-400">
              {openError}
            </div>
          )}

          {/* Dataset upload */}
          <section className="rounded-2xl border border-white/[0.06] bg-white/[0.02] p-6">
            <div className="mb-5 flex items-center gap-2.5">
              <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-white/[0.05]">
                <Database className="h-3.5 w-3.5 text-white/60" strokeWidth={1.75} />
              </div>
              <div>
                <h2 className="text-sm font-semibold text-white">Dataset</h2>
                <p className="text-xs text-white/40">
                  {project?.latest_run
                    ? "Upload a new file to run fresh analysis."
                    : "Upload a CSV or Excel file to begin."}
                </p>
              </div>
            </div>
            <UploadDataset projectId={projectId} />
          </section>

          {/* Analysis — receives stored result when user clicks "Open previous analysis" */}
          <section className="rounded-2xl border border-white/[0.06] bg-white/[0.02] p-6">
            <div className="mb-5 flex items-center gap-2.5">
              <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-indigo-600/15">
                <Zap className="h-3.5 w-3.5 text-indigo-400" strokeWidth={1.75} />
              </div>
              <div>
                <h2 className="text-sm font-semibold text-white">Analysis</h2>
                <p className="text-xs text-white/40">
                  {project?.latest_run?.has_result
                    ? "Run again to refresh with the latest file."
                    : "Run the full pipeline — insights, charts, and data quality report."}
                </p>
              </div>
            </div>
            <RunAnalysis
              projectId={projectId}
              initialResult={storedResult ?? undefined}
              initialRunId={project?.latest_run?.run_id}
            />
          </section>

          {/* Analysis history */}
          <HistoryPanel projectId={projectId} />
        </div>
      </div>
    </AppShell>
  );
}
