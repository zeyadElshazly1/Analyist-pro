type Props = {
  summary: {
    rows: number;
    columns: number;
    numeric_cols: number;
    categorical_cols: number;
    missing_pct: number;
  };
};

export function StatsCards({ summary }: Props) {
  const items = [
    { label: "Rows", value: summary.rows.toLocaleString() },
    { label: "Columns", value: summary.columns },
    { label: "Numeric", value: summary.numeric_cols },
    { label: "Categorical", value: summary.categorical_cols },
    { label: "Missing", value: `${summary.missing_pct}%`, warn: summary.missing_pct > 10 },
  ];

  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 md:grid-cols-5">
      {items.map((item) => (
        <div key={item.label} className="rounded-xl border border-white/[0.07] bg-white/[0.03] p-4">
          <p className="text-xs text-white/40">{item.label}</p>
          <p className={`mt-1.5 text-2xl font-semibold ${"warn" in item && item.warn ? "text-amber-400" : "text-white"}`}>
            {item.value}
          </p>
        </div>
      ))}
    </div>
  );
}
