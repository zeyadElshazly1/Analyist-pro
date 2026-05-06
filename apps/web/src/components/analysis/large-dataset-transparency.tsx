"use client";

import { Layers } from "lucide-react";

import type { LargeDatasetMeta } from "@/lib/api";
import { LARGE_DATASET_METHODOLOGY_NOTE } from "@/lib/api";

function sampleStrategyLabel(raw: string | undefined): string | undefined {
  if (!raw?.trim()) return undefined;
  const key = raw.trim();
  const labels: Record<string, string> = {
    timeseries_recent_rows_per_symbol: "Recent rows per symbol (time-series panel)",
    random_uniform: "Uniform random sample across rows",
    random_uniform_fallback_non_ts: "Uniform random sample (could not confirm time-series shape)",
    random_uniform_fallback_bad_dates: "Uniform random sample (date parsing fallback)",
    full: "Full dataset",
  };
  return labels[key] ?? key.replace(/_/g, " ");
}

type Props = {
  meta: LargeDatasetMeta;
  /** Full banner after tabs — compact single methodology paragraph for Report Builder preview */
  variant?: "full" | "compact";
};

export function LargeDatasetTransparencyBanner({ meta, variant = "full" }: Props) {
  if (!meta.large_dataset_mode) return null;

  if (variant === "compact") {
    return (
      <div className="rounded-lg border border-indigo-500/25 bg-indigo-500/[0.07] px-4 py-3">
        <p className="text-[10px] font-semibold uppercase tracking-wider text-indigo-300/80">
          Methodology
        </p>
        <p className="mt-1.5 text-xs leading-relaxed text-white/55">{LARGE_DATASET_METHODOLOGY_NOTE}</p>
      </div>
    );
  }

  const fullRows = meta.full_rows;
  const analyzed = meta.analyzed_rows;
  const symbols = meta.symbol_count;
  const d0 = meta.date_range_start;
  const d1 = meta.date_range_end;
  const strategyLine = sampleStrategyLabel(meta.sample_strategy);

  return (
    <div
      className="flex gap-3 rounded-xl border border-violet-500/30 bg-violet-500/[0.07] px-4 py-3.5"
      role="status"
    >
      <Layers className="mt-0.5 h-5 w-5 flex-shrink-0 text-violet-400" aria-hidden />
      <div className="min-w-0 space-y-2 text-sm leading-snug">
        <p className="font-semibold text-violet-100">Large dataset mode used</p>
        {typeof fullRows === "number" && typeof analyzed === "number" ? (
          <p className="text-[13px] text-white/70">
            Full file:{" "}
            <span className="font-medium text-white/[0.82]">{fullRows.toLocaleString()}</span> rows ·
            Analyzed/sample rows for expensive detectors:{" "}
            <span className="font-medium text-white/[0.82]">{analyzed.toLocaleString()}</span>
          </p>
        ) : (
          <p className="text-[13px] text-white/70">{LARGE_DATASET_METHODOLOGY_NOTE}</p>
        )}
        {strategyLine ? (
          <p className="text-xs text-white/50">
            <span className="text-white/40">Sample strategy:</span> {strategyLine}
          </p>
        ) : null}
        {typeof fullRows === "number" && typeof analyzed === "number" ? (
          <p className="text-[11px] leading-snug text-white/42">{LARGE_DATASET_METHODOLOGY_NOTE}</p>
        ) : null}
        {typeof symbols === "number" ? (
          <p className="text-xs text-white/50">Symbols covered: {symbols.toLocaleString()}</p>
        ) : null}
        {d0 && d1 ? (
          <p className="text-xs text-white/50">
            Date range: {d0} → {d1}
          </p>
        ) : d0 ? (
          <p className="text-xs text-white/50">Date range starts: {d0}</p>
        ) : d1 ? (
          <p className="text-xs text-white/50">Date range ends: {d1}</p>
        ) : null}
      </div>
    </div>
  );
}
