type Insight = {
    type?: string;
    confidence?: number;
    title?: string;
    finding?: string;
    action?: string;
    description?: string;
  };
  
  type Props = {
    insights: Insight[];
  };
  
  export function InsightsList({ insights }: Props) {
    if (!insights || insights.length === 0) {
      return <p className="text-white/60 text-sm">No insights found.</p>;
    }
  
    return (
      <div className="space-y-3">
        {insights.map((i, idx) => (
          <div
            key={idx}
            className="rounded-xl border border-white/10 bg-white/5 p-4"
          >
            <div className="flex flex-wrap items-center gap-2">
              <p className="text-white text-sm font-semibold">
                {i.title || i.type || "Insight"}
              </p>
  
              {i.type ? (
                <span className="rounded-full bg-white/10 px-2 py-1 text-xs text-white/70">
                  {i.type}
                </span>
              ) : null}
  
              {i.confidence !== undefined ? (
                <span className="rounded-full bg-white/10 px-2 py-1 text-xs text-white/70">
                  {i.confidence}% confidence
                </span>
              ) : null}
            </div>
  
            {i.finding || i.description ? (
              <p className="mt-2 text-sm text-white/70">
                {i.finding || i.description}
              </p>
            ) : null}
  
            {i.action ? (
              <p className="mt-3 text-sm text-white">
                Recommended action:{" "}
                <span className="text-white/70">{i.action}</span>
              </p>
            ) : null}
          </div>
        ))}
      </div>
    );
  }