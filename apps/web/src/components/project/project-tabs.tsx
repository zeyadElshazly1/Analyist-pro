"use client";

type Props = { value: string; onChange: (v: string) => void };

const TABS = [
  { id: "overview",      label: "Overview" },
  { id: "profile",       label: "Profile" },
  { id: "insights",      label: "Insights" },
  { id: "cleaning",      label: "Cleaning" },
  { id: "charts",        label: "Charts" },
  { id: "timeseries",    label: "Time Series" },
  { id: "duplicates",    label: "Duplicates" },
  { id: "outliers",      label: "Outliers" },
  { id: "correlations",  label: "Correlations" },
  { id: "compare",       label: "Compare Cols" },
  { id: "multifile",     label: "Compare Files" },
];

export function ProjectTabs({ value, onChange }: Props) {
  return (
    <div className="flex gap-1 overflow-x-auto rounded-xl border border-white/[0.07] bg-white/[0.03] p-1 [scrollbar-width:none]">
      {TABS.map((tab) => (
        <button
          key={tab.id}
          onClick={() => onChange(tab.id)}
          className={`flex-shrink-0 whitespace-nowrap rounded-lg px-3 py-1.5 text-sm font-medium transition-colors ${
            value === tab.id
              ? "bg-indigo-600 text-white shadow-sm"
              : "text-white/50 hover:text-white"
          }`}
        >
          {tab.label}
        </button>
      ))}
    </div>
  );
}
