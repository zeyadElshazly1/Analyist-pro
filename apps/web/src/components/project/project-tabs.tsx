"use client";

type Props = {
  value: string;
  onChange: (v: string) => void;
};

const tabs = [
  { id: "overview", label: "Overview" },
  { id: "profile", label: "Profile" },
  { id: "insights", label: "Insights" },
  { id: "cleaning", label: "Cleaning" },
  { id: "charts", label: "Charts" },
  { id: "timeseries", label: "Time Series" },
  { id: "duplicates", label: "Duplicates" },
  { id: "outliers", label: "Outliers" },
  { id: "correlations", label: "Correlations" },
  { id: "compare-cols", label: "Compare Cols" },
  { id: "compare-files", label: "Compare Files" },
  { id: "predictions", label: "Predictions" },
  { id: "ask-ai", label: "Ask AI" },
  { id: "pivot", label: "Pivot" },
  { id: "segments", label: "Segments" },
  { id: "ab-tests", label: "A/B Tests" },
  { id: "query", label: "SQL Query" },
];

export function ProjectTabs({ value, onChange }: Props) {
  return (
    <div className="overflow-x-auto [scrollbar-width:none] [-ms-overflow-style:none] [&::-webkit-scrollbar]:hidden">
      <div className="flex gap-1 border-b border-white/[0.07] pb-2 min-w-max">
        {tabs.map((t) => (
          <button
            key={t.id}
            onClick={() => onChange(t.id)}
            className={`rounded-lg px-4 py-2 text-sm font-medium transition-colors whitespace-nowrap ${
              value === t.id
                ? "bg-indigo-600 text-white"
                : "text-white/50 hover:text-white hover:bg-white/[0.05]"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>
    </div>
  );
}
