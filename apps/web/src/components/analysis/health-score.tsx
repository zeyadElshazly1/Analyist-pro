// eslint-disable-next-line @typescript-eslint/no-explicit-any
type HealthResult = Record<string, any>;

type LegacyScore = {
  total?: number;
  score?: number;
  grade?: string;
  label?: string;
  color?: string;
  breakdown?: {
    completeness: number;
    uniqueness: number;
    consistency: number;
    validity: number;
    structure: number;
  };
  deductions?: string[];
};

type Props = {
  healthResult?: HealthResult | null;  // canonical — primary source
  score?: LegacyScore | null;          // legacy fallback for old stored results only
};

const SEVERITY_STYLE: Record<string, { badge: string; dot: string }> = {
  high:   { badge: "bg-red-500/15 text-red-300 border-red-500/20",    dot: "bg-red-400" },
  medium: { badge: "bg-amber-500/15 text-amber-300 border-amber-500/20", dot: "bg-amber-400" },
  low:    { badge: "bg-white/[0.06] text-white/40 border-white/[0.08]",  dot: "bg-white/30" },
};

const DIMENSION_LABEL: Record<string, string> = {
  completeness: "Completeness",
  uniqueness:   "Uniqueness",
  consistency:  "Consistency",
  validity:     "Validity",
  structure:    "Structure",
};

const DATASET_TYPE_LABEL: Record<string, string> = {
  timeseries:    "Time Series",
  transactional: "Transactional",
  survey:        "Survey",
  general:       "General",
};

function getMeta(value: number) {
  if (value >= 85) return { ring: "#4ade80", label: "Excellent quality", text: "text-emerald-400" };
  if (value >= 70) return { ring: "#60a5fa", label: "Good quality",      text: "text-blue-400" };
  if (value >= 55) return { ring: "#fbbf24", label: "Needs review",      text: "text-amber-400" };
  if (value >= 40) return { ring: "#f97316", label: "Poor quality",      text: "text-orange-400" };
  return             { ring: "#f87171", label: "Critical issues",    text: "text-red-400" };
}

export function HealthScore({ score, healthResult }: Props) {
  // ── Canonical-first reads ────────────────────────────────────────────────────
  const hs          = healthResult?.health_score;
  const value       = hs?.total_score   ?? score?.total ?? score?.score ?? 0;
  const grade       = hs?.grade         ?? score?.grade ?? "–";
  const breakdown   = hs?.breakdown     ?? score?.breakdown;
  const datasetType = hs?.dataset_type;
  const warnings    = (healthResult?.health_warnings ?? []) as Array<{ dimension: string; message: string; severity: string }>;
  const legacyDeductions = score?.deductions ?? [];

  // Canonical trust signals
  const missingness  = healthResult?.missingness_stats;
  const duplicates   = healthResult?.duplicate_stats;
  const keyColumns   = (healthResult?.key_columns ?? []) as string[];
  const colHealth    = (healthResult?.column_health ?? []) as Array<{ column: string; score: number; issues: string[] }>;
  const worstCols    = colHealth.filter((c) => c.score < 70).slice(0, 3);

  const meta = getMeta(typeof value === "number" ? value : 0);

  const radius       = 34;
  const circumference = 2 * Math.PI * radius;
  const offset       = circumference - ((value as number) / 100) * circumference;

  const subScores = breakdown
    ? [
        { label: "Completeness", value: breakdown.completeness, max: 30 },
        { label: "Uniqueness",   value: breakdown.uniqueness,   max: 20 },
        { label: "Consistency",  value: breakdown.consistency,  max: 20 },
        { label: "Validity",     value: breakdown.validity,     max: 15 },
        { label: "Structure",    value: breakdown.structure,    max: 15 },
      ]
    : [];

  return (
    <div className="space-y-5">
      {/* ── Score ring + headline ──────────────────────────────────────────── */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center">
        <div className="relative flex-shrink-0">
          <svg width="88" height="88" viewBox="0 0 88 88" className="-rotate-90">
            <circle cx="44" cy="44" r={radius} fill="none" stroke="rgba(255,255,255,0.06)" strokeWidth="6" />
            <circle
              cx="44" cy="44" r={radius}
              fill="none"
              stroke={meta.ring}
              strokeWidth="6"
              strokeDasharray={circumference}
              strokeDashoffset={offset}
              strokeLinecap="round"
              style={{ transition: "stroke-dashoffset 0.6s ease" }}
            />
          </svg>
          <div className="absolute inset-0 flex flex-col items-center justify-center">
            <span className="text-lg font-bold text-white">{Math.round(value as number)}</span>
            <span className="text-[10px] text-white/40">/100</span>
          </div>
        </div>

        <div className="space-y-1.5">
          <div className="flex flex-wrap items-center gap-2">
            <p className="text-base font-semibold text-white">Dataset health score</p>
            <span className="rounded-full border border-white/10 bg-white/5 px-2 py-0.5 text-xs text-white/60">
              Grade {grade}
            </span>
            {datasetType && (
              <span className="rounded-full border border-white/[0.08] bg-white/[0.04] px-2 py-0.5 text-[10px] text-white/35">
                {DATASET_TYPE_LABEL[datasetType] ?? datasetType}
              </span>
            )}
          </div>
          <p className={`text-sm font-medium ${meta.text}`}>{meta.label}</p>
          <p className="text-xs text-white/40">
            Completeness · Uniqueness · Consistency · Validity · Structure
          </p>
        </div>
      </div>

      {/* ── Dimension sub-scores ──────────────────────────────────────────── */}
      {subScores.length > 0 && (
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-5">
          {subScores.map((s) => (
            <div key={s.label} className="rounded-xl border border-white/[0.07] bg-white/[0.03] p-3">
              <p className="text-[11px] text-white/40">{s.label}</p>
              <p className="mt-1 text-sm font-semibold text-white">
                {typeof s.value === "number" ? s.value.toFixed(1) : s.value}
                <span className="text-xs font-normal text-white/30">/{s.max}</span>
              </p>
              <div className="mt-2 h-1 overflow-hidden rounded-full bg-white/10">
                <div
                  className="h-full rounded-full bg-indigo-500"
                  style={{ width: `${Math.min(100, ((s.value as number) / s.max) * 100)}%` }}
                />
              </div>
            </div>
          ))}
        </div>
      )}

      {/* ── Missingness + duplicates quick-stats (canonical only) ─────────── */}
      {(missingness || duplicates) && (
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
          {missingness && (
            <>
              <div className="rounded-lg border border-white/[0.06] bg-white/[0.02] px-3 py-2">
                <p className="text-[10px] text-white/35">Missing cells</p>
                <p className={`mt-0.5 text-sm font-semibold ${missingness.missing_cell_pct > 10 ? "text-amber-400" : "text-white"}`}>
                  {missingness.missing_cell_pct?.toFixed(1)}%
                </p>
              </div>
              <div className="rounded-lg border border-white/[0.06] bg-white/[0.02] px-3 py-2">
                <p className="text-[10px] text-white/35">Rows w/ missing</p>
                <p className={`mt-0.5 text-sm font-semibold ${missingness.rows_with_any_missing_pct > 10 ? "text-amber-400" : "text-white"}`}>
                  {missingness.rows_with_any_missing?.toLocaleString()}
                </p>
              </div>
            </>
          )}
          {duplicates && (
            <>
              <div className="rounded-lg border border-white/[0.06] bg-white/[0.02] px-3 py-2">
                <p className="text-[10px] text-white/35">Duplicate rows</p>
                <p className={`mt-0.5 text-sm font-semibold ${duplicates.duplicate_row_count > 0 ? "text-amber-400" : "text-white"}`}>
                  {duplicates.duplicate_row_count?.toLocaleString()}
                </p>
              </div>
              <div className="rounded-lg border border-white/[0.06] bg-white/[0.02] px-3 py-2">
                <p className="text-[10px] text-white/35">Duplicate %</p>
                <p className={`mt-0.5 text-sm font-semibold ${duplicates.duplicate_row_pct > 5 ? "text-amber-400" : "text-white"}`}>
                  {duplicates.duplicate_row_pct?.toFixed(1)}%
                </p>
              </div>
            </>
          )}
        </div>
      )}

      {/* ── Warnings (canonical health_warnings, fallback to legacy deductions) */}
      {(warnings.length > 0 || legacyDeductions.length > 0) && (
        <div className="space-y-1.5">
          <p className="text-[10px] font-medium uppercase tracking-wider text-white/30">Score deductions</p>
          {warnings.length > 0
            ? warnings.map((w, i) => {
                const style = SEVERITY_STYLE[w.severity] ?? SEVERITY_STYLE.low;
                const dimLabel = DIMENSION_LABEL[w.dimension] ?? w.dimension;
                return (
                  <div key={i} className="flex items-start gap-2 rounded-lg border border-white/[0.05] bg-white/[0.02] px-3 py-2">
                    <span className={`mt-1 h-1.5 w-1.5 flex-shrink-0 rounded-full ${style.dot}`} />
                    <div className="min-w-0 flex-1">
                      <p className="text-xs text-white/55 leading-relaxed">{w.message}</p>
                    </div>
                    <span className={`flex-shrink-0 rounded-full border px-1.5 py-0.5 text-[10px] font-medium ${style.badge}`}>
                      {dimLabel}
                    </span>
                  </div>
                );
              })
            : legacyDeductions.map((d, i) => (
                <div key={i} className="rounded-lg border border-white/[0.05] bg-white/[0.02] px-3 py-2">
                  <p className="text-xs text-white/50">· {d}</p>
                </div>
              ))
          }
        </div>
      )}

      {/* ── Worst columns (canonical column_health) ───────────────────────── */}
      {worstCols.length > 0 && (
        <div className="space-y-1.5">
          <p className="text-[10px] font-medium uppercase tracking-wider text-white/30">Columns needing attention</p>
          {worstCols.map((col) => (
            <div key={col.column} className="flex items-center gap-3 rounded-lg border border-white/[0.05] bg-white/[0.02] px-3 py-2">
              <div className="min-w-0 flex-1">
                <p className="text-xs font-mono font-medium text-white/70">{col.column}</p>
                {col.issues.length > 0 && (
                  <p className="mt-0.5 text-[10px] text-white/35 truncate">{col.issues[0]}</p>
                )}
              </div>
              <span className={`flex-shrink-0 text-xs font-semibold ${col.score < 50 ? "text-red-400" : "text-amber-400"}`}>
                {col.score.toFixed(0)}/100
              </span>
            </div>
          ))}
        </div>
      )}

      {/* ── Key columns (canonical semantic_column_types / key_columns) ────── */}
      {keyColumns.length > 0 && (
        <div className="flex flex-wrap items-center gap-1.5">
          <span className="text-[10px] text-white/30">Key columns:</span>
          {keyColumns.map((col) => (
            <span key={col} className="rounded-full border border-indigo-500/20 bg-indigo-500/8 px-2 py-0.5 font-mono text-[10px] text-indigo-300/70">
              {col}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}
