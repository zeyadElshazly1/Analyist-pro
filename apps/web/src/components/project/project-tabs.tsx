"use client";

type Props = {
  value: string;
  onChange: (v: string) => void;
};

const TAB_GROUPS = [
  {
    id: "data-group",
    label: "Data",
    tabs: [
      { id: "data-table", label: "Table" },
    ],
  },
  {
    id: "overview-group",
    label: "Overview",
    tabs: [
      { id: "overview", label: "Summary" },
      { id: "profile", label: "Columns" },
      { id: "insights", label: "Insights" },
      { id: "cleaning", label: "Cleaning" },
    ],
  },
  {
    id: "explore-group",
    label: "Explore",
    tabs: [
      { id: "charts", label: "Charts" },
      { id: "timeseries", label: "Time Series" },
      { id: "correlations", label: "Correlations" },
      { id: "duplicates", label: "Duplicates" },
      { id: "outliers", label: "Outliers" },
    ],
  },
  {
    id: "compare-group",
    label: "Compare",
    tabs: [
      { id: "compare-cols", label: "Columns" },
      { id: "compare-files", label: "Files" },
      { id: "join", label: "Join" },
      { id: "diff", label: "Diff Runs" },
    ],
  },
  {
    id: "test-group",
    label: "Test",
    tabs: [
      { id: "segments", label: "Segments" },
      { id: "ab-tests", label: "A/B Tests" },
      { id: "pivot", label: "Pivot" },
    ],
  },
  {
    id: "predict-group",
    label: "Predict",
    tabs: [
      { id: "predictions", label: "AutoML" },
    ],
  },
  {
    id: "build-group",
    label: "Build",
    tabs: [
      { id: "query", label: "SQL" },
      { id: "ask-ai", label: "Ask AI" },
      { id: "story", label: "Story" },
    ],
  },
];

// Map each tab id to its group id
const TAB_TO_GROUP: Record<string, string> = {};
for (const group of TAB_GROUPS) {
  for (const tab of group.tabs) {
    TAB_TO_GROUP[tab.id] = group.id;
  }
}

export function ProjectTabs({ value, onChange }: Props) {
  const activeGroupId = TAB_TO_GROUP[value] ?? TAB_GROUPS[0].id;
  const activeGroup = TAB_GROUPS.find((g) => g.id === activeGroupId) ?? TAB_GROUPS[0];

  function handleGroupClick(groupId: string) {
    const group = TAB_GROUPS.find((g) => g.id === groupId);
    if (group) onChange(group.tabs[0].id);
  }

  return (
    <div className="space-y-1">
      {/* ── Group row ──────────────────────────────────────────────────────── */}
      <div className="overflow-x-auto [scrollbar-width:none] [-ms-overflow-style:none] [&::-webkit-scrollbar]:hidden">
        <div className="flex gap-1 min-w-max">
          {TAB_GROUPS.map((group) => {
            const isActive = group.id === activeGroupId;
            return (
              <button
                key={group.id}
                onClick={() => handleGroupClick(group.id)}
                className={`rounded-lg px-4 py-2 text-sm font-semibold transition-colors whitespace-nowrap ${
                  isActive
                    ? "bg-indigo-600 text-white"
                    : "text-white/50 hover:text-white hover:bg-white/[0.05]"
                }`}
              >
                {group.label}
              </button>
            );
          })}
        </div>
      </div>

      {/* ── Sub-tab row ────────────────────────────────────────────────────── */}
      {activeGroup.tabs.length > 1 && (
        <div className="overflow-x-auto [scrollbar-width:none] [-ms-overflow-style:none] [&::-webkit-scrollbar]:hidden">
          <div className="flex gap-1 border-b border-white/[0.07] pb-2 min-w-max">
            {activeGroup.tabs.map((t) => (
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
    </div>
  );
}
