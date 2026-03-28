type Insight = {
  type?: string;
  confidence?: number;
  title?: string;
  finding?: string;
  action?: string;
  description?: string;
};

type Props = { insights: Insight[] };

const TYPE_META: Record<string, { label: string; dot: string; badge: string }> = {
  correlation: {
    label: "Correlation",
    dot: "bg-indigo-400",
    badge: "bg-indigo-500/10 text-indigo-400 border-indigo-500/20",
  },
  anomaly: {
    label: "Anomaly",
    dot: "bg-amber-400",
    badge: "bg-amber-500/10 text-amber-400 border-amber-500/20",
  },
  segment: {
    label: "Segment",
    dot: "bg-emerald-400",
    badge: "bg-emerald-500/10 text-emerald-400 border-emerald-500/20",
  },
  data_quality: {
    label: "Data quality",
    dot: "bg-rose-400",
    badge: "bg-rose-500/10 text-rose-400 border-rose-500/20",
  },
};

function getTypeMeta(type?: string) {
  return (
    TYPE_META[type ?? ""] ?? {
      label: type ?? "Insight",
      dot: "bg-white/40",
      badge: "bg-white/5 text-white/50 border-white/10",
    }
  );
}

export function InsightsList({ insights }: Props) {
  if (!insights || insights.length === 0) {
    return <p className="text-sm text-white/40">No insights found.</p>;
  }

  return (
    <div className="space-y-3">
      {insights.map((insight, idx) => {
        const meta = getTypeMeta(insight.type);
        return (
          <div
            key={idx}
            className="rounded-xl border border-white/[0.07] bg-white/[0.03] p-4 transition-colors hover:bg-white/[0.05]"
          >
            <div className="flex items-start gap-2.5">
              <span className={`mt-1.5 h-2 w-2 flex-shrink-0 rounded-full ${meta.dot}`} />
              <div className="flex-1 min-w-0">
                <div className="flex flex-wrap items-center gap-2">
                  <p className="text-sm font-semibold text-white">
                    {insight.title || insight.type || "Insight"}
                  </p>
                  <span className={`rounded-full border px-2 py-0.5 text-[11px] font-medium ${meta.badge}`}>
                    {meta.label}
                  </span>
                  {insight.confidence !== undefined && (
                    <span className="rounded-full border border-white/10 bg-white/5 px-2 py-0.5 text-[11px] text-white/50">
                      {insight.confidence}% confidence
                    </span>
                  )}
                </div>

                {(insight.finding || insight.description) && (
                  <p className="mt-2 text-sm text-white/60 leading-relaxed">
                    {insight.finding || insight.description}
                  </p>
                )}

                {insight.action && (
                  <div className="mt-3 rounded-lg border border-white/[0.06] bg-white/[0.03] px-3 py-2">
                    <p className="text-[11px] font-medium uppercase tracking-wide text-white/35">
                      Recommended action
                    </p>
                    <p className="mt-1 text-xs text-white/65">{insight.action}</p>
                  </div>
                )}
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}
