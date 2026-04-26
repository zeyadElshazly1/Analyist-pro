"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { Button } from "@/components/ui/button";
import { Clock, Loader2, Play, CheckCircle2, Share2, Copy, Check, Download } from "lucide-react";

import { StatsCards } from "@/components/analysis/stats-cards";
import { InsightsList } from "@/components/analysis/insights-list";
import { HealthScore } from "@/components/analysis/health-score";
import { ProjectTabs } from "./project-tabs";
import { CleaningReport } from "@/components/analysis/cleaning-report";
import { CleaningReview } from "./cleaning-review";
import { CleaningSummaryCards } from "@/components/analysis/cleaning-summary-cards";
import { InsightHighlights } from "@/components/analysis/insight-highlights";
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
import { ReportBuilder } from "./report-builder";
import { PivotView } from "@/components/analysis/pivot-view";
import { SegmentsView } from "@/components/analysis/segments-view";
import { AbTestsView } from "@/components/analysis/ab-tests-view";
import { QueryView } from "@/components/analysis/query-view";
import { DataStoryView } from "@/components/analysis/data-story-view";
import { DataTableView } from "@/components/analysis/data-table-view";
import { DiffView } from "@/components/analysis/diff-view";
import { ApiError, getFreshToken, shareAnalysis, downloadCleanedData } from "@/lib/api";
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

type CleaningItem = {
  step: string;
  detail: string;
  impact: "high" | "medium" | "low";
};

// Reconstruct flat CleaningItem list from canonical CleaningResult block.
// Used by CleaningReview when cleaning_report is absent from the result
// (removed from API response — canonical cleaning_result is the source of truth).
// eslint-disable-next-line @typescript-eslint/no-explicit-any
function cleaningItemsFromCanonical(cr: Record<string, any> | null | undefined): CleaningItem[] {
  if (!cr) return [];
  const items: CleaningItem[] = [];
  for (const r of cr.renamed_columns ?? []) {
    items.push({ step: `Rename: ${r.original} → ${r.cleaned}`, detail: "Column name normalised", impact: "low" });
  }
  for (const col of cr.dropped_columns ?? []) {
    items.push({ step: `Drop column: ${col}`, detail: "Removed — high missingness or no content", impact: "medium" });
  }
  for (const fix of cr.type_fixes ?? []) {
    const count = fix.n_values_converted > 0 ? ` (${fix.n_values_converted} values)` : "";
    items.push({ step: `Type fix: ${fix.column}`, detail: `Converted to ${fix.to_dtype}${count}`, impact: "medium" });
  }
  for (const note of cr.missingness_notes ?? []) {
    const isSuggestion = note.strategy_applied === "safe_suggestion";
    items.push({ step: `${isSuggestion ? "[SUGGESTION] Impute missing" : "Impute missing"}: ${note.column}`, detail: `${note.missing_count} missing (${note.missing_pct}%), mechanism: ${note.mechanism}`, impact: isSuggestion ? "low" : "medium" });
  }
  const dn = cr.duplicate_notes;
  if (dn?.duplicate_rows_removed > 0) {
    items.push({ step: "Remove duplicate rows", detail: `Removed ${dn.duplicate_rows_removed} of ${dn.duplicate_rows_found} duplicates`, impact: "medium" });
  }
  for (const susp of cr.suspicious_columns ?? []) {
    items.push({ step: `[FLAG] ${susp.column}`, detail: susp.detail, impact: "medium" });
  }
  return items;
}

export type AnalysisResult = {
  analysis_id?: number;
  dataset_summary?: {
    rows?: number;
    columns?: number;
    numeric_cols?: number;
    categorical_cols?: number;
    missing_pct?: number;
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
  cleaning_summary?: Record<string, unknown> | null;
  cleaning_result?: Record<string, unknown> | null;  // canonical CleaningResult block
  health_result?: Record<string, unknown> | null;    // canonical HealthResult block
  profile_result?: ColProfile[] | null;              // canonical ProfileResult block
  profile?: ColProfile[] | null;                     // legacy fallback
  insights: Insight[];
  cleaning_report?: CleaningItem[] | null;
  narrative?: string;
  story_result?: import("@/lib/api").DataStory | null;  // stored AI data story
  [key: string]: unknown;
};

type Props = {
  projectId: number;
  initialResult?: AnalysisResult;   // pre-populated from stored run
  initialRunId?: number;            // run_id for the stored result (used as analysisId)
};

type ProgressState = {
  step: string;
  progress: number;
  detail: string;
};

function TabPanel({ children }: { children: React.ReactNode }) {
  return (
    <div className="rounded-2xl border border-white/[0.07] bg-white/[0.03] p-6">
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

export function RunAnalysis({ projectId, initialResult, initialRunId }: Props) {
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<AnalysisResult | null>(null);
  const [analysisId, setAnalysisId] = useState<number | null>(null);
  const [isStoredResult, setIsStoredResult] = useState(false);
  const [tab, setTab] = useState("overview");

  // Hydrate from a stored run passed by the parent page.
  // Runs when initialResult changes (e.g. after parent fetches /run/{id}/results).
  useEffect(() => {
    if (initialResult) {
      setResult(initialResult);
      setAnalysisId(initialRunId ?? null);
      setTab("overview");
      setIsStoredResult(true);
    }
  }, [initialResult, initialRunId]);
  const [useCleaned, setUseCleaned] = useState(true);
  const [downloading, setDownloading] = useState(false);

  // Sync tab ↔ URL hash for shareable deep-links
  useEffect(() => {
    const hash = window.location.hash.slice(1);
    if (hash) setTab(hash);
  }, []);

  const handleTabChange = useCallback((newTab: string) => {
    setTab(newTab);
    window.history.replaceState(null, "", `#${newTab}`);
  }, []);
  const [error, setError] = useState("");
  const [progress, setProgress] = useState<ProgressState | null>(null);
  const [shareToken, setShareToken] = useState<string | null>(null);
  const [sharing, setSharing] = useState(false);
  const [copied, setCopied] = useState(false);
  const esRef = useRef<EventSource | null>(null);

  async function handleRun() {
    if (esRef.current) {
      esRef.current.close();
    }

    setIsStoredResult(false);
    setLoading(true);
    setError("");
    setProgress({ step: "Reading your file", progress: 0, detail: "Preparing analysis…" });

    // Get a fresh token (not stale localStorage) before opening the SSE stream
    const token = await getFreshToken();
    if (!token) {
      setError("Not authenticated. Please log in again.");
      setLoading(false);
      setProgress(null);
      return;
    }
    const tokenParam = `?token=${encodeURIComponent(token)}&use_cleaned=${useCleaned}`;
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
            cleaning_report: raw.cleaning_report ?? cleaningItemsFromCanonical(raw.cleaning_result),
            insights: raw.insights ?? raw.insight_results ?? [],
          } as AnalysisResult;
          setResult(adapted);
          // run_id is the stable identifier for this analysis run
          if (raw.run_id) setAnalysisId(raw.run_id as number);
          setTab("overview");
          setLoading(false);
          setProgress(null);
          es.close();
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

    es.onerror = (event) => {
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
    <div className="space-y-6">
      <div className="flex flex-wrap items-center gap-3">
        {/* Data mode toggle */}
        <div className="flex items-center gap-1 rounded-lg border border-white/10 bg-white/[0.03] p-1 text-xs">
          <button
            onClick={() => setUseCleaned(true)}
            disabled={loading}
            className={`rounded-md px-3 py-1.5 transition-colors ${
              useCleaned
                ? "bg-indigo-600 text-white"
                : "text-white/50 hover:text-white/80"
            }`}
          >
            Cleaned data
          </button>
          <button
            onClick={() => setUseCleaned(false)}
            disabled={loading}
            className={`rounded-md px-3 py-1.5 transition-colors ${
              !useCleaned
                ? "bg-indigo-600 text-white"
                : "text-white/50 hover:text-white/80"
            }`}
          >
            Raw data
          </button>
        </div>

        <Button
          onClick={handleRun}
          disabled={loading}
          className="bg-indigo-600 hover:bg-indigo-500 text-white gap-2"
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

        {/* Download cleaned CSV — always available, not gated on analysis result */}
        <Button
          onClick={handleDownload}
          disabled={downloading || loading}
          variant="ghost"
          className="gap-2 text-xs text-white/50 hover:text-white border border-white/10 hover:border-white/20"
        >
          {downloading ? (
            <Loader2 className="h-3.5 w-3.5 animate-spin" />
          ) : (
            <Download className="h-3.5 w-3.5" />
          )}
          Download cleaned CSV
        </Button>

        {result && !loading && (
          <>
            {isStoredResult ? (
              <span className="flex items-center gap-1.5 text-xs text-indigo-300/70">
                <Clock className="h-3.5 w-3.5" />
                Viewing saved analysis
              </span>
            ) : (
              <span className="flex items-center gap-1.5 text-xs text-emerald-400">
                <CheckCircle2 className="h-3.5 w-3.5" />
                Ready to review
              </span>
            )}

            {!shareToken ? (
              <Button
                onClick={handleShare}
                disabled={sharing}
                variant="ghost"
                className="gap-2 text-xs text-white/50 hover:text-white border border-white/10 hover:border-white/20"
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
                onClick={handleCopy}
                className="flex items-center gap-1.5 rounded-lg border border-white/10 bg-white/[0.03] px-3 py-1.5 text-xs text-white/60 hover:text-white hover:border-white/20 transition-colors"
              >
                {copied ? (
                  <Check className="h-3.5 w-3.5 text-emerald-400" />
                ) : (
                  <Copy className="h-3.5 w-3.5" />
                )}
                {copied ? "Copied!" : "Copy share link"}
              </button>
            )}
          </>
        )}
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
        <div className="space-y-4">
          <ProjectTabs value={tab} onChange={handleTabChange} />

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
              <div className="space-y-4">
                <StatsCards healthResult={result.health_result} profileResult={result.profile_result ?? result.profile} summary={result.dataset_summary} />
                <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
                  <TabPanel><HealthScore healthResult={result.health_result} score={result.health_score} /></TabPanel>
                  <TabPanel>
                    <h2 className="mb-4 text-sm font-semibold text-white/70 uppercase tracking-wider">Cleaning Summary</h2>
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
                <h2 className="mb-4 font-semibold text-white">Cleaning Log</h2>
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
              <TabPanel><MultifileCompare currentProjectId={projectId} /></TabPanel>
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
                    <p className="text-xs text-white/40">Select insights, edit the summary, and export a client-ready PDF or Excel file.</p>
                  </div>
                  <ReportBuilder
                    projectId={projectId}
                    insights={result.insights ?? []}
                  />
                  <div className="border-t border-white/[0.06] pt-4">
                    <h3 className="mb-3 text-sm font-semibold text-white/60">Ask AI copilot</h3>
                    <AiChatView projectId={projectId} />
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
            <div className="rounded-2xl border border-white/[0.07] bg-white/[0.02] p-10 text-center">
              <div className="mx-auto mb-4 h-12 w-12 rounded-xl bg-indigo-500/10 flex items-center justify-center">
                <Play className="h-5 w-5 text-indigo-400" />
              </div>
              <p className="text-white/70 text-sm font-medium mb-1">Ready to analyze</p>
              <p className="text-white/35 text-xs">
                Upload a client file above, then click{" "}
                <span className="text-white/60">Analyze File</span> to begin
              </p>
            </div>
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
              {[
                { step: "1", label: "Intake", desc: "Parse & structure review" },
                { step: "2", label: "Health", desc: "Data quality check" },
                { step: "3", label: "Insights", desc: "Key patterns & findings" },
                { step: "4", label: "Export", desc: "PDF, Excel or share link" },
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
