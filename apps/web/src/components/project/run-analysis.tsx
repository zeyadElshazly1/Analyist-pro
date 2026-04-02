"use client";

import { useEffect, useMemo, useState } from "react";
import { Button } from "@/components/ui/button";
import {
  AnalysisArtifactPayload,
  AnalysisJob,
  ProjectDetail,
  exportReport,
  getAnalysisJob,
  startAnalysis,
} from "@/lib/api";
import { Loader2, Play, Radar, RefreshCw, Sparkles } from "lucide-react";

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

type Props = {
  projectId: number;
  project: ProjectDetail | null;
  onRefresh?: () => void;
};

type InsightItem = {
  title?: string;
  finding?: string;
  type?: string;
  confidence?: number;
  severity?: string;
  action?: string;
};

type HealthScoreShape = {
  total?: number;
  score?: number;
  grade?: string;
  breakdown?: {
    completeness: number;
    uniqueness: number;
    consistency: number;
    validity: number;
    structure: number;
  };
  deductions?: string[];
};

type CleaningSummaryShape = Record<string, unknown>;
type CleaningItem = Record<string, unknown>;
type ProfileShape = Record<string, unknown>;

function TabPanel({ children }: { children: React.ReactNode }) {
  return (
    <div className="rounded-2xl border border-white/[0.07] bg-white/[0.03] p-6">
      {children}
    </div>
  );
}

function SummaryCard({
  title,
  description,
  children,
}: {
  title: string;
  description?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="rounded-2xl border border-white/[0.07] bg-white/[0.03] p-5">
      <h3 className="text-sm font-semibold text-white">{title}</h3>
      {description ? <p className="mt-1 text-xs text-white/40">{description}</p> : null}
      <div className="mt-4">{children}</div>
    </div>
  );
}

export function RunAnalysis({ projectId, project, onRefresh }: Props) {
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<AnalysisArtifactPayload | null>(null);
  const [tab, setTab] = useState("overview");
  const [error, setError] = useState("");
  const [job, setJob] = useState<AnalysisJob | null>(null);

  const effectiveResult = result ?? project?.latest_analysis?.payload ?? null;
  const effectiveJob = job ?? project?.latest_job ?? null;
  const insights = useMemo(
    () => (effectiveResult?.insights ?? []) as InsightItem[],
    [effectiveResult]
  );
  const healthScore = (effectiveResult?.health_score ?? {}) as HealthScoreShape;
  const cleaningSummary = (effectiveResult?.cleaning_summary ?? {}) as CleaningSummaryShape;
  const cleaningReport = (effectiveResult?.cleaning_report ?? []) as CleaningItem[];
  const profile = (effectiveResult?.profile ?? {}) as ProfileShape;

  useEffect(() => {
    if (!effectiveJob?.id || effectiveJob.status === "completed" || effectiveJob.status === "failed") {
      return;
    }

    const timer = window.setInterval(async () => {
      try {
        const nextJob = await getAnalysisJob(effectiveJob.id);
        setJob(nextJob);
        if (nextJob.status === "completed") {
          setLoading(false);
          setError("");
          setResult(nextJob.result_artifact?.payload ?? null);
          onRefresh?.();
          window.clearInterval(timer);
        } else if (nextJob.status === "failed") {
          setLoading(false);
          setError(nextJob.error_message || "Analysis failed.");
          window.clearInterval(timer);
        }
      } catch (err) {
        setLoading(false);
        setError(err instanceof Error ? err.message : "Polling failed.");
        window.clearInterval(timer);
      }
    }, 1200);

    return () => window.clearInterval(timer);
  }, [effectiveJob, onRefresh]);

  const highPriorityInsights = useMemo(
    () =>
      insights.filter(
        (insight) =>
          String(insight.severity || "").toLowerCase() === "high" ||
          String(insight.type || "").toLowerCase() === "anomaly" ||
          String(insight.type || "").toLowerCase() === "data_quality"
      ),
    [insights]
  );

  async function handleRun() {
    if (!project?.latest_dataset?.id) {
      setError("Upload a dataset before running the analysis.");
      return;
    }

    try {
      setLoading(true);
      setError("");
      const nextJob = await startAnalysis(project.latest_dataset.id);
      setJob(nextJob);
    } catch (err) {
      setLoading(false);
      setError(err instanceof Error ? err.message : "Analysis failed.");
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 rounded-2xl border border-indigo-500/15 bg-indigo-500/5 p-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <p className="text-sm font-medium text-indigo-300">Executive summary workflow</p>
          <p className="mt-1 text-xs text-white/50">
            Upload once, save the result artifact, then revisit without recomputing the whole project.
          </p>
        </div>

        <div className="flex flex-wrap gap-2">
          <Button
            onClick={handleRun}
            disabled={loading || !project?.latest_dataset?.id}
            className="bg-indigo-600 text-white hover:bg-indigo-500"
          >
            {loading ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Processing...
              </>
            ) : (
              <>
                <Play className="mr-2 h-4 w-4" />
                Run saved analysis
              </>
            )}
          </Button>
          {effectiveResult ? (
            <Button
              variant="ghost"
              onClick={() => exportReport(projectId, "html")}
              className="border border-white/10 text-white/70 hover:bg-white/5 hover:text-white"
            >
              Export report
            </Button>
          ) : null}
        </div>
      </div>

      {effectiveJob && effectiveJob.status !== "completed" && effectiveJob.status !== "failed" ? (
        <div className="rounded-2xl border border-white/[0.07] bg-white/[0.03] p-4">
          <div className="mb-2 flex items-center justify-between gap-3">
            <div className="flex items-center gap-2 text-sm text-white">
              <RefreshCw className="h-4 w-4 text-indigo-400" />
              Analysis job #{effectiveJob.id}
            </div>
            <span className="text-xs text-white/45">{effectiveJob.stage}</span>
          </div>
          <div className="h-2 overflow-hidden rounded-full bg-white/10">
            <div
              className="h-full rounded-full bg-indigo-500 transition-all"
              style={{ width: `${effectiveJob.progress}%` }}
            />
          </div>
        </div>
      ) : null}

      {error ? (
        <div className="rounded-xl border border-red-500/20 bg-red-500/10 px-4 py-3 text-sm text-red-400">
          {error}
        </div>
      ) : null}

      {effectiveResult ? (
        <div className="space-y-5">
          <StatsCards summary={effectiveResult.dataset_summary} />

          <div className="grid gap-4 lg:grid-cols-[1.2fr_0.8fr]">
            <SummaryCard
              title="Understand"
              description="Narrative summary generated from the saved analysis artifact."
            >
              <div className="rounded-2xl border border-white/[0.06] bg-black/20 p-4">
                <div className="mb-3 flex items-center gap-2">
                  <Sparkles className="h-4 w-4 text-indigo-400" />
                  <p className="text-xs font-medium uppercase tracking-[0.16em] text-indigo-300/80">
                    Executive summary
                  </p>
                </div>
                <p className="text-sm leading-7 text-white/75">{effectiveResult.narrative}</p>
              </div>
            </SummaryCard>

            <SummaryCard
              title="Act"
              description="Highlight the most valuable next move before opening deeper tools."
            >
              <RecommendedAction insights={insights} />
            </SummaryCard>
          </div>

          <div className="grid gap-4 lg:grid-cols-2">
            <SummaryCard
              title="Key drivers"
              description="The strongest insights surfaced in the current saved run."
            >
              <InsightHighlights insights={insights} />
            </SummaryCard>

            <SummaryCard
              title="Risks and anomalies"
              description="High-severity issues and non-obvious patterns to review first."
            >
              {highPriorityInsights.length > 0 ? (
                <div className="space-y-3">
                  {highPriorityInsights.slice(0, 3).map((insight, index) => (
                    <div
                      key={index}
                      className="rounded-xl border border-amber-500/15 bg-amber-500/5 p-4"
                    >
                      <p className="text-sm font-semibold text-white">
                        {String(insight.title || insight.type || "Risk")}
                      </p>
                      <p className="mt-1 text-xs leading-6 text-white/60">
                        {String(insight.finding || "Review this pattern in the detailed analysis.")}
                      </p>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-sm text-white/45">
                  No high-severity risks were flagged in the latest saved analysis.
                </p>
              )}
            </SummaryCard>
          </div>

          <div className="grid gap-4 lg:grid-cols-2">
            <SummaryCard title="Health and quality">
              <HealthScore score={healthScore} />
            </SummaryCard>
            <SummaryCard title="Cleaning summary">
              <CleaningSummaryCards summary={cleaningSummary} />
            </SummaryCard>
          </div>

          <details className="group rounded-2xl border border-white/[0.07] bg-white/[0.03] p-5">
            <summary className="flex cursor-pointer list-none items-center justify-between gap-3">
              <div>
                <p className="text-sm font-semibold text-white">Explore more</p>
                <p className="mt-1 text-xs text-white/40">
                  Open advanced analysis tools, SQL, charts, ML, and deeper diagnostics.
                </p>
              </div>
              <span className="inline-flex items-center gap-2 rounded-full bg-white/5 px-3 py-1 text-xs text-white/60">
                <Radar className="h-3.5 w-3.5" />
                Deep dive tools
              </span>
            </summary>

            <div className="mt-5 space-y-4">
              <ProjectTabs value={tab} onChange={setTab} />

              {tab === "overview" && (
                <div className="space-y-4">
                  <TabPanel>
                    <h2 className="mb-4 font-semibold text-white">All insights</h2>
                    <InsightsList insights={insights} />
                  </TabPanel>
                  <TabPanel>
                    <h2 className="mb-4 font-semibold text-white">Cleaning report</h2>
                    <CleaningReport items={cleaningReport} />
                  </TabPanel>
                </div>
              )}

              {tab === "profile" && (
                <TabPanel>
                  <h2 className="mb-4 font-semibold text-white">Column profiles</h2>
                  <ProfileView profile={profile} />
                </TabPanel>
              )}
              {tab === "insights" && (
                <TabPanel>
                  <h2 className="mb-4 font-semibold text-white">Insight explorer</h2>
                  <InsightsList insights={insights} />
                </TabPanel>
              )}
              {tab === "cleaning" && (
                <TabPanel>
                  <h2 className="mb-4 font-semibold text-white">Cleaning report</h2>
                  <CleaningReport items={cleaningReport} />
                </TabPanel>
              )}
              {tab === "charts" && (
                <TabPanel>
                  <ChartViewer projectId={projectId} autoLoad />
                </TabPanel>
              )}
              {tab === "timeseries" && (
                <TabPanel>
                  <TimeseriesView projectId={projectId} />
                </TabPanel>
              )}
              {tab === "duplicates" && (
                <TabPanel>
                  <DuplicatesView projectId={projectId} />
                </TabPanel>
              )}
              {tab === "outliers" && (
                <TabPanel>
                  <OutlierView projectId={projectId} />
                </TabPanel>
              )}
              {tab === "correlations" && (
                <TabPanel>
                  <CorrelationMatrix projectId={projectId} />
                </TabPanel>
              )}
              {tab === "compare-cols" && (
                <TabPanel>
                  <ColumnCompare projectId={projectId} />
                </TabPanel>
              )}
              {tab === "compare-files" && (
                <TabPanel>
                  <MultifileCompare currentProjectId={projectId} />
                </TabPanel>
              )}
              {tab === "predictions" && (
                <TabPanel>
                  <PredictionsView projectId={projectId} />
                </TabPanel>
              )}
              {tab === "ask-ai" && (
                <TabPanel>
                  <AiChatView projectId={projectId} />
                </TabPanel>
              )}
              {tab === "pivot" && (
                <TabPanel>
                  <PivotView projectId={projectId} />
                </TabPanel>
              )}
              {tab === "segments" && (
                <TabPanel>
                  <SegmentsView projectId={projectId} />
                </TabPanel>
              )}
              {tab === "ab-tests" && (
                <TabPanel>
                  <AbTestsView projectId={projectId} />
                </TabPanel>
              )}
              {tab === "query" && (
                <TabPanel>
                  <QueryView projectId={projectId} />
                </TabPanel>
              )}
            </div>
          </details>
        </div>
      ) : (
        !loading && (
          <div className="rounded-2xl border border-white/[0.07] bg-white/[0.02] p-12 text-center">
            <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-xl bg-indigo-500/10">
              <Play className="h-5 w-5 text-indigo-400" />
            </div>
            <p className="text-sm text-white/50">
              Upload a dataset, then run the saved analysis to generate the executive summary and reusable artifact.
            </p>
          </div>
        )
      )}
    </div>
  );
}
