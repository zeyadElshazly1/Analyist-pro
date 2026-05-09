"use client";

import { ArrowRight, Check } from "lucide-react";

export type StepStatus = "unavailable" | "available" | "attention" | "complete";

// ── Default landing step ──────────────────────────────────────────────────────
// Single source of truth for the tab a freshly-completed or reopened run lands
// on, plus the human-readable label used in resume/reopen copy.  Any banner or
// CTA that promises "opens at <step>" should import these so the promise can't
// drift away from the actual `setTab(...)` behavior in run-analysis.tsx.
export const DEFAULT_LANDING_TAB = "intake";
export const DEFAULT_LANDING_TAB_LABEL = "Intake Review";

export function getStepForTab(tabId: string): string {
  return TAB_TO_STEP[tabId] ?? DEFAULT_LANDING_TAB;
}

type Props = {
  value: string;
  onChange: (v: string) => void;
  compareAvailable?: boolean;
  stepStatuses?: Record<string, StepStatus>;
};

const STEPS = [
  {
    id: "intake",
    label: "Intake Review",
    description: "Check how your file was parsed and structured",
    number: 1,
    primaryTab: "intake",
    tabs: [
      { id: "intake", label: "Intake review" },
      { id: "overview", label: "Summary" },
      { id: "data-table", label: "Raw data" },
    ],
  },
  {
    id: "cleaning",
    label: "Cleaning Review",
    description: "See what was fixed or flagged automatically",
    number: 2,
    primaryTab: "cleaning",
    tabs: [
      { id: "cleaning", label: "Cleaning log" },
    ],
  },
  {
    id: "health",
    label: "Health Check",
    description: "Dataset readiness, score, warnings, and column profiles",
    number: 3,
    primaryTab: "health",
    tabs: [
      { id: "health", label: "Health score" },
      { id: "profile", label: "Column profiles" },
    ],
  },
  {
    id: "insights",
    label: "Findings",
    description: "Key patterns, anomalies, and correlations",
    number: 4,
    primaryTab: "insights",
    tabs: [
      { id: "insights", label: "Top findings" },
      { id: "charts", label: "Charts" },
      { id: "timeseries", label: "Time series" },
      { id: "correlations", label: "Correlations" },
      { id: "duplicates", label: "Duplicates" },
      { id: "outliers", label: "Outliers" },
    ],
  },
  {
    id: "compare",
    label: "Compare Changes",
    description: "Compare this file against another version or run",
    number: 5,
    primaryTab: "compare-files",
    tabs: [
      { id: "compare-files", label: "Compare files" },
      { id: "compare-cols", label: "Compare columns" },
      { id: "diff", label: "Diff runs" },
    ],
  },
  {
    id: "report",
    label: "Build Report",
    description: "Assemble findings and export for your client",
    number: 6,
    primaryTab: "ask-ai",
    tabs: [
      { id: "ask-ai", label: "Ask AI / Copilot" },
      { id: "story", label: "Client summary" },
    ],
  },
];

const TAB_TO_STEP: Record<string, string> = {};
for (const step of STEPS) {
  for (const tab of step.tabs) {
    TAB_TO_STEP[tab.id] = step.id;
  }
}

export function ProjectTabs({ value, onChange, compareAvailable, stepStatuses }: Props) {
  const activeStepId  = TAB_TO_STEP[value] ?? STEPS[0].id;
  const activeStep    = STEPS.find((s) => s.id === activeStepId) ?? STEPS[0];
  const activeStepIdx = STEPS.findIndex((s) => s.id === activeStepId);
  const nextStep      = activeStepIdx < STEPS.length - 1 ? STEPS[activeStepIdx + 1] : null;

  return (
    <div className="space-y-3 min-w-0">

      {/* ── Step progress bar ────────────────────────────────────────────── */}
      <div className="overflow-x-auto [scrollbar-width:none] [-ms-overflow-style:none] [&::-webkit-scrollbar]:hidden pb-0.5">
        <div className="flex items-center gap-1 min-w-max px-0.5">
          {STEPS.map((step, idx) => {
            const status: StepStatus = stepStatuses?.[step.id] ?? "available";
            const isActive    = step.id === activeStepId;
            const isComplete  = !isActive && status === "complete";
            const isAttention = !isActive && status === "attention";
            const isUnavail   = !isActive && status === "unavailable";
            const isCompare   = step.id === "compare";

            const btnClass = isActive
              ? "bg-indigo-600 text-white"
              : isComplete
              ? "bg-indigo-600/15 text-indigo-300 hover:bg-indigo-600/25"
              : isAttention
              ? "text-amber-400/80 hover:text-amber-300 hover:bg-amber-500/[0.06]"
              : isUnavail
              ? "text-white/20 hover:text-white/30 hover:bg-white/[0.03]"
              : "text-white/40 hover:text-white/70 hover:bg-white/[0.05]";

            const badgeClass = isActive
              ? "bg-white/20 text-white"
              : isComplete
              ? "bg-indigo-500/25 text-indigo-200"
              : isAttention
              ? "bg-amber-500/15 text-amber-400"
              : isUnavail
              ? "bg-white/[0.04] text-white/15"
              : "bg-white/10 text-white/35";

            return (
              <div key={step.id} className="flex items-center gap-1">
                <button
                  type="button"
                  onClick={() => onChange(step.primaryTab)}
                  className={`flex items-center gap-2 rounded-lg px-3 py-2 text-[13px] font-medium transition-colors whitespace-nowrap ${btnClass}`}
                >
                  {/* Number / check badge */}
                  <span className={`flex h-5 w-5 flex-shrink-0 items-center justify-center rounded-full text-[10px] font-bold ${badgeClass}`}>
                    {isComplete
                      ? <Check className="h-3 w-3" />
                      : step.number}
                  </span>

                  {step.label}

                  {/* Compare available dot (emerald when data present, no attention) */}
                  {isCompare && compareAvailable && !isAttention && (
                    <span className="h-1.5 w-1.5 flex-shrink-0 rounded-full bg-emerald-400" title="Compare data available" />
                  )}
                  {/* Attention dot */}
                  {isAttention && (
                    <span className="h-1.5 w-1.5 flex-shrink-0 rounded-full bg-amber-400" title="Needs attention" />
                  )}
                </button>
                {idx < STEPS.length - 1 && (
                  <div className={`h-px w-4 flex-shrink-0 ${isComplete ? "bg-indigo-500/25" : "bg-white/[0.08]"}`} />
                )}
              </div>
            );
          })}
        </div>
      </div>

      {/* ── Step context: description + next-step nudge ──────────────────── */}
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between sm:gap-4">
        <p className="text-xs text-white/35 leading-snug sm:max-w-[70%]">{activeStep.description}</p>
        {nextStep && (
          <button
            type="button"
            onClick={() => onChange(nextStep.primaryTab)}
            className="flex flex-shrink-0 items-center gap-1 text-xs text-white/30 transition-colors hover:text-white/55"
          >
            Next: {nextStep.label}
            <ArrowRight className="h-2.5 w-2.5" />
          </button>
        )}
      </div>

      {/* ── Sub-tabs for current step ────────────────────────────────────── */}
      {activeStep.tabs.length > 1 && (
        <div className="overflow-x-auto [scrollbar-width:none] [-ms-overflow-style:none] [&::-webkit-scrollbar]:hidden -mx-1 px-1">
          <div className="flex gap-1.5 border-b border-white/[0.08] pb-2.5 min-w-max">
            {activeStep.tabs.map((t) => (
              <button
                type="button"
                key={t.id}
                onClick={() => onChange(t.id)}
                className={`rounded-lg px-3.5 py-2 text-[13px] font-medium transition-colors whitespace-nowrap ${
                  value === t.id
                    ? "bg-white/[0.11] text-white shadow-sm shadow-black/20"
                    : "text-white/42 hover:text-white/75 hover:bg-white/[0.05]"
                }`}
              >
                {t.label}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
