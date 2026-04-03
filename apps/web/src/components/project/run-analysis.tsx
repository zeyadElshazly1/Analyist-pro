"use client";

import { useState, useRef } from "react";
import { Button } from "@/components/ui/button";
import { Loader2, Play, CheckCircle2 } from "lucide-react";

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
  const [result, setResult] = useState<any | null>(null);
  const [tab, setTab] = useState("overview");
  const [error, setError] = useState("");
  const [progress, setProgress] = useState<ProgressState | null>(null);
  const esRef = useRef<EventSource | null>(null);

  function handleRun() {
    if (esRef.current) {
      esRef.current.close();
    }

    setLoading(true);
    setError("");
    setProgress({ step: "Starting…", progress: 0, detail: "" });

    const es = new EventSource(`${API_BASE_URL}/analysis/stream/${projectId}`);
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

    es.onerror = () => {
      setError("Analysis stream disconnected. Please try again.");
      setLoading(false);
      setProgress(null);
      es.close();
    };
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4">
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
          <span className="flex items-center gap-1.5 text-xs text-emerald-400">
            <CheckCircle2 className="h-3.5 w-3.5" />
            Analysis complete
          </span>
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

          {/* ── Overview ─────────────────────────────────────────────── */}
          {tab === "overview" && (
            <div className="space-y-4">
              <StatsCards summary={result.dataset_summary} />

              <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
                <TabPanel>
                  <HealthScore score={result.health_score} />
                </TabPanel>
                <TabPanel>
                  <h2 className="mb-4 text-sm font-semibold text-white/70 uppercase tracking-wider">
                    Cleaning Summary
                  </h2>
                  <CleaningSummaryCards summary={result.cleaning_summary} />
                </TabPanel>
              </div>

              <TabPanel>
                <h2 className="mb-4 font-semibold text-white">Top Highlights</h2>
                <InsightHighlights insights={result.insights} />
              </TabPanel>

              <RecommendedAction insights={result.insights} />
            </div>
          )}

          {/* ── Profile ──────────────────────────────────────────────── */}
          {tab === "profile" && (
            <TabPanel>
              <h2 className="mb-4 font-semibold text-white">Column Profiles</h2>
              <ProfileView profile={result.profile} />
            </TabPanel>
          )}

          {/* ── Insights ─────────────────────────────────────────────── */}
          {tab === "insights" && (
            <TabPanel>
              <h2 className="mb-4 font-semibold text-white">All Insights</h2>
              <InsightsList insights={result.insights} />
            </TabPanel>
          )}

          {/* ── Cleaning ─────────────────────────────────────────────── */}
          {tab === "cleaning" && (
            <TabPanel>
              <h2 className="mb-4 font-semibold text-white">Cleaning Report</h2>
              <CleaningReport items={result.cleaning_report} />
            </TabPanel>
          )}

          {/* ── Charts ───────────────────────────────────────────────── */}
          {tab === "charts" && (
            <TabPanel>
              <h2 className="mb-4 font-semibold text-white">Charts</h2>
              <ChartViewer projectId={projectId} autoLoad />
            </TabPanel>
          )}

          {/* ── Time Series ──────────────────────────────────────────── */}
          {tab === "timeseries" && (
            <TabPanel>
              <TimeseriesView projectId={projectId} />
            </TabPanel>
          )}

          {/* ── Duplicates ───────────────────────────────────────────── */}
          {tab === "duplicates" && (
            <TabPanel>
              <DuplicatesView projectId={projectId} />
            </TabPanel>
          )}

          {/* ── Outliers ─────────────────────────────────────────────── */}
          {tab === "outliers" && (
            <TabPanel>
              <OutlierView projectId={projectId} />
            </TabPanel>
          )}

          {/* ── Correlations ─────────────────────────────────────────── */}
          {tab === "correlations" && (
            <TabPanel>
              <CorrelationMatrix projectId={projectId} />
            </TabPanel>
          )}

          {/* ── Compare Columns ──────────────────────────────────────── */}
          {tab === "compare-cols" && (
            <TabPanel>
              <ColumnCompare projectId={projectId} />
            </TabPanel>
          )}

          {/* ── Compare Files ────────────────────────────────────────── */}
          {tab === "compare-files" && (
            <TabPanel>
              <MultifileCompare currentProjectId={projectId} />
            </TabPanel>
          )}

          {/* ── Predictions ──────────────────────────────────────────── */}
          {tab === "predictions" && (
            <TabPanel>
              <PredictionsView projectId={projectId} />
            </TabPanel>
          )}

          {/* ── Ask AI ───────────────────────────────────────────────── */}
          {tab === "ask-ai" && (
            <TabPanel>
              <AiChatView projectId={projectId} />
            </TabPanel>
          )}

          {/* ── Pivot ────────────────────────────────────────────────── */}
          {tab === "pivot" && (
            <TabPanel>
              <PivotView projectId={projectId} />
            </TabPanel>
          )}

          {/* ── Segments ─────────────────────────────────────────────── */}
          {tab === "segments" && (
            <TabPanel>
              <SegmentsView projectId={projectId} />
            </TabPanel>
          )}

          {/* ── A/B Tests ────────────────────────────────────────────── */}
          {tab === "ab-tests" && (
            <TabPanel>
              <AbTestsView projectId={projectId} />
            </TabPanel>
          )}

          {/* ── SQL Query ────────────────────────────────────────────── */}
          {tab === "query" && (
            <TabPanel>
              <QueryView projectId={projectId} />
            </TabPanel>
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
