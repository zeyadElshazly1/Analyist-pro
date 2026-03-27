"use client";

import { useState } from "react";
import { runAnalysis } from "@/lib/api";
import { Button } from "@/components/ui/button";

import { StatsCards } from "@/components/analysis/stats-cards";
import { InsightsList } from "@/components/analysis/insights-list";
import { HealthScore } from "@/components/analysis/health-score";
import { ProjectTabs } from "./project-tabs";
import { ColumnsTable } from "@/components/analysis/columns-table";
import { CleaningReport } from "@/components/analysis/cleaning-report";
import { CleaningSummaryCards } from "@/components/analysis/cleaning-summary-cards";
import { InsightHighlights } from "@/components/analysis/insight-highlights";
import { RecommendedAction } from "@/components/analysis/recommended-action";
import { ChartViewer } from "@/components/analysis/chart-viewer";

type Props = {
  projectId: number;
};

export function RunAnalysis({ projectId }: Props) {
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<any | null>(null);
  const [tab, setTab] = useState("overview");
  const [message, setMessage] = useState("");

  async function handleRun() {
    try {
      setLoading(true);
      setMessage("");
      const data = await runAnalysis(projectId);
      setResult(data);
    } catch (error) {
      if (error instanceof Error) {
        setMessage(error.message);
      } else {
        setMessage("Analysis failed.");
      }
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-6">
      <Button onClick={handleRun} disabled={loading}>
        {loading ? "Running..." : "Run analysis"}
      </Button>

      {message ? <p className="text-sm text-red-400">{message}</p> : null}

      {result ? (
        <div className="space-y-6">
          <ProjectTabs value={tab} onChange={setTab} />

          {tab === "overview" && (
            <div className="space-y-6">
              <StatsCards summary={result.dataset_summary} />

              <div className="rounded-2xl border border-white/10 bg-white/5 p-6">
                <HealthScore score={result.health_score} />
              </div>

              <div className="rounded-2xl border border-white/10 bg-white/5 p-6">
                <h2 className="mb-4 font-semibold text-white">Top highlights</h2>
                <InsightHighlights insights={result.insights} />
              </div>

              <div className="rounded-2xl border border-white/10 bg-white/5 p-6">
                <h2 className="mb-4 font-semibold text-white">Cleaning summary</h2>
                <CleaningSummaryCards summary={result.cleaning_summary} />
              </div>

              <RecommendedAction insights={result.insights} />
            </div>
          )}

          {tab === "insights" && (
            <div className="rounded-2xl border border-white/10 bg-white/5 p-6">
              <h2 className="mb-4 font-semibold text-white">Insights</h2>
              <InsightsList insights={result.insights} />
            </div>
          )}

          {tab === "columns" && (
            <div className="rounded-2xl border border-white/10 bg-white/5 p-6">
              <h2 className="mb-4 font-semibold text-white">Columns</h2>
              <ColumnsTable profile={result.profile} />
            </div>
          )}

          {tab === "cleaning" && (
            <div className="rounded-2xl border border-white/10 bg-white/5 p-6">
              <h2 className="mb-4 font-semibold text-white">Cleaning report</h2>
              <CleaningReport items={result.cleaning_report} />
            </div>
          )}

          {tab === "charts" && (
            <div className="rounded-2xl border border-white/10 bg-white/5 p-6">
              <h2 className="mb-4 font-semibold text-white">Charts</h2>
              <ChartViewer projectId={projectId} />
            </div>
          )}
        </div>
      ) : null}
    </div>
  );
}