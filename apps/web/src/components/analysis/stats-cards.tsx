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
      { label: "Rows", value: summary.rows },
      { label: "Columns", value: summary.columns },
      { label: "Numeric", value: summary.numeric_cols },
      { label: "Categorical", value: summary.categorical_cols },
      { label: "Missing %", value: summary.missing_pct },
    ];
  
    return (
      <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
        {items.map((item) => (
          <div
            key={item.label}
            className="rounded-2xl border border-white/10 bg-white/5 p-4"
          >
            <p className="text-xs text-white/60">{item.label}</p>
            <p className="text-xl font-semibold text-white mt-1">
              {item.value}
            </p>
          </div>
        ))}
      </div>
    );
  }