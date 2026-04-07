"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { getProjects, getProjectLatestInsights, type ProjectInsights } from "@/lib/api";
import {
  TrendingUp,
  AlertTriangle,
  Layers,
  Zap,
  ArrowRight,
  Loader2,
  BarChart2,
  Sparkles,
} from "lucide-react";

// ── Insight type icons & colors ────────────────────────────────────────────────
const INSIGHT_META: Record<string, { color: string; bg: string; Icon: React.ElementType }> = {
  correlation: { color: "text-indigo-400", bg: "bg-indigo-500/10", Icon: TrendingUp },
  anomaly:     { color: "text-amber-400",  bg: "bg-amber-500/10",  Icon: AlertTriangle },
  segment:     { color: "text-emerald-400",bg: "bg-emerald-500/10",Icon: Layers },
  distribution:{ color: "text-sky-400",    bg: "bg-sky-500/10",    Icon: BarChart2 },
  data_quality:{ color: "text-rose-400",   bg: "bg-rose-500/10",   Icon: AlertTriangle },
};
const DEFAULT_META = { color: "text-violet-400", bg: "bg-violet-500/10", Icon: Zap };

function HealthBadge({ score }: { score: number | null }) {
  if (score === null) return null;
  const grade = score >= 85 ? "A" : score >= 70 ? "B" : score >= 55 ? "C" : "D";
  const color =
    score >= 85 ? "text-emerald-400 bg-emerald-500/10 border-emerald-500/20" :
    score >= 70 ? "text-blue-400 bg-blue-500/10 border-blue-500/20" :
    score >= 55 ? "text-amber-400 bg-amber-500/10 border-amber-500/20" :
    "text-red-400 bg-red-500/10 border-red-500/20";
  return (
    <span className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[10px] font-semibold ${color}`}>
      {grade} · {score}
    </span>
  );
}

interface InsightCardProps {
  data: ProjectInsights;
}

function InsightCard({ data }: InsightCardProps) {
  const topInsight = data.insights[0];
  const meta = topInsight ? (INSIGHT_META[topInsight.type] ?? DEFAULT_META) : DEFAULT_META;

  return (
    <div className="rounded-xl border border-white/[0.06] bg-white/[0.02] p-4 hover:border-white/10 hover:bg-white/[0.035] transition-all group">
      {/* Project header */}
      <div className="flex items-start justify-between gap-2 mb-3">
        <div className="min-w-0">
          <p className="text-xs font-semibold text-white truncate">{data.project_name}</p>
          {data.created_at && (
            <p className="text-[10px] text-white/30 mt-0.5">
              {new Date(data.created_at).toLocaleDateString(undefined, { month: "short", day: "numeric" })}
            </p>
          )}
        </div>
        <HealthBadge score={data.health_score} />
      </div>

      {/* Top insight */}
      {topInsight ? (
        <div className="space-y-1">
          <div className="flex items-center gap-1.5">
            <div className={`flex h-5 w-5 flex-shrink-0 items-center justify-center rounded ${meta.bg}`}>
              <meta.Icon className={`h-3 w-3 ${meta.color}`} />
            </div>
            <p className="text-xs font-medium text-white/80 line-clamp-1">{topInsight.title}</p>
          </div>
          <p className="text-[11px] text-white/45 line-clamp-2 leading-relaxed pl-6">{topInsight.finding}</p>
        </div>
      ) : (
        <p className="text-[11px] text-white/30 italic">No insights yet</p>
      )}

      {/* CTA */}
      {data.analysis_id && (
        <Link
          href={`/reports/${data.project_id}`}
          className="mt-3 flex items-center gap-1 text-[10px] font-medium text-indigo-400 opacity-0 group-hover:opacity-100 transition-opacity"
        >
          View full analysis <ArrowRight className="h-2.5 w-2.5" />
        </Link>
      )}
    </div>
  );
}

// ── Main Widget ────────────────────────────────────────────────────────────────
export function InsightsWidget() {
  const [items, setItems] = useState<ProjectInsights[]>([]);
  const [loading, setLoading] = useState(true);
  const [hasAnalyses, setHasAnalyses] = useState(false);

  useEffect(() => {
    async function load() {
      try {
        const projects = await getProjects();
        const readyProjects = projects.filter((p) => p.status === "ready").slice(0, 3);
        setHasAnalyses(readyProjects.length > 0);
        if (readyProjects.length === 0) return;
        const results = await Promise.allSettled(
          readyProjects.map((p) => getProjectLatestInsights(p.id))
        );
        const insights = results
          .filter((r): r is PromiseFulfilledResult<ProjectInsights> => r.status === "fulfilled")
          .map((r) => r.value)
          .filter((r) => r.insights.length > 0 || r.health_score !== null);
        setItems(insights);
      } catch {
        // Silently fail — this is an enhancement widget
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-8">
        <Loader2 className="h-4 w-4 animate-spin text-white/30" />
      </div>
    );
  }

  if (!hasAnalyses) {
    return (
      <div className="flex flex-col items-center gap-2 py-6 text-center">
        <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-indigo-500/10">
          <Sparkles className="h-5 w-5 text-indigo-400" />
        </div>
        <p className="text-sm text-white/50">No analyses yet</p>
        <p className="text-xs text-white/30">Upload a dataset and run your first analysis to see insights here.</p>
      </div>
    );
  }

  if (items.length === 0) {
    return (
      <p className="text-sm text-white/40 py-4 text-center">No insight data available yet.</p>
    );
  }

  return (
    <div className="space-y-2">
      {items.map((item) => (
        <InsightCard key={item.project_id} data={item} />
      ))}
    </div>
  );
}
