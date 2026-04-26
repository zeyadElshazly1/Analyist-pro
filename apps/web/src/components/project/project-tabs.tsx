"use client";

import { useState } from "react";
import { ChevronDown, ChevronUp, ArrowRight, Check } from "lucide-react";

export type StepStatus = "unavailable" | "available" | "attention" | "complete";

export function getStepForTab(tabId: string): string {
  return TAB_TO_STEP[tabId] ?? "intake";
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
    primaryTab: "overview",
    tabs: [
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
    description: "Column-by-column data quality profile",
    number: 3,
    primaryTab: "profile",
    tabs: [
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

const ADVANCED_TABS = [
  { id: "query", label: "SQL query" },
  { id: "predictions", label: "AutoML" },
  { id: "ab-tests", label: "A/B tests" },
  { id: "segments", label: "Segments" },
  { id: "pivot", label: "Pivot table" },
  { id: "join", label: "Join datasets" },
];

const TAB_TO_STEP: Record<string, string> = {};
for (const step of STEPS) {
  for (const tab of step.tabs) {
    TAB_TO_STEP[tab.id] = step.id;
  }
}

export function ProjectTabs({ value, onChange, compareAvailable, stepStatuses }: Props) {
  const [advancedOpen, setAdvancedOpen] = useState(false);

  const activeStepId  = TAB_TO_STEP[value] ?? STEPS[0].id;
  const activeStep    = STEPS.find((s) => s.id === activeStepId) ?? STEPS[0];
  const activeStepIdx = STEPS.findIndex((s) => s.id === activeStepId);
  const nextStep      = activeStepIdx < STEPS.length - 1 ? STEPS[activeStepIdx + 1] : null;
  const isAdvanced    = ADVANCED_TABS.some((t) => t.id === value);

  return (
    <div className="space-y-2">

      {/* ── Step progress bar ────────────────────────────────────────────── */}
      <div className="overflow-x-auto [scrollbar-width:none] [-ms-overflow-style:none] [&::-webkit-scrollbar]:hidden">
        <div className="flex items-center gap-0.5 min-w-max">
          {STEPS.map((step, idx) => {
            const status: StepStatus = stepStatuses?.[step.id] ?? "available";
            const isActive    = step.id === activeStepId && !isAdvanced;
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
              <div key={step.id} className="flex items-center gap-0.5">
                <button
                  onClick={() => onChange(step.primaryTab)}
                  className={`flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-xs font-medium transition-colors whitespace-nowrap ${btnClass}`}
                >
                  {/* Number / check badge */}
                  <span className={`flex h-4 w-4 flex-shrink-0 items-center justify-center rounded-full text-[9px] font-bold ${badgeClass}`}>
                    {isComplete
                      ? <Check className="h-2.5 w-2.5" />
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
                  <div className={`h-px w-3 flex-shrink-0 ${isComplete ? "bg-indigo-500/20" : "bg-white/[0.07]"}`} />
                )}
              </div>
            );
          })}
        </div>
      </div>

      {/* ── Step context: description + next-step nudge ──────────────────── */}
      {!isAdvanced && (
        <div className="flex items-center justify-between gap-4">
          <p className="text-[11px] text-white/30 leading-none">{activeStep.description}</p>
          {nextStep && (
            <button
              onClick={() => onChange(nextStep.primaryTab)}
              className="flex flex-shrink-0 items-center gap-1 text-[11px] text-white/25 transition-colors hover:text-white/50"
            >
              Next: {nextStep.label}
              <ArrowRight className="h-2.5 w-2.5" />
            </button>
          )}
        </div>
      )}

      {/* ── Sub-tabs for current step ────────────────────────────────────── */}
      {!isAdvanced && activeStep.tabs.length > 1 && (
        <div className="overflow-x-auto [scrollbar-width:none] [-ms-overflow-style:none] [&::-webkit-scrollbar]:hidden">
          <div className="flex gap-1 border-b border-white/[0.07] pb-2 min-w-max">
            {activeStep.tabs.map((t) => (
              <button
                key={t.id}
                onClick={() => onChange(t.id)}
                className={`rounded-md px-3 py-1.5 text-xs font-medium transition-colors whitespace-nowrap ${
                  value === t.id
                    ? "bg-white/10 text-white"
                    : "text-white/40 hover:text-white/70 hover:bg-white/[0.04]"
                }`}
              >
                {t.label}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* ── Advanced drawer ──────────────────────────────────────────────── */}
      <div>
        <button
          onClick={() => setAdvancedOpen((o) => !o)}
          className="flex items-center gap-1.5 text-xs text-white/20 transition-colors hover:text-white/45"
        >
          {advancedOpen ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
          Advanced tools
        </button>

        {advancedOpen && (
          <div className="mt-2 flex flex-wrap gap-1">
            {ADVANCED_TABS.map((t) => (
              <button
                key={t.id}
                onClick={() => onChange(t.id)}
                className={`rounded-md px-3 py-1.5 text-xs font-medium transition-colors ${
                  value === t.id
                    ? "bg-white/10 text-white"
                    : "text-white/35 hover:text-white/60 hover:bg-white/[0.04]"
                }`}
              >
                {t.label}
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
