"use client";

import { useState } from "react";
import { AlertTriangle, ChevronDown, ChevronRight } from "lucide-react";

type SuspiciousIssue = {
  type?: string;
  column?: string;
  detail?: string;
};

type CleaningSummary = {
  original_rows?: number;
  original_cols?: number;
  final_rows?: number;
  final_cols?: number;
  rows_removed?: number;
  cols_removed?: number;
  steps?: number;
  time_saved_estimate?: string;
  confidence_score?: number;
  placeholders_replaced?: number;
  duplicate_cols_removed?: number;
  date_features_created?: string[];
  suspicious_issues_remaining?: SuspiciousIssue[];
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

// Normalise canonical CleaningResult → internal CleaningSummary shape.
// canonical.cleaning_summary uses steps_applied; legacy uses steps.
// eslint-disable-next-line @typescript-eslint/no-explicit-any
function fromCanonical(cr: Record<string, any>): CleaningSummary {
  const cs = cr.cleaning_summary ?? {};
  return {
    original_rows: cs.original_rows,
    original_cols: cs.original_cols,
    final_rows: cs.final_rows,
    final_cols: cs.final_cols,
    rows_removed: cs.rows_removed,
    cols_removed: cs.cols_removed,
    steps: cs.steps_applied ?? cs.steps,
    time_saved_estimate: cs.time_saved_estimate,
    confidence_score: cs.confidence_score,
    suspicious_issues_remaining: (cr.suspicious_columns ?? []).map(
      (sc: { issue_type?: string; column?: string; detail?: string }) => ({
        type: sc.issue_type,
        column: sc.column,
        detail: sc.detail,
      })
    ),
  };
}

export function CleaningSummaryCards({ cleaningResult, summary }: Props) {
  const [showIssues, setShowIssues] = useState(false);

  // Canonical-first resolution into a uniform CleaningSummary shape.
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const s: CleaningSummary | null = cleaningResult
    ? fromCanonical(cleaningResult as Record<string, any>)
    : summary
    ? (summary as unknown as CleaningSummary)
    : null;

  if (!s) {
    return <p className="text-sm text-white/60">No cleaning summary available.</p>;
  }

  const rowDelta = (s.original_rows ?? 0) - (s.final_rows ?? 0);
  const colDelta = (s.original_cols ?? 0) - (s.final_cols ?? 0);
  const issues = s.suspicious_issues_remaining ?? [];
  const dateFeats = s.date_features_created ?? [];

  return (
    <div className="space-y-4">
      {/* Top row: confidence + core stats */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
        {s.confidence_score !== undefined && (
          <ConfidenceBadge score={s.confidence_score} />
        )}
        <StatCard label="Original shape" value={`${s.original_rows?.toLocaleString()} × ${s.original_cols}`} />
        <StatCard label="Final shape"    value={`${s.final_rows?.toLocaleString()} × ${s.final_cols}`} />
        <StatCard label="Cleaning steps" value={s.steps ?? 0} sub={s.time_saved_estimate} />
      </div>

      {/* Secondary stats */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <StatCard label="Rows removed"   value={rowDelta} />
        <StatCard label="Cols removed"   value={colDelta} />
        <StatCard
          label="Placeholders replaced"
          value={s.placeholders_replaced ?? 0}
          sub="N/A, null, -, ? …"
        />
        <StatCard
          label="Duplicate cols removed"
          value={s.duplicate_cols_removed ?? 0}
        />
      </div>

      {/* Date features */}
      {dateFeats.length > 0 && (
        <div className="rounded-xl border border-teal-500/15 bg-teal-500/[0.04] px-4 py-3">
          <p className="text-xs font-medium text-teal-300 mb-2">
            Date features created ({dateFeats.length})
          </p>
          <div className="flex flex-wrap gap-1.5">
            {dateFeats.map((f) => (
              <span
                key={f}
                className="rounded-full bg-teal-500/15 border border-teal-500/20 px-2 py-0.5 text-xs text-teal-300 font-mono"
              >
                {f}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Suspicious issues */}
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
                  <p className="text-xs text-white/55 leading-relaxed">{issue.detail}</p>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
