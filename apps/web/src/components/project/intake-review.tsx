"use client";

import { CheckCircle, AlertTriangle, Info } from "lucide-react";

type ParseReport = {
  file_kind?: string;
  status?: string;
  confidence?: number;
  header_row?: number | null;
  table_start_row?: number | null;
  footer_start_row?: number | null;
  preamble_rows_skipped?: number;
  warnings?: string[];
  parsing_decisions?: string[];
  metadata?: Record<string, string>;
};

type Props = {
  filename: string;
  parseReport: ParseReport;
};

export function IntakeReview({ filename, parseReport }: Props) {
  const {
    file_kind = "flat_table",
    status = "ok",
    confidence = 1,
    header_row,
    preamble_rows_skipped = 0,
    footer_start_row,
    warnings = [],
    metadata = {},
  } = parseReport;

  const hasIssues = status !== "ok" || warnings.length > 0;
  const confidencePct = Math.round(confidence * 100);

  return (
    <div className="rounded-xl border border-white/[0.08] bg-white/[0.02] p-4 space-y-3">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          {hasIssues ? (
            <AlertTriangle className="h-4 w-4 text-amber-400 flex-shrink-0" />
          ) : (
            <CheckCircle className="h-4 w-4 text-emerald-400 flex-shrink-0" />
          )}
          <p className="text-sm font-semibold text-white">
            {hasIssues ? "File parsed with adjustments" : "File structure detected"}
          </p>
        </div>
        <span
          className={`rounded-full px-2 py-0.5 text-[10px] font-medium ${
            confidencePct >= 80
              ? "bg-emerald-500/15 text-emerald-400"
              : "bg-amber-500/15 text-amber-400"
          }`}
        >
          {confidencePct}% confidence
        </span>
      </div>

      {/* Detection details */}
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
        {[
          {
            label: "File type",
            value: file_kind.replace("_", " "),
          },
          {
            label: "Header row",
            value: header_row != null ? `Row ${header_row + 1}` : "Auto",
          },
          {
            label: "Preamble skipped",
            value:
              preamble_rows_skipped > 0
                ? `${preamble_rows_skipped} row${preamble_rows_skipped > 1 ? "s" : ""}`
                : "None",
            highlight: preamble_rows_skipped > 0,
          },
          {
            label: "Footer trimmed",
            value: footer_start_row != null ? `From row ${footer_start_row}` : "None",
            highlight: footer_start_row != null,
          },
        ].map((item) => (
          <div
            key={item.label}
            className="rounded-lg border border-white/[0.06] bg-white/[0.02] px-3 py-2"
          >
            <p className="text-[10px] text-white/35">{item.label}</p>
            <p
              className={`mt-0.5 text-xs font-medium ${
                item.highlight ? "text-amber-300" : "text-white/70"
              }`}
            >
              {item.value}
            </p>
          </div>
        ))}
      </div>

      {/* Preamble metadata extracted */}
      {Object.keys(metadata).length > 0 && (
        <div className="rounded-lg border border-indigo-500/20 bg-indigo-500/5 px-3 py-2">
          <p className="mb-1 text-[10px] font-medium text-indigo-400 uppercase tracking-wider">
            Extracted from header rows
          </p>
          <div className="flex flex-wrap gap-x-4 gap-y-1">
            {Object.entries(metadata).map(([k, v]) => (
              <span key={k} className="text-xs text-white/60">
                <span className="text-white/35">{k}:</span> {v}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Warnings */}
      {warnings.length > 0 && (
        <div className="space-y-1">
          {warnings.map((w, i) => (
            <div key={i} className="flex items-start gap-2">
              <Info className="mt-0.5 h-3.5 w-3.5 flex-shrink-0 text-amber-400/70" />
              <p className="text-xs text-white/50">{w}</p>
            </div>
          ))}
        </div>
      )}

      <p className="text-[11px] text-white/25">
        Parsed from <span className="text-white/40">{filename}</span> — looks right? Continue to Health to review the cleaning.
      </p>
    </div>
  );
}
