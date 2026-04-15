"use client";

import { TrendingUp, AlertTriangle, CheckCircle2 } from "lucide-react";

type PanelItem = {
  title?: string;
  summary?: string;
  action?: string;
  type?: string;
  severity?: string;
};

type ExecutivePanelData = {
  opportunities: PanelItem[];
  risks: PanelItem[];
  action_plan: PanelItem[];
};

type Props = {
  panel: ExecutivePanelData;
};

const SEVERITY_DOT: Record<string, string> = {
  high:   "bg-red-400",
  medium: "bg-amber-400",
  low:    "bg-white/30",
};

export function ExecutivePanel({ panel }: Props) {
  if (!panel) return null;

  const { opportunities = [], risks = [], action_plan = [] } = panel;

  if (opportunities.length === 0 && risks.length === 0 && action_plan.length === 0) {
    return null;
  }

  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
      {/* Opportunities */}
      <div className="rounded-2xl border border-emerald-500/15 bg-emerald-500/[0.04] p-5">
        <div className="flex items-center gap-2 mb-4">
          <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-emerald-500/15">
            <TrendingUp className="h-3.5 w-3.5 text-emerald-400" strokeWidth={2} />
          </div>
          <h3 className="text-sm font-semibold text-white">Opportunities</h3>
          {opportunities.length > 0 && (
            <span className="ml-auto rounded-full bg-emerald-500/20 px-2 py-0.5 text-xs font-medium text-emerald-300">
              {opportunities.length}
            </span>
          )}
        </div>

        {opportunities.length === 0 ? (
          <p className="text-xs text-white/30 italic">No strong opportunities detected.</p>
        ) : (
          <ul className="space-y-3">
            {opportunities.map((item, i) => (
              <li key={i} className="flex items-start gap-2.5">
                <span className={`mt-1.5 h-1.5 w-1.5 flex-shrink-0 rounded-full ${SEVERITY_DOT[item.severity ?? "medium"]}`} />
                <div className="min-w-0">
                  <p className="text-xs font-medium text-white leading-snug">{item.title}</p>
                  {item.summary && (
                    <p className="mt-0.5 text-xs text-white/45 leading-relaxed line-clamp-2">{item.summary}</p>
                  )}
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>

      {/* Risks */}
      <div className="rounded-2xl border border-red-500/15 bg-red-500/[0.04] p-5">
        <div className="flex items-center gap-2 mb-4">
          <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-red-500/15">
            <AlertTriangle className="h-3.5 w-3.5 text-red-400" strokeWidth={2} />
          </div>
          <h3 className="text-sm font-semibold text-white">Risks</h3>
          {risks.length > 0 && (
            <span className="ml-auto rounded-full bg-red-500/20 px-2 py-0.5 text-xs font-medium text-red-300">
              {risks.length}
            </span>
          )}
        </div>

        {risks.length === 0 ? (
          <p className="text-xs text-white/30 italic">No significant risks detected.</p>
        ) : (
          <ul className="space-y-3">
            {risks.map((item, i) => (
              <li key={i} className="flex items-start gap-2.5">
                <span className={`mt-1.5 h-1.5 w-1.5 flex-shrink-0 rounded-full ${SEVERITY_DOT[item.severity ?? "medium"]}`} />
                <div className="min-w-0">
                  <p className="text-xs font-medium text-white leading-snug">{item.title}</p>
                  {item.summary && (
                    <p className="mt-0.5 text-xs text-white/45 leading-relaxed line-clamp-2">{item.summary}</p>
                  )}
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>

      {/* Action Plan */}
      <div className="rounded-2xl border border-indigo-500/15 bg-indigo-500/[0.04] p-5">
        <div className="flex items-center gap-2 mb-4">
          <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-indigo-500/15">
            <CheckCircle2 className="h-3.5 w-3.5 text-indigo-400" strokeWidth={2} />
          </div>
          <h3 className="text-sm font-semibold text-white">Action Plan</h3>
          {action_plan.length > 0 && (
            <span className="ml-auto rounded-full bg-indigo-500/20 px-2 py-0.5 text-xs font-medium text-indigo-300">
              {action_plan.length}
            </span>
          )}
        </div>

        {action_plan.length === 0 ? (
          <p className="text-xs text-white/30 italic">No actions required at this time.</p>
        ) : (
          <ol className="space-y-3">
            {action_plan.map((item, i) => (
              <li key={i} className="flex items-start gap-2.5">
                <span className="mt-0.5 flex h-4 w-4 flex-shrink-0 items-center justify-center rounded-full bg-indigo-500/20 text-[10px] font-semibold text-indigo-300">
                  {i + 1}
                </span>
                <p className="text-xs text-white/60 leading-relaxed line-clamp-3">{item.action}</p>
              </li>
            ))}
          </ol>
        )}
      </div>
    </div>
  );
}
