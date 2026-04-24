"use client";

import { useEffect, useState } from "react";
import { FileText, Sparkles, Download, CheckCircle, Clock } from "lucide-react";
import { getDraftReport, saveDraftReport, exportReport } from "@/lib/api";
import type { ReportResult, ReportExportRecord } from "@/lib/api";

const TEMPLATES = [
  {
    id: "monthly_performance",
    label: "Monthly Performance",
    description: "Trend, top metric changes, anomalies, period comparison",
  },
  {
    id: "ops_kpi_review",
    label: "Ops / KPI Review",
    description: "Health score, top issues, KPI table, variance",
  },
  {
    id: "finance_summary",
    label: "Finance Summary",
    description: "Totals, outliers, category breakdown, period delta",
  },
];

type Insight = {
  title?: string;
  severity?: string;
  explanation?: string;  // canonical
  category?: string;     // canonical
  finding?: string;      // legacy
  type?: string;         // legacy
};

// Draft state — flat fields mirroring the API response
type Draft = {
  id?: number;
  title?: string;
  summary?: string;
  selected_insight_ids?: number[];
  selected_chart_ids?: string[];
  template?: string;
  report_result?: ReportResult | null;
};

type Props = {
  projectId: number;
  insights: Insight[];
  projectName?: string;
};

function formatExportDate(iso: string | null): string {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString(undefined, { dateStyle: "short", timeStyle: "short" });
  } catch {
    return iso;
  }
}

const FORMAT_LABEL: Record<string, string> = { pdf: "PDF", xlsx: "Excel", html: "HTML" };

export function ReportBuilder({ projectId, insights, projectName }: Props) {
  const [draft, setDraft] = useState<Draft>({
    title: projectName ?? "",
    summary: "",
    selected_insight_ids: [],
    selected_chart_ids: [],
    template: undefined,
    report_result: null,
  });
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    getDraftReport(projectId)
      .then((d) => {
        if (!d) return;
        // Canonical-first: use report_result fields when available
        const rr = d.report_result;
        setDraft({
          id:                   d.id,
          title:                rr?.title     ?? d.title     ?? projectName ?? "",
          summary:              rr?.summary   ?? d.summary   ?? "",
          selected_insight_ids: rr?.included_insights.map((i) => i.index_in_run ?? 0).filter((n) => n >= 0)
                                ?? d.selected_insight_ids ?? [],
          selected_chart_ids:   d.selected_chart_ids ?? [],
          template:             rr?.template  ?? d.template  ?? undefined,
          report_result:        rr ?? null,
        });
      })
      .catch(() => {});
  }, [projectId, projectName]);

  async function saveDraft(updates: Partial<Draft>) {
    const next = { ...draft, ...updates };
    setDraft(next);
    setSaving(true);
    setSaved(false);
    try {
      const saved_draft = await saveDraftReport(projectId, {
        title:                next.title,
        summary:              next.summary,
        selected_insight_ids: next.selected_insight_ids,
        selected_chart_ids:   next.selected_chart_ids,
        template:             next.template ?? null,
      });
      // Update canonical report_result from response
      setDraft((d) => ({ ...d, report_result: saved_draft.report_result ?? null }));
      setSaved(true);
    } catch {
      // silent — user can retry
    } finally {
      setSaving(false);
    }
  }

  function toggleInsight(idx: number) {
    const current = draft.selected_insight_ids ?? [];
    const next = current.includes(idx)
      ? current.filter((i) => i !== idx)
      : [...current, idx];
    saveDraft({ selected_insight_ids: next });
  }

  // Canonical-first: use report_result for display values
  const rr = draft.report_result;
  const selectedCount  = draft.selected_insight_ids?.length ?? 0;
  const exportHistory: ReportExportRecord[] = rr?.export_statuses ?? [];
  const aiSections     = rr?.ai_generated_sections ?? ["executive_summary"];
  const summaryIsAI    = aiSections.includes("executive_summary");

  return (
    <div className="space-y-5">
      {/* Template picker */}
      <div>
        <p className="mb-2 text-xs font-semibold text-white/50 uppercase tracking-wider">
          Report template
        </p>
        <div className="grid gap-2 sm:grid-cols-3">
          {TEMPLATES.map((t) => (
            <button
              key={t.id}
              onClick={() => saveDraft({ template: draft.template === t.id ? undefined : t.id })}
              className={`rounded-xl border p-3 text-left transition-all ${
                draft.template === t.id
                  ? "border-indigo-500/50 bg-indigo-600/10"
                  : "border-white/[0.07] bg-white/[0.02] hover:border-white/10"
              }`}
            >
              <p className="text-xs font-semibold text-white">{t.label}</p>
              <p className="mt-0.5 text-[11px] text-white/40">{t.description}</p>
            </button>
          ))}
        </div>
      </div>

      {/* Title */}
      <div>
        <label className="mb-1.5 block text-xs font-semibold text-white/50 uppercase tracking-wider">
          Report title
        </label>
        <input
          value={draft.title ?? ""}
          onChange={(e) => setDraft((d) => ({ ...d, title: e.target.value }))}
          onBlur={() => saveDraft({})}
          placeholder="e.g. April Performance Review — Acme Corp"
          className="w-full rounded-xl border border-white/[0.08] bg-white/[0.03] px-4 py-2.5 text-sm text-white placeholder:text-white/25 focus:border-indigo-500/50 focus:outline-none"
        />
      </div>

      {/* Executive summary */}
      <div>
        <label className="mb-1.5 block text-xs font-semibold text-white/50 uppercase tracking-wider">
          Executive summary
          {summaryIsAI && (
            <span className="ml-2 rounded-full bg-indigo-500/15 px-1.5 py-px text-[10px] font-medium text-indigo-400 normal-case">
              <Sparkles className="mb-px mr-0.5 inline h-2.5 w-2.5" />
              AI-generated — edit freely
            </span>
          )}
        </label>
        <textarea
          value={draft.summary ?? ""}
          onChange={(e) => setDraft((d) => ({ ...d, summary: e.target.value }))}
          onBlur={() => saveDraft({})}
          rows={4}
          placeholder="Write a client-safe summary of the key findings…"
          className="w-full resize-none rounded-xl border border-white/[0.08] bg-white/[0.03] px-4 py-2.5 text-sm text-white placeholder:text-white/25 focus:border-indigo-500/50 focus:outline-none"
        />
      </div>

      {/* Insight selection */}
      {insights.length > 0 && (
        <div>
          <p className="mb-2 text-xs font-semibold text-white/50 uppercase tracking-wider">
            Select findings to include
            <span className="ml-2 text-white/30 normal-case font-normal">
              ({selectedCount} of {insights.length} selected)
            </span>
          </p>
          <div className="space-y-1.5">
            {insights.slice(0, 10).map((ins, idx) => {
              const selected = draft.selected_insight_ids?.includes(idx);
              // Prefer canonical insight in report_result, fallback to full list entry
              const canonicalIns = rr?.included_insights.find((i) => i.index_in_run === idx);
              const label = canonicalIns?.title ?? ins.explanation ?? ins.finding ?? ins.title ?? `Finding ${idx + 1}`;
              const sev   = canonicalIns?.severity ?? ins.severity;
              return (
                <button
                  key={idx}
                  onClick={() => toggleInsight(idx)}
                  className={`flex w-full items-start gap-3 rounded-xl border p-3 text-left transition-all ${
                    selected
                      ? "border-indigo-500/40 bg-indigo-600/8"
                      : "border-white/[0.06] bg-white/[0.015] hover:border-white/10"
                  }`}
                >
                  <div
                    className={`mt-0.5 flex h-4 w-4 flex-shrink-0 items-center justify-center rounded border ${
                      selected
                        ? "border-indigo-500 bg-indigo-600"
                        : "border-white/20 bg-transparent"
                    }`}
                  >
                    {selected && <CheckCircle className="h-3 w-3 text-white" />}
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="text-xs font-medium text-white/80">{label}</p>
                    {sev && (
                      <span className="text-[10px] text-white/30">{sev} severity</span>
                    )}
                  </div>
                </button>
              );
            })}
          </div>
        </div>
      )}

      {/* Actions */}
      <div className="flex flex-wrap items-center gap-3 border-t border-white/[0.06] pt-4">
        <button
          onClick={() => exportReport(projectId, "pdf").catch(() => {})}
          className="flex items-center gap-2 rounded-xl bg-indigo-600 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-indigo-500"
        >
          <Download className="h-4 w-4" />
          Export PDF
        </button>
        <button
          onClick={() => exportReport(projectId, "xlsx").catch(() => {})}
          className="flex items-center gap-2 rounded-xl border border-white/10 bg-white/[0.04] px-4 py-2.5 text-sm font-medium text-white/70 transition hover:bg-white/[0.07] hover:text-white"
        >
          <FileText className="h-4 w-4" />
          Export Excel
        </button>
        {saving && (
          <span className="text-xs text-white/30">Saving…</span>
        )}
        {saved && !saving && (
          <span className="flex items-center gap-1.5 text-xs text-emerald-400">
            <CheckCircle className="h-3.5 w-3.5" />
            Saved
          </span>
        )}
      </div>

      {/* Export history (canonical report_result.export_statuses) */}
      {exportHistory.length > 0 && (
        <div>
          <p className="mb-1.5 text-[10px] font-medium uppercase tracking-wider text-white/30 flex items-center gap-1.5">
            <Clock className="h-3 w-3" />
            Export history
          </p>
          <div className="space-y-1">
            {exportHistory.map((rec, i) => (
              <div key={i} className="flex items-center justify-between rounded-lg border border-white/[0.05] bg-white/[0.02] px-3 py-2">
                <div className="flex items-center gap-2">
                  <span className={`h-1.5 w-1.5 rounded-full flex-shrink-0 ${
                    rec.status === "completed" ? "bg-emerald-400" :
                    rec.status === "failed"    ? "bg-red-400" : "bg-amber-400"
                  }`} />
                  <span className="text-xs font-medium text-white/60">
                    {FORMAT_LABEL[rec.format] ?? rec.format}
                  </span>
                </div>
                <span className="text-[11px] text-white/30">{formatExportDate(rec.exported_at)}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
