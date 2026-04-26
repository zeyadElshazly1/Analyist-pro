"use client";

import { useState } from "react";
import { Copy, Check, ChevronDown, ChevronUp } from "lucide-react";

type Insight = {
  // canonical V1
  insight_id?: string;
  category?: string;
  explanation?: string;
  recommendation?: string;
  columns_used?: string[];
  caveats?: string[];
  report_safe?: boolean;
  why_it_matters?: string;
  method_used?: string;
  // legacy
  type?: string;
  finding?: string;
  action?: string;
  description?: string;
  likely_drivers?: string;
  // common
  title?: string;
  severity?: string;
  confidence?: number;  // canonical 0.0–1.0; legacy 0–100
  evidence?: string;
};

type Props = { insights: Insight[] };

// ── Category styling ─────────────────────────────────────────────────────────

const CAT_META: Record<string, { dot: string; badge: string; label: string }> = {
  correlation:       { dot: "bg-indigo-400",  badge: "border-indigo-500/20 bg-indigo-500/10 text-indigo-300",   label: "Correlation" },
  anomaly:           { dot: "bg-red-400",      badge: "border-red-500/20 bg-red-500/10 text-red-300",           label: "Anomaly" },
  segment:           { dot: "bg-purple-400",   badge: "border-purple-500/20 bg-purple-500/10 text-purple-300",  label: "Segment" },
  distribution:      { dot: "bg-amber-400",    badge: "border-amber-500/20 bg-amber-500/10 text-amber-300",     label: "Distribution" },
  data_quality:      { dot: "bg-orange-400",   badge: "border-orange-500/20 bg-orange-500/10 text-orange-300", label: "Data Quality" },
  trend:             { dot: "bg-teal-400",     badge: "border-teal-500/20 bg-teal-500/10 text-teal-300",        label: "Trend" },
  concentration:     { dot: "bg-yellow-400",   badge: "border-yellow-500/20 bg-yellow-500/10 text-yellow-300", label: "Concentration" },
  interaction:       { dot: "bg-pink-400",     badge: "border-pink-500/20 bg-pink-500/10 text-pink-300",        label: "Interaction" },
  simpsons_paradox:  { dot: "bg-rose-400",     badge: "border-rose-500/20 bg-rose-500/10 text-rose-300",        label: "Simpson's Paradox" },
  missing_pattern:   { dot: "bg-slate-400",    badge: "border-slate-500/20 bg-slate-500/10 text-slate-300",    label: "Missing Pattern" },
  multicollinearity: { dot: "bg-cyan-400",     badge: "border-cyan-500/20 bg-cyan-500/10 text-cyan-300",        label: "Multicollinearity" },
  leading_indicator: { dot: "bg-emerald-400",  badge: "border-emerald-500/20 bg-emerald-500/10 text-emerald-300", label: "Leading Indicator" },
};

const FALLBACK_META = { dot: "bg-white/20", badge: "border-white/[0.08] bg-white/[0.05] text-white/40", label: "" };

// ── Helpers ───────────────────────────────────────────────────────────────────

function confPct(c: number | undefined): number | undefined {
  if (c === undefined) return undefined;
  return c <= 1 ? Math.round(c * 100) : Math.round(c);
}

function isReportSafe(i: Insight): boolean {
  if (typeof i.report_safe === "boolean") return i.report_safe;
  const conf = confPct(i.confidence) ?? 0;
  const cat  = i.category ?? i.type ?? "";
  return (
    (i.severity === "high" || i.severity === "medium") &&
    conf >= 60 &&
    cat !== "data_quality" &&
    cat !== "missing_pattern"
  );
}

function reviewReason(i: Insight): string {
  const cat  = i.category ?? i.type ?? "";
  const conf = confPct(i.confidence) ?? 0;
  if (cat === "data_quality" || cat === "missing_pattern")
    return "Data quality finding — verify with source before including in a report";
  if (conf < 60) return `Lower confidence (${conf}%) — may not generalise to all subsets`;
  return "Flagged for manual review before report inclusion";
}

function getBucket(i: Insight): "report" | "review" | "info" {
  if (isReportSafe(i)) return "report";
  if (i.severity === "high" || i.severity === "medium") return "review";
  return "info";
}

function sortByPriority(arr: Insight[]): Insight[] {
  const sevRank = (s: string | undefined) => (s === "high" ? 0 : s === "medium" ? 1 : 2);
  return [...arr].sort((a, b) => {
    const sd = sevRank(a.severity) - sevRank(b.severity);
    if (sd !== 0) return sd;
    return (confPct(b.confidence) ?? 0) - (confPct(a.confidence) ?? 0);
  });
}

function makeCopyText(i: Insight): string {
  const lines: string[] = [];
  const cat = i.category ?? i.type ?? "";
  lines.push(i.title ?? CAT_META[cat]?.label ?? "Insight");
  const body = i.explanation ?? i.finding ?? i.description ?? "";
  if (body) lines.push(body);
  if (i.evidence) lines.push(`Evidence: ${i.evidence}`);
  const action = i.recommendation ?? i.action ?? "";
  if (action) lines.push(`Action: ${action}`);
  return lines.join("\n");
}

// ── Copy button ──────────────────────────────────────────────────────────────

function CopyButton({ insight }: { insight: Insight }) {
  const [copied, setCopied] = useState(false);
  function handle(e: React.MouseEvent) {
    e.stopPropagation();
    navigator.clipboard.writeText(makeCopyText(insight)).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 1800);
    });
  }
  return (
    <button onClick={handle} className="rounded p-1 text-white/20 hover:text-white/50 transition-colors flex-shrink-0" title="Copy">
      {copied ? <Check className="h-3.5 w-3.5 text-emerald-400" /> : <Copy className="h-3.5 w-3.5" />}
    </button>
  );
}

// ── Insight card ─────────────────────────────────────────────────────────────

function InsightCard({ insight, reviewNote }: { insight: Insight; reviewNote?: string }) {
  const [open, setOpen] = useState(false);

  const cat      = insight.category ?? insight.type ?? "";
  const meta     = CAT_META[cat] ?? FALLBACK_META;
  const safe     = isReportSafe(insight);
  const confNum  = confPct(insight.confidence);
  const bodyText = insight.explanation ?? insight.finding ?? insight.description ?? "";
  const action   = insight.recommendation ?? insight.action ?? "";
  const why      = insight.why_it_matters ?? "";

  return (
    <div className="rounded-xl border border-white/[0.07] bg-white/[0.02] overflow-hidden">
      <button
        className="w-full text-left px-4 py-3 flex items-start gap-3 hover:bg-white/[0.02] transition-colors"
        onClick={() => setOpen((v) => !v)}
      >
        <span className={`mt-[5px] h-2 w-2 flex-shrink-0 rounded-full ${meta.dot}`} />
        <div className="flex-1 min-w-0 space-y-1">
          {/* Badge row */}
          <div className="flex flex-wrap items-center gap-1.5">
            <span className={`rounded-full border px-2 py-0.5 text-[10px] font-medium ${meta.badge}`}>
              {meta.label || cat}
            </span>
            {insight.severity === "high" && (
              <span className="rounded-full border border-red-500/20 bg-red-500/10 px-1.5 py-0.5 text-[10px] font-medium text-red-300">
                High priority
              </span>
            )}
            {safe ? (
              <span className="rounded-full border border-emerald-500/20 bg-emerald-500/10 px-1.5 py-0.5 text-[10px] font-medium text-emerald-400">
                ✓ Report-ready
              </span>
            ) : reviewNote ? null : (
              <span className="rounded-full border border-white/[0.08] bg-white/[0.04] px-1.5 py-0.5 text-[10px] text-white/30">
                Informational
              </span>
            )}
            {confNum !== undefined && (
              <span className="ml-auto text-[10px] tabular-nums text-white/30">
                {confNum}% confidence
              </span>
            )}
          </div>
          {/* Title */}
          <p className="text-sm font-semibold text-white leading-snug">
            {insight.title ?? meta.label ?? cat ?? "Insight"}
          </p>
          {/* Explanation */}
          {bodyText && (
            <p className={`text-xs text-white/55 leading-relaxed ${open ? "" : "line-clamp-2"}`}>
              {bodyText}
            </p>
          )}
          {/* Review note */}
          {reviewNote && !open && (
            <p className="text-[11px] text-amber-400/60">{reviewNote}</p>
          )}
        </div>
        <div className="flex items-center gap-0.5 ml-1 mt-0.5">
          <CopyButton insight={insight} />
          {open
            ? <ChevronUp className="h-3.5 w-3.5 text-white/20" />
            : <ChevronDown className="h-3.5 w-3.5 text-white/20" />}
        </div>
      </button>

      {open && (
        <div className="border-t border-white/[0.06] px-4 pb-4 pt-3 ml-5 space-y-2.5">
          {reviewNote && (
            <p className="text-[11px] text-amber-400/70 leading-relaxed">{reviewNote}</p>
          )}
          {why && (
            <div className="rounded-lg border border-indigo-500/10 bg-indigo-500/[0.06] px-3 py-2">
              <p className="mb-0.5 text-[10px] font-medium uppercase tracking-wider text-indigo-400/60">Why it matters</p>
              <p className="text-xs text-white/60 leading-relaxed">{why}</p>
            </div>
          )}
          {action && (
            <div className="rounded-lg border border-emerald-500/15 bg-emerald-500/[0.05] px-3 py-2">
              <p className="mb-0.5 text-[10px] font-medium uppercase tracking-wider text-emerald-400/60">Recommended action</p>
              <p className="text-xs text-white/70 leading-relaxed">{action}</p>
            </div>
          )}
          {insight.evidence && (
            <div className="rounded-lg bg-white/[0.04] px-3 py-1.5">
              <p className="mb-0.5 text-[10px] text-white/25">Evidence</p>
              <p className="text-[11px] font-mono text-white/50 break-all">{insight.evidence}</p>
            </div>
          )}
          {(insight.columns_used?.length ?? 0) > 0 && (
            <div className="flex flex-wrap items-center gap-1.5">
              <span className="text-[10px] text-white/25">Columns used:</span>
              {insight.columns_used?.map((c) => (
                <span key={c} className="rounded border border-white/[0.08] bg-white/[0.03] px-1.5 py-0.5 font-mono text-[10px] text-white/50">{c}</span>
              ))}
            </div>
          )}
          {(insight.caveats?.length ?? 0) > 0 && (
            <div className="space-y-0.5 pt-0.5">
              {insight.caveats?.map((c, i) => (
                <p key={i} className="text-[10px] text-white/25 leading-relaxed">ⓘ {c}</p>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ── Section header ────────────────────────────────────────────────────────────

function SectionHead({
  label, count, accent, sub,
}: {
  label: string; count: number; accent: string; sub?: string;
}) {
  return (
    <div className={`flex items-baseline gap-2 border-b pb-2 ${accent}`}>
      <p className="text-sm font-semibold text-white">{label}</p>
      <span className="text-xs text-white/35">{count} {count === 1 ? "finding" : "findings"}</span>
      {sub && <span className="ml-auto text-[11px] text-white/25">{sub}</span>}
    </div>
  );
}

// ── Main export ──────────────────────────────────────────────────────────────

export function InsightsList({ insights }: Props) {
  const [showInfo, setShowInfo] = useState(false);

  if (!insights || insights.length === 0) {
    return <p className="text-sm text-white/40">No insights found. Run analysis on a richer dataset.</p>;
  }

  const sorted = sortByPriority(insights);
  const forReport  = sorted.filter((i) => getBucket(i) === "report");
  const needsReview = sorted.filter((i) => getBucket(i) === "review");
  const info        = sorted.filter((i) => getBucket(i) === "info");

  return (
    <div className="space-y-6">

      {/* Summary bar */}
      <div className="flex flex-wrap gap-3">
        <span className="text-xs text-white/30">{insights.length} {insights.length === 1 ? "finding" : "findings"}</span>
        {forReport.length > 0 && (
          <span className="text-xs text-emerald-400/80">
            {forReport.length} report-ready
          </span>
        )}
        {needsReview.length > 0 && (
          <span className="text-xs text-amber-400/70">
            {needsReview.length} needs review
          </span>
        )}
        {info.length > 0 && (
          <span className="text-xs text-white/25">
            {info.length} informational
          </span>
        )}
      </div>

      {/* Section 1: Report-ready */}
      {forReport.length > 0 && (
        <div className="space-y-2">
          <SectionHead
            label="For your report"
            count={forReport.length}
            accent="border-emerald-500/20"
            sub="Safe to include without manual review"
          />
          {forReport.map((insight, i) => (
            <InsightCard key={insight.insight_id ?? i} insight={insight} />
          ))}
        </div>
      )}

      {/* Section 2: Needs review */}
      {needsReview.length > 0 && (
        <div className="space-y-2">
          <SectionHead
            label="Review before including"
            count={needsReview.length}
            accent="border-amber-500/20"
            sub="Verify each before adding to a client report"
          />
          {needsReview.map((insight, i) => (
            <InsightCard
              key={insight.insight_id ?? i}
              insight={insight}
              reviewNote={reviewReason(insight)}
            />
          ))}
        </div>
      )}

      {/* Section 3: Informational (collapsed) */}
      {info.length > 0 && (
        <div className="space-y-2">
          <button
            onClick={() => setShowInfo((v) => !v)}
            className="flex items-center gap-1.5 text-xs text-white/25 hover:text-white/45 transition-colors"
          >
            {showInfo ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
            {showInfo ? "Hide" : "Show"} {info.length} informational {info.length === 1 ? "finding" : "findings"}
          </button>
          {showInfo && info.map((insight, i) => (
            <InsightCard key={insight.insight_id ?? i} insight={insight} />
          ))}
        </div>
      )}

      {/* Nudge toward report building */}
      {forReport.length > 0 && (
        <p className="text-[11px] text-white/20">
          {forReport.length} finding{forReport.length > 1 ? "s" : ""} marked report-ready — head to{" "}
          <span className="text-white/35">Report</span> to select which ones to include.
        </p>
      )}
    </div>
  );
}
