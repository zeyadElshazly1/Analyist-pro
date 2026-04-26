"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  CheckCircle,
  ChevronDown,
  ChevronUp,
  Download,
  Eye,
  FileText,
  Loader2,
  Sparkles,
  TrendingUp,
  AlertTriangle,
  ArrowRight,
  BarChart2,
} from "lucide-react";
import { getDraftReport, saveDraftReport, exportReport } from "@/lib/api";

// ── Types ─────────────────────────────────────────────────────────────────────

type InsightItem = {
  insight_id?: string;
  title?: string;
  explanation?: string;   // canonical
  finding?: string;       // legacy
  severity?: string;
  category?: string;
  report_safe?: boolean;
  recommendation?: string;
  why_it_matters?: string;
  confidence?: number;
};

type ExecutivePanel = {
  opportunities?: Array<{ title: string; summary: string; severity: string }>;
  risks?:         Array<{ title: string; summary: string; severity: string }>;
  action_plan?:   Array<{ title?: string; action?: string; priority?: string; reason?: string }>;
};

type CompareResult = {
  file_a?: { file_name?: string };
  file_b?: { file_name?: string };
  row_volume_changes?: { count_a?: number; count_b?: number; diff?: number; diff_pct?: number };
  health_changes?: { score_a?: number; grade_a?: string; score_b?: number; grade_b?: string; direction?: string };
  summary_draft?: string;
  caution_flags?: Array<{ message: string; severity: string }>;
};

type Props = {
  projectId: number;
  insights?: InsightItem[];           // legacy UI insight array (fallback)
  insightResults?: InsightItem[];     // canonical insight_results (primary)
  narrative?: string;
  executivePanel?: ExecutivePanel | null;
  compareResult?: CompareResult | null;
  projectName?: string;
};

type Draft = {
  title: string;
  summary: string;
  selectedIndices: number[];
  template: string | undefined;
};

// ── Helpers ───────────────────────────────────────────────────────────────────

function severityDot(sev: string | undefined) {
  if (sev === "high")   return "bg-red-400";
  if (sev === "medium") return "bg-amber-400";
  return "bg-white/30";
}

function severityBadge(sev: string | undefined) {
  if (sev === "high")   return "border-red-500/30 bg-red-500/10 text-red-300";
  if (sev === "medium") return "border-amber-500/30 bg-amber-500/10 text-amber-300";
  return "border-white/10 bg-white/5 text-white/40";
}

// ── Main component ────────────────────────────────────────────────────────────

export function ReportBuilder({
  projectId,
  insights = [],
  insightResults,
  narrative,
  executivePanel,
  compareResult,
  projectName,
}: Props) {
  // Canonical-first: prefer insightResults, fall back to insights
  const allInsights: InsightItem[] = insightResults?.length ? insightResults : insights;

  const [draft, setDraft] = useState<Draft>({
    title:           projectName ?? "",
    summary:         narrative ?? "",
    selectedIndices: [],
    template:        undefined,
  });
  const [saving,    setSaving]    = useState(false);
  const [saved,     setSaved]     = useState(false);
  const [exporting, setExporting] = useState<string | null>(null);
  const [exportErr, setExportErr] = useState<string | null>(null);
  const [loaded,    setLoaded]    = useState(false);
  const [previewOpen, setPreviewOpen] = useState(true);

  const saveTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  // ── Load saved draft on mount ───────────────────────────────────────────────

  useEffect(() => {
    getDraftReport(projectId)
      .then((d) => {
        if (!d) {
          // No saved draft — auto-select top report-safe insights
          const topSafe = allInsights
            .map((ins, idx) => ({ ins, idx }))
            .filter(({ ins }) => ins.report_safe !== false)
            .slice(0, 5)
            .map(({ idx }) => idx);
          setDraft((prev) => ({
            ...prev,
            title:           projectName ?? "",
            summary:         narrative ?? "",
            selectedIndices: topSafe,
          }));
          setLoaded(true);
          return;
        }
        const rr = d.report_result;
        setDraft({
          title:           rr?.title     ?? d.title     ?? projectName ?? "",
          summary:         rr?.summary   ?? d.summary   ?? narrative   ?? "",
          selectedIndices: d.selected_insight_ids ?? [],
          template:        rr?.template  ?? d.template  ?? undefined,
        });
        setLoaded(true);
      })
      .catch(() => {
        setDraft((prev) => ({
          ...prev,
          summary: prev.summary || narrative || "",
        }));
        setLoaded(true);
      });
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId]);

  // ── Persist (debounced 800 ms) ──────────────────────────────────────────────

  const persistDraft = useCallback((next: Draft) => {
    if (saveTimer.current) clearTimeout(saveTimer.current);
    setSaved(false);
    setSaving(true);
    saveTimer.current = setTimeout(async () => {
      try {
        await saveDraftReport(projectId, {
          title:                next.title,
          summary:              next.summary,
          selected_insight_ids: next.selectedIndices,
          selected_chart_ids:   [],
          template:             next.template ?? null,
        });
        setSaved(true);
      } catch {
        // silent — draft still lives in local state
      } finally {
        setSaving(false);
      }
    }, 800);
  }, [projectId]);

  function update(patch: Partial<Draft>) {
    setDraft((prev) => {
      const next = { ...prev, ...patch };
      persistDraft(next);
      return next;
    });
  }

  function toggleInsight(idx: number) {
    setDraft((prev) => {
      const next = {
        ...prev,
        selectedIndices: prev.selectedIndices.includes(idx)
          ? prev.selectedIndices.filter((i) => i !== idx)
          : [...prev.selectedIndices, idx],
      };
      persistDraft(next);
      return next;
    });
  }

  async function handleExport(format: "pdf" | "xlsx" | "html") {
    setExportErr(null);
    setExporting(format);
    try {
      await exportReport(projectId, format);
    } catch (e) {
      setExportErr(e instanceof Error ? e.message : "Export failed — please try again.");
    } finally {
      setExporting(null);
    }
  }

  // ── Derived preview values ──────────────────────────────────────────────────

  const selectedInsights = draft.selectedIndices
    .map((idx) => allInsights[idx])
    .filter(Boolean);

  const actionItems = [
    ...(executivePanel?.action_plan ?? []).slice(0, 4).map((a) => ({
      label:  a.action || a.title || "",
      reason: a.reason,
    })),
    // Supplement from selected insights when action_plan is sparse
    ...(executivePanel?.action_plan?.length ? [] : selectedInsights
      .filter((ins) => ins.severity === "high" && ins.recommendation)
      .slice(0, 3)
      .map((ins) => ({ label: ins.recommendation!, reason: ins.why_it_matters }))),
  ].filter((a) => a.label);

  const hasCompare = !!(compareResult?.file_a || compareResult?.summary_draft);

  // ── Loading state ──────────────────────────────────────────────────────────

  if (!loaded) {
    return (
      <div className="flex items-center gap-2 py-8 text-sm text-white/30">
        <Loader2 className="h-4 w-4 animate-spin" />
        Loading draft…
      </div>
    );
  }

  return (
    <div className="space-y-6">

      {/* ── Configure ─────────────────────────────────────────────────────── */}
      <div className="space-y-5">

        {/* Title */}
        <div>
          <label className="mb-1.5 block text-xs font-semibold uppercase tracking-wider text-white/40">
            Report title
          </label>
          <input
            value={draft.title}
            onChange={(e) => update({ title: e.target.value })}
            placeholder="e.g. April Performance Review — Acme Corp"
            className="w-full rounded-xl border border-white/[0.08] bg-white/[0.03] px-4 py-2.5 text-sm text-white placeholder:text-white/20 focus:border-indigo-500/50 focus:outline-none"
          />
        </div>

        {/* Executive summary */}
        <div>
          <div className="mb-1.5 flex items-center gap-2">
            <label className="text-xs font-semibold uppercase tracking-wider text-white/40">
              Executive summary
            </label>
            {narrative && (
              <span className="flex items-center gap-1 rounded-full bg-indigo-500/15 px-1.5 py-px text-[10px] font-medium text-indigo-400">
                <Sparkles className="h-2.5 w-2.5" />
                AI-assisted — edit freely
              </span>
            )}
          </div>
          <textarea
            value={draft.summary}
            onChange={(e) => update({ summary: e.target.value })}
            rows={4}
            placeholder="Write a client-safe summary of what you found and why it matters…"
            className="w-full resize-none rounded-xl border border-white/[0.08] bg-white/[0.03] px-4 py-2.5 text-sm text-white placeholder:text-white/20 focus:border-indigo-500/50 focus:outline-none"
          />
        </div>

        {/* Insight selection */}
        {allInsights.length > 0 && (
          <div>
            <div className="mb-2 flex items-center justify-between">
              <label className="text-xs font-semibold uppercase tracking-wider text-white/40">
                Select findings to include
              </label>
              <span className="text-xs text-white/25">
                {draft.selectedIndices.length} / {Math.min(allInsights.length, 10)} selected
              </span>
            </div>
            <div className="space-y-1.5">
              {allInsights.slice(0, 10).map((ins, idx) => {
                const selected = draft.selectedIndices.includes(idx);
                const label = ins.title || ins.explanation || ins.finding || `Finding ${idx + 1}`;
                return (
                  <button
                    key={idx}
                    onClick={() => toggleInsight(idx)}
                    className={`flex w-full items-start gap-3 rounded-xl border px-3 py-2.5 text-left transition-all ${
                      selected
                        ? "border-indigo-500/40 bg-indigo-600/8"
                        : "border-white/[0.06] bg-white/[0.015] hover:border-white/10"
                    }`}
                  >
                    <div className={`mt-0.5 flex h-4 w-4 flex-shrink-0 items-center justify-center rounded border transition-colors ${
                      selected ? "border-indigo-500 bg-indigo-600" : "border-white/20"
                    }`}>
                      {selected && <CheckCircle className="h-3 w-3 text-white" />}
                    </div>
                    <span className={`mt-1.5 h-1.5 w-1.5 flex-shrink-0 rounded-full ${severityDot(ins.severity)}`} />
                    <div className="min-w-0 flex-1">
                      <p className="text-xs font-medium leading-snug text-white/80">{label}</p>
                      {ins.severity && (
                        <p className="mt-0.5 text-[10px] capitalize text-white/30">{ins.severity} severity</p>
                      )}
                    </div>
                  </button>
                );
              })}
            </div>
          </div>
        )}
      </div>

      {/* ── Live Preview ───────────────────────────────────────────────────── */}
      <div className="rounded-2xl border border-white/[0.07] bg-white/[0.02]">
        <button
          onClick={() => setPreviewOpen((v) => !v)}
          className="flex w-full items-center justify-between px-5 py-3.5"
        >
          <div className="flex items-center gap-2">
            <Eye className="h-4 w-4 text-indigo-400" />
            <span className="text-sm font-semibold text-white">Report Preview</span>
            <span className="text-xs text-white/25">
              {selectedInsights.length} finding{selectedInsights.length !== 1 ? "s" : ""} included
            </span>
          </div>
          {previewOpen
            ? <ChevronUp className="h-4 w-4 text-white/30" />
            : <ChevronDown className="h-4 w-4 text-white/30" />}
        </button>

        {previewOpen && (
          <div className="space-y-6 border-t border-white/[0.06] px-5 pb-6 pt-5">

            {/* Cover */}
            <PreviewSection icon={FileText} title="Cover" accent="indigo">
              <div className="rounded-xl border border-indigo-500/20 bg-indigo-600/5 px-5 py-4">
                <p className="mb-1 text-[10px] font-semibold uppercase tracking-widest text-indigo-400/60">
                  Analysis Report
                </p>
                <h3 className="text-base font-bold text-white">
                  {draft.title || <span className="italic text-white/20">Untitled report</span>}
                </h3>
                <p className="mt-1 text-xs text-white/30">Generated by Analyist Pro</p>
              </div>
            </PreviewSection>

            {/* Executive Summary */}
            <PreviewSection icon={Sparkles} title="Executive Summary" accent="indigo">
              {draft.summary ? (
                <p className="whitespace-pre-wrap text-sm leading-relaxed text-white/70">
                  {draft.summary}
                </p>
              ) : (
                <p className="italic text-sm text-white/25">
                  No summary yet — write one above.
                </p>
              )}
            </PreviewSection>

            {/* Key Findings */}
            <PreviewSection icon={BarChart2} title="Key Findings" accent="purple">
              {selectedInsights.length === 0 ? (
                <p className="italic text-sm text-white/25">
                  No findings selected — toggle insights above to include them.
                </p>
              ) : (
                <div className="space-y-2">
                  {selectedInsights.map((ins, i) => {
                    const label  = ins.title || ins.explanation || ins.finding || `Finding ${i + 1}`;
                    const detail = ins.explanation || ins.finding;
                    return (
                      <div
                        key={i}
                        className="rounded-lg border border-white/[0.06] bg-white/[0.02] px-4 py-3"
                      >
                        <div className="flex items-start gap-2.5">
                          <span className={`mt-1.5 h-1.5 w-1.5 flex-shrink-0 rounded-full ${severityDot(ins.severity)}`} />
                          <div className="min-w-0 flex-1">
                            <p className="text-xs font-semibold text-white/85">{label}</p>
                            {detail && detail !== label && (
                              <p className="mt-0.5 line-clamp-2 text-xs leading-snug text-white/45">
                                {detail}
                              </p>
                            )}
                          </div>
                          {ins.severity && (
                            <span className={`ml-auto flex-shrink-0 rounded-full border px-1.5 py-px text-[10px] font-medium capitalize ${severityBadge(ins.severity)}`}>
                              {ins.severity}
                            </span>
                          )}
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </PreviewSection>

            {/* Comparison Summary — only if compare data exists */}
            {hasCompare && (
              <PreviewSection icon={TrendingUp} title="Comparison Summary" accent="emerald">
                <div className="space-y-2">
                  {compareResult?.summary_draft && (
                    <p className="text-sm text-white/70">{compareResult.summary_draft}</p>
                  )}
                  {compareResult?.health_changes && (
                    <div className="grid grid-cols-2 gap-2">
                      {[
                        { label: compareResult.file_a?.file_name ?? "File A", score: compareResult.health_changes.score_a, grade: compareResult.health_changes.grade_a },
                        { label: compareResult.file_b?.file_name ?? "File B", score: compareResult.health_changes.score_b, grade: compareResult.health_changes.grade_b },
                      ].map(({ label, score, grade }) => (
                        <div key={label} className="rounded-lg border border-white/[0.06] bg-white/[0.02] px-3 py-2">
                          <p className="truncate text-[10px] text-white/35">{label}</p>
                          <p className="text-sm font-bold text-white">
                            {score != null ? Math.round(score) : "—"}
                            {grade && <span className="ml-1 text-xs font-normal text-white/40">{grade}</span>}
                          </p>
                        </div>
                      ))}
                    </div>
                  )}
                  {compareResult?.caution_flags?.slice(0, 3).map((f, i) => (
                    <div key={i} className="flex items-start gap-2 text-xs text-white/50">
                      <AlertTriangle className="mt-0.5 h-3 w-3 flex-shrink-0 text-amber-400/70" />
                      {f.message}
                    </div>
                  ))}
                </div>
              </PreviewSection>
            )}

            {/* Recommended Next Steps */}
            {actionItems.length > 0 && (
              <PreviewSection icon={ArrowRight} title="Recommended Next Steps" accent="amber">
                <div className="space-y-1.5">
                  {actionItems.map((a, i) => (
                    <div key={i} className="flex items-start gap-2.5">
                      <span className="mt-1 flex h-4 w-4 flex-shrink-0 items-center justify-center rounded-full bg-white/[0.06] text-[10px] font-bold text-white/40">
                        {i + 1}
                      </span>
                      <div>
                        <p className="text-xs text-white/70">{a.label}</p>
                        {a.reason && (
                          <p className="mt-0.5 text-[11px] text-white/35">{a.reason}</p>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </PreviewSection>
            )}

          </div>
        )}
      </div>

      {/* ── Export ────────────────────────────────────────────────────────── */}
      <div className="flex flex-wrap items-center gap-3 border-t border-white/[0.06] pt-4">
        <button
          onClick={() => handleExport("pdf")}
          disabled={!!exporting}
          className="flex items-center gap-2 rounded-xl bg-indigo-600 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-indigo-500 disabled:opacity-60"
        >
          {exporting === "pdf" ? <Loader2 className="h-4 w-4 animate-spin" /> : <Download className="h-4 w-4" />}
          Export PDF
        </button>
        <button
          onClick={() => handleExport("xlsx")}
          disabled={!!exporting}
          className="flex items-center gap-2 rounded-xl border border-white/10 bg-white/[0.04] px-4 py-2.5 text-sm font-medium text-white/70 transition hover:bg-white/[0.07] hover:text-white disabled:opacity-60"
        >
          {exporting === "xlsx" ? <Loader2 className="h-4 w-4 animate-spin" /> : <FileText className="h-4 w-4" />}
          Export Excel
        </button>
        <div className="ml-auto flex items-center gap-1.5 text-xs">
          {saving && <span className="text-white/30">Saving…</span>}
          {saved && !saving && (
            <span className="flex items-center gap-1 text-emerald-400">
              <CheckCircle className="h-3.5 w-3.5" />
              Draft saved
            </span>
          )}
        </div>
      </div>

      {exportErr && (
        <p className="rounded-xl border border-red-500/20 bg-red-500/5 px-4 py-2.5 text-sm text-red-400">
          {exportErr}
        </p>
      )}
    </div>
  );
}

// ── PreviewSection ────────────────────────────────────────────────────────────

const ACCENT: Record<string, string> = {
  indigo:  "text-indigo-400",
  purple:  "text-violet-400",
  emerald: "text-emerald-400",
  amber:   "text-amber-400",
};

function PreviewSection({
  icon: Icon,
  title,
  accent = "indigo",
  children,
}: {
  icon: React.ElementType;
  title: string;
  accent?: string;
  children: React.ReactNode;
}) {
  return (
    <div>
      <div className="mb-2.5 flex items-center gap-2">
        <Icon className={`h-3.5 w-3.5 flex-shrink-0 ${ACCENT[accent] ?? "text-white/40"}`} />
        <p className="text-xs font-semibold uppercase tracking-wider text-white/40">{title}</p>
      </div>
      {children}
    </div>
  );
}
