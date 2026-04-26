// eslint-disable-next-line @typescript-eslint/no-explicit-any
type HealthResult = Record<string, any>;

type LegacyScore = {
  total?: number; score?: number;
  grade?: string; label?: string;
  breakdown?: { completeness: number; uniqueness: number; consistency: number; validity: number; structure: number };
  deductions?: string[];
};

type Props = {
  healthResult?: HealthResult | null;
  score?: LegacyScore | null;
};

// ── Constants ────────────────────────────────────────────────────────────────

const DIMENSION_MAX: Record<string, number> = {
  completeness: 30, uniqueness: 20, consistency: 20, validity: 15, structure: 15,
};
const DIMENSION_LABEL: Record<string, string> = {
  completeness: "Completeness", uniqueness: "Uniqueness",
  consistency: "Consistency",   validity: "Validity",  structure: "Structure",
};
const DATASET_TYPE_LABEL: Record<string, string> = {
  timeseries: "Time Series", transactional: "Transactional",
  survey: "Survey",           general: "General",
};

// ── Score metadata helpers ────────────────────────────────────────────────────

function scoreTheme(v: number) {
  if (v >= 85) return { ring: "#4ade80", banner: "border-emerald-500/20 bg-emerald-500/[0.04]", text: "text-emerald-300", badge: "bg-emerald-500/15 text-emerald-400 border-emerald-500/25" };
  if (v >= 70) return { ring: "#60a5fa", banner: "border-blue-500/20 bg-blue-500/[0.04]",       text: "text-blue-300",   badge: "bg-blue-500/15 text-blue-400 border-blue-500/25" };
  if (v >= 55) return { ring: "#fbbf24", banner: "border-amber-500/20 bg-amber-500/[0.04]",     text: "text-amber-300",  badge: "bg-amber-500/15 text-amber-400 border-amber-500/25" };
  if (v >= 40) return { ring: "#f97316", banner: "border-orange-500/20 bg-orange-500/[0.04]",   text: "text-orange-300", badge: "bg-orange-500/15 text-orange-400 border-orange-500/25" };
  return               { ring: "#f87171", banner: "border-red-500/20 bg-red-500/[0.04]",         text: "text-red-300",    badge: "bg-red-500/15 text-red-400 border-red-500/25" };
}

function verdictLabel(v: number) {
  if (v >= 85) return "Strong — ready for analysis";
  if (v >= 70) return "Good — minor issues to review";
  if (v >= 55) return "Fair — review before sharing with a client";
  if (v >= 40) return "Poor — significant issues present";
  return               "Critical — needs cleanup before use";
}

// ── Client risk bullet derivation ────────────────────────────────────────────

type RiskItem = { text: string; risk: boolean; detail?: string };

function deriveClientRisk(
  missingness: Record<string, any> | undefined,
  duplicates: Record<string, any> | undefined,
  highWarnings: number,
): RiskItem[] {
  const items: RiskItem[] = [];

  // Missing values
  const missingPct: number = missingness?.missing_cell_pct ?? 0;
  const missingCols: Array<{ column: string; missing_pct: number }> =
    missingness?.columns_with_missing ?? [];
  const badCols = missingCols.filter((c) => c.missing_pct > 10).slice(0, 3);

  if (missingPct < 1) {
    items.push({ text: "Missing data is under 1% — minimal impact on analysis", risk: false });
  } else if (missingPct < 5) {
    items.push({
      text: `${missingPct.toFixed(1)}% missing data — unlikely to affect most analyses`,
      risk: false,
    });
  } else {
    const cols = badCols.map((c) => `${c.column} (${c.missing_pct.toFixed(0)}%)`).join(", ");
    items.push({
      text: `${missingPct.toFixed(1)}% missing data — a client may notice gaps`,
      risk: true,
      detail: badCols.length > 0 ? `Worst affected: ${cols}` : undefined,
    });
  }

  // Duplicates
  const dupCount: number = duplicates?.duplicate_row_count ?? 0;
  const dupPct: number   = duplicates?.duplicate_row_pct ?? 0;
  if (dupCount === 0) {
    items.push({ text: "No duplicate rows detected", risk: false });
  } else {
    items.push({
      text: `${dupCount.toLocaleString()} duplicate rows (${dupPct.toFixed(1)}%) — may inflate totals or skew averages`,
      risk: true,
    });
  }

  // Structural / critical warnings
  if (highWarnings === 0) {
    items.push({ text: "No critical structural issues detected", risk: false });
  } else {
    items.push({
      text: `${highWarnings} critical ${highWarnings === 1 ? "issue" : "issues"} detected — see deductions below`,
      risk: true,
    });
  }

  return items;
}

// ── Positive signals derivation ───────────────────────────────────────────────

function derivePositives(
  breakdown: Record<string, number> | undefined,
  duplicates: Record<string, any> | undefined,
  missingness: Record<string, any> | undefined,
  highWarnings: number,
): string[] {
  const out: string[] = [];
  if (breakdown) {
    if ((breakdown.completeness ?? 0) / 30 >= 0.9)  out.push("Completeness is strong — very few missing values");
    if ((breakdown.uniqueness ?? 0)   / 20 >= 0.9)  out.push("Uniqueness is strong — minimal duplicates");
    if ((breakdown.consistency ?? 0)  / 20 >= 0.9)  out.push("Data formats are consistent");
    if ((breakdown.validity ?? 0)     / 15 >= 0.9)  out.push("Value distributions look normal");
    if ((breakdown.structure ?? 0)    / 15 >= 0.9)  out.push("Column structure is clean");
  }
  if (!breakdown && duplicates?.duplicate_row_count === 0) out.push("No duplicate rows");
  if (!breakdown && (missingness?.missing_cell_pct ?? 100) < 1) out.push("Missing data is under 1%");
  if (highWarnings === 0 && out.length === 0) out.push("No critical quality issues detected");
  return out;
}

// ── Main component ────────────────────────────────────────────────────────────

export function HealthScore({ score, healthResult }: Props) {
  // Canonical-first reads
  const hs          = healthResult?.health_score;
  const value       = Math.round(hs?.total_score ?? score?.total ?? score?.score ?? 0);
  const grade       = hs?.grade      ?? score?.grade ?? "–";
  const breakdown   = hs?.breakdown  ?? score?.breakdown;
  const datasetType = hs?.dataset_type;
  const rowCount    = healthResult?.row_count    as number | undefined;
  const colCount    = healthResult?.column_count as number | undefined;

  const warnings     = (healthResult?.health_warnings ?? []) as Array<{ dimension: string; message: string; severity: string }>;
  const legacyDeductions = score?.deductions ?? [];
  const missingness  = healthResult?.missingness_stats  as Record<string, any> | undefined;
  const duplicates   = healthResult?.duplicate_stats    as Record<string, any> | undefined;
  const keyColumns   = (healthResult?.key_columns ?? []) as string[];
  const colHealth    = (healthResult?.column_health ?? []) as Array<{ column: string; score: number; issues: string[] }>;

  // Categorise warnings
  const highWarnings   = warnings.filter((w) => w.severity === "high");
  const medWarnings    = warnings.filter((w) => w.severity === "medium");
  const lowWarnings    = warnings.filter((w) => w.severity === "low");
  const hasWarnings    = warnings.length > 0 || legacyDeductions.length > 0;

  // Worst columns — up to 5, score < 70
  const worstCols = colHealth.filter((c) => c.score < 70).slice(0, 5);

  // Derived sections
  const riskItems  = deriveClientRisk(missingness, duplicates, highWarnings.length);
  const positives  = derivePositives(breakdown, duplicates, missingness, highWarnings.length);

  const theme       = scoreTheme(value);
  const radius      = 34;
  const circumference = 2 * Math.PI * radius;
  const offset      = circumference - (value / 100) * circumference;

  const subScores = breakdown
    ? (["completeness", "uniqueness", "consistency", "validity", "structure"] as const)
        .filter((k) => breakdown[k] != null)
        .map((k) => ({ key: k, label: DIMENSION_LABEL[k], value: breakdown[k] as number, max: DIMENSION_MAX[k] }))
    : [];

  return (
    <div className="space-y-5">

      {/* ── Verdict banner ────────────────────────────────────────────────── */}
      <div className={`flex items-center gap-4 rounded-xl border px-4 py-3.5 ${theme.banner}`}>
        {/* Score ring */}
        <div className="relative flex-shrink-0">
          <svg width="72" height="72" viewBox="0 0 88 88" className="-rotate-90">
            <circle cx="44" cy="44" r={radius} fill="none" stroke="rgba(255,255,255,0.06)" strokeWidth="6" />
            <circle
              cx="44" cy="44" r={radius}
              fill="none" stroke={theme.ring} strokeWidth="6"
              strokeDasharray={circumference} strokeDashoffset={offset}
              strokeLinecap="round"
              style={{ transition: "stroke-dashoffset 0.6s ease" }}
            />
          </svg>
          <div className="absolute inset-0 flex flex-col items-center justify-center">
            <span className="text-base font-bold text-white">{value}</span>
            <span className="text-[9px] text-white/35">/100</span>
          </div>
        </div>

        {/* Text */}
        <div className="flex-1 min-w-0">
          <div className="flex flex-wrap items-center gap-2 mb-0.5">
            <p className="text-sm font-semibold text-white">Data quality report</p>
            <span className={`rounded-full border px-2 py-0.5 text-xs font-bold ${theme.badge}`}>
              Grade {grade}
            </span>
            {datasetType && (
              <span className="rounded-full border border-white/[0.08] bg-white/[0.03] px-2 py-0.5 text-[10px] text-white/40">
                {DATASET_TYPE_LABEL[datasetType] ?? datasetType}
              </span>
            )}
          </div>
          <p className={`text-sm font-medium ${theme.text}`}>{verdictLabel(value)}</p>
          {(rowCount != null || colCount != null) && (
            <p className="mt-0.5 text-[11px] text-white/30">
              {rowCount != null && `${rowCount.toLocaleString()} rows`}
              {rowCount != null && colCount != null && " · "}
              {colCount != null && `${colCount} columns`}
            </p>
          )}
        </div>
      </div>

      {/* ── Dimension breakdown ───────────────────────────────────────────── */}
      {subScores.length > 0 && (
        <div>
          <p className="mb-2 text-[10px] font-medium uppercase tracking-wider text-white/25">
            Score breakdown
          </p>
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-5">
            {subScores.map((s) => {
              const pct = Math.min(100, (s.value / s.max) * 100);
              const isWeak = pct < 60;
              return (
                <div key={s.key} className={`rounded-xl border p-3 ${isWeak ? "border-amber-500/15 bg-amber-500/5" : "border-white/[0.07] bg-white/[0.03]"}`}>
                  <p className="text-[10px] text-white/40">{s.label}</p>
                  <p className="mt-1 text-sm font-semibold text-white">
                    {typeof s.value === "number" ? s.value.toFixed(1) : s.value}
                    <span className="text-[10px] font-normal text-white/25">/{s.max}</span>
                  </p>
                  <div className="mt-2 h-1 overflow-hidden rounded-full bg-white/10">
                    <div
                      className={`h-full rounded-full transition-all ${isWeak ? "bg-amber-500" : "bg-indigo-500"}`}
                      style={{ width: `${pct}%` }}
                    />
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* ── Client readiness ─────────────────────────────────────────────── */}
      <div>
        <p className="mb-2 text-[10px] font-medium uppercase tracking-wider text-white/25">
          Client readiness
        </p>
        <div className="space-y-1.5">
          {riskItems.map((item, i) => (
            <div
              key={i}
              className={`rounded-lg border px-3 py-2 ${
                item.risk
                  ? "border-amber-500/20 bg-amber-500/[0.06]"
                  : "border-emerald-500/15 bg-emerald-500/[0.04]"
              }`}
            >
              <div className="flex items-start gap-2">
                <span className={`mt-0.5 flex-shrink-0 text-xs ${item.risk ? "text-amber-400" : "text-emerald-400"}`}>
                  {item.risk ? "⚠" : "✓"}
                </span>
                <p className={`text-xs leading-relaxed ${item.risk ? "text-amber-200/80" : "text-white/60"}`}>
                  {item.text}
                </p>
              </div>
              {item.detail && (
                <p className="mt-1 pl-4 text-[11px] text-white/35">{item.detail}</p>
              )}
            </div>
          ))}
        </div>
      </div>

      {/* ── What's hurting the score ─────────────────────────────────────── */}
      {hasWarnings && (
        <div>
          <p className="mb-2 text-[10px] font-medium uppercase tracking-wider text-white/25">
            {highWarnings.length > 0 ? "Score deductions — review these" : "Score deductions"}
          </p>
          <div className="space-y-1.5">
            {/* High severity */}
            {highWarnings.map((w, i) => (
              <div key={`h${i}`} className="flex items-start gap-2 rounded-lg border border-red-500/20 bg-red-500/[0.06] px-3 py-2">
                <span className="mt-0.5 h-1.5 w-1.5 flex-shrink-0 rounded-full bg-red-400" />
                <div className="min-w-0 flex-1">
                  <p className="text-xs leading-relaxed text-white/70">{w.message}</p>
                </div>
                <span className="flex-shrink-0 rounded-full border border-red-500/20 bg-red-500/10 px-1.5 py-0.5 text-[10px] font-medium text-red-300">
                  {DIMENSION_LABEL[w.dimension] ?? w.dimension}
                </span>
              </div>
            ))}
            {/* Medium severity */}
            {medWarnings.map((w, i) => (
              <div key={`m${i}`} className="flex items-start gap-2 rounded-lg border border-amber-500/15 bg-amber-500/[0.05] px-3 py-2">
                <span className="mt-0.5 h-1.5 w-1.5 flex-shrink-0 rounded-full bg-amber-400" />
                <div className="min-w-0 flex-1">
                  <p className="text-xs leading-relaxed text-white/60">{w.message}</p>
                </div>
                <span className="flex-shrink-0 rounded-full border border-amber-500/20 bg-amber-500/10 px-1.5 py-0.5 text-[10px] font-medium text-amber-300">
                  {DIMENSION_LABEL[w.dimension] ?? w.dimension}
                </span>
              </div>
            ))}
            {/* Low severity — de-emphasised */}
            {lowWarnings.map((w, i) => (
              <div key={`l${i}`} className="flex items-start gap-2 rounded-lg border border-white/[0.05] bg-white/[0.015] px-3 py-1.5">
                <span className="mt-0.5 h-1.5 w-1.5 flex-shrink-0 rounded-full bg-white/20" />
                <p className="text-[11px] leading-relaxed text-white/35">{w.message}</p>
              </div>
            ))}
            {/* Legacy deductions — no severity data */}
            {warnings.length === 0 && legacyDeductions.map((d: string, i: number) => (
              <div key={`ld${i}`} className="flex items-start gap-2 rounded-lg border border-white/[0.05] bg-white/[0.02] px-3 py-2">
                <span className="mt-0.5 h-1.5 w-1.5 flex-shrink-0 rounded-full bg-white/20" />
                <p className="text-xs text-white/50">{d}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ── What looks healthy ────────────────────────────────────────────── */}
      {positives.length > 0 && (
        <div>
          <p className="mb-2 text-[10px] font-medium uppercase tracking-wider text-white/25">
            What looks healthy
          </p>
          <div className="space-y-1">
            {positives.map((p, i) => (
              <div key={i} className="flex items-center gap-2 rounded-lg border border-emerald-500/10 bg-emerald-500/[0.03] px-3 py-1.5">
                <span className="text-emerald-400/70 text-xs">✓</span>
                <p className="text-xs text-white/55">{p}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ── Most affected columns ─────────────────────────────────────────── */}
      {worstCols.length > 0 && (
        <div>
          <p className="mb-2 text-[10px] font-medium uppercase tracking-wider text-white/25">
            Most affected columns
          </p>
          <div className="space-y-1.5">
            {worstCols.map((col) => {
              const isCritical = col.score < 50;
              return (
                <div
                  key={col.column}
                  className={`rounded-lg border px-3 py-2.5 ${
                    isCritical
                      ? "border-red-500/15 bg-red-500/[0.04]"
                      : "border-amber-500/15 bg-amber-500/[0.04]"
                  }`}
                >
                  <div className="flex items-center justify-between gap-2 mb-1">
                    <span className="text-xs font-mono font-semibold text-white/80">{col.column}</span>
                    <span className={`text-xs font-semibold tabular-nums ${isCritical ? "text-red-400" : "text-amber-400"}`}>
                      {col.score.toFixed(0)}/100
                    </span>
                  </div>
                  {col.issues.length > 0 && (
                    <div className="space-y-0.5">
                      {col.issues.map((issue, j) => (
                        <p key={j} className="text-[11px] text-white/40 leading-relaxed">· {issue}</p>
                      ))}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* ── Key columns (identifiers excluded from stats) ─────────────────── */}
      {keyColumns.length > 0 && (
        <div className="flex flex-wrap items-center gap-1.5">
          <span className="text-[10px] text-white/25">ID columns (excluded from stats):</span>
          {keyColumns.map((col) => (
            <span key={col} className="rounded-full border border-indigo-500/20 bg-indigo-500/[0.08] px-2 py-0.5 font-mono text-[10px] text-indigo-300/60">
              {col}
            </span>
          ))}
        </div>
      )}

    </div>
  );
}
