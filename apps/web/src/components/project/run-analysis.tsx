"use client";

import { useState } from "react";
import { runAnalysis } from "@/lib/api";
import { Play, Loader2 } from "lucide-react";

import { StatsCards } from "@/components/analysis/stats-cards";
import { InsightsList } from "@/components/analysis/insights-list";
import { HealthScore } from "@/components/analysis/health-score";
import { ProjectTabs } from "./project-tabs";
import { ProfileView } from "@/components/analysis/profile-view";
import { CleaningReport } from "@/components/analysis/cleaning-report";
import { CleaningSummaryCards } from "@/components/analysis/cleaning-summary-cards";
import { InsightHighlights } from "@/components/analysis/insight-highlights";
import { RecommendedAction } from "@/components/analysis/recommended-action";
import { ChartViewer } from "@/components/analysis/chart-viewer";
import { TimeseriesView } from "@/components/analysis/timeseries-view";
import { DuplicatesView } from "@/components/analysis/duplicates-view";
import { OutlierView } from "@/components/analysis/outlier-view";
import { CorrelationMatrix } from "@/components/analysis/correlation-matrix";
import { ColumnCompare } from "@/components/analysis/column-compare";
import { MultifileCompare } from "@/components/analysis/multifile-compare";

type Props = { projectId: number };

export function RunAnalysis({ projectId }: Props) {
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<any>(null);
  const [tab, setTab] = useState("overview");
  const [error, setError] = useState("");

  async function handleRun() {
    setLoading(true); setError("");
    try { setResult(await runAnalysis(projectId)); }
    catch (e) { setError(e instanceof Error ? e.message : "Analysis failed."); }
    finally { setLoading(false); }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4">
        <button onClick={handleRun} disabled={loading}
          className="flex items-center gap-2 rounded-lg bg-indigo-600 px-5 py-2.5 text-sm font-medium text-white transition hover:bg-indigo-500 disabled:opacity-60">
          {loading
            ? <><Loader2 className="h-4 w-4 animate-spin" />Running analysis…</>
            : <><Play className="h-4 w-4" />{result ? "Re-run analysis" : "Run analysis"}</>}
        </button>
        {result && !loading && (
          <p className="text-xs text-white/30">
            {result.dataset_summary?.rows?.toLocaleString()} rows · {result.dataset_summary?.columns} columns
          </p>
        )}
      </div>

      {error && <p className="text-sm text-red-400">{error}</p>}

      {result && (
        <div className="space-y-5">
          <ProjectTabs value={tab} onChange={setTab} />

          {tab === "overview" && (
            <div className="space-y-4">
              <StatsCards summary={result.dataset_summary} />
              <div className="rounded-2xl border border-white/[0.07] bg-white/[0.03] p-5">
                <HealthScore score={result.health_score} />
              </div>
              <div className="rounded-2xl border border-white/[0.07] bg-white/[0.03] p-5">
                <h2 className="mb-4 text-sm font-semibold text-white/80">Top insights</h2>
                <InsightHighlights insights={result.insights} />
              </div>
              <RecommendedAction insights={result.insights} />
              <div className="rounded-2xl border border-white/[0.07] bg-white/[0.03] p-5">
                <h2 className="mb-4 text-sm font-semibold text-white/80">Cleaning summary</h2>
                <CleaningSummaryCards summary={result.cleaning_summary} />
              </div>
            </div>
          )}

          {tab === "profile" && (
            <div className="rounded-2xl border border-white/[0.07] bg-white/[0.03] p-5">
              <h2 className="mb-1 text-sm font-semibold text-white/80">Column profiles</h2>
              <p className="mb-4 text-xs text-white/35">Click any row to expand full stats.</p>
              <ProfileView profile={result.profile} />
            </div>
          )}

          {tab === "insights" && (
            <div className="rounded-2xl border border-white/[0.07] bg-white/[0.03] p-5">
              <h2 className="mb-4 text-sm font-semibold text-white/80">Blind spot finder</h2>
              <InsightsList insights={result.insights} />
            </div>
          )}

          {tab === "cleaning" && (
            <div className="space-y-4">
              <div className="rounded-2xl border border-white/[0.07] bg-white/[0.03] p-5">
                <h2 className="mb-4 text-sm font-semibold text-white/80">Summary</h2>
                <CleaningSummaryCards summary={result.cleaning_summary} />
              </div>
              <div className="rounded-2xl border border-white/[0.07] bg-white/[0.03] p-5">
                <h2 className="mb-4 text-sm font-semibold text-white/80">Step-by-step report</h2>
                <CleaningReport items={result.cleaning_report} />
              </div>
            </div>
          )}

          {tab === "charts" && (
            <div className="rounded-2xl border border-white/[0.07] bg-white/[0.03] p-5">
              <h2 className="mb-4 text-sm font-semibold text-white/80">Auto-generated charts</h2>
              <ChartViewer projectId={projectId} autoLoad />
            </div>
          )}

          {tab === "timeseries" && (
            <div className="rounded-2xl border border-white/[0.07] bg-white/[0.03] p-5">
              <h2 className="mb-1 text-sm font-semibold text-white/80">Time series</h2>
              <p className="mb-4 text-xs text-white/35">Pick a date column and a metric to plot over time.</p>
              <TimeseriesView projectId={projectId} />
            </div>
          )}

          {tab === "duplicates" && (
            <div className="rounded-2xl border border-white/[0.07] bg-white/[0.03] p-5">
              <h2 className="mb-1 text-sm font-semibold text-white/80">Duplicate detector</h2>
              <p className="mb-4 text-xs text-white/35">Scans for exact and near-duplicate rows.</p>
              <DuplicatesView projectId={projectId} />
            </div>
          )}

          {tab === "outliers" && (
            <div className="rounded-2xl border border-white/[0.07] bg-white/[0.03] p-5">
              <h2 className="mb-1 text-sm font-semibold text-white/80">Outlier explorer</h2>
              <p className="mb-4 text-xs text-white/35">Z-score outlier detection per column (threshold: |Z| &gt; 3).</p>
              <OutlierView projectId={projectId} />
            </div>
          )}

          {tab === "correlations" && (
            <div className="rounded-2xl border border-white/[0.07] bg-white/[0.03] p-5">
              <h2 className="mb-1 text-sm font-semibold text-white/80">Correlation matrix</h2>
              <p className="mb-4 text-xs text-white/35">Pearson correlation between all numeric columns.</p>
              <CorrelationMatrix projectId={projectId} />
            </div>
          )}

          {tab === "compare" && (
            <div className="rounded-2xl border border-white/[0.07] bg-white/[0.03] p-5">
              <h2 className="mb-1 text-sm font-semibold text-white/80">Column comparison</h2>
              <p className="mb-4 text-xs text-white/35">Auto-detects column types and picks the right chart.</p>
              <ColumnCompare projectId={projectId} />
            </div>
          )}

          {tab === "multifile" && (
            <div className="rounded-2xl border border-white/[0.07] bg-white/[0.03] p-5">
              <h2 className="mb-1 text-sm font-semibold text-white/80">Compare files</h2>
              <p className="mb-4 text-xs text-white/35">Compare datasets from two different projects side-by-side.</p>
              <MultifileCompare />
            </div>
          )}
        </div>
      )}
    </div>
  );
}
