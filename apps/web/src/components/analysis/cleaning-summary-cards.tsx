"use client";

import { useState } from "react";
import { AlertTriangle, ChevronDown, ChevronRight } from "lucide-react";

// ── Canonical types (mirror app/schemas/cleaning.py) ───────────────────────
type SuspiciousIssue = {
  type?: string;
  column?: string;
  detail?: string;
};

type ColumnRename     = { original: string; cleaned: string };
type TypeFix          = { column: string; to_dtype: string; n_values_converted: number };
type MissingnessNote  = {
  column: string; missing_count: number; missing_pct: number;
  mechanism: string; strategy_applied: string;
};
type DuplicateNote    = {
  duplicate_rows_found: number;
  duplicate_rows_removed: number;
  duplicate_columns: string[];
};
type SuspiciousColumn = { column: string; issue_type: string; detail: string };
type CleaningSummaryBlock = {
  original_rows?: number; original_cols?: number;
  final_rows?: number;    final_cols?: number;
  rows_removed?: number;  cols_removed?: number;
  steps_applied?: number; steps?: number;       // canonical / legacy aliases
  confidence_score?: number;
  time_saved_estimate?: string;
};
type CanonicalCR = {
  renamed_columns?:    ColumnRename[];
  dropped_columns?:    string[];
  type_fixes?:         TypeFix[];
  missingness_notes?:  MissingnessNote[];
  duplicate_notes?:    DuplicateNote;
  suspicious_columns?: SuspiciousColumn[];
  cleaning_summary?:   CleaningSummaryBlock;
};

// Internal view model — only fields with a known source.  Optional fields are
// rendered only when defined; we never substitute `?? 0` because that would
// claim work happened (or didn't) when in reality the value was simply not
// measured by the cleaning pipeline.  This is the trust contract for the cards.
type CleaningSummaryView = {
  // Headline
  confidence_score?: number;
  // Shape
  original_rows?: number;
  original_cols?: number;
  final_rows?: number;
  final_cols?: number;
  rows_removed?: number;
  cols_removed?: number;
  // Steps + saved time
  steps?: number;
  time_saved_estimate?: string;
  // Truthful canonical counters — only populated when canonical block exists.
  type_fixes_count?: number;          // count of type conversions actually applied
  imputations_count?: number;         // missing values imputed (excluding suggestions/drops)
  duplicate_cols_removed_count?: number;  // length of duplicate_notes.duplicate_columns
  duplicate_rows_removed?: number;
  suspicious_count?: number;          // columns flagged for review
  // Issue list (already rendered in CleaningReview, shown here as a teaser)
  issues_remaining: SuspiciousIssue[];
};

type Props = {
  cleaningResult?: Record<string, unknown> | null;  // canonical — primary
  summary?: Record<string, unknown> | null;         // legacy fallback
};

function ConfidenceBadge({ score }: { score: number }) {
  const color =
    score >= 80 ? "text-emerald-400 bg-emerald-500/15 border-emerald-500/25"
    : score >= 60 ? "text-amber-400 bg-amber-500/15 border-amber-500/25"
    : "text-red-400 bg-red-500/15 border-red-500/25";

  const label = score >= 80 ? "High" : score >= 60 ? "Medium" : "Low";

  return (
    <div className={`rounded-xl border p-4 ${color}`}>
      <p className="text-xs font-medium opacity-70 uppercase tracking-wide">Confidence Score</p>
      <div className="mt-2 flex items-end gap-2">
        <span className="text-3xl font-bold">{score}</span>
        <span className="mb-0.5 text-sm font-medium opacity-80">/ 100 · {label}</span>
      </div>
      <div className="mt-2 h-1.5 w-full rounded-full bg-white/10">
        <div
          className="h-full rounded-full bg-current opacity-60"
          style={{ width: `${score}%` }}
        />
      </div>
    </div>
  );
}

function StatCard({ label, value, sub }: { label: string; value: string | number; sub?: string }) {
  return (
    <div className="rounded-xl border border-white/[0.07] bg-white/[0.03] p-4">
      <p className="text-xs text-white/40 uppercase tracking-wide">{label}</p>
      <p className="mt-1.5 text-2xl font-semibold text-white">{value}</p>
      {sub && <p className="mt-0.5 text-xs text-white/30">{sub}</p>}
    </div>
  );
}

// ── Adapters ─────────────────────────────────────────────────────────────────

// Canonical CleaningResult → view.  Counters are derived from real list lengths
// (no fabricated zeros) — every value here corresponds to data the pipeline
// actually emitted.
function fromCanonical(cr: CanonicalCR): CleaningSummaryView {
  const cs = cr.cleaning_summary ?? {};
  const dupNotes = cr.duplicate_notes;
  const missing = cr.missingness_notes ?? [];

  // Imputations count = missingness notes where a strategy was actually applied
  // (excludes safe-mode suggestions and high-missing drops, which are reported
  // separately and would otherwise inflate the "filled" headline).
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

// Legacy summary → view.  Only fields the legacy pipeline truly populated.  We
// intentionally drop placeholders_replaced / duplicate_cols_removed /
// date_features_created from the cards: those are not in the canonical schema
// (P1-8 in QA) and we now only show counters that exist on both paths so the
// summary cannot drift between canonical and legacy renderings.
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
    // legacy paths don't carry truthful list-derived canonical counters,
    // so leave them undefined — the cards will simply not render.
    issues_remaining: Array.isArray(legacy.suspicious_issues_remaining)
      ? (legacy.suspicious_issues_remaining as SuspiciousIssue[])
      : [],
  };
}

function formatShape(rows?: number, cols?: number): string | null {
  if (typeof rows !== "number" || typeof cols !== "number") return null;
  return `${rows.toLocaleString()} × ${cols.toLocaleString()}`;
}

// ── Main component ───────────────────────────────────────────────────────────

export function CleaningSummaryCards({ cleaningResult, summary }: Props) {
  const [showIssues, setShowIssues] = useState(false);

  // Canonical-first: prefer cleaning_result; fall back to legacy summary.
  const view: CleaningSummaryView | null = cleaningResult
    ? fromCanonical(cleaningResult as CanonicalCR)
    : summary
    ? fromLegacy(summary as Record<string, unknown>)
    : null;

  if (!view) {
    return <p className="text-sm text-white/60">No cleaning summary available.</p>;
  }

  const originalShape = formatShape(view.original_rows, view.original_cols);
  const finalShape    = formatShape(view.final_rows,    view.final_cols);
  const issues        = view.issues_remaining;

  // Each secondary card is only shown when its value is meaningful — a
  // missing or zero canonical counter does NOT render so we never imply
  // precision the pipeline didn't measure.
  const secondaryCards: Array<{ label: string; value: string | number; sub?: string }> = [];

  if (typeof view.rows_removed === "number" && view.rows_removed > 0) {
    secondaryCards.push({ label: "Rows removed", value: view.rows_removed.toLocaleString() });
  }
  if (typeof view.cols_removed === "number" && view.cols_removed > 0) {
    secondaryCards.push({ label: "Columns removed", value: view.cols_removed.toLocaleString() });
  }
  if (typeof view.type_fixes_count === "number" && view.type_fixes_count > 0) {
    secondaryCards.push({
      label: "Type conversions",
      value: view.type_fixes_count,
      sub: "currency, %, numeric, date, boolean",
    });
  }
  if (typeof view.imputations_count === "number" && view.imputations_count > 0) {
    secondaryCards.push({
      label: "Missing values filled",
      value: view.imputations_count,
      sub: "columns imputed",
    });
  }
  if (typeof view.duplicate_rows_removed === "number" && view.duplicate_rows_removed > 0) {
    secondaryCards.push({
      label: "Duplicate rows removed",
      value: view.duplicate_rows_removed.toLocaleString(),
    });
  }
  if (typeof view.duplicate_cols_removed_count === "number" && view.duplicate_cols_removed_count > 0) {
    secondaryCards.push({
      label: "Duplicate columns removed",
      value: view.duplicate_cols_removed_count,
    });
  }
  if (typeof view.suspicious_count === "number" && view.suspicious_count > 0) {
    secondaryCards.push({
      label: "Suspicious columns",
      value: view.suspicious_count,
      sub: "flagged for review",
    });
  }

  const topCards: Array<React.ReactNode> = [];
  if (originalShape) {
    topCards.push(<StatCard key="orig" label="Original shape" value={originalShape} />);
  }
  if (finalShape) {
    topCards.push(<StatCard key="final" label="Final shape" value={finalShape} />);
  }
  if (typeof view.steps === "number") {
    topCards.push(
      <StatCard
        key="steps"
        label="Cleaning steps"
        value={view.steps}
        sub={view.time_saved_estimate}
      />,
    );
  }

  const hasAnyContent =
    view.confidence_score !== undefined ||
    topCards.length > 0 ||
    secondaryCards.length > 0 ||
    issues.length > 0;

  if (!hasAnyContent) {
    return (
      <p className="text-sm text-white/60">
        No cleaning summary available for this run.
      </p>
    );
  }

  return (
    <div className="space-y-4">
      {/* Top row: confidence + core stats — only renders cards we actually have */}
      {(view.confidence_score !== undefined || topCards.length > 0) && (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
          {view.confidence_score !== undefined && (
            <ConfidenceBadge score={view.confidence_score} />
          )}
          {topCards}
        </div>
      )}

      {/* Secondary stats — only truthful canonical counters; cards with no
          measured value are omitted rather than rendered as 0 */}
      {secondaryCards.length > 0 && (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          {secondaryCards.map((c) => (
            <StatCard key={c.label} label={c.label} value={c.value} sub={c.sub} />
          ))}
        </div>
      )}

      {/* Suspicious issues teaser (full detail lives in CleaningReview) */}
      {issues.length > 0 && (
        <div className="rounded-xl border border-amber-500/20 bg-amber-500/[0.05]">
          <button
            className="flex w-full items-center gap-2 px-4 py-3 text-left"
            onClick={() => setShowIssues((v) => !v)}
          >
            <AlertTriangle className="h-3.5 w-3.5 flex-shrink-0 text-amber-400" />
            <span className="flex-1 text-xs font-medium text-amber-300">
              {issues.length} suspicious issue{issues.length > 1 ? "s" : ""} remaining (not auto-fixed)
            </span>
            {showIssues
              ? <ChevronDown className="h-3.5 w-3.5 text-amber-400/60" />
              : <ChevronRight className="h-3.5 w-3.5 text-amber-400/60" />
            }
          </button>

          {showIssues && (
            <div className="border-t border-amber-500/15 px-4 pb-3 space-y-2">
              {issues.map((issue, i) => (
                <div key={i} className="pt-2">
                  {issue.column && (
                    <p className="text-xs font-semibold text-amber-300 mb-0.5">{issue.column}</p>
                  )}
                  {issue.detail && (
                    <p className="text-xs text-white/55 leading-relaxed">{issue.detail}</p>
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
