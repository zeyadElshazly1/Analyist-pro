"use client";

import { useState } from "react";
import { ChevronDown, ChevronUp } from "lucide-react";

type Props = {
  value: string;
  onChange: (v: string) => void;
};

const STEPS = [
  {
    id: "intake",
    label: "Intake",
    number: 1,
    primaryTab: "overview",
    tabs: [
      { id: "overview", label: "Summary" },
      { id: "data-table", label: "Raw data" },
    ],
  },
  {
    id: "health",
    label: "Health",
    number: 2,
    primaryTab: "profile",
    tabs: [
      { id: "profile", label: "Column profiles" },
      { id: "cleaning", label: "Cleaning log" },
    ],
  },
  {
    id: "insights",
    label: "Insights",
    number: 3,
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
    label: "Compare",
    number: 4,
    primaryTab: "compare-files",
    tabs: [
      { id: "compare-files", label: "Compare files" },
      { id: "compare-cols", label: "Compare columns" },
      { id: "diff", label: "Diff runs" },
    ],
  },
  {
    id: "report",
    label: "Report",
    number: 5,
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

export function ProjectTabs({ value, onChange }: Props) {
  const [advancedOpen, setAdvancedOpen] = useState(false);

  const activeStepId = TAB_TO_STEP[value] ?? STEPS[0].id;
  const activeStep = STEPS.find((s) => s.id === activeStepId) ?? STEPS[0];
  const isAdvanced = ADVANCED_TABS.some((t) => t.id === value);

  function handleStepClick(step: typeof STEPS[number]) {
    onChange(step.primaryTab);
  }

  return (
    <div className="space-y-2">
      {/* ── Step progress bar ───────────────────────────────────────────── */}
      <div className="overflow-x-auto [scrollbar-width:none] [-ms-overflow-style:none] [&::-webkit-scrollbar]:hidden">
        <div className="flex items-center gap-1 min-w-max">
          {STEPS.map((step, idx) => {
            const isActive = step.id === activeStepId && !isAdvanced;
            const isDone =
              !isAdvanced &&
              STEPS.findIndex((s) => s.id === activeStepId) > idx;
            return (
              <div key={step.id} className="flex items-center gap-1">
                <button
                  onClick={() => handleStepClick(step)}
                  className={`flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium transition-colors whitespace-nowrap ${
                    isActive
                      ? "bg-indigo-600 text-white"
                      : isDone
                      ? "bg-indigo-600/20 text-indigo-300 hover:bg-indigo-600/30"
                      : "text-white/40 hover:text-white hover:bg-white/[0.05]"
                  }`}
                >
                  <span
                    className={`flex h-5 w-5 flex-shrink-0 items-center justify-center rounded-full text-[10px] font-bold ${
                      isActive
                        ? "bg-white/20 text-white"
                        : isDone
                        ? "bg-indigo-500/40 text-indigo-200"
                        : "bg-white/10 text-white/40"
                    }`}
                  >
                    {step.number}
                  </span>
                  {step.label}
                </button>
                {idx < STEPS.length - 1 && (
                  <div className="h-px w-4 bg-white/[0.08] flex-shrink-0" />
                )}
              </div>
            );
          })}
        </div>
      </div>

      {/* ── Sub-tabs for active step ────────────────────────────────────── */}
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

      {/* ── Advanced drawer ─────────────────────────────────────────────── */}
      <div>
        <button
          onClick={() => setAdvancedOpen((o) => !o)}
          className="flex items-center gap-1.5 text-xs text-white/25 hover:text-white/50 transition-colors"
        >
          {advancedOpen ? (
            <ChevronUp className="h-3 w-3" />
          ) : (
            <ChevronDown className="h-3 w-3" />
          )}
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
