"use client";

import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react";
import {
  Bar,
  BarChart,
  Cell,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import {
  Activity,
  ArrowRight,
  BarChart3,
  ClipboardList,
  FileText,
  LayoutDashboard,
  Loader2,
  ShieldCheck,
} from "lucide-react";
import type { AnalysisPlan, LargeDatasetMeta } from "@/lib/api";
import { ApiError, getSuggestedCharts } from "@/lib/api";
import type { SuggestedChartPayload } from "@/lib/chart-payload";
import { formatChartValue } from "@/lib/chart-format";
import { RecommendedAction } from "@/components/analysis/recommended-action";

// ── Insight helpers (mirror RecommendedAction — display only, no pipeline logic) ──

type DashboardInsight = {
  insight_id?: string;
  title?: string;
  recommendation?: string;
  action?: string;
  report_safe?: boolean;
  severity?: string;
  confidence?: number;
  category?: string;
  type?: string;
  explanation?: string;
  finding?: string;
};

function confPct(i: DashboardInsight, fallback: number): number {
  if (typeof i.confidence !== "number" || !Number.isFinite(i.confidence)) {
    return fallback;
  }
  return Math.max(0, Math.min(100, i.confidence * 100));
}

function isReportSafe(i: DashboardInsight): boolean {
  if (typeof i.report_safe === "boolean") return i.report_safe;
  const conf = confPct(i, 0);
  const cat = i.category ?? i.type ?? "";
  return (
    (i.severity === "high" || i.severity === "medium") &&
    conf >= 60 &&
    cat !== "data_quality" &&
    cat !== "missing_pattern"
  );
}

function findingSortKey(i: DashboardInsight): number {
  const sev = i.severity === "high" ? 0 : i.severity === "medium" ? 1 : 2;
  const safe = isReportSafe(i) ? 0 : 1;
  const conf = confPct(i, 50);
  return safe * 1000 + sev * 100 + (100 - conf);
}

function insightHeadline(i: DashboardInsight): string {
  return (
    (i.title ?? "").trim() ||
    (i.explanation ?? "").trim().slice(0, 120) ||
    (i.finding ?? "").trim().slice(0, 120) ||
    "Finding"
  );
}

function insightBody(i: DashboardInsight): string {
  return (
    (i.recommendation ?? "").trim() ||
    (i.action ?? "").trim() ||
    (i.explanation ?? "").trim() ||
    (i.finding ?? "").trim() ||
    ""
  );
}

// ── Dataset / health (display helpers from existing result shapes) ────────────

const DATASET_KIND_LABELS: Record<string, string> = {
  sales: "Sales",
  finance: "Finance / Market",
  insurance: "Insurance",
  hr: "HR / People",
  marketing: "Marketing",
  operations: "Operations",
  research: "Research",
  generic: "General dataset",
};

const HEALTH_DATASET_TYPE_LABELS: Record<string, string> = {
  timeseries: "Time Series",
  transactional: "Transactional",
  survey: "Survey",
  general: "General",
  financial_markets_snapshot: "Financial Markets Snapshot",
  financial_markets_timeseries: "Financial Markets Time Series",
};

function kindLabel(kind: string): string {
  return DATASET_KIND_LABELS[kind] ?? kind.replace(/_/g, " ");
}

type HealthScoreShape = {
  total?: number;
  score?: number;
  grade?: string;
};

function healthTotalFromBlocks(
  health_score: HealthScoreShape | null | undefined,
  health_result: Record<string, unknown> | null | undefined,
): number | null {
  if (health_score && typeof health_score === "object") {
    if (typeof health_score.total === "number" && Number.isFinite(health_score.total)) {
      return health_score.total;
    }
    if (typeof health_score.score === "number" && Number.isFinite(health_score.score)) {
      return health_score.score;
    }
  }
  const hr = health_result as { health_score?: { total_score?: number } } | null | undefined;
  const ts = hr?.health_score?.total_score;
  if (typeof ts === "number" && Number.isFinite(ts)) return ts;
  return null;
}

type DatasetSummary = {
  rows?: number;
  columns?: number;
  domain?: string;
  analyzed_rows?: number;
} | null;

type HealthResultLite = {
  row_count?: number;
  column_count?: number;
  health_score?: { dataset_type?: string };
} | null;

function rowColCounts(
  summary: DatasetSummary,
  healthResult: HealthResultLite,
  largeDataset?: LargeDatasetMeta,
): { rows: number; cols: number } {
  const rows =
    healthResult?.row_count ??
    summary?.rows ??
    largeDataset?.analyzed_rows ??
    largeDataset?.full_rows ??
    0;
  const cols = healthResult?.column_count ?? summary?.columns ?? largeDataset?.full_columns ?? 0;
  return { rows, cols };
}

function datasetKindDisplay(
  plan: AnalysisPlan | null | undefined,
  healthResult: HealthResultLite,
  summary: DatasetSummary,
): string {
  if (plan?.dataset_kind) return kindLabel(plan.dataset_kind);
  const dt = healthResult?.health_score?.dataset_type;
  if (dt) return HEALTH_DATASET_TYPE_LABELS[dt] ?? dt.replace(/_/g, " ");
  if (summary?.domain) return summary.domain;
  return "General dataset";
}

function planOrInsightsConfidence(
  plan: AnalysisPlan | null | undefined,
  insights: DashboardInsight[],
): { label: string; value: string; sub?: string } {
  if (plan && typeof plan.confidence === "number" && Number.isFinite(plan.confidence)) {
    const pct = Math.round(plan.confidence * 100);
    return {
      label: "Classification",
      value: `${pct}%`,
      sub: "Dataset intelligence",
    };
  }
  if (!insights.length) {
    return { label: "Confidence", value: "—", sub: "Run insights to score" };
  }
  const vals = insights
    .map((i) => (typeof i.confidence === "number" && Number.isFinite(i.confidence) ? confPct(i, NaN) : NaN))
    .filter((n) => Number.isFinite(n));
  if (vals.length === 0) {
    return { label: "Confidence", value: "—", sub: "Insights pending" };
  }
  const avg = Math.round(vals.reduce((a, b) => a + b, 0) / vals.length);
  return { label: "Avg. insight confidence", value: `${avg}%`, sub: "Across findings" };
}

function buildExecutiveStory(narrative: string | undefined, insights: DashboardInsight[]): string {
  const n = narrative?.trim();
  if (n) {
    const parts = n.split(/(?<=[.!?])\s+/).filter(Boolean);
    const joined = parts.slice(0, 3).join(" ");
    return joined.length >= 40 ? joined : n.slice(0, 420).trim();
  }
  const lines = insights
    .slice(0, 3)
    .map((i) => insightHeadline(i))
    .filter(Boolean);
  if (lines.length === 0) {
    return "Run the analysis pipeline to generate findings, then review charts and the report builder for client delivery.";
  }
  return lines.join(" ");
}

function truncate(text: string, max: number): string {
  const t = text.trim();
  if (t.length <= max) return t;
  return `${t.slice(0, max - 1)}…`;
}

// ── Compact charts ─────────────────────────────────────────────────────────────

const CHART_COLORS = ["#818cf8", "#34d399", "#fbbf24", "#f472b6", "#22d3ee"];

function rowNumeric(row: Record<string, unknown>, key: string): number | null {
  const v = row[key];
  if (typeof v === "number" && Number.isFinite(v)) return v;
  if (typeof v === "string") {
    const n = Number.parseFloat(v.replace(/,/g, ""));
    return Number.isFinite(n) ? n : null;
  }
  return null;
}

const MINI_TOOLTIP = {
  contentStyle: {
    background: "#111118",
    border: "1px solid rgba(255,255,255,0.08)",
    borderRadius: 8,
    fontSize: 11,
    color: "#fff",
  },
};

function MiniChartPreview({ chart }: { chart: SuggestedChartPayload }) {
  const rows = chart.data ?? [];
  const slice = rows.slice(0, 10);
  const xk = chart.x_key;
  const yk = chart.y_key;

  const barData = slice
    .map((row, i) => {
      const y = rowNumeric(row, yk);
      const rawX = row[xk];
      const x =
        rawX != null && String(rawX).trim()
          ? String(rawX).trim().slice(0, 14)
          : `•${i + 1}`;
      return { x, y: y ?? 0, __hasY: y != null };
    })
    .filter((d) => d.__hasY);

  const lineData = slice
    .map((row, i) => {
      const y = rowNumeric(row, yk);
      return { i, y: y ?? 0, __hasY: y != null };
    })
    .filter((d) => d.__hasY);

  const h = 88;

  if (chart.type === "bar" && barData.length >= 2) {
    return (
      <ResponsiveContainer width="100%" height={h}>
        <BarChart data={barData} margin={{ top: 4, right: 4, left: -18, bottom: 0 }}>
          <XAxis dataKey="x" tick={{ fill: "rgba(255,255,255,0.35)", fontSize: 9 }} axisLine={false} tickLine={false} />
          <YAxis hide domain={["auto", "auto"]} />
          <Tooltip
            cursor={{ fill: "rgba(255,255,255,0.04)" }}
            contentStyle={MINI_TOOLTIP.contentStyle}
            formatter={(v: unknown) => [
              chart.value_format === "percent"
                ? formatChartValue(v, "percent", chart.value_scale ?? "decimal")
                : String(v ?? "—"),
              chart.y_label ?? "Value",
            ]}
          />
          <Bar dataKey="y" radius={[4, 4, 0, 0]}>
            {barData.map((_, i) => (
              <Cell key={i} fill={CHART_COLORS[i % CHART_COLORS.length]} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    );
  }

  if (chart.type === "line" && lineData.length >= 2) {
    return (
      <ResponsiveContainer width="100%" height={h}>
        <LineChart data={lineData} margin={{ top: 4, right: 4, left: -18, bottom: 0 }}>
          <XAxis dataKey="i" hide />
          <YAxis hide domain={["auto", "auto"]} />
          <Tooltip contentStyle={MINI_TOOLTIP.contentStyle} />
          <Line type="monotone" dataKey="y" stroke="#818cf8" strokeWidth={2} dot={false} />
        </LineChart>
      </ResponsiveContainer>
    );
  }

  return (
    <div className="flex h-[88px] items-center justify-center rounded-lg bg-white/[0.03]">
      <BarChart3 className="h-8 w-8 text-white/15" aria-hidden />
    </div>
  );
}

function pickPreviewCharts(raw: SuggestedChartPayload[]): SuggestedChartPayload[] {
  const out: SuggestedChartPayload[] = [];
  const preferred = ["bar", "line", "pie", "scatter"] as const;
  for (const t of preferred) {
    for (const c of raw) {
      if (c.type !== t) continue;
      if (!c.data?.length) continue;
      if (out.length >= 4) return out;
      if (!out.includes(c)) out.push(c);
    }
  }
  for (const c of raw) {
    if (!c.data?.length) continue;
    if (out.length >= 4) break;
    if (!out.includes(c)) out.push(c);
  }
  return out.slice(0, 4);
}

// ── Exported dashboard ─────────────────────────────────────────────────────────

export type BusinessDashboardProps = {
  projectId: number;
  dataset_summary?: DatasetSummary;
  analysis_plan?: AnalysisPlan | null;
  health_score?: HealthScoreShape | null;
  health_result?: Record<string, unknown> | null;
  narrative?: string | null;
  insights: DashboardInsight[];
  largeDataset?: LargeDatasetMeta;
  onNavigateToTab: (tabId: string) => void;
};

export function BusinessDashboard({
  projectId,
  dataset_summary,
  analysis_plan,
  health_score,
  health_result,
  narrative,
  insights,
  largeDataset,
  onNavigateToTab,
}: BusinessDashboardProps) {
  const healthResultLite = health_result as HealthResultLite;
  const [charts, setCharts] = useState<SuggestedChartPayload[]>([]);
  const [chartsLoading, setChartsLoading] = useState(true);
  const [chartsError, setChartsError] = useState(false);

  const loadCharts = useCallback(async () => {
    setChartsLoading(true);
    setChartsError(false);
    try {
      const res = await getSuggestedCharts(projectId);
      setCharts(pickPreviewCharts(res.charts ?? []));
    } catch (e) {
      if (!(e instanceof ApiError && e.status === 401)) {
        setChartsError(true);
      }
      setCharts([]);
    } finally {
      setChartsLoading(false);
    }
  }, [projectId]);

  useEffect(() => {
    loadCharts();
  }, [loadCharts]);

  const healthNum = healthTotalFromBlocks(health_score, health_result);
  const { rows, cols } = rowColCounts(dataset_summary ?? null, healthResultLite, largeDataset);
  const safeCount = useMemo(() => insights.filter(isReportSafe).length, [insights]);
  const confBlock = planOrInsightsConfidence(analysis_plan ?? undefined, insights);
  const datasetKind = datasetKindDisplay(analysis_plan ?? undefined, healthResultLite, dataset_summary ?? null);

  const keyFindings = useMemo(() => {
    return [...insights].sort((a, b) => findingSortKey(a) - findingSortKey(b)).slice(0, 5);
  }, [insights]);

  const storyText = buildExecutiveStory(narrative ?? undefined, insights);

  return (
    <section className="rounded-xl border border-white/[0.07] bg-gradient-to-b from-white/[0.05] to-white/[0.02] p-5 shadow-[inset_0_1px_0_0_rgba(255,255,255,0.04)] sm:p-6 lg:p-8">
      <div className="mb-6 flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="flex items-start gap-3">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-indigo-600/20 border border-indigo-500/25">
            <LayoutDashboard className="h-5 w-5 text-indigo-300" aria-hidden />
          </div>
          <div>
            <h2 className="text-lg font-semibold tracking-tight text-white">Executive overview</h2>
            <p className="mt-0.5 text-xs text-white/40">
              Consultant-ready snapshot of this dataset — refine details in each workflow tab.
            </p>
          </div>
        </div>
      </div>

      {/* 1. Executive summary strip */}
      <div className="flex flex-wrap gap-2 sm:gap-3">
        <MetricPill icon={<FileText className="h-3.5 w-3.5" />} label="Dataset kind" value={datasetKind} accent="indigo" />
        <MetricPill icon={<Activity className="h-3.5 w-3.5" />} label={confBlock.label} value={confBlock.value} hint={confBlock.sub} accent="slate" />
        <MetricPill
          icon={<ShieldCheck className="h-3.5 w-3.5" />}
          label="Health score"
          value={healthNum != null ? `${Math.round(healthNum)}` : "—"}
          hint={health_score?.grade ? `Grade ${health_score.grade}` : undefined}
          accent="emerald"
        />
        <MetricPill
          icon={<BarChart3 className="h-3.5 w-3.5" />}
          label="Shape"
          value={`${typeof rows === "number" ? rows.toLocaleString() : rows} × ${cols}`}
          hint="rows × columns"
          accent="slate"
        />
        <MetricPill icon={<ClipboardList className="h-3.5 w-3.5" />} label="Findings" value={`${insights.length}`} accent="slate" />
        <MetricPill
          icon={<ShieldCheck className="h-3.5 w-3.5" />}
          label="Report-ready"
          value={`${safeCount}`}
          hint="Findings tagged for client reports"
          accent="amber"
        />
      </div>

      <div className="mt-8 grid grid-cols-1 gap-6 lg:grid-cols-2 lg:gap-8 lg:items-start">
        {/* Left column */}
        <div className="space-y-6 min-w-0">
          {/* 2. Business story */}
          <div className="rounded-xl border border-white/[0.06] bg-white/[0.03] p-5">
            <p className="mb-2 text-[10px] font-semibold uppercase tracking-[0.14em] text-white/35">Business story</p>
            <p className="text-sm leading-relaxed text-white/75">{storyText}</p>
          </div>

          {/* 3. Key findings board */}
          <div className="rounded-xl border border-white/[0.06] bg-white/[0.03] p-5">
            <div className="mb-4 flex items-center justify-between gap-3">
              <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-white/35">Key findings</p>
              <button
                type="button"
                onClick={() => onNavigateToTab("insights")}
                className="text-[11px] font-medium text-indigo-400 hover:text-indigo-300 transition-colors"
              >
                Open all findings →
              </button>
            </div>
            {keyFindings.length === 0 ? (
              <p className="text-xs text-white/35">No findings yet — complete analysis or check other tabs.</p>
            ) : (
              <ul className="space-y-3">
                {keyFindings.map((insight, idx) => {
                  const body = truncate(insightBody(insight), 140);
                  const sev = (insight.severity ?? "medium").toLowerCase();
                  const sevClass =
                    sev === "high"
                      ? "border-rose-500/25 bg-rose-500/10 text-rose-300"
                      : sev === "low"
                        ? "border-white/10 bg-white/[0.04] text-white/45"
                        : "border-amber-500/20 bg-amber-500/10 text-amber-200";
                  return (
                    <li
                      key={insight.insight_id ?? `finding-${idx}`}
                      className="rounded-lg border border-white/[0.06] bg-black/20 px-4 py-3"
                    >
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="text-sm font-medium text-white">{truncate(insightHeadline(insight), 72)}</span>
                        <span className={`rounded-full border px-2 py-0.5 text-[10px] font-medium capitalize ${sevClass}`}>
                          {insight.severity ?? "medium"}
                        </span>
                        {isReportSafe(insight) && (
                          <span className="rounded-full border border-emerald-500/25 bg-emerald-500/10 px-2 py-0.5 text-[10px] font-medium text-emerald-300">
                            Report-ready
                          </span>
                        )}
                        <span className="text-[10px] text-white/35">{Math.round(confPct(insight, 0))}% conf.</span>
                      </div>
                      {body ? <p className="mt-2 text-xs leading-snug text-white/55">{body}</p> : null}
                    </li>
                  );
                })}
              </ul>
            )}
          </div>
        </div>

        {/* Right column */}
        <div className="space-y-6 min-w-0">
          {/* 4. Chart preview grid */}
          <div className="rounded-xl border border-white/[0.06] bg-white/[0.03] p-5">
            <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
              <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-white/35">Chart previews</p>
              <button
                type="button"
                onClick={() => onNavigateToTab("charts")}
                className="inline-flex items-center gap-1 text-[11px] font-medium text-indigo-400 hover:text-indigo-300 transition-colors"
              >
                Charts workspace
                <ArrowRight className="h-3 w-3" />
              </button>
            </div>

            {chartsLoading ? (
              <div className="flex items-center justify-center gap-2 py-12 text-xs text-white/35">
                <Loader2 className="h-4 w-4 animate-spin text-indigo-400" />
                Loading suggested charts…
              </div>
            ) : chartsError || charts.length === 0 ? (
              <div className="rounded-lg border border-dashed border-white/12 bg-white/[0.02] px-4 py-8 text-center">
                <BarChart3 className="mx-auto mb-2 h-8 w-8 text-white/20" aria-hidden />
                <p className="text-sm text-white/55">Charts available in the Charts tab</p>
                <p className="mt-1 text-xs text-white/35">Open the full chart workspace for interactions and exports.</p>
                <button
                  type="button"
                  onClick={() => onNavigateToTab("charts")}
                  className="mt-4 inline-flex items-center gap-2 rounded-lg bg-indigo-600/90 px-4 py-2 text-xs font-medium text-white hover:bg-indigo-500 transition-colors"
                >
                  Go to Charts
                  <ArrowRight className="h-3.5 w-3.5" />
                </button>
              </div>
            ) : (
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                {charts.map((chart, i) => (
                  <button
                    key={`${chart.title}-${i}`}
                    type="button"
                    onClick={() => onNavigateToTab("charts")}
                    className="rounded-lg border border-white/[0.06] bg-black/25 p-3 text-left transition-colors hover:border-indigo-500/25 hover:bg-white/[0.04]"
                  >
                    <div className="mb-2 flex items-start justify-between gap-2">
                      <span className="text-xs font-medium text-white line-clamp-2">{chart.title}</span>
                      <span className="shrink-0 rounded bg-white/[0.06] px-1.5 py-0.5 text-[9px] font-semibold uppercase tracking-wide text-white/45">
                        {chart.type}
                      </span>
                    </div>
                    <MiniChartPreview chart={chart} />
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* 5. Recommended next action */}
          <RecommendedAction insights={insights} />

          {/* 6. Report CTA */}
          <div className="flex flex-col gap-3 rounded-xl border border-indigo-500/20 bg-indigo-600/[0.07] p-5 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <p className="text-sm font-semibold text-white">Client deliverable</p>
              <p className="mt-1 text-xs text-white/45">
                Pull findings into the report builder, then export PDF or Excel.
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                onClick={() => onNavigateToTab("ask-ai")}
                className="inline-flex items-center justify-center gap-2 rounded-lg bg-indigo-600 px-4 py-2.5 text-xs font-semibold text-white shadow-lg shadow-indigo-900/30 hover:bg-indigo-500 transition-colors"
              >
                Build client report
                <ArrowRight className="h-3.5 w-3.5" />
              </button>
              <button
                type="button"
                onClick={() => onNavigateToTab("story")}
                className="inline-flex items-center justify-center rounded-lg border border-white/15 bg-white/[0.04] px-4 py-2.5 text-xs font-medium text-white/70 hover:bg-white/[0.07] hover:text-white transition-colors"
              >
                Client summary
              </button>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

function MetricPill({
  icon,
  label,
  value,
  hint,
  accent,
}: {
  icon: ReactNode;
  label: string;
  value: string;
  hint?: string;
  accent: "indigo" | "emerald" | "amber" | "slate";
}) {
  const ring =
    accent === "indigo"
      ? "border-indigo-500/20 bg-indigo-500/[0.06]"
      : accent === "emerald"
        ? "border-emerald-500/20 bg-emerald-500/[0.06]"
        : accent === "amber"
          ? "border-amber-500/20 bg-amber-500/[0.06]"
          : "border-white/[0.08] bg-white/[0.04]";
  return (
    <div className={`min-w-[140px] flex-1 rounded-xl border px-3 py-2.5 ${ring}`}>
      <div className="flex items-center gap-2 text-white/40">
        <span className="text-white/50">{icon}</span>
        <span className="text-[10px] font-medium uppercase tracking-wide">{label}</span>
      </div>
      <p className="mt-1 text-sm font-semibold text-white tracking-tight">{value}</p>
      {hint ? <p className="mt-0.5 text-[10px] text-white/30">{hint}</p> : null}
    </div>
  );
}
