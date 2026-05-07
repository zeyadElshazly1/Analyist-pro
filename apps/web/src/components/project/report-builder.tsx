"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  Check,
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
  Info,
  X,
  RefreshCw,
} from "lucide-react";
import { getDraftReport, saveDraftReport, exportReport, ApiError } from "@/lib/api";
import type { AvailableChart, CompareResult, IncludedChart } from "@/lib/api";
import {
  buildDeterministicExecutiveSummary,
  selectRecommendedInsightKeys,
} from "@/lib/report-draft-fallback";
import type { ExecutiveSummaryRichInput } from "@/lib/report-draft-fallback";

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
  columns_used?: string[];
  evidence?: string;
  caveats?: string[] | string;
};

type ExecutivePanel = {
  opportunities?: Array<{ title: string; summary: string; severity: string }>;
  risks?:         Array<{ title: string; summary: string; severity: string }>;
  action_plan?:   Array<{ title?: string; action?: string; priority?: string; reason?: string }>;
};

type HealthBlock = {
  health_score?: { total_score?: number; grade?: string };
  health_warnings?: Array<{ severity: string; message: string }>;
};

type CleaningBlock = {
  renamed_columns?: unknown[];
  dropped_columns?: unknown[];
  type_fixes?: unknown[];
  missingness_notes?: Array<{ strategy_applied?: string }>;
  duplicate_notes?: { removed?: boolean };
  suspicious_columns?: Array<{ column: string; issue_type: string }>;
  cleaning_summary?: { steps_applied?: number };
};

type Props = {
  projectId: number;
  insights?: InsightItem[];           // legacy UI insight array (fallback)
  insightResults?: InsightItem[];     // canonical insight_results (primary)
  narrative?: string;
  executivePanel?: ExecutivePanel | null;
  compareResult?: CompareResult | null;
  projectName?: string;
  /** Rows/columns from analysis — improves local executive-summary fallback */
  datasetSummary?: {
    rows?: number;
    columns?: number;
    numeric_cols?: number;
    categorical_cols?: number;
    large_dataset_mode?: boolean;
    analyzed_rows?: number;
    sample_strategy?: string | null;
  } | null;
  /** Overall health score 0–100 when known */
  healthTotal?: number | null;
  healthResult?: HealthBlock | null;
  cleaningResult?: CleaningBlock | null;
  onNavigateTo?: (tab: string) => void;
};

/** Exported for callers that attach loosely-typed analysis payloads. */
export type ReportInsightItem = InsightItem;
export type ReportExecutivePanel = ExecutivePanel;
export type ReportHealthBlock = HealthBlock;
export type ReportCleaningBlock = CleaningBlock;

// Selection key is normally the canonical ``insight_id`` string, falling
// back to a numeric positional index only for legacy drafts (or the
// vanishingly rare insight that lacks an id).  Storing the key — not the
// index — means a re-run that re-orders findings can no longer silently
// swap which findings end up in the export.
type SelectionKey = string | number;

type Draft = {
  title: string;
  summary: string;
  selected: SelectionKey[];
  template: string | undefined;
};

type ExportRecord = {
  format: "pdf" | "xlsx" | "html";
  status: "success" | "failed" | "unavailable";
  at: Date;
  message?: string;
};

// Map the canonical ReportExportRecord (audit-log backed) onto the local
// strip representation.  ``completed`` and ``pending`` collapse onto
// ``success`` for display — pending is rare today (no async export queue)
// and rendering it as success keeps the strip simple.  Unknown statuses
// fall back to ``failed`` so the row is shown rather than silently dropped.
function fromBackendExport(rec: import("@/lib/api").ReportExportRecord): ExportRecord | null {
  if (!rec.format || (rec.format !== "pdf" && rec.format !== "xlsx" && rec.format !== "html")) {
    return null;
  }
  let status: ExportRecord["status"];
  if (rec.status === "completed" || rec.status === "pending") status = "success";
  else if (rec.status === "unavailable") status = "unavailable";
  else status = "failed";

  const at = rec.exported_at ? new Date(rec.exported_at) : new Date();
  return {
    format: rec.format,
    status,
    at: isNaN(at.getTime()) ? new Date() : at,
    message: rec.error_message ?? undefined,
  };
}

const FORMAT_LABEL: Record<string, string> = { pdf: "PDF", xlsx: "Excel", html: "HTML" };

function relativeTime(date: Date): string {
  const secs = Math.floor((Date.now() - date.getTime()) / 1000);
  if (secs < 10) return "just now";
  if (secs < 60) return `${secs}s ago`;
  const mins = Math.floor(secs / 60);
  if (mins < 60) return `${mins} min ago`;
  return `${Math.floor(mins / 60)}h ago`;
}

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

// ── ReportBrief helpers ───────────────────────────────────────────────────────

function insightReportSafe(i: InsightItem): boolean {
  if (typeof i.report_safe === "boolean") return i.report_safe;
  // Canonical insight confidence is 0.0–1.0 (see app/schemas/insight.py and
  // the adapter in projects/[id]/page.tsx).  Multiply for the threshold only.
  const conf =
    typeof i.confidence === "number" && Number.isFinite(i.confidence)
      ? Math.max(0, Math.min(100, i.confidence * 100))
      : 0;
  const cat = i.category ?? "";
  return (
    (i.severity === "high" || i.severity === "medium") &&
    conf >= 60 &&
    cat !== "data_quality" && cat !== "missing_pattern"
  );
}

// Stable identity for an insight in the draft selection.  Prefer the
// canonical ``insight_id`` (a deterministic hex digest the pipeline emits
// on every run); fall back to the positional index only when the
// pipeline did not produce an id, so legacy results still toggle.
function selectionKey(ins: InsightItem, idx: number): SelectionKey {
  return typeof ins.insight_id === "string" && ins.insight_id
    ? ins.insight_id
    : idx;
}

// Resolve a draft selection key back to the insight in the current run.
// Strings match by ``insight_id``; numbers fall back to positional index
// so legacy drafts keep working.  Returns ``undefined`` when the key has
// no match — callers should drop missing entries rather than coerce
// them into the wrong finding.
function findInsightByKey(
  list: InsightItem[],
  key: SelectionKey,
): InsightItem | undefined {
  if (typeof key === "string") {
    return list.find((i) => i.insight_id === key);
  }
  if (typeof key === "number" && key >= 0 && key < list.length) {
    return list[key];
  }
  return undefined;
}

const GRADE_CFG: Record<string, { card: string; text: string; verdict: string }> = {
  A: { card: "border-emerald-500/15 bg-emerald-500/[0.04]", text: "text-emerald-400", verdict: "Clean data — strong foundation" },
  B: { card: "border-indigo-500/15 bg-indigo-500/[0.04]",  text: "text-indigo-400",  verdict: "Good quality — minor issues" },
  C: { card: "border-amber-500/15 bg-amber-500/[0.04]",    text: "text-amber-400",   verdict: "Fair quality — review before sharing" },
  D: { card: "border-red-500/15 bg-red-500/[0.04]",        text: "text-red-400",     verdict: "Poor quality — needs attention" },
};
const GRADE_FALLBACK = { card: "border-white/[0.07] bg-white/[0.02]", text: "text-white/40", verdict: "No health data yet" };

// ── ReportBrief ───────────────────────────────────────────────────────────────

function ReportBrief({
  allInsights,
  healthResult,
  cleaningResult,
  compareResult,
}: {
  allInsights: InsightItem[];
  healthResult?: HealthBlock | null;
  cleaningResult?: CleaningBlock | null;
  compareResult?: CompareResult | null;
}) {
  // Health
  const grade = healthResult?.health_score?.grade ?? null;
  const gradeCfg = grade ? (GRADE_CFG[grade] ?? GRADE_FALLBACK) : GRADE_FALLBACK;
  const highWarnings = (healthResult?.health_warnings ?? []).filter((w) => w.severity === "high").length;

  // Cleaning
  const cr = cleaningResult;
  const stepsApplied =
    cr?.cleaning_summary?.steps_applied ??
    (
      (cr?.renamed_columns?.length ?? 0) +
      (cr?.dropped_columns?.length ?? 0) +
      (cr?.type_fixes?.length ?? 0) +
      (cr?.missingness_notes?.filter((n) => n.strategy_applied !== "safe_suggestion").length ?? 0) +
      (cr?.duplicate_notes?.removed ? 1 : 0)
    );
  const suspiciousCount = cr?.suspicious_columns?.length ?? 0;

  // Findings
  const reportReadyCount  = allInsights.filter(insightReportSafe).length;
  const reviewNeededCount = allInsights.filter(
    (i) => !insightReportSafe(i) && (i.severity === "high" || i.severity === "medium"),
  ).length;

  // Compare
  const rowDiff        = compareResult?.row_volume_changes?.diff ?? 0;
  const highCautionCt  = (compareResult?.caution_flags ?? []).filter((f) => f.severity === "high").length;
  const compareSummary = compareResult?.summary_draft;

  return (
    <div className="rounded-xl border border-white/[0.07] bg-white/[0.015] p-4 space-y-3">
      <p className="text-[10px] font-semibold uppercase tracking-wider text-white/25">
        Before you write — workflow recap
      </p>

      <div className={`grid gap-2 ${compareResult ? "grid-cols-2 sm:grid-cols-4" : "grid-cols-3"}`}>

        {/* Health */}
        <div className={`rounded-lg border px-3 py-2.5 space-y-0.5 ${gradeCfg.card}`}>
          <p className="text-[10px] font-medium uppercase tracking-wider text-white/30">Data Health</p>
          <p className={`text-2xl font-black leading-tight ${gradeCfg.text}`}>
            {grade ?? "—"}
          </p>
          <p className="text-[10px] leading-snug text-white/45">{gradeCfg.verdict}</p>
          {highWarnings > 0 && (
            <p className="text-[10px] text-red-400/80">
              {highWarnings} high-priority warning{highWarnings !== 1 ? "s" : ""}
            </p>
          )}
        </div>

        {/* Cleaning */}
        <div className="rounded-lg border border-white/[0.07] bg-white/[0.02] px-3 py-2.5 space-y-0.5">
          <p className="text-[10px] font-medium uppercase tracking-wider text-white/30">Cleaning</p>
          <p className="text-2xl font-black leading-tight text-white/80">{stepsApplied}</p>
          <p className="text-[10px] leading-snug text-white/45">
            {stepsApplied === 1 ? "action applied" : "actions applied"}
          </p>
          {suspiciousCount > 0 && (
            <p className="text-[10px] text-amber-400/80">
              {suspiciousCount} column{suspiciousCount !== 1 ? "s" : ""} flagged
            </p>
          )}
        </div>

        {/* Findings */}
        <div className={`rounded-lg border px-3 py-2.5 space-y-0.5 ${
          reportReadyCount > 0
            ? "border-emerald-500/15 bg-emerald-500/[0.04]"
            : "border-white/[0.07] bg-white/[0.02]"
        }`}>
          <p className="text-[10px] font-medium uppercase tracking-wider text-white/30">Findings</p>
          <p className={`text-2xl font-black leading-tight ${reportReadyCount > 0 ? "text-emerald-400" : "text-white/50"}`}>
            {reportReadyCount}
          </p>
          <p className="text-[10px] leading-snug text-white/45">
            {reportReadyCount === 1 ? "report-ready" : "report-ready"} of {allInsights.length} total
          </p>
          {reviewNeededCount > 0 && (
            <p className="text-[10px] text-amber-400/80">
              {reviewNeededCount} need{reviewNeededCount === 1 ? "s" : ""} review
            </p>
          )}
        </div>

        {/* Compare — only when compare data exists */}
        {compareResult && (
          <div className="rounded-lg border border-indigo-500/15 bg-indigo-500/[0.04] px-3 py-2.5 space-y-0.5">
            <p className="text-[10px] font-medium uppercase tracking-wider text-white/30">Comparison</p>
            <p className={`text-2xl font-black leading-tight ${
              rowDiff > 0 ? "text-emerald-400" : rowDiff < 0 ? "text-red-400" : "text-white/40"
            }`}>
              {rowDiff > 0 ? "+" : ""}{rowDiff !== 0 ? rowDiff.toLocaleString() : "±0"}
            </p>
            <p className="text-[10px] leading-snug text-white/45">row delta</p>
            {highCautionCt > 0 && (
              <p className="text-[10px] text-amber-400/80">
                {highCautionCt} high-severity flag{highCautionCt !== 1 ? "s" : ""}
              </p>
            )}
            {compareSummary && (
              <p className="mt-1 text-[10px] leading-relaxed text-white/35 line-clamp-2">
                {compareSummary}
              </p>
            )}
          </div>
        )}

      </div>
    </div>
  );
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
  datasetSummary,
  healthTotal,
  healthResult,
  cleaningResult,
  onNavigateTo,
}: Props) {
  // Canonical-first: prefer insightResults, fall back to insights
  const allInsights: InsightItem[] = insightResults?.length ? insightResults : insights;

  const [draft, setDraft] = useState<Draft>({
    title:    projectName ?? "",
    summary:  narrative ?? "",
    selected: [],
    template: undefined,
  });
  const [saving,    setSaving]    = useState(false);
  const [saved,     setSaved]     = useState(false);
  const [exporting, setExporting] = useState<string | null>(null);
  const [exportErr, setExportErr] = useState<string | null>(null);
  const [pdfUnavailable, setPdfUnavailable] = useState(false);
  const [exportHistory, setExportHistory] = useState<ExportRecord[]>([]);
  const [exportedWeak, setExportedWeak] = useState(false);
  const [loaded,    setLoaded]    = useState(false);
  const [previewOpen, setPreviewOpen] = useState(true);
  const [draftLoadError, setDraftLoadError] = useState<string | null>(null);
  const [includedCharts, setIncludedCharts] = useState<IncludedChart[]>([]);
  const [availableCharts, setAvailableCharts] = useState<AvailableChart[]>([]);
  const [selectedChartIds, setSelectedChartIds] = useState<string[]>([]);

  const saveTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const insightsRef = useRef(insights);
  const insightResultsRef = useRef(insightResults);
  insightsRef.current = insights;
  insightResultsRef.current = insightResults;
  const allInsightsRef = useRef(allInsights);
  allInsightsRef.current = allInsights;
  const selectedChartIdsRef = useRef(selectedChartIds);
  selectedChartIdsRef.current = selectedChartIds;

  const richSummaryInput = useCallback(
    (insightsList: InsightItem[]): ExecutiveSummaryRichInput => ({
      narrative: narrative ?? "",
      insights: insightsList,
      datasetSummary: datasetSummary ?? null,
      healthTotal: healthTotal ?? null,
      healthResult: healthResult
        ? { health_score: healthResult.health_score }
        : null,
      cleaningResult: cleaningResult ?? null,
      compareResult: compareResult
        ? {
            summary_draft: compareResult.summary_draft,
            row_volume_changes: compareResult.row_volume_changes,
          }
        : null,
      executivePanel: executivePanel ?? null,
    }),
    [
      narrative,
      datasetSummary,
      healthTotal,
      healthResult,
      cleaningResult,
      compareResult,
      executivePanel,
    ],
  );

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
          selected_insight_ids: next.selected,
          selected_chart_ids:   selectedChartIdsRef.current,
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

  // ── Load saved draft on mount / project change ───────────────────────────────

  useEffect(() => {
    getDraftReport(projectId)
      .then((d) => {
        setDraftLoadError(null);
        if (!d) {
          const list = insightResultsRef.current?.length
            ? insightResultsRef.current
            : insightsRef.current;
          const summary = buildDeterministicExecutiveSummary(richSummaryInput(list));
          const selected = selectRecommendedInsightKeys(list);
          setDraft({
            title:    projectName ?? "",
            summary,
            selected,
            template: undefined,
          });
          setExportHistory([]);
          setLoaded(true);
          return;
        }
        const rr = d.report_result;
        // Hydrate whatever the backend returned: stable insight_id strings
        // for new drafts, numeric indices for legacy ones.  Both shapes
        // resolve correctly through ``findInsightByKey`` below.
        const stored = (d.selected_insight_ids ?? []) as SelectionKey[];
        setDraft({
          title:    rr?.title    ?? d.title    ?? projectName ?? "",
          summary:  rr?.summary  ?? d.summary  ?? narrative   ?? "",
          selected: stored,
          template: rr?.template ?? d.template ?? undefined,
        });
        // Hydrate the export-history strip from the audit-log-backed
        // report_result.export_statuses.  The backend already returns up
        // to the most recent 10 attempts in newest-first order; we cap at
        // 6 here to match the local-append slice and keep the strip tight.
        const remoteHistory = (rr?.export_statuses ?? [])
          .map(fromBackendExport)
          .filter((x): x is ExportRecord => x !== null)
          .slice(0, 6);
        setExportHistory(remoteHistory);
        setIncludedCharts(rr?.included_charts ?? []);
        setAvailableCharts(d.available_charts ?? []);
        setSelectedChartIds((d.selected_chart_ids ?? []).filter((id): id is string => typeof id === "string"));
        setLoaded(true);
      })
      .catch(() => {
        setDraftLoadError(
          "We couldn't load your saved report draft from the server. You're viewing a local preview based on this analysis — reconnect to sync your draft.",
        );
        const summary = buildDeterministicExecutiveSummary(
          richSummaryInput(
            insightResultsRef.current?.length
              ? insightResultsRef.current
              : insightsRef.current,
          ),
        );
        const selected = selectRecommendedInsightKeys(
          insightResultsRef.current?.length
            ? insightResultsRef.current
            : insightsRef.current,
        );
        setDraft({
          title:    projectName ?? "",
          summary:  narrative?.trim() ? narrative : summary,
          selected,
          template: undefined,
        });
        setExportHistory([]);
        setLoaded(true);
      });
  }, [projectId, projectName, richSummaryInput]);

  // If insights arrive after the first fetch (streaming UI), fill an empty selection once.
  useEffect(() => {
    if (!loaded || draftLoadError) return;
    const list = allInsightsRef.current;
    if (list.length === 0) return;
    setDraft((prev) => {
      if (prev.selected.length > 0) return prev;
      const rec = selectRecommendedInsightKeys(list);
      if (rec.length === 0) return prev;
      const next = { ...prev, selected: rec };
      persistDraft(next);
      return next;
    });
  }, [loaded, allInsights.length, draftLoadError, persistDraft]);

  function update(patch: Partial<Draft>) {
    setDraft((prev) => {
      const next = { ...prev, ...patch };
      persistDraft(next);
      return next;
    });
  }

  function moveChart(chartId: string, direction: "up" | "down") {
    setSelectedChartIds((prev) => {
      const idx = prev.indexOf(chartId);
      if (idx === -1) return prev;
      if (direction === "up"   && idx === 0)              return prev;
      if (direction === "down" && idx === prev.length - 1) return prev;
      const next = [...prev];
      const swap = direction === "up" ? idx - 1 : idx + 1;
      [next[idx], next[swap]] = [next[swap], next[idx]];
      if (saveTimer.current) clearTimeout(saveTimer.current);
      setSaved(false);
      setSaving(true);
      saveDraftReport(projectId, {
        title:                draft.title,
        summary:              draft.summary,
        selected_insight_ids: draft.selected,
        selected_chart_ids:   next,
        template:             draft.template ?? null,
      })
        .then(() => setSaved(true))
        .catch(() => {/* silent */})
        .finally(() => setSaving(false));
      return next;
    });
  }

  function toggleChart(chartId: string) {
    setSelectedChartIds((prev) => {
      const next = prev.includes(chartId)
        ? prev.filter((id) => id !== chartId)
        : [...prev, chartId];
      // Persist using the already-queued insight draft state — fire a save
      // immediately (not debounced via persistDraft) so chart toggles are
      // independent of any in-flight summary edit.
      if (saveTimer.current) clearTimeout(saveTimer.current);
      setSaved(false);
      setSaving(true);
      saveDraftReport(projectId, {
        title:                draft.title,
        summary:              draft.summary,
        selected_insight_ids: draft.selected,
        selected_chart_ids:   next,
        template:             draft.template ?? null,
      })
        .then(() => setSaved(true))
        .catch(() => {/* silent — local state still updated */})
        .finally(() => setSaving(false));
      return next;
    });
  }

  function toggleInsight(ins: InsightItem, idx: number) {
    const key = selectionKey(ins, idx);
    setDraft((prev) => {
      const next = {
        ...prev,
        selected: prev.selected.includes(key)
          ? prev.selected.filter((k) => k !== key)
          : [...prev.selected, key],
      };
      persistDraft(next);
      return next;
    });
  }

  function pushExportRecord(rec: ExportRecord) {
    setExportHistory((prev) => [rec, ...prev].slice(0, 6));
  }

  // Re-fetch the draft after an export attempt and replace the local
  // history with the canonical, audit-log-backed list.  This is what
  // makes a refresh / reopen show the exact same strip the user saw
  // immediately after exporting — no duplicates, no drift.  Best-effort
  // only; if the GET fails the optimistic local row stays visible.
  const refreshExportHistory = useCallback(async () => {
    try {
      const d = await getDraftReport(projectId);
      const rr = d?.report_result;
      const remoteHistory = (rr?.export_statuses ?? [])
        .map(fromBackendExport)
        .filter((x): x is ExportRecord => x !== null)
        .slice(0, 6);
      if (remoteHistory.length > 0) {
        setExportHistory(remoteHistory);
      }
    } catch {
      // silent — keep the optimistic local row
    }
  }, [projectId]);

  async function handleExport(format: "pdf" | "xlsx" | "html") {
    setExportErr(null);
    setPdfUnavailable(false);
    if (reportIsWeak) setExportedWeak(true);
    setExporting(format);
    try {
      await exportReport(projectId, format);
      // Optimistic append for instant feedback…
      pushExportRecord({ format, status: "success", at: new Date() });
    } catch (e) {
      if (e instanceof ApiError && e.status === 501 && format === "pdf") {
        setPdfUnavailable(true);
        pushExportRecord({ format: "pdf", status: "unavailable", at: new Date() });
      } else {
        const msg = e instanceof ApiError ? e.userMessage : "Export failed — please try again.";
        setExportErr(msg);
        pushExportRecord({ format, status: "failed", at: new Date(), message: msg });
      }
    } finally {
      setExporting(null);
      // …then reconcile against the audit-log-backed canonical list so
      // the row carries the server timestamp and survives a page refresh.
      refreshExportHistory();
    }
  }

  // ── Derived preview values ──────────────────────────────────────────────────

  // Resolve every saved selection key back to the live insight on this run.
  // Missing keys (e.g. an insight_id from a previous run that no longer
  // exists) are dropped silently — we'd rather show fewer findings than
  // surface the wrong one.
  const selectedInsights = draft.selected
    .map((k) => findInsightByKey(allInsights, k))
    .filter((x): x is InsightItem => Boolean(x));

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

  // Report is "weak" when there is nothing meaningful to export yet
  const summaryTooShort = draft.summary.trim().length < 40;
  const noFindingsSelected = selectedInsights.length === 0 && allInsights.length > 0;
  const reportIsWeak = noFindingsSelected || summaryTooShort;

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

      {draftLoadError && (
        <div className="flex gap-3 rounded-xl border border-amber-500/25 bg-amber-500/[0.07] px-4 py-3">
          <AlertTriangle className="mt-0.5 h-4 w-4 flex-shrink-0 text-amber-400" />
          <p className="text-sm leading-snug text-amber-100/90">{draftLoadError}</p>
        </div>
      )}

      {/* ── Pre-write brief ───────────────────────────────────────────────── */}
      <ReportBrief
        allInsights={allInsights}
        healthResult={healthResult}
        cleaningResult={cleaningResult}
        compareResult={compareResult}
      />

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
          <div className="mb-1.5 flex flex-wrap items-center justify-between gap-2">
            <div className="flex items-center gap-2">
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
            <button
              type="button"
              onClick={() =>
                update({
                  summary: buildDeterministicExecutiveSummary(richSummaryInput(allInsights)),
                })
              }
              className="inline-flex items-center gap-1.5 rounded-lg border border-white/[0.08] bg-white/[0.04] px-2.5 py-1 text-[11px] font-medium text-white/55 transition hover:border-white/15 hover:bg-white/[0.07] hover:text-white/75"
            >
              <RefreshCw className="h-3 w-3" />
              Regenerate executive summary
            </button>
          </div>
          <textarea
            value={draft.summary}
            onChange={(e) => update({ summary: e.target.value })}
            rows={4}
            placeholder="Write a client-safe summary of what you found and why it matters…"
            className="w-full resize-none rounded-xl border border-white/[0.08] bg-white/[0.03] px-4 py-2.5 text-sm text-white placeholder:text-white/20 focus:border-indigo-500/50 focus:outline-none"
          />
          {draft.summary.trim().length === 0 && (
            <p className="mt-1 text-[11px] text-white/30">
              Add a short executive summary before exporting — 2–3 sentences is enough.
            </p>
          )}
          {draft.summary.trim().length > 0 && draft.summary.trim().length < 40 && (
            <p className="mt-1 text-[11px] text-amber-400/60">
              Summary is quite short — a bit more context will help the client understand the key takeaway.
            </p>
          )}
        </div>

        {/* Insight selection */}
        {allInsights.length > 0 && (
          <div>
            <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
              <label className="text-xs font-semibold uppercase tracking-wider text-white/40">
                Select findings to include
              </label>
              <div className="flex flex-wrap items-center gap-2">
                <button
                  type="button"
                  onClick={() =>
                    update({ selected: selectRecommendedInsightKeys(allInsights) })
                  }
                  disabled={allInsights.length === 0}
                  className="rounded-lg border border-indigo-500/25 bg-indigo-500/10 px-2.5 py-1 text-[11px] font-medium text-indigo-300 transition hover:border-indigo-500/40 hover:bg-indigo-500/15 disabled:cursor-not-allowed disabled:opacity-40"
                >
                  Select recommended findings
                </button>
                <span className="text-xs text-white/25">
                  {selectedInsights.length} / {Math.min(allInsights.length, 10)} selected
                </span>
              </div>
            </div>
            <div className="space-y-1.5">
              {allInsights.slice(0, 10).map((ins, idx) => {
                const key = selectionKey(ins, idx);
                const selected = draft.selected.includes(key);
                const label = ins.title || ins.explanation || ins.finding || `Finding ${idx + 1}`;
                return (
                  <button
                    key={typeof key === "string" ? key : `idx-${idx}`}
                    onClick={() => toggleInsight(ins, idx)}
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

            {/* No findings selected hint */}
            {allInsights.length > 0 && selectedInsights.length === 0 && (
              <div className="flex flex-col gap-2 rounded-lg border border-amber-500/15 bg-amber-500/[0.04] px-3 py-2 sm:flex-row sm:items-center sm:justify-between">
                <p className="text-xs text-amber-200/85">
                  No findings selected yet — choose 2–5 findings to build a client report.
                </p>
                <div className="flex flex-shrink-0 gap-2">
                  <button
                    type="button"
                    onClick={() =>
                      update({ selected: selectRecommendedInsightKeys(allInsights) })
                    }
                    className="rounded-lg border border-amber-500/30 bg-amber-500/10 px-2.5 py-1 text-[11px] font-medium text-amber-200 transition hover:bg-amber-500/15"
                  >
                    Select recommended
                  </button>
                  {onNavigateTo && (
                    <button
                      type="button"
                      onClick={() => onNavigateTo("insights")}
                      className="text-xs font-medium text-amber-400 transition hover:text-amber-300"
                    >
                      Review Findings →
                    </button>
                  )}
                </div>
              </div>
            )}

            {/* Compare soft nudge */}
            {!compareResult && allInsights.length > 0 && (
              <div className="flex items-center justify-between">
                <p className="text-[11px] text-white/25">
                  No comparison loaded — upload a second file to add a before/after summary
                </p>
                {onNavigateTo && (
                  <button
                    onClick={() => onNavigateTo("compare-files")}
                    className="ml-3 flex-shrink-0 text-[11px] text-white/35 transition hover:text-white/55"
                  >
                    Compare Files →
                  </button>
                )}
              </div>
            )}
          </div>
        )}

        {/* Chart selection */}
        <div>
          <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
            <label className="text-xs font-semibold uppercase tracking-wider text-white/40">
              Charts to include
            </label>
            {availableCharts.length > 0 && (
              <span className="text-xs text-white/25">
                {selectedChartIds.length} / {availableCharts.length} selected
              </span>
            )}
          </div>

          {availableCharts.length === 0 ? (
            <div className="rounded-xl border border-white/[0.06] bg-white/[0.015] px-4 py-3">
              <p className="text-xs text-white/30">
                No chart suggestions are available for this run yet.
              </p>
            </div>
          ) : (() => {
            // Derive two ordered sublists:
            // 1. selected: in selectedChartIds order (so Up/Down have meaning)
            // 2. unselected: in catalog order
            const byId = Object.fromEntries(availableCharts.map((c) => [c.chart_id, c]));
            const selectedRows = selectedChartIds
              .map((id) => byId[id])
              .filter((c): c is AvailableChart => Boolean(c));
            const unselectedRows = availableCharts.filter(
              (c) => !selectedChartIds.includes(c.chart_id),
            );
            return (
              <>
                <div className="space-y-1.5">
                  {selectedRows.map((ch, rowIdx) => (
                    <div
                      key={ch.chart_id}
                      className="flex items-center gap-2 rounded-xl border border-indigo-500/40 bg-indigo-600/8 px-3 py-2.5"
                    >
                      {/* Checkbox */}
                      <button
                        type="button"
                        onClick={() => toggleChart(ch.chart_id)}
                        className="flex h-4 w-4 flex-shrink-0 items-center justify-center rounded border border-indigo-500 bg-indigo-600 transition-colors"
                        aria-label={`Remove ${ch.title || ch.chart_id}`}
                      >
                        <CheckCircle className="h-3 w-3 text-white" />
                      </button>
                      <BarChart2 className="h-3.5 w-3.5 flex-shrink-0 text-indigo-400/60" />
                      <div className="min-w-0 flex-1">
                        <p className="truncate text-xs font-medium text-white/80">
                          {ch.title || ch.chart_id}
                        </p>
                      </div>
                      <span className="flex-shrink-0 rounded-full border border-indigo-500/25 bg-indigo-500/10 px-1.5 py-px text-[10px] font-medium uppercase tracking-wide text-indigo-300">
                        {ch.chart_type}
                      </span>
                      {/* Up / Down */}
                      <div className="flex flex-shrink-0 flex-col gap-px">
                        <button
                          type="button"
                          disabled={rowIdx === 0}
                          onClick={() => moveChart(ch.chart_id, "up")}
                          className="flex h-4 w-4 items-center justify-center rounded text-white/30 transition hover:text-white/70 disabled:cursor-not-allowed disabled:opacity-20"
                          aria-label="Move up"
                        >
                          <ChevronUp className="h-3.5 w-3.5" />
                        </button>
                        <button
                          type="button"
                          disabled={rowIdx === selectedRows.length - 1}
                          onClick={() => moveChart(ch.chart_id, "down")}
                          className="flex h-4 w-4 items-center justify-center rounded text-white/30 transition hover:text-white/70 disabled:cursor-not-allowed disabled:opacity-20"
                          aria-label="Move down"
                        >
                          <ChevronDown className="h-3.5 w-3.5" />
                        </button>
                      </div>
                    </div>
                  ))}

                  {/* Unselected charts — add-only, no reorder controls */}
                  {unselectedRows.length > 0 && selectedRows.length > 0 && (
                    <div className="my-1 border-t border-white/[0.05]" />
                  )}
                  {unselectedRows.map((ch) => (
                    <button
                      key={ch.chart_id}
                      type="button"
                      onClick={() => toggleChart(ch.chart_id)}
                      className="flex w-full items-center gap-2 rounded-xl border border-white/[0.06] bg-white/[0.015] px-3 py-2.5 text-left transition-all hover:border-white/10"
                    >
                      <div className="flex h-4 w-4 flex-shrink-0 items-center justify-center rounded border border-white/20 transition-colors" />
                      <BarChart2 className="h-3.5 w-3.5 flex-shrink-0 text-white/25" />
                      <div className="min-w-0 flex-1">
                        <p className="truncate text-xs font-medium text-white/80">
                          {ch.title || ch.chart_id}
                        </p>
                      </div>
                      <span className="flex-shrink-0 rounded-full border border-white/10 bg-white/[0.03] px-1.5 py-px text-[10px] font-medium uppercase tracking-wide text-white/35">
                        {ch.chart_type}
                      </span>
                    </button>
                  ))}
                </div>

                {selectedChartIds.length === 0 && (
                  <p className="mt-2 text-[11px] text-white/30">
                    No charts selected for this report yet.
                  </p>
                )}
                {selectedChartIds.length > 0 && (
                  <p className="mt-2 text-[11px] text-white/30">
                    Chart order controls the order used in HTML and Excel exports.
                  </p>
                )}
              </>
            );
          })()}
        </div>

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
                <p className="mt-1 text-xs text-white/30">Generated by Analyst Pro</p>
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

            {/* Selected Charts preview */}
            {(() => {
              const byAvailId = Object.fromEntries(availableCharts.map((c) => [c.chart_id, c]));
              const previewCharts = availableCharts.length > 0
                // Map selectedChartIds in order so the preview reflects any reordering.
                ? selectedChartIds.map((id) => byAvailId[id]).filter((c): c is AvailableChart => Boolean(c))
                : includedCharts.map((ch) => ({ ...ch, selected: true }));
              if (previewCharts.length === 0) return null;
              return (
                <PreviewSection icon={BarChart2} title="Selected Charts" accent="indigo">
                  <div className="space-y-1.5">
                    {previewCharts.map((ch) => (
                      <div
                        key={ch.chart_id}
                        className="flex items-center justify-between gap-3 rounded-lg border border-white/[0.06] bg-white/[0.02] px-4 py-2.5"
                      >
                        <p className="min-w-0 flex-1 truncate text-xs text-white/70">
                          {ch.title || ch.chart_id}
                        </p>
                        <span className="flex-shrink-0 rounded-full border border-indigo-500/25 bg-indigo-500/10 px-1.5 py-px text-[10px] font-medium uppercase tracking-wide text-indigo-300">
                          {ch.chart_type}
                        </span>
                      </div>
                    ))}
                  </div>
                </PreviewSection>
              );
            })()}

            {/* Comparison Summary — only rendered when compare data is available */}
            {hasCompare && (
              <PreviewSection icon={TrendingUp} title="Comparison Summary" accent="emerald">
                <div className="space-y-3">
                  {/* AI summary draft */}
                  {compareResult?.summary_draft && (
                    <p className="text-sm leading-relaxed text-white/70">{compareResult.summary_draft}</p>
                  )}

                  {/* Health score change */}
                  {compareResult?.health_changes && (
                    <div className="grid grid-cols-2 gap-2">
                      {[
                        { label: compareResult.file_a.file_name, score: compareResult.health_changes.score_a, grade: compareResult.health_changes.grade_a },
                        { label: compareResult.file_b.file_name, score: compareResult.health_changes.score_b, grade: compareResult.health_changes.grade_b },
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

                  {/* Row volume change */}
                  {compareResult?.row_volume_changes && (() => {
                    const rv = compareResult.row_volume_changes;
                    const diff = rv.diff;
                    const pct  = rv.diff_pct;
                    if (diff === 0) return null;
                    const sign = diff > 0 ? "+" : "";
                    return (
                      <p className="text-xs text-white/50">
                        Row count changed: {rv.count_a.toLocaleString()} → {rv.count_b.toLocaleString()}
                        {" "}
                        <span className={diff > 0 ? "text-emerald-400" : "text-red-400"}>
                          ({sign}{diff.toLocaleString()}{pct != null ? `, ${sign}${pct.toFixed(1)}%` : ""})
                        </span>
                      </p>
                    );
                  })()}

                  {/* Schema changes */}
                  {compareResult?.schema_changes && (() => {
                    const sc = compareResult.schema_changes;
                    const added   = sc.added_columns.length;
                    const removed = sc.removed_columns.length;
                    if (added === 0 && removed === 0) return null;
                    return (
                      <div className="flex flex-wrap gap-1.5">
                        {sc.added_columns.slice(0, 4).map((col) => (
                          <span key={col} className="rounded-full border border-emerald-500/30 bg-emerald-500/10 px-2 py-px text-[10px] text-emerald-300">
                            + {col}
                          </span>
                        ))}
                        {sc.removed_columns.slice(0, 4).map((col) => (
                          <span key={col} className="rounded-full border border-red-500/30 bg-red-500/10 px-2 py-px text-[10px] text-red-300">
                            − {col}
                          </span>
                        ))}
                        {(added > 4 || removed > 4) && (
                          <span className="text-[10px] text-white/30 self-center">
                            +{Math.max(0, added - 4) + Math.max(0, removed - 4)} more
                          </span>
                        )}
                      </div>
                    );
                  })()}

                  {/* Top significant metric deltas */}
                  {compareResult?.metric_deltas && (() => {
                    const significant = compareResult.metric_deltas
                      .filter((d) => d.change_flag === "significant" || d.change_flag === "notable")
                      .slice(0, 3);
                    if (significant.length === 0) return null;
                    return (
                      <div className="space-y-1">
                        <p className="text-[10px] font-medium uppercase tracking-wider text-white/25">
                          Key metric shifts
                        </p>
                        {significant.map((d) => {
                          const pct = d.mean_delta_pct;
                          const sign = pct != null && pct > 0 ? "+" : "";
                          const color = d.change_flag === "significant" ? "text-red-400" : "text-amber-400";
                          return (
                            <div key={d.column} className="flex items-center justify-between text-xs">
                              <span className="text-white/60 font-medium">{d.column}</span>
                              <span className={`font-mono ${color}`}>
                                {pct != null ? `${sign}${pct.toFixed(1)}%` : "—"}
                              </span>
                            </div>
                          );
                        })}
                      </div>
                    );
                  })()}

                  {/* Caution flags */}
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

            {/* Large-dataset methodology note */}
            {datasetSummary?.large_dataset_mode && (
              <div className="rounded-lg border border-blue-500/25 bg-blue-500/[0.08] px-4 py-2.5 text-xs text-blue-300">
                <span className="font-semibold text-blue-200">Large Dataset</span>
                {" — "}
                {(datasetSummary.analyzed_rows ?? datasetSummary.rows ?? 0).toLocaleString()} rows analyzed.
                {datasetSummary.sample_strategy && (
                  <span className="text-blue-300/70"> {datasetSummary.sample_strategy}</span>
                )}
              </div>
            )}

            {/* Report footer metadata */}
            <div className="rounded-xl border border-white/[0.05] bg-white/[0.02] px-4 py-3 space-y-1.5">
              <div className="flex items-center gap-1.5 mb-1">
                <Info className="h-3 w-3 text-white/20" />
                <p className="text-[10px] font-semibold uppercase tracking-wider text-white/20">
                  Included in every export
                </p>
              </div>
              <div className="flex flex-wrap gap-x-4 gap-y-1 text-[10px] text-white/35">
                <span>Source file name</span>
                <span>Rows &amp; columns analyzed</span>
                <span>Cleaning steps applied</span>
                <span>Generated timestamp</span>
              </div>
              <p className="text-[10px] text-white/20 pt-0.5">
                Full export also includes: data quality breakdown, column profiles, cleaning history.
              </p>
              <span className="inline-flex items-center gap-1 rounded-full border border-indigo-500/20 bg-indigo-500/[0.07] px-2 py-px text-[10px] text-indigo-400/70">
                <Sparkles className="h-2.5 w-2.5" />
                AI-assisted draft — review before sharing
              </span>
            </div>

          </div>
        )}
      </div>

      {/* ── Export ────────────────────────────────────────────────────────── */}
      <div className="space-y-3 border-t border-white/[0.06] pt-4">

        {/* Buttons row */}
        <div className="flex flex-wrap items-center gap-3">
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
          <button
            onClick={() => handleExport("html")}
            disabled={!!exporting}
            className="flex items-center gap-2 rounded-xl border border-white/10 bg-white/[0.04] px-4 py-2.5 text-sm font-medium text-white/70 transition hover:bg-white/[0.07] hover:text-white disabled:opacity-60"
          >
            {exporting === "html" ? <Loader2 className="h-4 w-4 animate-spin" /> : <FileText className="h-4 w-4" />}
            Export HTML
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

        {/* PDF unavailable — actionable fallback */}
        {pdfUnavailable && (
          <div className="rounded-xl border border-amber-500/20 bg-amber-500/[0.05] px-4 py-3 space-y-2">
            <div className="flex items-start gap-2">
              <AlertTriangle className="mt-0.5 h-4 w-4 flex-shrink-0 text-amber-400" />
              <div>
                <p className="text-sm font-medium text-amber-300">PDF export not available on this server</p>
                <p className="mt-0.5 text-xs text-white/50">
                  The PDF renderer is not installed. Export as HTML or Excel instead — HTML can be printed to PDF from any browser.
                </p>
              </div>
            </div>
            <div className="flex gap-2 pl-6">
              <button
                onClick={() => { setPdfUnavailable(false); handleExport("html"); }}
                disabled={!!exporting}
                className="flex items-center gap-1.5 rounded-lg border border-white/10 bg-white/[0.04] px-3 py-1.5 text-xs font-medium text-white/70 hover:bg-white/[0.07] hover:text-white disabled:opacity-60"
              >
                {exporting === "html" ? <Loader2 className="h-3 w-3 animate-spin" /> : <FileText className="h-3 w-3" />}
                Export HTML instead
              </button>
              <button
                onClick={() => { setPdfUnavailable(false); handleExport("xlsx"); }}
                disabled={!!exporting}
                className="flex items-center gap-1.5 rounded-lg border border-white/10 bg-white/[0.04] px-3 py-1.5 text-xs font-medium text-white/70 hover:bg-white/[0.07] hover:text-white disabled:opacity-60"
              >
                {exporting === "xlsx" ? <Loader2 className="h-3 w-3 animate-spin" /> : <FileText className="h-3 w-3" />}
                Export Excel instead
              </button>
            </div>
          </div>
        )}

        {/* Generic error */}
        {exportErr && (
          <div className="flex items-start gap-2 rounded-xl border border-red-500/20 bg-red-500/5 px-4 py-2.5">
            <AlertTriangle className="mt-0.5 h-4 w-4 flex-shrink-0 text-red-400" />
            <p className="text-sm text-red-400">{exportErr}</p>
          </div>
        )}

        {/* Export history strip */}
        {exportHistory.length > 0 && (
          <ExportHistoryStrip history={exportHistory} onRetry={handleExport} exporting={exporting} />
        )}

        {/* Weak-content warning — shown after first export attempt with thin content */}
        {exportedWeak && reportIsWeak && (
          <div className="flex items-start gap-2 rounded-xl border border-amber-500/15 bg-amber-500/[0.04] px-4 py-2.5">
            <AlertTriangle className="mt-0.5 h-3.5 w-3.5 flex-shrink-0 text-amber-400/70" />
            <p className="text-xs text-amber-300/70">
              This export may be too thin for client delivery —{" "}
              {noFindingsSelected && "select some findings"}
              {noFindingsSelected && summaryTooShort && " and "}
              {summaryTooShort && "add an executive summary"}
              {" "}to strengthen the report.
            </p>
          </div>
        )}

      </div>
    </div>
  );
}

// ── ExportHistoryStrip ────────────────────────────────────────────────────────

function ExportHistoryStrip({
  history,
  onRetry,
  exporting,
}: {
  history: ExportRecord[];
  onRetry: (format: "pdf" | "xlsx" | "html") => void;
  exporting: string | null;
}) {
  const lastSuccess = history.find((r) => r.status === "success");

  return (
    <div className="rounded-xl border border-white/[0.06] bg-white/[0.015] px-4 py-3 space-y-2.5">
      {/* Summary line */}
      <div className="flex items-center justify-between gap-3">
        <p className="text-[10px] font-semibold uppercase tracking-wider text-white/25">
          Export history
        </p>
        {lastSuccess && (
          <span className="flex items-center gap-1 rounded-full border border-emerald-500/20 bg-emerald-500/[0.07] px-2 py-px text-[10px] font-medium text-emerald-400">
            <Check className="h-2.5 w-2.5" />
            Last success: {FORMAT_LABEL[lastSuccess.format]} · {relativeTime(lastSuccess.at)}
          </span>
        )}
      </div>

      {/* Row per attempt */}
      <div className="space-y-1.5">
        {history.map((rec, i) => {
          const isSuccess     = rec.status === "success";
          const isUnavailable = rec.status === "unavailable";
          const isFailed      = rec.status === "failed";

          return (
            <div key={i} className="flex items-center gap-2.5">
              {/* Status icon */}
              <span className={`flex h-4 w-4 flex-shrink-0 items-center justify-center rounded-full ${
                isSuccess     ? "bg-emerald-500/15"
                : isUnavailable ? "bg-amber-500/15"
                : "bg-red-500/15"
              }`}>
                {isSuccess     && <Check          className="h-2.5 w-2.5 text-emerald-400" />}
                {isUnavailable && <AlertTriangle  className="h-2.5 w-2.5 text-amber-400" />}
                {isFailed      && <X              className="h-2.5 w-2.5 text-red-400" />}
              </span>

              {/* Format badge */}
              <span className={`rounded border px-1.5 py-px text-[10px] font-medium ${
                isSuccess
                  ? "border-emerald-500/20 text-emerald-300"
                  : isUnavailable
                  ? "border-amber-500/20 text-amber-300/70"
                  : "border-red-500/20 text-red-300/70"
              }`}>
                {FORMAT_LABEL[rec.format]}
              </span>

              {/* Status text */}
              <p className={`flex-1 text-[11px] leading-snug ${
                isSuccess ? "text-white/55" : isUnavailable ? "text-amber-400/70" : "text-red-400/70"
              }`}>
                {isSuccess
                  ? "Downloaded successfully"
                  : isUnavailable
                  ? "Not available on this server — use HTML or Excel"
                  : (rec.message ?? "Export failed")}
              </p>

              {/* Timestamp */}
              <span className="flex-shrink-0 text-[10px] text-white/20">
                {relativeTime(rec.at)}
              </span>

              {/* Retry for failures */}
              {isFailed && (
                <button
                  onClick={() => onRetry(rec.format)}
                  disabled={!!exporting}
                  className="flex-shrink-0 rounded border border-white/10 px-1.5 py-0.5 text-[10px] text-white/35 hover:border-white/20 hover:text-white/60 disabled:opacity-40 transition-colors"
                >
                  Retry
                </button>
              )}
            </div>
          );
        })}
      </div>

      {/* Sendable formats note — only when at least one success exists */}
      {lastSuccess && (() => {
        const successFormats = [...new Set(
          history.filter((r) => r.status === "success").map((r) => FORMAT_LABEL[r.format])
        )];
        return (
          <p className="text-[10px] text-white/30 border-t border-white/[0.05] pt-2">
            Ready to send: {successFormats.join(", ")}
          </p>
        );
      })()}
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
