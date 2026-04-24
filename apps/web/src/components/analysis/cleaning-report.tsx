type CleaningItem = {
  step: string;
  detail: string;
  impact: "high" | "medium" | "low";
};

type Props = {
  cleaningResult?: Record<string, unknown> | null;  // canonical — primary
  items?: CleaningItem[];                           // legacy fallback
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

const IMPACT_STYLE = {
  high:   "bg-rose-500/10 text-rose-400 border-rose-500/20",
  medium: "bg-amber-500/10 text-amber-400 border-amber-500/20",
  low:    "bg-white/5 text-white/40 border-white/10",
};

export function CleaningReport({ cleaningResult, items: legacyItems }: Props) {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const items: CleaningItem[] = cleaningResult
    ? cleaningItemsFromCanonical(cleaningResult as Record<string, any>)
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
