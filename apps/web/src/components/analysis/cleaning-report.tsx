export type CleaningItem = {
  step: string;
  detail: string;
  impact: "high" | "medium" | "low";
};

/** Canonical cleaning block (subset matching API / cleaning-review). */
export type CanonicalCleaningResult = {
  renamed_columns?: Array<{ original: string; cleaned: string }>;
  dropped_columns?: string[];
  type_fixes?: Array<{ column: string; to_dtype: string; n_values_converted: number }>;
  missingness_notes?: Array<{
    column: string;
    missing_count: number;
    missing_pct: number;
    mechanism: string;
    strategy_applied: string;
  }>;
  duplicate_notes?: {
    duplicate_rows_found: number;
    duplicate_rows_removed: number;
    duplicate_columns?: string[];
  };
  suspicious_columns?: Array<{ column: string; detail: string; issue_type?: string }>;
};

type Props = {
  cleaningResult?: CanonicalCleaningResult | null;
  items?: CleaningItem[];
};

export function cleaningItemsFromCanonical(
  cr: CanonicalCleaningResult | null | undefined,
): CleaningItem[] {
  if (!cr) return [];
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
  const removed = dn?.duplicate_rows_removed ?? 0;
  if (dn != null && removed > 0) {
    const found = dn.duplicate_rows_found ?? 0;
    items.push({ step: "Remove duplicate rows", detail: `Removed ${removed} of ${found} duplicates`, impact: "medium" });
  }
  for (const susp of cr.suspicious_columns ?? [])
    items.push({ step: `[FLAG] ${susp.column}`, detail: susp.detail, impact: "medium" });
  return items;
}

const IMPACT_STYLE = {
  high:   "bg-rose-500/10 text-rose-400 border-rose-500/20",
  medium: "bg-amber-500/10 text-amber-400 border-amber-500/20",
  low:    "bg-white/5 text-white/40 border-white/10",
};

export function CleaningReport({ cleaningResult, items: legacyItems }: Props) {
  const items: CleaningItem[] = cleaningResult
    ? cleaningItemsFromCanonical(cleaningResult)
    : (legacyItems ?? []);

  if (items.length === 0) {
    return (
      <p className="text-sm text-emerald-400">
        No cleaning actions needed — dataset was already clean.
      </p>
    );
  }

  return (
    <div className="space-y-2">
      {items.map((item, i) => (
        <div
          key={i}
          className="flex items-start gap-3 rounded-xl border border-white/[0.06] bg-white/[0.02] px-4 py-3"
        >
          <span className="mt-0.5 text-xs text-white/30 w-4 flex-shrink-0">{i + 1}</span>
          <div className="flex-1 min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <p className="text-sm font-medium text-white">{item.step}</p>
              <span className={`rounded-full border px-2 py-0.5 text-[11px] font-medium ${IMPACT_STYLE[item.impact] ?? IMPACT_STYLE.low}`}>
                {item.impact} impact
              </span>
            </div>
            <p className="mt-1 text-xs text-white/50">{item.detail}</p>
          </div>
        </div>
      ))}
    </div>
  );
}
