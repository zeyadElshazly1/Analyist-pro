import { Lightbulb } from "lucide-react";

type Insight = { action?: string; title?: string };
type Props = { insights: Insight[] };

export function RecommendedAction({ insights }: Props) {
  const first = insights?.find((i) => i.action);

  return (
    <div className="rounded-xl border border-indigo-500/15 bg-indigo-500/5 p-5">
      <div className="flex items-center gap-2 mb-3">
        <Lightbulb className="h-4 w-4 text-indigo-400" />
        <p className="text-sm font-medium text-indigo-300">Recommended next action</p>
      </div>
      {first ? (
        <>
          <p className="text-sm text-white/60">
            Based on <span className="font-medium text-white">{first.title || "top insight"}</span>:
          </p>
          <p className="mt-2 text-sm text-white/80">{first.action}</p>
        </>
      ) : (
        <p className="text-sm text-white/60">
          Run a deeper analysis on the most important business metric in this dataset.
        </p>
      )}
    </div>
  );
}
