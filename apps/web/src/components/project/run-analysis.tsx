"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { Button } from "@/components/ui/button";
import { Clock, Loader2, Play, CheckCircle2, Share2, Copy, Check, Download } from "lucide-react";

import { StatsCards } from "@/components/analysis/stats-cards";
import { InsightsList } from "@/components/analysis/insights-list";
import { HealthScore } from "@/components/analysis/health-score";
import {
  cleaningItemsFromCanonical,
  type CleaningItem,
  type CanonicalCleaningResult,
} from "@/components/analysis/cleaning-report";
import { ProjectTabs, getStepForTab, DEFAULT_LANDING_TAB } from "./project-tabs";
import type { StepStatus } from "./project-tabs";
import { CleaningReview } from "./cleaning-review";
import { IntakeReview, type IntakeResult } from "./intake-review";
import { AnalysisPlanCard } from "@/components/analysis/analysis-plan-card";
import { CleaningSummaryCards } from "@/components/analysis/cleaning-summary-cards";
import { InsightHighlights } from "@/components/analysis/insight-highlights";
import { LargeDatasetTransparencyBanner } from "@/components/analysis/large-dataset-transparency";
import { RecommendedAction } from "@/components/analysis/recommended-action";
import { ChartViewer } from "@/components/analysis/chart-viewer";
import { ProfileView } from "@/components/analysis/profile-view";
import { TimeseriesView } from "@/components/analysis/timeseries-view";
import { DuplicatesView } from "@/components/analysis/duplicates-view";
import { OutlierView } from "@/components/analysis/outlier-view";
import { CorrelationMatrix } from "@/components/analysis/correlation-matrix";
import { ColumnCompare } from "@/components/analysis/column-compare";
import { MultifileCompare } from "@/components/analysis/multifile-compare";
import { JoinView } from "@/components/analysis/join-view";
import { PredictionsView } from "@/components/analysis/predictions-view";
import { AiChatView } from "@/components/analysis/ai-chat-view";
import { ReportBuilder, type ReportInsightItem, type ReportExecutivePanel, type ReportHealthBlock, type ReportCleaningBlock } from "./report-builder";
import { PivotView } from "@/components/analysis/pivot-view";
import { SegmentsView } from "@/components/analysis/segments-view";
import { AbTestsView } from "@/components/analysis/ab-tests-view";
import { QueryView } from "@/components/analysis/query-view";
import { DataStoryView } from "@/components/analysis/data-story-view";
import { DataTableView } from "@/components/analysis/data-table-view";
import { DiffView } from "@/components/analysis/diff-view";
import { ApiError, getFreshToken, shareAnalysis, downloadCleanedData, pickLargeDatasetMeta } from "@/lib/api";
import type { CompareResult, LargeDatasetMeta } from "@/lib/api";
import { toast } from "@/components/ui/toast";
import { SafePanel } from "@/components/ui/error-boundary";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL || "http://127.0.0.1:8000";

type Insight = {
  // canonical V1 fields (InsightResult)
  insight_id?: string;
  category?: string;      // InsightCategory — use over legacy `type`
  explanation?: string;   // replaces `finding`
  recommendation?: string; // replaces `action`
  columns_used?: string[];
  method_used?: string;
  report_safe?: boolean;
  caveats?: string[];
  chart_suggestion?: string;
  // legacy fields (raw pipeline / backward-compat SSE result)
  type?: string;
  finding?: string;
  action?: string;
  description?: string;
  why_it_matters?: string;
  likely_drivers?: string;
  // common to both
  title?: string;
  severity?: string;
  confidence?: number;    // canonical: 0.0–1.0; legacy: 0–100
  evidence?: string;
};

type ColProfile = {
  column: string;
  type: string;
  dtype: string;
  missing: number;
  missing_pct: number;
  unique: number;
  unique_pct: number;
  flags: string[];
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
  top_values?: Record<string, number>;
  most_common?: string;
  most_common_pct?: number;
  recommended_chart?: string;
};

export type AnalysisResult = {
  analysis_id?: number;
  dataset_summary?: {
    rows?: number;
    columns?: number;
    numeric_cols?: number;
    categorical_cols?: number;
    missing_pct?: number;
    large_dataset_mode?: boolean;
    analyzed_rows?: number;
    sample_strategy?: string | null;
  } | null;
  health_score?: {
    total?: number;
    score?: number;
    grade?: string;
    label?: string;
    color?: string;
    breakdown?: {
      completeness: number;
      uniqueness: number;
      consistency: number;
      validity: number;
      structure: number;
    };
    deductions?: string[];
  } | null;
  analysis_plan?: import("@/lib/api").AnalysisPlan | null;  // Dataset Intelligence Layer (86C)
  intake_result?: Record<string, unknown> | null;    // canonical IntakeResult block
  cleaning_summary?: Record<string, unknown> | null;
  cleaning_result?: Record<string, unknown> | null;  // canonical CleaningResult block
  health_result?: Record<string, unknown> | null;    // canonical HealthResult block
  profile_result?: ColProfile[] | null;              // canonical ProfileResult block
  profile?: ColProfile[] | null;                     // legacy fallback
  insight_results?: unknown[] | null;                // canonical InsightResult[]
  executive_panel?: Record<string, unknown> | null;  // canonical executive panel
  insights: Insight[];
  cleaning_report?: CleaningItem[] | null;
  narrative?: string;
  story_result?: import("@/lib/api").DataStory | null;  // stored AI data story
  // Compare block — populated when the user has run /explore/multifile against
  // this project; pinned to the active run via run_tracker.persist_compare_result.
  compare_result?: CompareResult | null;
} & Partial<LargeDatasetMeta> & {
  [key: string]: unknown;
};

type Props = {
  projectId: number;
  projectName?: string;
  initialResult?: AnalysisResult;          // pre-populated from stored run
  initialRunId?: number;                   // run_id for the stored result (used as analysisId)
  initialCompareResult?: CompareResult;    // pre-populated compare (e.g. demo mode)
  /** Called when a live SSE run finishes successfully — parent can refresh project/latest_run for banners. */
  onFreshRunComplete?: () => void;
};

type ProgressState = {
  step: string;
  progress: number;
  detail: string;
};

// ── Step completion derivation ────────────────────────────────────────────────

function deriveStepStatuses(
  result: AnalysisResult | null,
  visited: Set<string>,
  compare: CompareResult | null,
): Record<string, StepStatus> {
  function slot(stepId: string, hasData: boolean, needsAttention: boolean): StepStatus {
    if (!hasData) return "unavailable";
    if (needsAttention) return "attention";
    return visited.has(stepId) ? "complete" : "available";
  }

  if (!result) {
    return {
      intake: "unavailable", cleaning: "unavailable", health: "unavailable",
      insights: "unavailable", compare: "unavailable", report: "unavailable",
    };
  }

  // Health score — handle both top-level legacy field and canonical health_result block
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const hs = result.health_score as any;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const hr = result.health_result as any;
  const rawScore: number = hs?.total ?? hs?.score ?? hr?.health_score?.total_score ?? 0;
  const grade: string =
    hs?.grade ?? hr?.health_score?.grade
    ?? (rawScore >= 80 ? "A" : rawScore >= 60 ? "B" : rawScore >= 40 ? "C" : "D");

  // Cleaning — attention if suspicious columns or unremoved duplicate rows
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const cr = result.cleaning_result as any;
  const cleaningAttention = Boolean(
    (cr?.suspicious_columns?.length ?? 0) > 0 ||
    ((cr?.duplicate_notes?.duplicate_rows_found ?? 0) > 0 && !cr?.duplicate_notes?.removed),
  );

  // Health — attention if grade C/D or any high-severity warning
  const healthWarnings: Array<{ severity: string }> = (hr?.health_warnings ?? []) as Array<{ severity: string }>;
  const highWarningCount = healthWarnings.filter((w) => w.severity === "high").length;
  const healthAttention = grade === "C" || grade === "D" || highWarningCount > 0;

  // Findings — attention if fewer than half of insights are report-safe.
  // Canonical insight confidence is 0.0–1.0 (see app/schemas/insight.py and
  // the adapter in projects/[id]/page.tsx).  Multiply for the threshold only.
  const insights = result.insights ?? [];
  const safeCount = insights.filter((i) => {
    if (typeof i.report_safe === "boolean") return i.report_safe;
    const conf =
      typeof i.confidence === "number" && Number.isFinite(i.confidence)
        ? Math.max(0, Math.min(100, i.confidence * 100))
        : 0;
    const cat = (i.category ?? i.type ?? "") as string;
    return (
      (i.severity === "high" || i.severity === "medium") &&
      conf >= 60 &&
      cat !== "data_quality" && cat !== "missing_pattern"
    );
  }).length;
  const findingsAttention = insights.length > 0 && safeCount < Math.ceil(insights.length / 2);

  // Compare — attention if any high-severity caution flag
  const compareAttention = (compare?.caution_flags ?? []).some((f) => f.severity === "high");

  // Report — attention if insights exist but none are report-safe
  const reportAttention = insights.length > 0 && safeCount === 0;

  return {
    intake:   slot("intake",   true,                grade === "D"),
    cleaning: slot("cleaning", !!cr,                cleaningAttention),
    health:   slot("health",   !!hr,                healthAttention),
    insights: slot("insights", insights.length > 0, findingsAttention),
    compare:  slot("compare",  !!compare,           compareAttention),
    report:   slot("report",   true,                reportAttention),
  };
}

function TabPanel({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-w-0 w-full rounded-xl border border-white/[0.06] bg-white/[0.025] p-6 shadow-[inset_0_1px_0_0_rgba(255,255,255,0.03)] sm:p-8 lg:p-10">
      {children}
    </div>
  );
}

function ProgressBar({ progress, step, detail }: ProgressState) {
  return (
    <div className="rounded-xl border border-white/[0.07] bg-white/[0.02] p-4 space-y-3">
      <div className="flex items-center justify-between text-sm">
        <span className="text-white/80 font-medium">{step}</span>
        <span className="text-white/40">{progress}%</span>
      </div>
      {detail && <p className="text-xs text-white/40">{detail}</p>}
      <div className="h-1.5 w-full rounded-full bg-white/[0.06] overflow-hidden">
        <div
          className="h-full rounded-full bg-indigo-500 transition-all duration-500 ease-out"
          style={{ width: `${progress}%` }}
        />
      </div>
    </div>
  );
}

function healthTotalFromResult(result: AnalysisResult | null): number | null {
  if (!result) return null;
  const hs = result.health_score;
  if (hs && typeof hs === "object") {
    if (typeof hs.total === "number" && Number.isFinite(hs.total)) return hs.total;
    if (typeof hs.score === "number" && Number.isFinite(hs.score)) return hs.score;
  }
  const hr = result.health_result as { health_score?: { total_score?: number } } | null | undefined;
  const ts = hr?.health_score?.total_score;
  if (typeof ts === "number" && Number.isFinite(ts)) return ts;
  return null;
}

export function RunAnalysis({
  projectId,
  projectName,
  initialResult,
  initialRunId,
  initialCompareResult,
  onFreshRunComplete,
}: Props) {
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<AnalysisResult | null>(null);
  const [analysisId, setAnalysisId] = useState<number | null>(null);
  const [isStoredResult, setIsStoredResult] = useState(false);
  // Default landing tab — fresh runs and reopened runs both start here.  The
  // RunStateBanner promises "Opens at <DEFAULT_LANDING_TAB_LABEL>" so this
  // must stay tied to the centralized constant.
  const [tab, setTab] = useState(DEFAULT_LANDING_TAB);
  // Ephemeral in-session step visitation — reset whenever a new result loads
  const [visitedSteps, setVisitedSteps] = useState<Set<string>>(
    new Set<string>([DEFAULT_LANDING_TAB]),
  );

  // Hydrate from a stored run passed by the parent page.
  // Runs when initialResult changes (e.g. after parent fetches /run/{id}/results).
  useEffect(() => {
    if (initialResult) {
      setResult(initialResult);
      setAnalysisId(initialRunId ?? null);
      setTab(DEFAULT_LANDING_TAB);
      setIsStoredResult(true);
      // Rehydrate compareResult from the persisted block on the run so the
      // Compare tab and Report Builder both show the saved comparison
      // without forcing the user to re-run /explore/multifile.  null when
      // the run was never paired against another file.
      setCompareResult(initialResult.compare_result ?? null);
      // Reset visitation — user is now viewing the default landing step
      setVisitedSteps(new Set<string>([DEFAULT_LANDING_TAB]));
    }
  }, [initialResult, initialRunId]);
  const [downloading, setDownloading] = useState(false);
  const [compareResult, setCompareResult] = useState<CompareResult | null>(null);

  useEffect(() => {
    if (initialCompareResult) setCompareResult(initialCompareResult);
  }, [initialCompareResult]);

  // Sync tab ↔ URL hash for shareable deep-links
  useEffect(() => {
    const hash = window.location.hash.slice(1);
    if (hash) setTab(hash);
  }, []);

  const handleTabChange = useCallback((newTab: string) => {
    setTab(newTab);
    window.history.replaceState(null, "", `#${newTab}`);
    setVisitedSteps((prev) => {
      const stepId = getStepForTab(newTab);
      if (prev.has(stepId)) return prev;
      const next = new Set(prev);
      next.add(stepId);
      return next;
    });
  }, []);
  const [error, setError] = useState("");
  const [progress, setProgress] = useState<ProgressState | null>(null);
  const [shareToken, setShareToken] = useState<string | null>(null);
  const [sharing, setSharing] = useState(false);
  const [copied, setCopied] = useState(false);
  const esRef = useRef<EventSource | null>(null);

  const largeDatasetMeta = result
    ? pickLargeDatasetMeta(result as Record<string, unknown>)
    : undefined;

  async function handleRun() {
    if (esRef.current) {
      esRef.current.close();
    }

    setIsStoredResult(false);
    setLoading(true);
    setError("");
    setProgress({ step: "Reading your file", progress: 0, detail: "Preparing analysis…" });
    setVisitedSteps(new Set<string>());

    // Get a fresh token (not stale localStorage) before opening the SSE stream
    const token = await getFreshToken();
    if (!token) {
      setError("Not authenticated. Please log in again.");
      setLoading(false);
      setProgress(null);
      return;
    }
    const tokenParam = `?token=${encodeURIComponent(token)}&use_cleaned=true`;
    const es = new EventSource(`${API_BASE_URL}/analysis/stream/${projectId}${tokenParam}`);
    esRef.current = es;

    es.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);

        if (data.error) {
          setError(data.error);
          setLoading(false);
          setProgress(null);
          es.close();
          return;
        }

        if (data.result) {
          // Reconstruct fields the backend no longer includes (removed as duplicates).
          // cleaning_report is rebuilt from canonical cleaning_result.
          // insights is populated from canonical insight_results.
          const raw = data.result;
          const adapted: AnalysisResult = {
            ...raw,
            profile_result: raw.profile_result ?? raw.profile,
            cleaning_report: raw.cleaning_report ?? cleaningItemsFromCanonical(raw.cleaning_result as CanonicalCleaningResult | null | undefined),
            insights: raw.insights ?? raw.insight_results ?? [],
          } as AnalysisResult;
          setResult(adapted);
          // run_id is the stable identifier for this analysis run
          if (raw.run_id) setAnalysisId(raw.run_id as number);
          // Land on the default step (Intake Review) — keep this in sync with
          // the RunStateBanner promise on the project page.
          setTab(DEFAULT_LANDING_TAB);
          // Auto-mark the default landing step as visited on first view
          setVisitedSteps(new Set<string>([DEFAULT_LANDING_TAB]));
          setLoading(false);
          setProgress(null);
          es.close();
          onFreshRunComplete?.();
          return;
        }

        if (data.step) {
          setProgress({
            step: data.step,
            progress: data.progress ?? 0,
            detail: data.detail ?? "",
          });
        }
      } catch {
        // non-JSON line, ignore
      }
    };

    es.onerror = () => {
      // Only show error if we were actively loading (not a clean close)
      if (loading) {
        setError(
          "The analysis stream was interrupted. This may be due to a network issue or server restart. Please try again."
        );
        setLoading(false);
        setProgress(null);
      }
      es.close();
    };
  }

  async function handleDownload() {
    setDownloading(true);
    try {
      await downloadCleanedData(projectId);
    } catch (err) {
      const msg = err instanceof ApiError ? err.userMessage : "Download failed. Please try again.";
      toast.error(msg);
    } finally {
      setDownloading(false);
    }
  }

  async function handleShare() {
    setSharing(true);
    try {
      const { share_token } = await shareAnalysis(projectId);
      setShareToken(share_token);
      toast.success("Share link created. Copy it to share your analysis.");
    } catch (err) {
      const msg = err instanceof ApiError ? err.userMessage : "Failed to create share link. Please try again.";
      toast.error(msg);
    } finally {
      setSharing(false);
    }
  }

  function handleCopy() {
    if (!shareToken) return;
    const url = `${window.location.origin}/share/${shareToken}`;
    navigator.clipboard.writeText(url).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  }

  return (
    <div className="min-w-0 w-full space-y-6">
      {/* Toolbar — compact primary actions + status + secondary actions */}
      <div className="rounded-xl border border-white/[0.06] bg-white/[0.02] px-4 py-3 sm:px-5">
        <div className="flex flex-col gap-3 min-[520px]:flex-row min-[520px]:items-center min-[520px]:justify-between min-[520px]:gap-4">
          <div className="flex min-w-0 flex-wrap items-center gap-3">
            <Button
              onClick={handleRun}
              disabled={loading}
              size="sm"
              className="shrink-0 bg-indigo-600 hover:bg-indigo-500 text-white gap-2 h-9"
            >
              {loading ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Analyzing…
                </>
              ) : (
                <>
                  <Play className="h-4 w-4" />
                  Analyze File
                </>
              )}
            </Button>

            {result && !loading && (
              <span
                className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[11px] font-medium leading-none ${
                  isStoredResult
                    ? "border-indigo-500/25 bg-indigo-500/10 text-indigo-200/90"
                    : "border-emerald-500/25 bg-emerald-500/10 text-emerald-300/95"
                }`}
              >
                {isStoredResult ? (
                  <>
                    <Clock className="h-3 w-3 opacity-80" />
                    Viewing saved analysis
                  </>
                ) : (
                  <>
                    <CheckCircle2 className="h-3 w-3 opacity-90" />
                    Ready to review
                  </>
                )}
              </span>
            )}
          </div>

          {result && !loading && (
            <div className="flex flex-wrap items-center gap-2 min-[520px]:justify-end">
              {!shareToken ? (
                <Button
                  onClick={handleShare}
                  disabled={sharing}
                  variant="ghost"
                  size="sm"
                  className="h-9 gap-2 border border-white/10 text-xs text-white/65 hover:text-white hover:border-white/20 hover:bg-white/[0.04]"
                >
                  {sharing ? (
                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  ) : (
                    <Share2 className="h-3.5 w-3.5" />
                  )}
                  Share
                </Button>
              ) : (
                <button
                  type="button"
                  onClick={handleCopy}
                  className="flex h-9 items-center gap-1.5 rounded-md border border-white/10 bg-white/[0.04] px-3 text-xs font-medium text-white/70 hover:border-white/18 hover:bg-white/[0.06] hover:text-white transition-colors"
                >
                  {copied ? (
                    <Check className="h-3.5 w-3.5 text-emerald-400" />
                  ) : (
                    <Copy className="h-3.5 w-3.5" />
                  )}
                  {copied ? "Copied!" : "Copy share link"}
                </button>
              )}
              <Button
                onClick={handleDownload}
                disabled={downloading || loading}
                variant="ghost"
                size="sm"
                className="h-9 gap-2 border border-white/10 text-xs text-white/65 hover:text-white hover:border-white/20 hover:bg-white/[0.04]"
              >
                {downloading ? (
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                ) : (
                  <Download className="h-3.5 w-3.5" />
                )}
                Download CSV
              </Button>
            </div>
          )}
        </div>
      </div>

      {error ? (
        <div className="rounded-xl border border-red-500/20 bg-red-500/10 px-4 py-3 text-sm text-red-400">
          {error}
        </div>
      ) : null}

      {loading && progress && (
        <ProgressBar
          step={progress.step}
          progress={progress.progress}
          detail={progress.detail}
        />
      )}

      {result ? (
        <div className="space-y-5 min-w-0">
          <ProjectTabs
            value={tab}
            onChange={handleTabChange}
            compareAvailable={!!compareResult}
            stepStatuses={deriveStepStatuses(result, visitedSteps, compareResult)}
          />

          {largeDatasetMeta ? (
            <LargeDatasetTransparencyBanner meta={largeDatasetMeta} variant="full" />
          ) : null}

          {/* ── Intake Review ────────────────────────────────────────── */}
          {tab === "intake" && (
            <SafePanel label="Intake Review">
              <TabPanel>
                <h2 className="mb-4 font-semibold text-white">Intake Review</h2>

                {/* ── Analysis Plan card (Dataset Intelligence Layer) ─── */}
                {result.analysis_plan && (
                  <div className="mb-6">
                    <AnalysisPlanCard plan={result.analysis_plan} />
                  </div>
                )}

                {result.intake_result &&
                Object.keys(result.intake_result).length > 0 ? (
                  <IntakeReview
                    filename={
                      (result.intake_result.file_name as string | undefined) ??
                      "uploaded file"
                    }
                    intakeResult={result.intake_result as IntakeResult}
                  />
                ) : (
                  <div className="rounded-xl border border-white/[0.07] bg-white/[0.02] px-6 py-8 text-center">
                    <p className="text-sm text-white/60">
                      Intake review was not saved for this run.
                    </p>
                    <p className="mt-1 text-xs text-white/35">
                      Re-run the analysis to capture parse confidence, warnings, and a preview of the data.
                    </p>
                  </div>
                )}
              </TabPanel>
            </SafePanel>
          )}

          {/* ── Data Table ───────────────────────────────────────────── */}
          {tab === "data-table" && (
            <SafePanel label="Data Table">
              <TabPanel>
                <h2 className="mb-4 font-semibold text-white">Raw Data</h2>
                <DataTableView projectId={projectId} />
              </TabPanel>
            </SafePanel>
          )}

          {/* ── Overview ─────────────────────────────────────────────── */}
          {tab === "overview" && (
            <SafePanel label="Overview">
              <div className="space-y-6 min-w-0">
                <StatsCards
                  healthResult={result.health_result}
                  profileResult={result.profile_result ?? result.profile}
                  summary={result.dataset_summary}
                  largeDataset={largeDatasetMeta}
                />
                <div className="grid grid-cols-1 gap-6 lg:grid-cols-2 lg:items-start lg:gap-8">
                  <TabPanel>
                    <h2 className="mb-1 text-xs font-semibold uppercase tracking-[0.16em] text-white/50">
                      Data quality
                    </h2>
                    <p className="mb-5 max-w-prose text-[13px] leading-relaxed text-white/38">
                      Health score, dimensions, and readiness signals for this dataset.
                    </p>
                    <HealthScore
                      healthResult={result.health_result}
                      score={result.health_score}
                      largeDataset={largeDatasetMeta}
                    />
                  </TabPanel>
                  <TabPanel>
                    <CleaningSummaryCards cleaningResult={result.cleaning_result} summary={result.cleaning_summary} />
                  </TabPanel>
                </div>
                <TabPanel>
                  <h2 className="mb-4 font-semibold text-white">Top Highlights</h2>
                  <InsightHighlights insights={result.insights} />
                </TabPanel>
                <RecommendedAction insights={result.insights} />
              </div>
            </SafePanel>
          )}

          {/* ── Health Check ─────────────────────────────────────────── */}
          {tab === "health" && (
            <SafePanel label="Health Check">
              <TabPanel>
                <h2 className="mb-4 font-semibold text-white">Health Check</h2>
                {result.health_result || result.health_score ? (
                  <HealthScore
                    healthResult={result.health_result}
                    score={result.health_score}
                    largeDataset={largeDatasetMeta}
                  />
                ) : (
                  <div className="rounded-xl border border-white/[0.07] bg-white/[0.02] px-6 py-8 text-center">
                    <p className="text-sm text-white/60">
                      Health check was not saved for this run.
                    </p>
                    <p className="mt-1 text-xs text-white/35">
                      Re-run the analysis to capture the dataset health score, warnings, and client-readiness notes.
                    </p>
                  </div>
                )}
              </TabPanel>
            </SafePanel>
          )}

          {/* ── Profile ──────────────────────────────────────────────── */}
          {tab === "profile" && (
            <SafePanel label="Column Profiles">
              <TabPanel>
                <h2 className="mb-4 font-semibold text-white">Column Profiles</h2>
                <ProfileView profileResult={result.profile_result} profile={result.profile} projectId={projectId} />
              </TabPanel>
            </SafePanel>
          )}

          {/* ── Insights ─────────────────────────────────────────────── */}
          {tab === "insights" && (
            <SafePanel label="Insights">
              <TabPanel>
                <div className="mb-4 flex items-center justify-between">
                  <h2 className="font-semibold text-white">Top Findings</h2>
                  <button
                    onClick={() => handleTabChange("compare-files")}
                    className="flex items-center gap-1.5 rounded-lg border border-indigo-500/30 bg-indigo-600/10 px-3 py-1.5 text-xs font-medium text-indigo-300 transition hover:bg-indigo-600/20"
                  >
                    Compare with another file →
                  </button>
                </div>
                <InsightsList insights={result.insights} />
              </TabPanel>
            </SafePanel>
          )}

          {/* ── Cleaning ─────────────────────────────────────────────── */}
          {tab === "cleaning" && (
            <SafePanel label="Cleaning Report">
              <TabPanel>
                <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <h2 className="font-semibold text-white">Cleaning Review</h2>
                    <p className="mt-1 max-w-xl text-xs text-white/40">
                      Download the cleaned dataset after reviewing the cleaning log.
                    </p>
                  </div>
                  <Button
                    onClick={handleDownload}
                    disabled={downloading || loading}
                    variant="ghost"
                    className="gap-2 text-xs text-white/60 hover:text-white border border-white/10 hover:border-white/20"
                  >
                    {downloading ? (
                      <Loader2 className="h-3.5 w-3.5 animate-spin" />
                    ) : (
                      <Download className="h-3.5 w-3.5" />
                    )}
                    Download cleaned CSV
                  </Button>
                </div>
                <CleaningReview
                  cleaningResult={result.cleaning_result}
                  items={result.cleaning_report ?? undefined}
                />
              </TabPanel>
            </SafePanel>
          )}

          {/* ── Charts ───────────────────────────────────────────────── */}
          {tab === "charts" && (
            <SafePanel label="Charts">
              <TabPanel>
                <h2 className="mb-4 font-semibold text-white">Charts</h2>
                <ChartViewer projectId={projectId} autoLoad />
              </TabPanel>
            </SafePanel>
          )}

          {/* ── Time Series ──────────────────────────────────────────── */}
          {tab === "timeseries" && (
            <SafePanel label="Time Series">
              <TabPanel><TimeseriesView projectId={projectId} /></TabPanel>
            </SafePanel>
          )}

          {/* ── Duplicates ───────────────────────────────────────────── */}
          {tab === "duplicates" && (
            <SafePanel label="Duplicates">
              <TabPanel><DuplicatesView projectId={projectId} /></TabPanel>
            </SafePanel>
          )}

          {/* ── Outliers ─────────────────────────────────────────────── */}
          {tab === "outliers" && (
            <SafePanel label="Outliers">
              <TabPanel><OutlierView projectId={projectId} /></TabPanel>
            </SafePanel>
          )}

          {/* ── Correlations ─────────────────────────────────────────── */}
          {tab === "correlations" && (
            <SafePanel label="Correlations">
              <TabPanel><CorrelationMatrix projectId={projectId} /></TabPanel>
            </SafePanel>
          )}

          {/* ── Compare Columns ──────────────────────────────────────── */}
          {tab === "compare-cols" && (
            <SafePanel label="Column Comparison">
              <TabPanel><ColumnCompare projectId={projectId} /></TabPanel>
            </SafePanel>
          )}

          {/* ── Compare Files ────────────────────────────────────────── */}
          {tab === "compare-files" && (
            <SafePanel label="File Comparison">
              <TabPanel>
                <MultifileCompare
                  currentProjectId={projectId}
                  onCompareResult={setCompareResult}
                  initialCompareResult={compareResult}
                />
              </TabPanel>
            </SafePanel>
          )}

          {/* ── Join Datasets ─────────────────────────────────────────── */}
          {tab === "join" && (
            <SafePanel label="Join Datasets">
              <TabPanel><JoinView currentProjectId={projectId} /></TabPanel>
            </SafePanel>
          )}

          {/* ── Diff Runs ────────────────────────────────────────────── */}
          {tab === "diff" && (
            <SafePanel label="Diff Runs">
              <TabPanel><DiffView projectId={projectId} /></TabPanel>
            </SafePanel>
          )}

          {/* ── Predictions ──────────────────────────────────────────── */}
          {tab === "predictions" && (
            <SafePanel label="Predictions">
              <TabPanel><PredictionsView projectId={projectId} /></TabPanel>
            </SafePanel>
          )}

          {/* ── Report Builder + AI Copilot ──────────────────────────── */}
          {tab === "ask-ai" && (
            <SafePanel label="Report Builder">
              <TabPanel>
                <div className="space-y-6">
                  <div>
                    <h2 className="mb-1 font-semibold text-white">Build your report</h2>
                    <p className="text-xs text-white/40">
                      Select findings, edit the summary, preview the assembled report, then export a client-ready PDF or Excel file.
                    </p>
                  </div>
                  <ReportBuilder
                    projectId={projectId}
                    projectName={projectName}
                    datasetSummary={result.dataset_summary}
                    healthTotal={healthTotalFromResult(result)}
                    insights={result.insights ?? []}
                    insightResults={
                      result.insight_results == null
                        ? undefined
                        : (result.insight_results as ReportInsightItem[])
                    }
                    narrative={result.narrative}
                    executivePanel={result.executive_panel as ReportExecutivePanel | null | undefined}
                    compareResult={compareResult}
                    healthResult={result.health_result as ReportHealthBlock | null | undefined}
                    cleaningResult={result.cleaning_result as ReportCleaningBlock | null | undefined}
                    largeDataset={largeDatasetMeta}
                    onNavigateTo={handleTabChange}
                  />
                  <div className="border-t border-white/[0.06] pt-4">
                    <h3 className="mb-3 text-sm font-semibold text-white/60">Ask AI copilot</h3>
                    <AiChatView
                      projectId={projectId}
                      contextColumns={(result.profile_result ?? result.profile ?? []).map((p) => p.column)}
                      contextInsightTitles={(result.insights ?? [])
                        .map((i) => (i.title || i.finding || "").trim())
                        .filter(Boolean)}
                    />
                  </div>
                </div>
              </TabPanel>
            </SafePanel>
          )}

          {/* ── Pivot ────────────────────────────────────────────────── */}
          {tab === "pivot" && (
            <SafePanel label="Pivot Table">
              <TabPanel><PivotView projectId={projectId} /></TabPanel>
            </SafePanel>
          )}

          {/* ── Segments ─────────────────────────────────────────────── */}
          {tab === "segments" && (
            <SafePanel label="Segments">
              <TabPanel><SegmentsView projectId={projectId} /></TabPanel>
            </SafePanel>
          )}

          {/* ── A/B Tests ────────────────────────────────────────────── */}
          {tab === "ab-tests" && (
            <SafePanel label="Statistical Tests">
              <TabPanel><AbTestsView projectId={projectId} /></TabPanel>
            </SafePanel>
          )}

          {/* ── SQL Query ────────────────────────────────────────────── */}
          {tab === "query" && (
            <SafePanel label="SQL Query">
              <TabPanel><QueryView projectId={projectId} /></TabPanel>
            </SafePanel>
          )}

          {/* ── Client Summary ───────────────────────────────────────── */}
          {tab === "story" && (
            <SafePanel label="Client Summary">
              <TabPanel>
                <DataStoryView
                  analysisId={analysisId}
                  storedStory={result?.story_result ?? null}
                />
              </TabPanel>
            </SafePanel>
          )}
        </div>
      ) : (
        !loading && (
          <div className="space-y-3">
            <div className="rounded-2xl border border-white/[0.07] bg-white/[0.02] px-8 py-8 text-center">
              <div className="mx-auto mb-4 h-12 w-12 rounded-xl bg-indigo-500/10 flex items-center justify-center">
                <Play className="h-5 w-5 text-indigo-400" />
              </div>
              <p className="text-white/70 text-sm font-medium mb-1">Ready to analyze</p>
              <p className="text-white/35 text-xs">
                Upload a client file above, then click{" "}
                <span className="text-white/60">Analyze File</span> to run the full pipeline
              </p>
            </div>
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
              {[
                { step: "1", label: "Intake Review",    desc: "Check file parsing & structure" },
                { step: "2", label: "Cleaning Review",  desc: "See what was fixed automatically" },
                { step: "3", label: "Health Check",     desc: "Column-by-column data quality" },
                { step: "4", label: "Findings",         desc: "Key patterns & anomalies" },
                { step: "5", label: "Compare Changes",  desc: "Compare file versions (optional)" },
                { step: "6", label: "Build Report",     desc: "Export client-ready PDF or Excel" },
              ].map((s) => (
                <div
                  key={s.step}
                  className="rounded-xl border border-white/[0.05] bg-white/[0.02] p-3 text-left"
                >
                  <span className="mb-1.5 flex h-5 w-5 items-center justify-center rounded-full bg-white/[0.06] text-[10px] font-bold text-white/30">
                    {s.step}
                  </span>
                  <p className="text-xs font-medium text-white/50">{s.label}</p>
                  <p className="mt-0.5 text-[11px] text-white/25">{s.desc}</p>
                </div>
              ))}
            </div>
          </div>
        )
      )}
    </div>
  );
}
