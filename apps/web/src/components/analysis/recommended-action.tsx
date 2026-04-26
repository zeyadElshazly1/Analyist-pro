import { Lightbulb, ArrowRight } from "lucide-react";

type Insight = {
  title?: string;
  recommendation?: string;
  action?: string;
  report_safe?: boolean;
  severity?: string;
  confidence?: number;
  category?: string;
  type?: string;
};

type Props = { insights: Insight[] };

function isReportSafe(i: Insight): boolean {
  if (typeof i.report_safe === "boolean") return i.report_safe;
  const conf = i.confidence === undefined ? 0 : (i.confidence <= 1 ? i.confidence * 100 : i.confidence);
  const cat  = i.category ?? i.type ?? "";
  return (
    (i.severity === "high" || i.severity === "medium") &&
    conf >= 60 &&
    cat !== "data_quality" && cat !== "missing_pattern"
  );
}

function sortKey(i: Insight): number {
  const sev  = i.severity === "high" ? 0 : i.severity === "medium" ? 1 : 2;
  const safe = isReportSafe(i) ? 0 : 1;
  const conf = i.confidence === undefined ? 50 : (i.confidence <= 1 ? i.confidence * 100 : i.confidence);
  return safe * 1000 + sev * 100 + (100 - conf);
}

export function RecommendedAction({ insights }: Props) {
  if (!insights?.length) return null;

  // Up to 3 actions, prioritised: report-safe first, then by severity + confidence
  const withAction = insights
    .filter((i) => !!(i.recommendation ?? i.action))
    .sort((a, b) => sortKey(a) - sortKey(b))
    .slice(0, 3);

  if (withAction.length === 0) return null;

  const primary = withAction[0];
  const rest    = withAction.slice(1);

  return (
    <div className="rounded-xl border border-indigo-500/15 bg-indigo-500/[0.05] p-4 space-y-3">
      <div className="flex items-center gap-2">
        <Lightbulb className="h-4 w-4 text-indigo-400 flex-shrink-0" />
        <p className="text-sm font-semibold text-indigo-300">
          {withAction.length === 1 ? "Top recommended action" : "Recommended actions"}
        </p>
      </div>

      {/* Primary action */}
      <div className="rounded-lg border border-indigo-500/10 bg-indigo-500/[0.06] px-4 py-3">
        <p className="mb-1 text-[10px] text-indigo-400/60 font-medium uppercase tracking-wider">
          Based on: {primary.title || "top insight"}
          {isReportSafe(primary) && (
            <span className="ml-2 text-emerald-400/70">· Report-ready</span>
          )}
        </p>
        <p className="text-sm text-white/80 leading-relaxed">
          {primary.recommendation ?? primary.action}
        </p>
      </div>

      {/* Secondary actions */}
      {rest.length > 0 && (
        <div className="space-y-1.5">
          {rest.map((insight, i) => (
            <div key={i} className="flex items-start gap-2 rounded-lg border border-white/[0.05] bg-white/[0.02] px-3 py-2">
              <ArrowRight className="mt-0.5 h-3.5 w-3.5 flex-shrink-0 text-indigo-400/40" />
              <div>
                <p className="text-[10px] text-white/30 mb-0.5">{insight.title || "Additional finding"}</p>
                <p className="text-xs text-white/55 leading-relaxed">{insight.recommendation ?? insight.action}</p>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
