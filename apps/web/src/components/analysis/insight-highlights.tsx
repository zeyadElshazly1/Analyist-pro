type Insight = {
    title?: string;
    finding?: string;
    type?: string;
  };
  
  type Props = {
    insights: Insight[];
  };
  
  export function InsightHighlights({ insights }: Props) {
    if (!insights || insights.length === 0) {
      return (
        <p className="text-sm text-white/60">
          No key highlights available.
        </p>
      );
    }
  
    const topThree = insights.slice(0, 3);
  
    return (
      <div className="grid gap-4 md:grid-cols-3">
        {topThree.map((insight, index) => (
          <div
            key={`${insight.title}-${index}`}
            className="rounded-2xl border border-white/10 bg-white/5 p-4"
          >
            <p className="text-xs uppercase tracking-wide text-white/50">
              Highlight {index + 1}
            </p>
            <p className="mt-2 font-semibold text-white">
              {insight.title || insight.type || "Insight"}
            </p>
            <p className="mt-2 text-sm text-white/70">
              {insight.finding || "No finding available."}
            </p>
          </div>
        ))}
      </div>
    );
  }