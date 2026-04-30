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

function confidencePalette(score: number) {
  if (score >= 80) {
    return {
      border: "border-emerald-500/25",
      bar: "bg-emerald-400",
      text: "text-emerald-300",
      badge: "border-emerald-500/30 bg-emerald-500/12 text-emerald-200",
    };
  }
  if (score >= 60) {
    return {
      border: "border-amber-500/25",
      bar: "bg-amber-400",
      text: "text-amber-300",
      badge: "border-amber-500/30 bg-amber-500/12 text-amber-200",
    };
  }
  return {
    border: "border-red-500/25",
    bar: "bg-red-400",
    text: "text-red-300",
    badge: "border-red-500/30 bg-red-500/12 text-red-200",
  };
}

function confidenceBandLabel(score: number) {
  if (score >= 80) return "High confidence";
  if (score >= 60) return "Medium confidence";
  return "Low confidence";
}

/** One short sentence only — no essay copy inside KPI surfaces. */
function confidenceOneLiner(score: number) {
  if (score >= 80) return "Strong pipeline fit — spot-check the log if you need strict guarantees.";
  if (score >= 60) return "Mostly clean — review flagged items before client-ready exports.";
  return "Ambiguous in places — confirm suspicious columns in the full cleaning report.";
}

function CompactConfidenceRow({ score }: { score: number }) {
  const p = confidencePalette(score);
  const label = confidenceBandLabel(score);
  const hint = confidenceOneLiner(score);

  return (
    <div
      className={`col-span-full rounded-xl border ${p.border} bg-white/[0.03] px-4 py-3 sm:px-5`}
    >
      <div className="flex flex-col gap-2.5 sm:flex-row sm:items-center sm:justify-between sm:gap-4">
        <div className="flex min-w-0 flex-wrap items-center gap-x-3 gap-y-1.5 sm:gap-x-5">
          <span className="text-[10px] font-semibold uppercase tracking-[0.12em] text-white/45">
            Cleaning confidence
          </span>
          <div className="flex items-baseline gap-1 tabular-nums">
            <span className={`text-2xl font-bold leading-none sm:text-3xl ${p.text}`}>{score}</span>
            <span className="text-sm font-medium text-white/35">/100</span>
          </div>
          <span className={`shrink-0 rounded-full border px-2 py-0.5 text-[10px] font-semibold ${p.badge}`}>
            {label}
          </span>
        </div>
        <p className="max-w-full text-[11px] leading-snug text-white/42 sm:max-w-[min(100%,20rem)] sm:text-right">
          {hint}
        </p>
      </div>
      <div className="mt-2.5 h-1 w-full overflow-hidden rounded-full bg-white/[0.08]">
        <div
          className={`h-full rounded-full ${p.bar} opacity-90 transition-all duration-500`}
          style={{ width: `${Math.min(100, Math.max(0, score))}%` }}
        />
      </div>
    </div>
  );
}

function ShapeKpiCard({
  title,
  rows,
  cols,
  className = "",
}: {
  title: string;
  rows: number;
  cols: number;
  className?: string;
}) {
  return (
    <div
      className={`flex min-h-[92px] flex-col justify-center rounded-xl border border-white/[0.08] bg-white/[0.03] px-4 py-3 min-w-0 ${className}`}
    >
      <p className="text-[10px] font-semibold uppercase tracking-[0.12em] text-white/40">{title}</p>
      <p className="mt-1.5 text-sm font-semibold tabular-nums text-white leading-snug sm:text-base">
        <span className="whitespace-nowrap">{rows.toLocaleString()} rows</span>
        <span className="text-white/35"> · </span>
        <span className="whitespace-nowrap">{cols.toLocaleString()} columns</span>
      </p>
    </div>
  );
}

function StepsKpiCard({
  steps,
  timeSaved,
  className = "",
}: {
  steps: number;
  timeSaved?: string;
  className?: string;
}) {
  return (
    <div
      className={`flex min-h-[92px] flex-col justify-center rounded-xl border border-white/[0.08] bg-white/[0.03] px-4 py-3 min-w-0 ${className}`}
    >
      <p className="text-[10px] font-semibold uppercase tracking-[0.12em] text-white/40">Cleaning steps</p>
      <p className="mt-1.5 text-xl font-semibold tabular-nums text-white sm:text-2xl leading-none">
        {steps}
      </p>
      {timeSaved ? (
        <p className="mt-1.5 min-w-0 truncate text-xs text-indigo-300/85" title={timeSaved}>
          {timeSaved}
          <span className="text-white/35"> · est.</span>
        </p>
      ) : null}
    </div>
  );
}

function MetricKpiCard({
  label,
  value,
  sub,
  variant = "default",
  className = "",
}: {
  label: string;
  value: string | number;
  sub?: string;
  variant?: "default" | "amber";
  className?: string;
}) {
  const shell =
    variant === "amber"
      ? "border-amber-500/22 bg-amber-500/[0.05]"
      : "border-white/[0.08] bg-white/[0.03]";
  return (
    <div
      className={`flex min-h-[92px] flex-col justify-center rounded-xl border px-4 py-3 min-w-0 ${shell} ${className}`}
    >
      <p
        className={`text-[10px] font-semibold uppercase tracking-[0.12em] ${
          variant === "amber" ? "text-amber-200/75" : "text-white/40"
        }`}
      >
        {label}
      </p>
      <p
        className={`mt-1.5 truncate text-xl font-semibold tabular-nums sm:text-2xl leading-none ${
          variant === "amber" ? "text-amber-100" : "text-white"
        }`}
      >
        {value}
      </p>
      {sub ? (
        <p className="mt-1 line-clamp-2 text-[11px] leading-snug text-white/38" title={sub}>
          {sub}
        </p>
      ) : null}
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

  const typeFixes =
    typeof view.type_fixes_count === "number" && view.type_fixes_count > 0
      ? view.type_fixes_count
      : undefined;
  const imputations =
    typeof view.imputations_count === "number" && view.imputations_count > 0
      ? view.imputations_count
      : undefined;

  const extraTiles: Array<{ label: string; value: string | number; sub?: string }> = [];

  if (typeof view.rows_removed === "number" && view.rows_removed > 0) {
    extraTiles.push({ label: "Rows removed", value: view.rows_removed.toLocaleString() });
  }
  if (typeof view.cols_removed === "number" && view.cols_removed > 0) {
    extraTiles.push({ label: "Columns removed", value: view.cols_removed.toLocaleString() });
  }
  if (typeof view.duplicate_rows_removed === "number" && view.duplicate_rows_removed > 0) {
    extraTiles.push({
      label: "Duplicate rows removed",
      value: view.duplicate_rows_removed.toLocaleString(),
    });
  }
  if (
    typeof view.duplicate_cols_removed_count === "number" &&
    view.duplicate_cols_removed_count > 0
  ) {
    extraTiles.push({
      label: "Duplicate columns removed",
      value: view.duplicate_cols_removed_count,
    });
  }

  const hasSteps = typeof view.steps === "number";
  const hasConfidence = view.confidence_score !== undefined;

  const hasDashboardBody =
    hasOriginal ||
    hasFinal ||
    hasSteps ||
    typeFixes !== undefined ||
    imputations !== undefined ||
    suspiciousCount !== undefined ||
    extraTiles.length > 0;

  const hasAnyContent = hasConfidence || hasDashboardBody || issues.length > 0;

  if (!hasAnyContent) {
    return (
      <p className="text-sm text-white/60">No cleaning summary available for this run.</p>
    );
  }

  const showStepsTypeRow = hasSteps || typeFixes !== undefined;
  const showImputeSuspiciousRow = imputations !== undefined || suspiciousCount !== undefined;

  return (
    <div className="space-y-3 min-w-0">
      <header className="space-y-0.5">
        <h2 className="text-[10px] font-semibold uppercase tracking-[0.14em] text-white/48">
          Cleaning summary
        </h2>
        <p className="text-[11px] text-white/35">Metrics from this run only.</p>
      </header>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 min-w-0">
        {hasConfidence ? (
          <div className="col-span-full min-w-0">
            <CompactConfidenceRow score={view.confidence_score!} />
          </div>
        ) : null}

        {hasOriginal ? (
          <ShapeKpiCard
            title="Original shape"
            rows={view.original_rows!}
            cols={view.original_cols!}
            className={!hasFinal ? "sm:col-span-2" : ""}
          />
        ) : null}
        {hasFinal ? (
          <ShapeKpiCard
            title="Final shape"
            rows={view.final_rows!}
            cols={view.final_cols!}
            className={!hasOriginal ? "sm:col-span-2" : ""}
          />
        ) : null}

        {showStepsTypeRow && hasSteps ? (
          <StepsKpiCard
            steps={view.steps!}
            timeSaved={view.time_saved_estimate}
            className={typeFixes === undefined ? "sm:col-span-2" : ""}
          />
        ) : null}
        {showStepsTypeRow && typeFixes !== undefined ? (
          <MetricKpiCard
            label="Type conversions"
            value={typeFixes}
            sub="Normalized dtypes in pipeline."
            className={!hasSteps ? "sm:col-span-2" : ""}
          />
        ) : null}

        {showImputeSuspiciousRow && imputations !== undefined ? (
          <MetricKpiCard
            label="Missing values filled"
            value={imputations}
            sub="Columns imputed per notes."
            className={suspiciousCount === undefined ? "sm:col-span-2" : ""}
          />
        ) : null}
        {showImputeSuspiciousRow && suspiciousCount !== undefined ? (
          <MetricKpiCard
            label="Suspicious columns"
            value={suspiciousCount}
            sub="Review below or in Cleaning."
            variant="amber"
            className={imputations === undefined ? "sm:col-span-2" : ""}
          />
        ) : null}

        {extraTiles.map((c) => (
          <MetricKpiCard key={c.label} label={c.label} value={c.value} sub={c.sub} />
        ))}
      </div>

      {issues.length > 0 ? (
        <div className="overflow-hidden rounded-xl border border-amber-500/20 bg-amber-500/[0.04]">
          <button
            type="button"
            className="flex w-full items-center gap-3 px-4 py-2.5 text-left transition hover:bg-amber-500/[0.04] sm:px-4"
            onClick={() => setShowIssues((v) => !v)}
          >
            <AlertTriangle className="h-3.5 w-3.5 flex-shrink-0 text-amber-400" />
            <span className="min-w-0 flex-1 text-xs font-medium leading-snug text-amber-100/90">
              {issues.length} suspicious issue{issues.length > 1 ? "s" : ""} (not auto-fixed)
            </span>
            {showIssues ? (
              <ChevronDown className="h-3.5 w-3.5 flex-shrink-0 text-amber-400/70" />
            ) : (
              <ChevronRight className="h-3.5 w-3.5 flex-shrink-0 text-amber-400/70" />
            )}
          </button>

          {showIssues ? (
            <div className="space-y-2 border-t border-amber-500/12 px-3 py-3 sm:px-4">
              {issues.map((issue, i) => (
                <div key={i} className="rounded-lg border border-white/[0.06] bg-black/20 px-3 py-2">
                  {issue.column ? (
                    <p className="font-mono text-[11px] font-semibold text-amber-200/90">{issue.column}</p>
                  ) : null}
                  {issue.detail ? (
                    <p className="mt-0.5 text-[11px] leading-relaxed text-white/50">{issue.detail}</p>
                  ) : null}
                </div>
              ))}
            </div>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
