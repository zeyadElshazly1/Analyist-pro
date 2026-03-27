"use client";

type Props = {
  value: string;
  onChange: (v: string) => void;
};

const tabs = [
  { id: "overview", label: "Overview" },
  { id: "columns", label: "Columns" },
  { id: "insights", label: "Insights" },
  { id: "cleaning", label: "Cleaning" },
  { id: "charts", label: "Charts" },
];

export function ProjectTabs({ value, onChange }: Props) {
  return (
    <div className="flex flex-wrap gap-2 border-b border-white/10 pb-2">
      {tabs.map((t) => (
        <button
          key={t.id}
          onClick={() => onChange(t.id)}
          className={`rounded-lg px-4 py-2 text-sm transition ${
            value === t.id
              ? "bg-white/10 text-white"
              : "text-white/60 hover:text-white"
          }`}
        >
          {t.label}
        </button>
      ))}
    </div>
  );
}