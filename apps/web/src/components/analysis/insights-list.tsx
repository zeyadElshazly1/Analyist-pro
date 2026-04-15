"use client";

import { useState } from "react";
import { Copy, Check } from "lucide-react";

type Insight = {
  type?: string;
  severity?: string;
  confidence?: number;
  title?: string;
  finding?: string;
  evidence?: string;
  action?: string;
  description?: string;
  why_it_matters?: string;
  likely_drivers?: string;
};

type Props = {
  insights: Insight[];
};

const TYPE_META: Record<string, { dot: string; badge: string; label: string }> = {
  correlation:       { dot: "bg-indigo-400",  badge: "bg-indigo-500/20 text-indigo-300",   label: "Correlation" },
  anomaly:           { dot: "bg-red-400",      badge: "bg-red-500/20 text-red-300",         label: "Anomaly" },
  segment:           { dot: "bg-purple-400",   badge: "bg-purple-500/20 text-purple-300",   label: "Segment" },
  distribution:      { dot: "bg-amber-400",    badge: "bg-amber-500/20 text-amber-300",     label: "Distribution" },
  data_quality:      { dot: "bg-orange-400",   badge: "bg-orange-500/20 text-orange-300",   label: "Data Quality" },
  trend:             { dot: "bg-teal-400",     badge: "bg-teal-500/20 text-teal-300",       label: "Trend" },
  concentration:     { dot: "bg-yellow-400",   badge: "bg-yellow-500/20 text-yellow-300",   label: "Concentration" },
  interaction:       { dot: "bg-pink-400",     badge: "bg-pink-500/20 text-pink-300",       label: "Interaction" },
  simpsons_paradox:  { dot: "bg-rose-400",     badge: "bg-rose-500/20 text-rose-300",       label: "Simpson's" },
  missing_pattern:   { dot: "bg-slate-400",    badge: "bg-slate-500/20 text-slate-300",     label: "Missing Pattern" },
  multicollinearity: { dot: "bg-cyan-400",     badge: "bg-cyan-500/20 text-cyan-300",       label: "Multicollinearity" },
  leading_indicator: { dot: "bg-emerald-400",  badge: "bg-emerald-500/20 text-emerald-300", label: "Leading Indicator" },
};

const SEVERITY_META: Record<string, string> = {
  high:   "border-red-500/20 bg-red-500/5",
  medium: "border-white/[0.07] bg-white/[0.03]",
  low:    "border-white/[0.04] bg-white/[0.02]",
};

const ALL_TYPES = [
  "all",
  "correlation", "anomaly", "segment", "distribution", "data_quality",
  "trend", "concentration", "interaction", "simpsons_paradox",
  "missing_pattern", "multicollinearity", "leading_indicator",
];

function CopyInsightButton({ insight }: { insight: Insight }) {
  const [copied, setCopied] = useState(false);

  function handleCopy(e: React.MouseEvent) {
    e.stopPropagation();
    const lines: string[] = [];
    const title = insight.title ?? insight.type ?? "Insight";
    lines.push(title);
    if (insight.finding ?? insight.description) lines.push(insight.finding ?? insight.description ?? "");
    if (insight.evidence) lines.push(`Evidence: ${insight.evidence}`);
    if (insight.action) lines.push(`Action: ${insight.action}`);
    navigator.clipboard.writeText(lines.join("\n")).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 1800);
    });
  }

  return (
    <button
      onClick={handleCopy}
      className="flex-shrink-0 rounded p-1 text-white/20 hover:text-white/60 transition-colors"
      title="Copy insight"
    >
      {copied ? <Check className="h-3.5 w-3.5 text-emerald-400" /> : <Copy className="h-3.5 w-3.5" />}
    </button>
  );
}

export function InsightsList({ insights }: Props) {
  const [filter, setFilter] = useState("all");
  const [expandedIdx, setExpandedIdx] = useState<number | null>(null);

  if (!insights || insights.length === 0) {
    return <p className="text-white/40 text-sm">No insights found. Run analysis on a richer dataset.</p>;
  }

  const filtered = filter === "all" ? insights : insights.filter((i) => i.type === filter);

  return (
    <div className="space-y-4">
      {/* Filter tabs */}
      <div className="flex flex-wrap gap-1.5">
        {ALL_TYPES.map((type) => {
          const count = type === "all" ? insights.length : insights.filter((i) => i.type === type).length;
          if (count === 0 && type !== "all") return null;
          const meta = type !== "all" ? TYPE_META[type] : null;
          return (
            <button
              key={type}
              onClick={() => setFilter(type)}
              className={`rounded-full px-3 py-1 text-xs font-medium transition-colors ${
                filter === type
                  ? "bg-indigo-600 text-white"
                  : "bg-white/[0.06] text-white/50 hover:text-white"
              }`}
            >
              {type === "all" ? "All" : (meta?.label ?? type)} {count > 0 ? `(${count})` : ""}
            </button>
          );
        })}
      </div>

      {/* Insight cards */}
      <div className="space-y-2">
        {filtered.map((insight, idx) => {
          const meta = TYPE_META[insight.type ?? ""] ?? { dot: "bg-white/20", badge: "bg-white/10 text-white/50", label: insight.type ?? "" };
          const severityClass = SEVERITY_META[insight.severity ?? "medium"] ?? SEVERITY_META.medium;
          const isExpanded = expandedIdx === idx;

          return (
            <div
              key={idx}
              className={`rounded-xl border p-4 transition-all ${severityClass}`}
            >
              {/* Header */}
              <div className="flex items-start gap-2">
                <button
                  className="flex flex-1 items-start gap-3 text-left"
                  onClick={() => setExpandedIdx(isExpanded ? null : idx)}
                >
                  <span className={`mt-1.5 h-2 w-2 rounded-full flex-shrink-0 ${meta.dot}`} />
                  <div className="flex-1 min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <p className="text-sm font-semibold text-white">
                        {insight.title ?? insight.type ?? "Insight"}
                      </p>
                      <span className={`rounded-full px-2 py-0.5 text-xs ${meta.badge}`}>
                        {meta.label || insight.type}
                      </span>
                      {insight.severity === "high" && (
                        <span className="rounded-full bg-red-500/20 px-2 py-0.5 text-xs text-red-300">high severity</span>
                      )}
                      {insight.confidence !== undefined && (
                        <span className="rounded-full bg-white/[0.08] px-2 py-0.5 text-xs text-white/50">
                          {insight.confidence}% confidence
                        </span>
                      )}
                    </div>

                    {insight.finding || insight.description ? (
                      <p className="mt-1.5 text-sm text-white/60 leading-relaxed">
                        {insight.finding ?? insight.description}
                      </p>
                    ) : null}
                  </div>
                </button>
                <CopyInsightButton insight={insight} />
              </div>

              {/* Expanded: evidence + why_it_matters + likely_drivers + action */}
              {isExpanded && (
                <div className="mt-3 ml-5 space-y-2 border-t border-white/[0.07] pt-3">
                  {insight.evidence && (
                    <div className="rounded-lg bg-white/[0.04] px-3 py-2">
                      <p className="text-xs font-medium text-white/40 mb-0.5">Evidence</p>
                      <p className="text-xs font-mono text-white/60">{insight.evidence}</p>
                    </div>
                  )}

                  {insight.why_it_matters && (
                    <div className="rounded-lg bg-indigo-500/[0.07] border border-indigo-500/10 px-3 py-2">
                      <p className="text-xs font-medium text-indigo-400/80 mb-0.5">Why it matters</p>
                      <p className="text-xs text-white/60 leading-relaxed">{insight.why_it_matters}</p>
                    </div>
                  )}

                  {insight.likely_drivers && (
                    <div className="rounded-lg bg-purple-500/[0.07] border border-purple-500/10 px-3 py-2">
                      <p className="text-xs font-medium text-purple-400/80 mb-0.5">Likely drivers</p>
                      <p className="text-xs text-white/60 leading-relaxed">{insight.likely_drivers}</p>
                    </div>
                  )}

                  {insight.action && (
                    <div className="rounded-lg border border-indigo-500/20 bg-indigo-500/10 px-3 py-2">
                      <p className="text-xs font-medium text-indigo-400 mb-0.5">Recommended Action</p>
                      <p className="text-sm text-indigo-200">{insight.action}</p>
                    </div>
                  )}
                </div>
              )}

              {/* Collapsed: show action hint */}
              {!isExpanded && insight.action && (
                <p className="mt-2 ml-5 text-xs text-indigo-400/70 cursor-pointer" onClick={() => setExpandedIdx(idx)}>
                  Click to see recommendation →
                </p>
              )}
            </div>
          );
        })}
      </div>

      {filtered.length === 0 && (
        <p className="text-sm text-white/40">No {filter} insights found.</p>
      )}
    </div>
  );
}
