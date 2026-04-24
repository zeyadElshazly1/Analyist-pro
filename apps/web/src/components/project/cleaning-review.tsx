"use client";

import { CheckCircle, AlertTriangle, Info, Minus } from "lucide-react";

type CleaningItem = {
  step: string;
  detail: string;
  impact?: "high" | "medium" | "low" | string;
};

type SummaryBar = {
  steps?: number;
  rows_removed?: number;
  columns_fixed?: number;
};

type Props = {
  cleaningResult?: Record<string, unknown> | null;  // canonical — primary
  items?: CleaningItem[];                           // legacy fallback
  summary?: SummaryBar;                            // legacy fallback
};

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function cleaningItemsFromCanonical(cr: Record<string, any>): CleaningItem[] {
  const items: CleaningItem[] = [];
  for (const r of cr.renamed_columns ?? [])
    items.push({ step: `Rename: ${r.original} → ${r.cleaned}`, detail: "Column name normalised", impact: "low" });
  for (const col of cr.dropped_columns ?? [])
    items.push({ step: `Drop column: ${col}`, detail: "Removed — high missingness or no content", impact: "medium" });
  for (const fix of cr.type_fixes ?? []) {
    const count = fix.n_values_converted > 0 ? ` (${fix.n_values_converted} values)` : "";
    items.push({ step: `Type fix: ${fix.column}`, detail: `Converted to ${fix.to_dtype}${count}`, impact: "medium" });
  }
  for (const note of cr.missingness_notes ?? []) {
    const isSuggestion = note.strategy_applied === "safe_suggestion";
    items.push({ step: `${isSuggestion ? "[SUGGESTION] Impute missing" : "Impute missing"}: ${note.column}`, detail: `${note.missing_count} missing (${note.missing_pct}%), mechanism: ${note.mechanism}`, impact: isSuggestion ? "low" : "medium" });
  }
  const dn = cr.duplicate_notes;
  if (dn?.duplicate_rows_removed > 0)
    items.push({ step: "Remove duplicate rows", detail: `Removed ${dn.duplicate_rows_removed} of ${dn.duplicate_rows_found} duplicates`, impact: "medium" });
  for (const susp of cr.suspicious_columns ?? [])
    items.push({ step: `[FLAG] ${susp.column}`, detail: susp.detail, impact: "medium" });
  return items;
}

const FLAGGED_KEYWORDS = ["outlier", "suspicious", "zero", "anomal", "unusual", "manual"];

function isAutoApplied(item: CleaningItem): boolean {
  const step = (item.step ?? "").toLowerCase();
  return !FLAGGED_KEYWORDS.some((kw) => step.includes(kw));
}

export function CleaningReview({ cleaningResult, items: legacyItems, summary: legacySummary }: Props) {
  // Canonical-first: derive items from cleaningResult, else use legacy items.
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const items: CleaningItem[] = cleaningResult
    ? cleaningItemsFromCanonical(cleaningResult as Record<string, any>)
    : (legacyItems ?? []);

  // Derive summary bar from canonical cleaning_summary, else use legacy.
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const cs = (cleaningResult as any)?.cleaning_summary;
  const summary: SummaryBar | undefined = cs
    ? { steps: cs.steps_applied ?? cs.steps, rows_removed: cs.rows_removed, columns_fixed: cs.cols_removed }
    : legacySummary;

  if (!items || items.length === 0) {
    return (
      <div className="rounded-xl border border-emerald-500/20 bg-emerald-500/5 p-4 flex items-center gap-3">
        <CheckCircle className="h-4 w-4 text-emerald-400 flex-shrink-0" />
        <div>
          <p className="text-sm font-medium text-white">No cleaning needed</p>
          <p className="text-xs text-white/40">Dataset was already clean — no changes applied.</p>
        </div>
      </div>
    );
  }

  const highImpact = items.filter((i) => i.impact === "high");
  const mediumImpact = items.filter((i) => i.impact === "medium" && isAutoApplied(i));
  const flagged = items.filter((i) => i.impact === "medium" && !isAutoApplied(i));
  const lowImpact = items.filter((i) => i.impact === "low" || (!i.impact && isAutoApplied(i)));

  const autoApplied = [...highImpact, ...mediumImpact];
  const forReview = flagged;
  const minor = lowImpact;

  return (
    <div className="space-y-4">
      {/* Summary bar */}
      {summary && (
        <div className="grid grid-cols-3 gap-2">
          {[
            { label: "Steps applied", value: summary.steps ?? items.length },
            { label: "Rows removed", value: summary.rows_removed ?? "—" },
            { label: "Columns fixed", value: summary.columns_fixed ?? "—" },
          ].map((s) => (
            <div
              key={s.label}
              className="rounded-lg border border-white/[0.06] bg-white/[0.02] px-3 py-2 text-center"
            >
              <p className="text-lg font-bold text-white">{s.value}</p>
              <p className="text-[10px] text-white/35">{s.label}</p>
            </div>
          ))}
        </div>
      )}

      {/* Section: Applied automatically */}
      {autoApplied.length > 0 && (
        <Section
          icon={<CheckCircle className="h-4 w-4 text-emerald-400" />}
          title="Applied automatically"
          subtitle={`${autoApplied.length} change${autoApplied.length > 1 ? "s" : ""} made — safe to proceed`}
          items={autoApplied}
          chipColor="emerald"
        />
      )}

      {/* Section: Worth reviewing */}
      {forReview.length > 0 && (
        <Section
          icon={<AlertTriangle className="h-4 w-4 text-amber-400" />}
          title="Worth reviewing"
          subtitle={`${forReview.length} item${forReview.length > 1 ? "s" : ""} flagged — check before exporting`}
          items={forReview}
          chipColor="amber"
        />
      )}

      {/* Section: Minor / informational */}
      {minor.length > 0 && (
        <Section
          icon={<Info className="h-4 w-4 text-white/30" />}
          title="Minor adjustments"
          subtitle={`${minor.length} low-impact item${minor.length > 1 ? "s" : ""}`}
          items={minor}
          chipColor="slate"
          collapsed
        />
      )}
    </div>
  );
}

type SectionProps = {
  icon: React.ReactNode;
  title: string;
  subtitle: string;
  items: CleaningItem[];
  chipColor: "emerald" | "amber" | "slate";
  collapsed?: boolean;
};

function Section({ icon, title, subtitle, items, chipColor }: SectionProps) {
  const chipClass =
    chipColor === "emerald"
      ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/20"
      : chipColor === "amber"
      ? "bg-amber-500/10 text-amber-400 border-amber-500/20"
      : "bg-white/[0.05] text-white/35 border-white/10";

  return (
    <div className="rounded-xl border border-white/[0.07] bg-white/[0.015] overflow-hidden">
      <div className="flex items-center gap-2.5 px-4 py-3 border-b border-white/[0.06]">
        {icon}
        <div className="flex-1 min-w-0">
          <p className="text-sm font-semibold text-white">{title}</p>
          <p className="text-[11px] text-white/35">{subtitle}</p>
        </div>
      </div>
      <div className="divide-y divide-white/[0.04]">
        {items.map((item, i) => (
          <div key={i} className="flex items-start gap-3 px-4 py-2.5">
            <Minus className="mt-1 h-3 w-3 flex-shrink-0 text-white/20" />
            <div className="flex-1 min-w-0">
              <div className="flex flex-wrap items-center gap-2">
                <p className="text-xs font-medium text-white/80">{item.step}</p>
                {item.impact && (
                  <span className={`rounded-full border px-1.5 py-px text-[10px] font-medium ${chipClass}`}>
                    {item.impact}
                  </span>
                )}
              </div>
              {item.detail && (
                <p className="mt-0.5 text-[11px] text-white/40">{item.detail}</p>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
