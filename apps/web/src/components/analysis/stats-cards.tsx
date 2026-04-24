// eslint-disable-next-line @typescript-eslint/no-explicit-any
type HealthResult = Record<string, any>;

type LegacySummary = {
  rows?: number;
  columns?: number;
  numeric_cols?: number;
  categorical_cols?: number;
  missing_pct?: number;
  domain?: string;
};

type Props = {
  healthResult?: HealthResult | null;   // canonical — primary
  profileResult?: any[] | null;         // canonical — numeric/categorical counts // eslint-disable-line @typescript-eslint/no-explicit-any
  summary?: LegacySummary | null;       // legacy fallback for old stored results
};

const DOMAIN_BADGE: Record<string, string> = {
  "Finance / Sales":       "bg-emerald-500/15 text-emerald-300 border-emerald-500/20",
  "Healthcare":            "bg-rose-500/15 text-rose-300 border-rose-500/20",
  "E-commerce":            "bg-amber-500/15 text-amber-300 border-amber-500/20",
  "Marketing / Analytics": "bg-indigo-500/15 text-indigo-300 border-indigo-500/20",
  "IoT / Manufacturing":   "bg-cyan-500/15 text-cyan-300 border-cyan-500/20",
  "Demographics":          "bg-purple-500/15 text-purple-300 border-purple-500/20",
  "General":               "bg-white/[0.06] text-white/40 border-white/[0.08]",
  // canonical dataset_type values
  "Transactional":         "bg-emerald-500/15 text-emerald-300 border-emerald-500/20",
  "Time Series":           "bg-teal-500/15 text-teal-300 border-teal-500/20",
  "Survey":                "bg-purple-500/15 text-purple-300 border-purple-500/20",
};

const DATASET_TYPE_DISPLAY: Record<string, string> = {
  timeseries:    "Time Series",
  transactional: "Transactional",
  survey:        "Survey",
  general:       "General",
};

export function StatsCards({ healthResult, profileResult, summary }: Props) {
  // Canonical-first reads — fall back to legacy summary values for old stored results.
  const rowCount       = healthResult?.row_count    ?? summary?.rows    ?? 0;
  const colCount       = healthResult?.column_count ?? summary?.columns ?? 0;
  const missingPct     = healthResult?.missingness_stats?.missing_cell_pct ?? summary?.missing_pct ?? 0;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const numericCols    = profileResult ? profileResult.filter((c: any) => c.type === "numeric").length    : (summary?.numeric_cols    ?? 0);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const categoricalCols = profileResult ? profileResult.filter((c: any) => c.type === "categorical").length : (summary?.categorical_cols ?? 0);

  const items = [
    { label: "Rows",        value: (rowCount as number).toLocaleString() },
    { label: "Columns",     value: colCount },
    { label: "Numeric",     value: numericCols },
    { label: "Categorical", value: categoricalCols },
    { label: "Missing",     value: `${typeof missingPct === "number" ? missingPct.toFixed(1) : missingPct}%`, warn: (missingPct as number) > 10 },
  ];

  // Domain label: canonical dataset_type beats old heuristic domain
  const canonicalType = healthResult?.health_score?.dataset_type;
  const domainLabel   = canonicalType
    ? (DATASET_TYPE_DISPLAY[canonicalType] ?? canonicalType)
    : (summary?.domain ?? "General");
  const domainClass   = DOMAIN_BADGE[domainLabel] ?? DOMAIN_BADGE["General"];

  return (
    <div className="space-y-3">
      {/* Domain / dataset-type badge */}
      <div className="flex items-center gap-2">
        <span className={`inline-flex items-center rounded-full border px-3 py-1 text-xs font-medium ${domainClass}`}>
          {domainLabel}
        </span>
        <span className="text-xs text-white/30">{canonicalType ? "dataset type" : "detected domain"}</span>
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
