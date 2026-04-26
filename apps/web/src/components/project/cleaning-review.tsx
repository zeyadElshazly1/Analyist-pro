"use client";

import { CheckCircle2, AlertTriangle, ArrowRight, Info } from "lucide-react";

// ── Canonical CleaningResult types (mirrors app/schemas/cleaning.py) ───────
type ColumnRename     = { original: string; cleaned: string };
type TypeFix         = { column: string; to_dtype: string; n_values_converted: number };
type MissingnessNote = {
  column: string; missing_count: number; missing_pct: number;
  mechanism: string; strategy_applied: string;
};
type DuplicateNote   = {
  duplicate_rows_found: number; duplicate_rows_removed: number;
  duplicate_columns: string[];
};
type SuspiciousColumn = { column: string; issue_type: string; detail: string };
type CleaningSummary = {
  original_rows?: number; original_cols?: number;
  final_rows?: number;    final_cols?: number;
  rows_removed?: number;  cols_removed?: number;
  steps_applied?: number;
  confidence_score?: number; confidence_grade?: string;
  time_saved_estimate?: string; mode?: string;
};
type CanonicalCR = {
  renamed_columns?:    ColumnRename[];
  dropped_columns?:    string[];
  type_fixes?:         TypeFix[];
  missingness_notes?:  MissingnessNote[];
  duplicate_notes?:    DuplicateNote;
  suspicious_columns?: SuspiciousColumn[];
  assumptions_made?:   string[];
  cleaning_summary?:   CleaningSummary;
};

// Legacy items — kept so run-analysis.tsx callers don't need updating
type LegacyItem = { step: string; detail: string; impact?: string };

type Props = {
  cleaningResult?: Record<string, unknown> | null;
  items?: LegacyItem[];
  summary?: { steps?: number; rows_removed?: number; columns_fixed?: number };
};

// ── Display helpers ──────────────────────────────────────────────────────────
const DTYPE_LABELS: Record<string, string> = {
  numeric:    "number",
  datetime:   "date / time",
  boolean:    "true / false",
  currency:   "currency",
  percentage: "percentage",
};

const STRATEGY_LABELS: Record<string, string> = {
  mean:          "filled with column mean",
  median:        "filled with column median",
  mode:          "filled with most common value",
  knn:           "filled using KNN",
  mice:          "filled using MICE",
  flag_and_fill: "flagged (MNAR) and filled",
  dropped:       "column dropped",
};

const MECHANISM_LABELS: Record<string, string> = {
  MCAR:    "missing at random",
  MAR:     "correlated with other columns",
  MNAR:    "value-dependent missingness",
  unknown: "unknown mechanism",
};

const ISSUE_LABELS: Record<string, string> = {
  suspicious_zeros:   "Suspicious zeros",
  outliers_preserved: "Outliers preserved",
  high_missing:       "High missing rate",
};

function issueLabel(type: string) {
  return ISSUE_LABELS[type] ?? "Flagged for review";
}

function gradeColor(score: number | undefined) {
  if (score == null) return { banner: "border-white/[0.07] bg-white/[0.02]", text: "text-white/60", badge: "bg-white/5 text-white/50 border-white/10" };
  if (score >= 80) return { banner: "border-emerald-500/20 bg-emerald-500/5", text: "text-emerald-300", badge: "bg-emerald-500/15 text-emerald-400 border-emerald-500/25" };
  if (score >= 60) return { banner: "border-amber-500/20 bg-amber-500/5",   text: "text-amber-300",  badge: "bg-amber-500/15 text-amber-400 border-amber-500/25" };
  return { banner: "border-red-500/20 bg-red-500/5", text: "text-red-300", badge: "bg-red-500/15 text-red-400 border-red-500/25" };
}

// ── Pill component ───────────────────────────────────────────────────────────
function Pill({ label, color = "default" }: { label: string; color?: "green" | "amber" | "red" | "default" }) {
  const cls =
    color === "green"  ? "border-emerald-500/25 bg-emerald-500/10 text-emerald-300" :
    color === "amber"  ? "border-amber-500/25 bg-amber-500/10 text-amber-300" :
    color === "red"    ? "border-red-500/25 bg-red-500/10 text-red-300" :
                         "border-white/[0.08] bg-white/[0.03] text-white/55";
  return (
    <span className={`inline-block rounded-full border px-2 py-px text-[10px] font-medium ${cls}`}>
      {label}
    </span>
  );
}

// ── Auto-applied section sub-group ───────────────────────────────────────────
function AutoGroup({
  label, count, children,
}: {
  label: string; count: number; children: React.ReactNode;
}) {
  return (
    <div>
      <p className="mb-1.5 text-[10px] font-medium uppercase tracking-wider text-white/25">
        {label} <span className="text-white/20">· {count}</span>
      </p>
      <div className="space-y-1">{children}</div>
    </div>
  );
}

function AutoRow({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex items-start gap-2 rounded-lg border border-white/[0.05] bg-white/[0.02] px-3 py-2">
      <span className="mt-0.5 flex-shrink-0 text-emerald-400/50">·</span>
      <div className="flex-1 min-w-0">{children}</div>
    </div>
  );
}

// ── Main component ───────────────────────────────────────────────────────────
export function CleaningReview({ cleaningResult, items: legacyItems }: Props) {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const cr = cleaningResult as CanonicalCR | null | undefined;
  const cs = cr?.cleaning_summary;

  // ── Extract canonical fields ─────────────────────────────────────────────
  const renames       = cr?.renamed_columns    ?? [];
  const dropped       = cr?.dropped_columns    ?? [];
  const typeFixes     = cr?.type_fixes         ?? [];
  const missingNotes  = cr?.missingness_notes  ?? [];
  const dupNotes      = cr?.duplicate_notes;
  const suspicious    = cr?.suspicious_columns ?? [];
  const assumptions   = cr?.assumptions_made   ?? [];

  // Split missingness notes into applied vs. suggestions
  const imputedNotes  = missingNotes.filter(
    (n) => n.strategy_applied !== "safe_suggestion" && n.strategy_applied !== "dropped"
  );
  const suggestions   = missingNotes.filter((n) => n.strategy_applied === "safe_suggestion");

  // Duplicate findings
  const dupRowsRemoved  = dupNotes?.duplicate_rows_removed ?? 0;
  const dupRowsFound    = dupNotes?.duplicate_rows_found   ?? 0;
  const dupColsRemoved  = dupNotes?.duplicate_columns      ?? [];
  const dupFoundNotRemoved = dupRowsFound > 0 && dupRowsRemoved === 0;

  // Section presence flags
  const hasAutoApplied = (
    renames.length > 0 || typeFixes.length > 0 || imputedNotes.length > 0 ||
    dropped.length > 0 || dupRowsRemoved > 0 || dupColsRemoved.length > 0
  );
  const hasFlagged = suspicious.length > 0 || suggestions.length > 0 || dupFoundNotRemoved;
  const hasAssumptions = assumptions.length > 0;

  // ── No canonical data — render legacy fallback ───────────────────────────
  if (!cr && legacyItems && legacyItems.length > 0) {
    return (
      <div className="space-y-2">
        {legacyItems.map((item, i) => (
          <div key={i} className="rounded-lg border border-white/[0.06] bg-white/[0.02] px-4 py-2.5">
            <p className="text-xs font-medium text-white/75">{item.step}</p>
            {item.detail && <p className="mt-0.5 text-[11px] text-white/40">{item.detail}</p>}
          </div>
        ))}
      </div>
    );
  }

  // ── Empty state — nothing was changed and nothing flagged ────────────────
  if (!hasAutoApplied && !hasFlagged) {
    return (
      <div className="rounded-xl border border-emerald-500/20 bg-emerald-500/5 p-4 flex items-center gap-3">
        <CheckCircle2 className="h-4 w-4 text-emerald-400 flex-shrink-0" />
        <div>
          <p className="text-sm font-semibold text-white">No cleaning needed</p>
          <p className="text-xs text-white/40 mt-0.5">
            Dataset was already clean — no changes were applied and nothing was flagged.
          </p>
        </div>
      </div>
    );
  }

  const { banner, text, badge } = gradeColor(cs?.confidence_score);
  const modeLabel = cs?.mode === "safe" ? "Safe mode" : cs?.mode === "aggressive" ? "Full cleaning" : null;

  return (
    <div className="space-y-5">

      {/* ── Confidence banner ──────────────────────────────────────────────── */}
      {cs && (
        <div className={`flex items-center justify-between rounded-xl border px-4 py-3.5 ${banner}`}>
          <div>
            <div className="flex items-center gap-2">
              <CheckCircle2 className={`h-4 w-4 flex-shrink-0 ${text}`} />
              <p className={`text-sm font-semibold ${text}`}>
                Grade {cs.confidence_grade ?? "—"} · {Math.round(cs.confidence_score ?? 0)}/100 data quality score
              </p>
            </div>
            <p className="mt-0.5 pl-6 text-xs text-white/35">
              {[
                modeLabel,
                cs.steps_applied != null ? `${cs.steps_applied} steps applied` : null,
                cs.time_saved_estimate ? `saved ${cs.time_saved_estimate}` : null,
              ].filter(Boolean).join(" · ")}
            </p>
          </div>
          <span className={`flex-shrink-0 rounded-full border px-2.5 py-0.5 text-sm font-bold ${badge}`}>
            {cs.confidence_grade ?? "—"}
          </span>
        </div>
      )}

      {/* ── Applied automatically ─────────────────────────────────────────── */}
      {hasAutoApplied && (
        <div className="rounded-xl border border-white/[0.07] bg-white/[0.015] overflow-hidden">
          <div className="flex items-center gap-2.5 border-b border-white/[0.06] px-4 py-3">
            <CheckCircle2 className="h-4 w-4 text-emerald-400" />
            <div>
              <p className="text-sm font-semibold text-white">Applied automatically</p>
              <p className="text-[11px] text-white/35">
                These changes were made safely — you don&apos;t need to act on them.
              </p>
            </div>
          </div>
          <div className="px-4 py-3 space-y-4">

            {/* Column renames */}
            {renames.length > 0 && (
              <AutoGroup label="Column names normalised" count={renames.length}>
                <div className="grid grid-cols-1 gap-1 sm:grid-cols-2">
                  {renames.map((r, i) => (
                    <div key={i} className="flex items-center gap-1.5 rounded-lg border border-white/[0.05] bg-white/[0.02] px-3 py-1.5">
                      <span className="text-xs font-mono text-white/50 truncate max-w-[100px]">{r.original}</span>
                      <ArrowRight className="h-3 w-3 flex-shrink-0 text-white/20" />
                      <span className="text-xs font-mono text-white/75 truncate max-w-[100px]">{r.cleaned}</span>
                    </div>
                  ))}
                </div>
              </AutoGroup>
            )}

            {/* Type conversions */}
            {typeFixes.length > 0 && (
              <AutoGroup label="Data type conversions" count={typeFixes.length}>
                {typeFixes.map((fix, i) => (
                  <AutoRow key={i}>
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="text-xs font-medium text-white/80">{fix.column}</span>
                      <span className="text-[10px] text-white/30">→</span>
                      <Pill label={DTYPE_LABELS[fix.to_dtype] ?? fix.to_dtype} color="green" />
                      {fix.n_values_converted > 0 && (
                        <span className="text-[11px] text-white/35">
                          {fix.n_values_converted.toLocaleString()} values converted
                        </span>
                      )}
                    </div>
                  </AutoRow>
                ))}
              </AutoGroup>
            )}

            {/* Duplicate cleanup */}
            {(dupRowsRemoved > 0 || dupColsRemoved.length > 0) && (
              <AutoGroup
                label="Duplicate cleanup"
                count={dupRowsRemoved + dupColsRemoved.length}
              >
                {dupRowsRemoved > 0 && (
                  <AutoRow>
                    <p className="text-xs text-white/70">
                      <span className="font-medium">{dupRowsRemoved.toLocaleString()}</span> duplicate{" "}
                      {dupRowsRemoved === 1 ? "row" : "rows"} removed
                      {dupRowsFound > dupRowsRemoved && (
                        <span className="text-white/35"> ({dupRowsFound.toLocaleString()} found)</span>
                      )}
                    </p>
                  </AutoRow>
                )}
                {dupColsRemoved.length > 0 && (
                  <AutoRow>
                    <p className="text-xs text-white/70 mb-1">
                      {dupColsRemoved.length} duplicate {dupColsRemoved.length === 1 ? "column" : "columns"} removed
                    </p>
                    <div className="flex flex-wrap gap-1">
                      {dupColsRemoved.map((col) => (
                        <Pill key={col} label={col} />
                      ))}
                    </div>
                  </AutoRow>
                )}
              </AutoGroup>
            )}

            {/* Missing value imputation */}
            {imputedNotes.length > 0 && (
              <AutoGroup label="Missing values filled" count={imputedNotes.length}>
                {imputedNotes.map((note, i) => (
                  <AutoRow key={i}>
                    <div className="flex items-start justify-between gap-2 flex-wrap">
                      <div>
                        <span className="text-xs font-medium text-white/80">{note.column}</span>
                        <span className="ml-2 text-[11px] text-white/35">
                          {note.missing_count.toLocaleString()} missing ({note.missing_pct.toFixed(1)}%)
                        </span>
                      </div>
                      <div className="flex items-center gap-1.5 flex-wrap">
                        <Pill label={STRATEGY_LABELS[note.strategy_applied] ?? note.strategy_applied} color="green" />
                        <Pill label={MECHANISM_LABELS[note.mechanism] ?? note.mechanism} />
                      </div>
                    </div>
                  </AutoRow>
                ))}
              </AutoGroup>
            )}

            {/* Dropped columns */}
            {dropped.length > 0 && (
              <AutoGroup label="Columns dropped — too many missing values" count={dropped.length}>
                <AutoRow>
                  <div className="flex flex-wrap gap-1">
                    {dropped.map((col) => (
                      <Pill key={col} label={col} color="amber" />
                    ))}
                  </div>
                </AutoRow>
              </AutoGroup>
            )}

          </div>
        </div>
      )}

      {/* ── Needs your attention ─────────────────────────────────────────── */}
      {hasFlagged && (
        <div className="rounded-xl border border-amber-500/20 bg-amber-500/[0.04] overflow-hidden">
          <div className="flex items-center gap-2.5 border-b border-amber-500/15 px-4 py-3">
            <AlertTriangle className="h-4 w-4 text-amber-400" />
            <div>
              <p className="text-sm font-semibold text-amber-200">Needs your attention</p>
              <p className="text-[11px] text-amber-200/50">
                These were not auto-fixed — review before exporting.
              </p>
            </div>
          </div>
          <div className="px-4 py-3 space-y-3">

            {/* Suspicious columns */}
            {suspicious.map((sc, i) => (
              <div key={i} className="rounded-lg border border-amber-500/20 bg-amber-500/5 px-3 py-2.5">
                <div className="flex items-center gap-2 mb-0.5 flex-wrap">
                  <span className="text-xs font-semibold text-white/85">{sc.column}</span>
                  <Pill label={issueLabel(sc.issue_type)} color="amber" />
                </div>
                <p className="text-[11px] leading-relaxed text-white/50">{sc.detail}</p>
              </div>
            ))}

            {/* Safe-mode suggestions — imputation was suggested but not applied */}
            {suggestions.length > 0 && (
              <div className="rounded-lg border border-amber-500/15 bg-amber-500/5 px-3 py-2.5">
                <p className="text-xs font-semibold text-amber-200/80 mb-1.5">
                  Not filled — safe mode left these as-is
                </p>
                <div className="space-y-1.5">
                  {suggestions.map((note, i) => (
                    <div key={i} className="flex items-center gap-2 flex-wrap">
                      <span className="text-xs font-medium text-white/70">{note.column}</span>
                      <span className="text-[11px] text-white/35">
                        {note.missing_count.toLocaleString()} missing ({note.missing_pct.toFixed(1)}%)
                      </span>
                      <Pill label={MECHANISM_LABELS[note.mechanism] ?? note.mechanism} color="amber" />
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Duplicates found but not removed */}
            {dupFoundNotRemoved && (
              <div className="rounded-lg border border-amber-500/15 bg-amber-500/5 px-3 py-2.5">
                <p className="text-xs font-semibold text-amber-200/80">
                  {dupRowsFound.toLocaleString()} duplicate rows found — not removed
                </p>
                <p className="mt-0.5 text-[11px] text-white/45">
                  Safe mode preserved them. Review and decide whether to exclude them from your analysis.
                </p>
              </div>
            )}

          </div>
        </div>
      )}

      {/* ── Assumptions (only if the pipeline emits them) ─────────────────── */}
      {hasAssumptions && (
        <div className="rounded-xl border border-indigo-500/15 bg-indigo-500/[0.04] px-4 py-3">
          <div className="flex items-center gap-2 mb-2">
            <Info className="h-3.5 w-3.5 text-indigo-400/70" />
            <p className="text-[10px] font-semibold uppercase tracking-wider text-indigo-400/60">
              Inferences made automatically
            </p>
          </div>
          <div className="space-y-1">
            {assumptions.map((a, i) => (
              <p key={i} className="text-[11px] text-white/50 leading-relaxed">· {a}</p>
            ))}
          </div>
        </div>
      )}

      {/* ── Footer nudge ─────────────────────────────────────────────────── */}
      <p className="text-[11px] text-white/25">
        {hasFlagged
          ? "Review the flagged items above before drawing conclusions — they may affect your analysis."
          : "All changes were safe and automatic. Continue to Health to see the quality score."}
      </p>

    </div>
  );
}
