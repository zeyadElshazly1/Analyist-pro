/* eslint-disable @typescript-eslint/no-explicit-any */
"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { AppShell } from "@/components/layout/app-shell";
import { UploadDataset } from "@/components/project/upload-dataset";
import { RunAnalysis, type AnalysisResult } from "@/components/project/run-analysis";
import { DEFAULT_LANDING_TAB_LABEL } from "@/components/project/project-tabs";
import {
  getProject,
  getAnalysisHistory,
  getRunResults,
  type LatestRun,
  type ProjectDetail,
  type RunResultsResponse,
} from "@/lib/api";
import {
  AlertCircle,
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

// ── Adapter: canonical RunResults → RunAnalysis shape ─────────────────────────

// Canonical insight confidence scale is 0.0–1.0 (see app/schemas/insight.py).
// Live SSE results already arrive on this scale.  This adapter is the single
// boundary that has historically corrupted reopened runs by multiplying by 100;
// instead we now defensively NORMALIZE legacy stored values that are > 1 back
// down to the 0.0–1.0 canonical scale.  After this point, all downstream
// state and components can assume confidence ∈ [0, 1].
function normalizeInsightConfidence<T extends { confidence?: number }>(i: T): T {
  if (typeof i.confidence !== "number" || !Number.isFinite(i.confidence)) {
    return i;
  }
  // Legacy reopened runs may have been persisted on a 0–100 scale by an
  // earlier version of this adapter; bring them back to canonical 0.0–1.0.
  const c = i.confidence > 1 ? i.confidence / 100 : i.confidence;
  // Clamp into the canonical range so a corrupted value (e.g. NaN-ish or
  // >100) cannot leak into UI scoring/sorting heuristics.
  const clamped = Math.max(0, Math.min(1, c));
  return clamped === i.confidence ? i : { ...i, confidence: clamped };
}

function isInsightLike(value: unknown): value is Record<string, unknown> {
  return Boolean(
    value &&
    typeof value === "object" &&
    !Array.isArray(value) &&
    (
      typeof (value as Record<string, unknown>).title === "string" ||
      typeof (value as Record<string, unknown>).explanation === "string" ||
      typeof (value as Record<string, unknown>).finding === "string" ||
      typeof (value as Record<string, unknown>).insight_id === "string"
    )
  );
}

function normalizeStoredInsights(raw: unknown): ReturnType<typeof normalizeInsightConfidence>[] {
  if (!Array.isArray(raw)) return [];
  // Malformed legacy items (non-objects or missing required fields) are dropped
  // rather than passed through to UI components that assume a valid shape.
  return raw.filter(isInsightLike).map((i) => normalizeInsightConfidence(i as { confidence?: number }));
}

function adaptStoredResults(stored: RunResultsResponse): AnalysisResult {
  const hr = stored.health_result;
  const cr = stored.cleaning_result;
  const pr = stored.profile_result ?? [];

  // Preserve canonical 0.0–1.0 confidence (with defensive clamp for any
  // legacy 0–100 values still in older result_json blobs).
  // Malformed items are filtered out by normalizeStoredInsights.
  const normalizedInsights = normalizeStoredInsights(stored.insight_results);

  return {
    run_id: stored.run_id,
    analysis_id: stored.run_id,
    // intake_result carries parse confidence, warnings, preview sample, etc.
    // for the Intake Review step on reopened runs (null for legacy result_json
    // that pre-dates intake persistence — IntakeReview shows a clean empty state).
    intake_result: stored.intake_result ?? null,
    // health_result passes the canonical block directly — HealthScore/StatsCards read from it
    health_result: hr ?? null,
    // cleaning_result passes the canonical block directly — CleaningSummaryCards/CleaningReview read from it
    cleaning_result: cr ?? null,
    insights: normalizedInsights,
    insight_results: normalizedInsights,
    profile_result: pr,
    narrative: stored.narrative ?? undefined,
    executive_panel: stored.executive_panel ?? undefined,
    // story_result: pre-populate DataStoryView so reopening shows stored story
    story_result: stored.story_result ?? undefined,
    // compare_result: rehydrate the Compare tab and Report Builder context on
    // reopened runs (null when this run was never paired against another file).
    compare_result: stored.compare_result ?? null,
    large_dataset_mode: stored.large_dataset_mode === true ? true : undefined,
    full_rows: typeof stored.full_rows === "number" ? stored.full_rows : undefined,
    full_columns: typeof stored.full_columns === "number" ? stored.full_columns : undefined,
    analyzed_rows: typeof stored.analyzed_rows === "number" ? stored.analyzed_rows : undefined,
    sample_strategy: typeof stored.sample_strategy === "string" ? stored.sample_strategy : undefined,
    symbol_count: typeof stored.symbol_count === "number" ? stored.symbol_count : undefined,
    date_range_start: typeof stored.date_range_start === "string" ? stored.date_range_start : undefined,
    date_range_end: typeof stored.date_range_end === "string" ? stored.date_range_end : undefined,
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
    <section className="rounded-xl border border-white/[0.05] bg-white/[0.015] p-5 sm:p-6 lg:p-8">
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

const ACTIVE_RUN_STATUSES = new Set([
  "created",
  "cleaning_complete",
  "profiling_complete",
  "insights_complete",
]);

function formatRunStatus(status: string): string {
  return status.replace(/_/g, " ");
}

function isActiveRunStatus(status: string): boolean {
  return ACTIVE_RUN_STATUSES.has(status);
}

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
            <p className="text-sm font-medium text-white">Saved analysis available</p>
            <p className="mt-0.5 text-xs text-white/40">
              {run.filename && <span className="text-white/60">{run.filename}</span>}
              {run.filename && finishedAt && <span className="mx-1.5 text-white/20">·</span>}
              {finishedAt && <span>{finishedAt}</span>}
              <span className="mx-1.5 text-white/20">·</span>
              {/* Single source of truth for the landing step label, see
                  DEFAULT_LANDING_TAB(_LABEL) in project-tabs.tsx.  Keep this
                  honest — fresh and reopened runs both land on this step. */}
              <span className="text-white/35">Opens at {DEFAULT_LANDING_TAB_LABEL}</span>
            </p>
          </div>
        </div>
        <button
          onClick={onOpenPrevious}
          disabled={loadingPrevious}
          className="flex shrink-0 items-center gap-1.5 rounded-lg bg-emerald-600/20 px-3 py-1.5 text-xs font-medium text-emerald-300 hover:bg-emerald-600/30 disabled:opacity-60 transition-colors"
          aria-label={`Open the saved analysis at ${DEFAULT_LANDING_TAB_LABEL}`}
        >
          {loadingPrevious ? <Loader2 className="h-3 w-3 animate-spin" /> : <Zap className="h-3 w-3" />}
          Open run
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
            <p className="text-sm font-medium text-white">Last analysis failed</p>
            {run.error_summary && (
              <p className="mt-0.5 text-xs text-red-300/70">{run.error_summary}</p>
            )}
            <p className="mt-1 text-xs text-white/35">
              Upload a corrected file or run the analysis again below to retry.
            </p>
          </div>
        </div>
      </div>
    );
  }

  if (isActiveRunStatus(run.status)) {
    return (
      <div className="flex items-center gap-3 rounded-xl border border-indigo-500/20 bg-indigo-500/5 px-4 py-3">
        <Loader2 className="h-4 w-4 flex-shrink-0 animate-spin text-indigo-400" strokeWidth={1.75} />
        <div>
          <p className="text-sm font-medium text-white">Analysis in progress</p>
          <p className="mt-0.5 text-xs text-white/40 capitalize">
            {formatRunStatus(run.status)}…
          </p>
        </div>
      </div>
    );
  }

  // Unknown or stale status — do not imply something is actively running.
  return (
    <div className="flex items-center gap-3 rounded-xl border border-amber-500/20 bg-amber-500/5 px-4 py-3">
      <AlertCircle className="h-4 w-4 flex-shrink-0 text-amber-400" strokeWidth={1.75} />
      <div>
        <p className="text-sm font-medium text-white">Analysis not complete</p>
        <p className="mt-0.5 text-xs text-white/40">
          This run did not finish. Run the analysis again to refresh the result.
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

  const handleFreshRunComplete = useCallback(() => {
    setOpenError(null);
    setStoredResult(null);
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
        <div className="mx-auto w-full max-w-[1600px] space-y-6 px-6 py-6 lg:px-8 lg:py-10">

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
          <section className="rounded-xl border border-white/[0.05] bg-white/[0.015] p-5 sm:p-6 lg:p-8">
            <div className="mb-5 flex items-center gap-2.5">
              <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-white/[0.05]">
                <Database className="h-3.5 w-3.5 text-white/60" strokeWidth={1.75} />
              </div>
              <div>
                <h2 className="text-sm font-semibold text-white">
                  {project?.latest_run ? "Upload new file" : "Step 1 — Upload your file"}
                </h2>
                <p className="text-xs text-white/40">
                  {project?.latest_run
                    ? "Upload a new client file to refresh the analysis."
                    : "Drop a client CSV or Excel file to start the workflow."}
                </p>
              </div>
            </div>
            <UploadDataset projectId={projectId} />
          </section>

          {/* Analysis workflow */}
          <section className="rounded-xl border border-white/[0.05] bg-white/[0.015] p-5 sm:p-6 lg:p-8">
            <div className="mb-5 flex items-center justify-between gap-3">
              <div className="flex items-center gap-2.5">
                <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-indigo-600/15">
                  <Zap className="h-3.5 w-3.5 text-indigo-400" strokeWidth={1.75} />
                </div>
                <div>
                  <h2 className="text-sm font-semibold text-white">Analysis workflow</h2>
                  <p className="text-xs text-white/40">
                    {storedResult
                      ? "Viewing saved analysis — you can re-run at any time."
                      : project?.latest_run?.has_result
                      ? "Intake → Cleaning → Health → Findings → Report"
                      : "Run the pipeline to walk through each step."}
                  </p>
                </div>
              </div>
            </div>
            <RunAnalysis
              projectId={projectId}
              projectName={project?.name}
              initialResult={storedResult ?? undefined}
              initialRunId={project?.latest_run?.run_id}
              onFreshRunComplete={handleFreshRunComplete}
            />
          </section>

          {/* Analysis history */}
          <HistoryPanel projectId={projectId} />
        </div>
      </div>
    </AppShell>
  );
}
