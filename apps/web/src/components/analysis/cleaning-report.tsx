type CleaningItem = {
  step: string;
  detail: string;
  impact: "high" | "medium" | "low";
};

type Props = { items: CleaningItem[] };

const IMPACT_STYLE = {
  high:   "bg-rose-500/10 text-rose-400 border-rose-500/20",
  medium: "bg-amber-500/10 text-amber-400 border-amber-500/20",
  low:    "bg-white/5 text-white/40 border-white/10",
};

export function CleaningReport({ items }: Props) {
  if (!items || items.length === 0) {
    return (
      <p className="text-sm text-emerald-400">
        No cleaning actions needed — dataset was already clean.
      </p>
    );
  }

  return (
    <div className="space-y-2">
      {items.map((item, i) => (
        <div
          key={i}
          className="flex items-start gap-3 rounded-xl border border-white/[0.06] bg-white/[0.02] px-4 py-3"
        >
          <span className="mt-0.5 text-xs text-white/30 w-4 flex-shrink-0">{i + 1}</span>
          <div className="flex-1 min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <p className="text-sm font-medium text-white">{item.step}</p>
              <span className={`rounded-full border px-2 py-0.5 text-[11px] font-medium ${IMPACT_STYLE[item.impact] ?? IMPACT_STYLE.low}`}>
                {item.impact} impact
              </span>
            </div>
            <p className="mt-1 text-xs text-white/50">{item.detail}</p>
          </div>
        </div>
      ))}
    </div>
  );
}
