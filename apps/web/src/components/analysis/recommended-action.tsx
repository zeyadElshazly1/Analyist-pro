type Insight = {
    action?: string;
    title?: string;
  };
  
  type Props = {
    insights: Insight[];
  };
  
  export function RecommendedAction({ insights }: Props) {
    const firstWithAction = insights?.find((i) => i.action);
  
    if (!firstWithAction) {
      return (
        <div className="rounded-2xl border border-white/10 bg-white/5 p-5">
          <p className="text-sm font-medium text-white">Recommended next action</p>
          <p className="mt-2 text-sm text-white/60">
            Run a deeper analysis on the most important business metric in this dataset.
          </p>
        </div>
      );
    }
  
    return (
      <div className="rounded-2xl border border-white/10 bg-white/5 p-5">
        <p className="text-sm font-medium text-white">Recommended next action</p>
        <p className="mt-2 text-sm text-white/70">
          Based on <span className="font-medium text-white">{firstWithAction.title || "top insight"}</span>,
          the next best move is:
        </p>
        <p className="mt-3 text-sm text-white">{firstWithAction.action}</p>
      </div>
    );
  }