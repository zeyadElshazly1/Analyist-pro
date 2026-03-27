type Props = {
    summary: Record<string, unknown> | null | undefined;
  };
  
  export function CleaningSummaryCards({ summary }: Props) {
    if (!summary || typeof summary !== "object") {
      return (
        <p className="text-sm text-white/60">
          No cleaning summary available.
        </p>
      );
    }
  
    const entries = Object.entries(summary);
  
    if (entries.length === 0) {
      return (
        <p className="text-sm text-white/60">
          No cleaning summary available.
        </p>
      );
    }
  
    return (
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        {entries.map(([key, value]) => (
          <div
            key={key}
            className="rounded-2xl border border-white/10 bg-white/5 p-4"
          >
            <p className="text-xs uppercase tracking-wide text-white/50">
              {key.replaceAll("_", " ")}
            </p>
            <p className="mt-2 text-lg font-semibold text-white">
              {typeof value === "object" ? JSON.stringify(value) : String(value)}
            </p>
          </div>
        ))}
      </div>
    );
  }