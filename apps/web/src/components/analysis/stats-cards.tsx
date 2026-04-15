type Props = {
  summary: {
    rows: number;
    columns: number;
    numeric_cols: number;
    categorical_cols: number;
    missing_pct: number;
    domain?: string;
  };
};

const DOMAIN_BADGE: Record<string, string> = {
  "Finance / Sales":       "bg-emerald-500/15 text-emerald-300 border-emerald-500/20",
  "Healthcare":            "bg-rose-500/15 text-rose-300 border-rose-500/20",
  "E-commerce":            "bg-amber-500/15 text-amber-300 border-amber-500/20",
  "Marketing / Analytics": "bg-indigo-500/15 text-indigo-300 border-indigo-500/20",
  "IoT / Manufacturing":   "bg-cyan-500/15 text-cyan-300 border-cyan-500/20",
  "Demographics":          "bg-purple-500/15 text-purple-300 border-purple-500/20",
  "General":               "bg-white/[0.06] text-white/40 border-white/[0.08]",
};

export function StatsCards({ summary }: Props) {
  const items = [
    { label: "Rows",        value: summary.rows.toLocaleString() },
    { label: "Columns",     value: summary.columns },
    { label: "Numeric",     value: summary.numeric_cols },
    { label: "Categorical", value: summary.categorical_cols },
    { label: "Missing",     value: `${summary.missing_pct}%`, warn: summary.missing_pct > 10 },
  ];

  const domainLabel = summary.domain ?? "General";
  const domainClass = DOMAIN_BADGE[domainLabel] ?? DOMAIN_BADGE["General"];

  return (
    <div className="space-y-3">
      {/* Domain badge */}
      <div className="flex items-center gap-2">
        <span className={`inline-flex items-center rounded-full border px-3 py-1 text-xs font-medium ${domainClass}`}>
          {domainLabel}
        </span>
        <span className="text-xs text-white/30">detected domain</span>
      </div>

      {/* Stat cards */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 md:grid-cols-5">
        {items.map((item) => (
          <div key={item.label} className="rounded-xl border border-white/[0.07] bg-white/[0.03] p-4">
            <p className="text-xs text-white/40">{item.label}</p>
            <p className={`mt-1.5 text-2xl font-semibold ${"warn" in item && item.warn ? "text-amber-400" : "text-white"}`}>
              {item.value}
            </p>
          </div>
        ))}
      </div>
    </div>
  );
}
