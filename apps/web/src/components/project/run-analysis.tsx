"use client";

import { useState, useRef } from "react";
import { Button } from "@/components/ui/button";
import { Loader2, Play, CheckCircle2, Share2, Copy, Check } from "lucide-react";

import { StatsCards } from "@/components/analysis/stats-cards";
import { InsightsList } from "@/components/analysis/insights-list";
import { HealthScore } from "@/components/analysis/health-score";
import { ProjectTabs } from "./project-tabs";
import { CleaningReport } from "@/components/analysis/cleaning-report";
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
import { PredictionsView } from "@/components/analysis/predictions-view";
import { AiChatView } from "@/components/analysis/ai-chat-view";
import { PivotView } from "@/components/analysis/pivot-view";
import { SegmentsView } from "@/components/analysis/segments-view";
import { AbTestsView } from "@/components/analysis/ab-tests-view";
import { QueryView } from "@/components/analysis/query-view";
import { DataStoryView } from "@/components/analysis/data-story-view";
import { DataTableView } from "@/components/analysis/data-table-view";
import { DiffView } from "@/components/analysis/diff-view";
import { ApiError, getFreshToken, shareAnalysis } from "@/lib/api";
import { toast } from "@/components/ui/toast";
import { SafePanel } from "@/components/ui/error-boundary";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL || "http://127.0.0.1:8000";

type Props = {
  projectId: number;
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

export function RunAnalysis({ projectId }: Props) {
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<Record<string, unknown> | null>(null);
  const [analysisId, setAnalysisId] = useState<number | null>(null);
  const [tab, setTab] = useState("overview");
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

    setLoading(true);
    setError("");
    setProgress({ step: "Starting…", progress: 0, detail: "" });

    // Get a fresh token (not stale localStorage) before opening the SSE stream
    const token = await getFreshToken();
    if (!token) {
      setError("Not authenticated. Please log in again.");
      setLoading(false);
      setProgress(null);
      return;
    }
    const tokenParam = `?token=${encodeURIComponent(token)}`;
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
          setResult(data.result);
          if (data.result.analysis_id) setAnalysisId(data.result.analysis_id as number);
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
              Run Analysis
            </>
          )}
        </Button>

        {result && !loading && (
          <>
            <span className="flex items-center gap-1.5 text-xs text-emerald-400">
              <CheckCircle2 className="h-3.5 w-3.5" />
              Analysis complete
            </span>

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
          <ProjectTabs value={tab} onChange={setTab} />

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
                <StatsCards summary={result.dataset_summary} />
                <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
                  <TabPanel><HealthScore score={result.health_score} /></TabPanel>
                  <TabPanel>
                    <h2 className="mb-4 text-sm font-semibold text-white/70 uppercase tracking-wider">Cleaning Summary</h2>
                    <CleaningSummaryCards summary={result.cleaning_summary} />
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
                <ProfileView profile={result.profile} />
              </TabPanel>
            </SafePanel>
          )}

          {/* ── Insights ─────────────────────────────────────────────── */}
          {tab === "insights" && (
            <SafePanel label="Insights">
              <TabPanel>
                <h2 className="mb-4 font-semibold text-white">All Insights</h2>
                <InsightsList insights={result.insights} />
              </TabPanel>
            </SafePanel>
          )}

          {/* ── Cleaning ─────────────────────────────────────────────── */}
          {tab === "cleaning" && (
            <SafePanel label="Cleaning Report">
              <TabPanel>
                <h2 className="mb-4 font-semibold text-white">Cleaning Report</h2>
                <CleaningReport items={result.cleaning_report} />
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

          {/* ── Ask AI ───────────────────────────────────────────────── */}
          {tab === "ask-ai" && (
            <SafePanel label="AI Chat">
              <TabPanel><AiChatView projectId={projectId} /></TabPanel>
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

          {/* ── Data Story ───────────────────────────────────────────── */}
          {tab === "story" && (
            <SafePanel label="Data Story">
              <TabPanel><DataStoryView analysisId={analysisId} /></TabPanel>
            </SafePanel>
          )}
        </div>
      ) : (
        !loading && (
          <div className="rounded-2xl border border-white/[0.07] bg-white/[0.02] p-12 text-center">
            <div className="mx-auto mb-4 h-12 w-12 rounded-xl bg-indigo-500/10 flex items-center justify-center">
              <Play className="h-5 w-5 text-indigo-400" />
            </div>
            <p className="text-white/50 text-sm">
              Upload a dataset and click{" "}
              <span className="text-white/80">Run Analysis</span> to get started
            </p>
          </div>
        )
      )}
    </div>
  );
}
