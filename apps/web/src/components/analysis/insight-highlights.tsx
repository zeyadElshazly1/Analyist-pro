type Insight = {
  title?: string;
  category?: string;      // canonical
  explanation?: string;   // canonical — replaces finding
  type?: string;          // legacy
  finding?: string;       // legacy
  confidence?: number;
};

type Props = { insights: Insight[] };

const TYPE_STYLE: Record<string, { card: string; dot: string }> = {
  correlation: { card: "border-indigo-500/20 bg-indigo-500/5", dot: "bg-indigo-400" },
  anomaly:     { card: "border-amber-500/20 bg-amber-500/5",   dot: "bg-amber-400" },
  segment:     { card: "border-emerald-500/20 bg-emerald-500/5", dot: "bg-emerald-400" },
  data_quality:{ card: "border-rose-500/20 bg-rose-500/5",     dot: "bg-rose-400" },
};

export function InsightHighlights({ insights }: Props) {
  if (!insights || insights.length === 0) {
    return <p className="text-sm text-white/40">No highlights available.</p>;
  }

  return (
    <div className="grid gap-3 md:grid-cols-3">
      {insights.slice(0, 3).map((insight, i) => {
        const insightType = insight.category ?? insight.type ?? "";
        const style = TYPE_STYLE[insightType] ?? {
          card: "border-white/10 bg-white/[0.03]",
          dot: "bg-white/30",
        };
        return (
          <div key={i} className={`rounded-xl border p-4 ${style.card}`}>
            <div className="flex items-center gap-2 mb-2">
              <span className={`h-2 w-2 rounded-full flex-shrink-0 ${style.dot}`} />
              <span className="text-[11px] uppercase tracking-wide text-white/40 font-medium">
                Highlight {i + 1}
              </span>
            </div>
            <p className="text-sm font-semibold text-white leading-snug">
              {insight.title || insightType || "Insight"}
            </p>
            <p className="mt-2 text-xs text-white/60 leading-relaxed line-clamp-3">
              {insight.explanation ?? insight.finding ?? "No finding available."}
            </p>
          </div>
        );
      })}
    </div>
  );
}
