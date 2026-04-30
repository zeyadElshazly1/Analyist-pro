"use client";

import { useState } from "react";
import { AlertTriangle, ChevronDown, ChevronRight } from "lucide-react";

// ── Canonical types (mirror app/schemas/cleaning.py) ───────────────────────
type SuspiciousIssue = {
  type?: string;
  column?: string;
  detail?: string;
};

type ColumnRename = { original: string; cleaned: string };
type TypeFix = { column: string; to_dtype: string; n_values_converted: number };
type MissingnessNote = {
  column: string;
  missing_count: number;
  missing_pct: number;
  mechanism: string;
  strategy_applied: string;
};
type DuplicateNote = {
  duplicate_rows_found: number;
  duplicate_rows_removed: number;
  duplicate_columns: string[];
};
type SuspiciousColumn = { column: string; issue_type: string; detail: string };
type CleaningSummaryBlock = {
  original_rows?: number;
  original_cols?: number;
  final_rows?: number;
  final_cols?: number;
  rows_removed?: number;
  cols_removed?: number;
  steps_applied?: number;
  steps?: number;
  confidence_score?: number;
  time_saved_estimate?: string;
};
type CanonicalCR = {
  renamed_columns?: ColumnRename[];
  dropped_columns?: string[];
  type_fixes?: TypeFix[];
  missingness_notes?: MissingnessNote[];
  duplicate_notes?: DuplicateNote;
  suspicious_columns?: SuspiciousColumn[];
  cleaning_summary?: CleaningSummaryBlock;
};

type CleaningSummaryView = {
  confidence_score?: number;
  original_rows?: number;
  original_cols?: number;
  final_rows?: number;
  final_cols?: number;
  rows_removed?: number;
  cols_removed?: number;
  steps?: number;
  time_saved_estimate?: string;
  type_fixes_count?: number;
  imputations_count?: number;
  duplicate_cols_removed_count?: number;
  duplicate_rows_removed?: number;
  suspicious_count?: number;
  issues_remaining: SuspiciousIssue[];
};

type Props = {
  cleaningResult?: Record<string, unknown> | null;
  summary?: Record<string, unknown> | null;
};

// ── Presentation helpers (copy is qualitative by score band, not data) ───────

function confidencePalette(score: number) {
  if (score >= 80) {
    return {
      border: "border-emerald-500/30",
      bg: "from-emerald-500/[0.08] to-white/[0.02]",
      bar: "bg-emerald-400",
      text: "text-emerald-300",
      badge: "border-emerald-500/35 bg-emerald-500/15 text-emerald-200",
    };
  }
  if (score >= 60) {
    return {
      border: "border-amber-500/30",
      bg: "from-amber-500/[0.07] to-white/[0.02]",
      bar: "bg-amber-400",
      text: "text-amber-300",
      badge: "border-amber-500/35 bg-amber-500/15 text-amber-200",
    };
  }
  return {
    border: "border-red-500/30",
    bg: "from-red-500/[0.07] to-white/[0.02]",
    bar: "bg-red-400",
    text: "text-red-300",
    badge: "border-red-500/35 bg-red-500/15 text-red-200",
  };
}

function confidenceBandLabel(score: number) {
  if (score >= 80) return "High confidence";
  if (score >= 60) return "Medium confidence";
  return "Low confidence";
}

/** Short explanation tied to score band only — does not invent numeric facts. */
function confidenceNarration(score: number) {
  if (score >= 80) {
    return "The pipeline applied most normalization steps with strong signals. Outputs are a solid starting point for analysis; spot-check the cleaning log if you tighten assumptions.";
  }
  if (score >= 60) {
    return "Most changes applied cleanly, but some columns needed judgment calls. Review flagged items and the full cleaning report before client-facing work.";
  }
  return "Several transformations were ambiguous. Treat this dataset as provisional until you have walked through suspicious columns and the detailed cleaning log.";
}

function ConfidenceMainCard({ score }: { score: number }) {
  const p = confidencePalette(score);
  const label = confidenceBandLabel(score);

  return (
    <div
      className={`flex h-full min-h-[260px] flex-col rounded-2xl border ${p.border} bg-gradient-to-b ${p.bg} p-6 shadow-lg shadow-black/20 sm:p-8`}
    >
      <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-white/45">
        Cleaning confidence
      </p>
      <div className="mt-5 flex flex-wrap items-baseline gap-2">
        <span className={`text-4xl font-bold tabular-nums tracking-tight sm:text-5xl ${p.text}`}>
          {score}
        </span>
        <span className="text-base font-medium text-white/35">/100</span>
      </div>
      <span
        className={`mt-3 inline-flex w-fit rounded-full border px-2.5 py-0.5 text-[11px] font-semibold ${p.badge}`}
      >
        {label}
      </span>
      <p className="mt-5 text-sm leading-relaxed text-white/60">{confidenceNarration(score)}</p>
      <div className="mt-auto pt-8">
        <div className="h-1.5 w-full overflow-hidden rounded-full bg-white/[0.08]">
          <div
            className={`h-full rounded-full ${p.bar} opacity-85 transition-all duration-500`}
            style={{ width: `${Math.min(100, Math.max(0, score))}%` }}
          />
        </div>
      </div>
    </div>
  );
}

function ShapeTile({
  variant,
  rows,
  cols,
}: {
  variant: "original" | "final";
  rows: number;
  cols: number;
}) {
  const title = variant === "original" ? "Original shape" : "Final shape";
  return (
    <div className="flex h-full min-h-[148px] flex-col rounded-2xl border border-white/[0.09] bg-white/[0.04] p-5 shadow-md shadow-black/15">
      <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-white/45">{title}</p>
      <div className="mt-4 grid grid-cols-2 gap-4 min-w-0">
        <div className="min-w-0">
          <p className="text-2xl font-semibold tabular-nums tracking-tight text-white sm:text-3xl whitespace-nowrap overflow-hidden text-ellipsis">
            {rows.toLocaleString()}
          </p>
          <p className="mt-0.5 text-xs font-medium text-white/40">Rows</p>
        </div>
        <div className="min-w-0 border-l border-white/[0.06] pl-4">
          <p className="text-2xl font-semibold tabular-nums tracking-tight text-white sm:text-3xl whitespace-nowrap">
            {cols.toLocaleString()}
          </p>
          <p className="mt-0.5 text-xs font-medium text-white/40">Columns</p>
        </div>
      </div>
    </div>
  );
}

function StepsTile({
  steps,
  timeSaved,
}: {
  steps: number;
  timeSaved?: string;
}) {
  return (
    <div className="flex h-full min-h-[120px] flex-col rounded-2xl border border-white/[0.09] bg-white/[0.04] p-5 shadow-md shadow-black/15">
      <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-white/45">Cleaning steps</p>
      <p className="mt-3 text-3xl font-semibold tabular-nums text-white sm:text-4xl">{steps}</p>
      <p className="mt-1 text-xs text-white/40">Pipeline steps recorded for this run</p>
      {timeSaved ? (
        <p className="mt-auto pt-3 text-sm text-indigo-300/90 leading-snug">
          <span className="text-white/35">Est. time saved · </span>
          {timeSaved}
        </p>
      ) : (
        <div className="mt-auto pt-3" aria-hidden />
      )}
    </div>
  );
}

function SuspiciousTile({ count }: { count: number }) {
  return (
    <div className="flex h-full min-h-[120px] flex-col rounded-2xl border border-amber-500/25 bg-amber-500/[0.06] p-5 shadow-md shadow-black/15">
      <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-amber-200/80">Suspicious columns</p>
      <p className="mt-3 text-3xl font-semibold tabular-nums text-amber-100 sm:text-4xl">{count}</p>
      <p className="mt-1 text-xs text-amber-200/55 leading-relaxed">
        Flagged for manual review — details below and in the Cleaning tab.
      </p>
    </div>
  );
}

function SecondaryMetricTile({
  label,
  value,
  sub,
}: {
  label: string;
  value: string | number;
  sub?: string;
}) {
  return (
    <div className="flex min-h-[108px] flex-col rounded-2xl border border-white/[0.08] bg-white/[0.03] p-4 sm:p-5">
      <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-white/40">{label}</p>
      <p className="mt-2 break-normal text-xl font-semibold tabular-nums text-white sm:text-2xl">{value}</p>
      {sub ? (
        <p className="mt-auto pt-3 text-xs leading-relaxed text-white/38">{sub}</p>
      ) : (
        <div className="mt-auto pt-3" aria-hidden />
      )}
    </div>
  );
}

// ── Adapters ─────────────────────────────────────────────────────────────────

function fromCanonical(cr: CanonicalCR): CleaningSummaryView {
  const cs = cr.cleaning_summary ?? {};
  const dupNotes = cr.duplicate_notes;
  const missing = cr.missingness_notes ?? [];
  const imputed = missing.filter(
    (n) => n.strategy_applied !== "safe_suggestion" && n.strategy_applied !== "dropped",
  );

  return {
    confidence_score: cs.confidence_score,
    original_rows: cs.original_rows,
    original_cols: cs.original_cols,
    final_rows: cs.final_rows,
    final_cols: cs.final_cols,
    rows_removed: cs.rows_removed,
    cols_removed: cs.cols_removed,
    steps: cs.steps_applied ?? cs.steps,
    time_saved_estimate: cs.time_saved_estimate,
    type_fixes_count: (cr.type_fixes ?? []).length,
    imputations_count: imputed.length,
    duplicate_cols_removed_count: dupNotes?.duplicate_columns?.length ?? 0,
    duplicate_rows_removed: dupNotes?.duplicate_rows_removed,
    suspicious_count: (cr.suspicious_columns ?? []).length,
    issues_remaining: (cr.suspicious_columns ?? []).map((sc) => ({
      type: sc.issue_type,
      column: sc.column,
      detail: sc.detail,
    })),
  };
}

function fromLegacy(legacy: Record<string, unknown>): CleaningSummaryView {
  const num = (v: unknown): number | undefined =>
    typeof v === "number" && Number.isFinite(v) ? v : undefined;
  const str = (v: unknown): string | undefined =>
    typeof v === "string" && v.length > 0 ? v : undefined;

  return {
    confidence_score: num(legacy.confidence_score),
    original_rows: num(legacy.original_rows),
    original_cols: num(legacy.original_cols),
    final_rows: num(legacy.final_rows),
    final_cols: num(legacy.final_cols),
    rows_removed: num(legacy.rows_removed),
    cols_removed: num(legacy.cols_removed),
    steps: num(legacy.steps_applied) ?? num(legacy.steps),
    time_saved_estimate: str(legacy.time_saved_estimate),
    issues_remaining: Array.isArray(legacy.suspicious_issues_remaining)
      ? (legacy.suspicious_issues_remaining as SuspiciousIssue[])
      : [],
  };
}

// ── Main component ───────────────────────────────────────────────────────────

export function CleaningSummaryCards({ cleaningResult, summary }: Props) {
  const [showIssues, setShowIssues] = useState(false);

  const view: CleaningSummaryView | null = cleaningResult
    ? fromCanonical(cleaningResult as CanonicalCR)
    : summary
    ? fromLegacy(summary as Record<string, unknown>)
    : null;

  if (!view) {
    return <p className="text-sm text-white/60">No cleaning summary available.</p>;
  }

  const issues = view.issues_remaining;
  const hasOriginal =
    typeof view.original_rows === "number" && typeof view.original_cols === "number";
  const hasFinal = typeof view.final_rows === "number" && typeof view.final_cols === "number";
  const suspiciousCount =
    typeof view.suspicious_count === "number" && view.suspicious_count > 0
      ? view.suspicious_count
      : undefined;

  const secondaryTiles: Array<{ label: string; value: string | number; sub?: string }> = [];

  if (typeof view.rows_removed === "number" && view.rows_removed > 0) {
    secondaryTiles.push({ label: "Rows removed", value: view.rows_removed.toLocaleString() });
  }
  if (typeof view.cols_removed === "number" && view.cols_removed > 0) {
    secondaryTiles.push({ label: "Columns removed", value: view.cols_removed.toLocaleString() });
  }
  if (typeof view.type_fixes_count === "number" && view.type_fixes_count > 0) {
    secondaryTiles.push({
      label: "Type conversions",
      value: view.type_fixes_count,
      sub: "currency, %, numeric, date, boolean",
    });
  }
  if (typeof view.imputations_count === "number" && view.imputations_count > 0) {
    secondaryTiles.push({
      label: "Missing values filled",
      value: view.imputations_count,
      sub: "Columns imputed per pipeline notes",
    });
  }
  if (typeof view.duplicate_rows_removed === "number" && view.duplicate_rows_removed > 0) {
    secondaryTiles.push({
      label: "Duplicate rows removed",
      value: view.duplicate_rows_removed.toLocaleString(),
    });
  }
  if (
    typeof view.duplicate_cols_removed_count === "number" &&
    view.duplicate_cols_removed_count > 0
  ) {
    secondaryTiles.push({
      label: "Duplicate columns removed",
      value: view.duplicate_cols_removed_count,
    });
  }

  const hasSteps = typeof view.steps === "number";
  const hasConfidence = view.confidence_score !== undefined;
  const stepsAndSuspicious = hasSteps && suspiciousCount !== undefined;

  const metricsHasContent =
    hasOriginal ||
    hasFinal ||
    hasSteps ||
    suspiciousCount !== undefined ||
    secondaryTiles.length > 0;

  const metricsColumn = (
    <div className="min-w-0 space-y-4">
      {(hasOriginal || hasFinal) && (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          {hasOriginal && (
            <ShapeTile variant="original" rows={view.original_rows!} cols={view.original_cols!} />
          )}
          {hasFinal && <ShapeTile variant="final" rows={view.final_rows!} cols={view.final_cols!} />}
        </div>
      )}

      {(hasSteps || suspiciousCount !== undefined) && (
        <div className={`grid gap-4 ${stepsAndSuspicious ? "sm:grid-cols-2" : "grid-cols-1"}`}>
          {hasSteps && (
            <div className={stepsAndSuspicious ? "" : "max-w-xl"}>
              <StepsTile steps={view.steps!} timeSaved={view.time_saved_estimate} />
            </div>
          )}
          {suspiciousCount !== undefined && <SuspiciousTile count={suspiciousCount} />}
        </div>
      )}

      {secondaryTiles.length > 0 && (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-3">
          {secondaryTiles.map((c) => (
            <SecondaryMetricTile key={c.label} label={c.label} value={c.value} sub={c.sub} />
          ))}
        </div>
      )}
    </div>
  );

  const hasDashboardBody = metricsHasContent;

  const hasAnyContent = hasConfidence || hasDashboardBody || issues.length > 0;

  if (!hasAnyContent) {
    return (
      <p className="text-sm text-white/60">No cleaning summary available for this run.</p>
    );
  }

  return (
    <div className="space-y-5">
      <header className="space-y-1">
        <h2 className="text-xs font-semibold uppercase tracking-[0.16em] text-white/50">
          Cleaning summary
        </h2>
        <p className="max-w-prose text-[13px] leading-relaxed text-white/38">
          Shape, step count, and pipeline confidence from this run. Metrics appear only when the backend reported them.
        </p>
      </header>

      {hasConfidence ? (
        <div className="grid gap-5 lg:grid-cols-12 lg:items-stretch lg:gap-6">
          <div className={`min-w-0 ${metricsHasContent ? "lg:col-span-5" : "lg:col-span-12"}`}>
            <ConfidenceMainCard score={view.confidence_score!} />
          </div>
          {metricsHasContent && (
            <div className="min-w-0 lg:col-span-7">{metricsColumn}</div>
          )}
        </div>
      ) : (
        metricsColumn
      )}

      {issues.length > 0 && (
        <div className="overflow-hidden rounded-2xl border border-amber-500/20 bg-amber-500/[0.05] shadow-md shadow-black/10">
          <button
            type="button"
            className="flex w-full items-center gap-3 px-4 py-3.5 text-left transition hover:bg-amber-500/[0.04] sm:px-5"
            onClick={() => setShowIssues((v) => !v)}
          >
            <AlertTriangle className="h-4 w-4 flex-shrink-0 text-amber-400" />
            <span className="min-w-0 flex-1 text-sm font-medium leading-snug text-amber-100/90">
              {issues.length} suspicious issue{issues.length > 1 ? "s" : ""} remaining (not auto-fixed)
            </span>
            {showIssues ? (
              <ChevronDown className="h-4 w-4 flex-shrink-0 text-amber-400/70" />
            ) : (
              <ChevronRight className="h-4 w-4 flex-shrink-0 text-amber-400/70" />
            )}
          </button>

          {showIssues && (
            <div className="space-y-3 border-t border-amber-500/15 px-4 py-4 sm:px-5">
              {issues.map((issue, i) => (
                <div key={i} className="rounded-xl border border-white/[0.06] bg-black/15 px-3 py-2.5">
                  {issue.column && (
                    <p className="font-mono text-xs font-semibold text-amber-200/90">{issue.column}</p>
                  )}
                  {issue.detail && (
                    <p className="mt-1 text-xs leading-relaxed text-white/55">{issue.detail}</p>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
