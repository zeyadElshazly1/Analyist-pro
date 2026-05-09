"use client";

import type { AnalysisPlan } from "@/lib/api";

// ── Helpers ──────────────────────────────────────────────────────────────────

function confidenceColor(confidence: number): {
  bar: string; label: string; text: string; badge: string;
} {
  if (confidence >= 0.8)
    return {
      bar:   "bg-emerald-500",
      label: "High confidence",
      text:  "text-emerald-300",
      badge: "bg-emerald-500/15 text-emerald-400 border-emerald-500/25",
    };
  if (confidence >= 0.6)
    return {
      bar:   "bg-amber-400",
      label: "Moderate confidence",
      text:  "text-amber-300",
      badge: "bg-amber-500/15 text-amber-400 border-amber-500/25",
    };
  return {
    bar:   "bg-white/20",
    label: "Low confidence — generic analysis",
    text:  "text-white/50",
    badge: "bg-white/5 text-white/40 border-white/10",
  };
}

function kindLabel(kind: string): string {
  const labels: Record<string, string> = {
    sales:      "Sales",
    finance:    "Finance / Market",
    insurance:  "Insurance",
    hr:         "HR / People",
    marketing:  "Marketing",
    operations: "Operations",
    research:   "Research",
    generic:    "General dataset",
  };
  return labels[kind] ?? kind;
}

function templateLabel(hint: string): string {
  const labels: Record<string, string> = {
    executive_summary: "Executive summary",
    detailed_audit:    "Detailed audit",
    trend_report:      "Trend report",
    generic:           "Standard report",
  };
  return labels[hint] ?? hint;
}

// ── Sub-components ────────────────────────────────────────────────────────────

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div>
      <p className="mb-1.5 text-xs font-medium uppercase tracking-wide text-white/35">{title}</p>
      {children}
    </div>
  );
}

function PillList({ items, color = "default" }: {
  items: string[];
  color?: "emerald" | "amber" | "red" | "default";
}) {
  if (items.length === 0) return <p className="text-xs text-white/30">None detected</p>;
  const cls = {
    emerald: "bg-emerald-500/10 text-emerald-400 border-emerald-500/20",
    amber:   "bg-amber-500/10 text-amber-400 border-amber-500/20",
    red:     "bg-red-500/10 text-red-400 border-red-500/20",
    default: "bg-white/[0.06] text-white/60 border-white/[0.08]",
  }[color];
  return (
    <div className="flex flex-wrap gap-1.5">
      {items.map((item) => (
        <span key={item} className={`inline-flex rounded-full border px-2.5 py-0.5 text-xs ${cls}`}>
          {item}
        </span>
      ))}
    </div>
  );
}

// ── Main component ────────────────────────────────────────────────────────────

export function AnalysisPlanCard({ plan }: { plan: AnalysisPlan }) {
  const { bar, label: confLabel, text: confText, badge: confBadge } = confidenceColor(plan.confidence);
  const pct = Math.round(plan.confidence * 100);

  return (
    <div className="rounded-xl border border-white/[0.07] bg-white/[0.02] p-5 space-y-5">

      {/* ── Header ─────────────────────────────────────────────────────────── */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-xs uppercase tracking-wide text-white/35 mb-0.5">
            What Analyst Pro thinks this file is
          </p>
          <h3 className="text-base font-semibold text-white">{kindLabel(plan.dataset_kind)}</h3>
          {plan.primary_entity && (
            <p className="mt-0.5 text-xs text-white/40">
              Primary unit: <span className="text-white/60">{plan.primary_entity}</span>
            </p>
          )}
        </div>
        <span className={`flex-shrink-0 rounded-full border px-2.5 py-1 text-xs font-semibold ${confBadge}`}>
          {pct}%
        </span>
      </div>

      {/* ── Confidence bar ─────────────────────────────────────────────────── */}
      <div>
        <div className="mb-1.5 flex items-center justify-between">
          <p className={`text-xs ${confText}`}>{confLabel}</p>
          <p className="text-xs text-white/30">{pct}/100</p>
        </div>
        <div className="h-1.5 w-full rounded-full bg-white/[0.06]">
          <div className={`h-1.5 rounded-full ${bar}`} style={{ width: `${pct}%` }} />
        </div>
      </div>

      {/* ── Context ────────────────────────────────────────────────────────── */}
      {plan.business_context && (
        <Section title="Business context">
          <p className="text-sm text-white/55 leading-relaxed">{plan.business_context}</p>
        </Section>
      )}

      {/* ── Columns grid ───────────────────────────────────────────────────── */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <Section title="Columns likely to drive the analysis">
          <PillList items={plan.target_metrics} color="emerald" />
        </Section>

        <Section title="Key segments & dimensions">
          <PillList items={plan.important_dimensions} color="default" />
        </Section>

        <Section title="Date / time columns">
          <PillList items={plan.time_columns} color="amber" />
        </Section>

        <Section title="Columns to treat carefully">
          <PillList items={plan.columns_to_ignore} color="default" />
        </Section>
      </div>

      {/* ── Warnings ───────────────────────────────────────────────────────── */}
      {plan.analysis_warnings.length > 0 && (
        <Section title="Heads-up">
          <ul className="space-y-1.5">
            {plan.analysis_warnings.map((w, i) => (
              <li key={i} className="flex items-start gap-2 text-xs text-amber-300/80">
                <span className="mt-px flex-shrink-0">⚠</span>
                <span>{w}</span>
              </li>
            ))}
          </ul>
        </Section>
      )}

      {/* ── Footer ─────────────────────────────────────────────────────────── */}
      <div className="flex items-center justify-between border-t border-white/[0.05] pt-3">
        <p className="text-xs text-white/30">
          Recommended report style:{" "}
          <span className="text-white/50">{templateLabel(plan.report_template_hint)}</span>
        </p>
        <p className="text-xs text-white/20">Dataset Intelligence · 86C</p>
      </div>
    </div>
  );
}
