type Insight = {
  insight_id?: string;
  category?: string;
  explanation?: string;
  report_safe?: boolean;
  why_it_matters?: string;
  type?: string;
  finding?: string;
  title?: string;
  severity?: string;
  confidence?: number;
};

type Props = { insights: Insight[] };

const CAT_STYLE: Record<string, { card: string; dot: string }> = {
  correlation:       { card: "border-indigo-500/20 bg-indigo-500/[0.05]",  dot: "bg-indigo-400" },
  anomaly:           { card: "border-red-500/20 bg-red-500/[0.05]",        dot: "bg-red-400" },
  segment:           { card: "border-purple-500/20 bg-purple-500/[0.05]",  dot: "bg-purple-400" },
  trend:             { card: "border-teal-500/20 bg-teal-500/[0.05]",      dot: "bg-teal-400" },
  distribution:      { card: "border-amber-500/20 bg-amber-500/[0.05]",    dot: "bg-amber-400" },
  data_quality:      { card: "border-orange-500/20 bg-orange-500/[0.05]",  dot: "bg-orange-400" },
  concentration:     { card: "border-yellow-500/20 bg-yellow-500/[0.05]",  dot: "bg-yellow-400" },
  leading_indicator: { card: "border-emerald-500/20 bg-emerald-500/[0.05]", dot: "bg-emerald-400" },
};

const FALLBACK = { card: "border-white/10 bg-white/[0.03]", dot: "bg-white/30" };

function isReportSafe(i: Insight): boolean {
  if (typeof i.report_safe === "boolean") return i.report_safe;
  const conf = i.confidence === undefined ? 0 : (i.confidence <= 1 ? i.confidence * 100 : i.confidence);
  const cat  = i.category ?? i.type ?? "";
  return (
    (i.severity === "high" || i.severity === "medium") &&
    conf >= 60 &&
    cat !== "data_quality" && cat !== "missing_pattern"
  );
}

function sortKey(i: Insight): number {
  const sev  = i.severity === "high" ? 0 : i.severity === "medium" ? 1 : 2;
  const safe = isReportSafe(i) ? 0 : 1;
  const conf = i.confidence === undefined ? 50 : (i.confidence <= 1 ? i.confidence * 100 : i.confidence);
  return safe * 1000 + sev * 100 + (100 - conf);
}

export function InsightHighlights({ insights }: Props) {
  if (!insights || insights.length === 0) {
    return <p className="text-sm text-white/40">No highlights available.</p>;
  }

  const top3 = [...insights].sort((a, b) => sortKey(a) - sortKey(b)).slice(0, 3);

  return (
    <div className="grid gap-3 md:grid-cols-3">
      {top3.map((insight, i) => {
        const cat   = insight.category ?? insight.type ?? "";
        const style = CAT_STYLE[cat] ?? FALLBACK;
        const safe  = isReportSafe(insight);
        const body  = insight.explanation ?? insight.finding ?? "";

        return (
          <div key={insight.insight_id ?? i} className={`rounded-xl border p-4 ${style.card}`}>
            <div className="flex items-start justify-between gap-2 mb-2">
              <div className="flex items-center gap-2">
                <span className={`h-2 w-2 flex-shrink-0 rounded-full ${style.dot}`} />
                <span className="text-[10px] font-medium uppercase tracking-wider text-white/40">
                  #{i + 1} finding
                </span>
              </div>
              {safe ? (
                <span className="flex-shrink-0 rounded-full border border-emerald-500/20 bg-emerald-500/10 px-1.5 py-0.5 text-[10px] font-medium text-emerald-400">
                  ✓ Report-ready
                </span>
              ) : (
                <span className="flex-shrink-0 rounded-full border border-amber-500/20 bg-amber-500/10 px-1.5 py-0.5 text-[10px] font-medium text-amber-400/70">
                  Review needed
                </span>
              )}
            </div>
            <p className="text-sm font-semibold text-white leading-snug">
              {insight.title || cat || "Insight"}
            </p>
            <p className="mt-2 text-xs text-white/55 leading-relaxed line-clamp-3">
              {body || "No finding available."}
            </p>
            {insight.why_it_matters && (
              <p className="mt-2 text-[11px] text-indigo-300/60 leading-relaxed line-clamp-2">
                {insight.why_it_matters}
              </p>
            )}
          </div>
        );
      })}
    </div>
  );
}
