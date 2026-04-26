"use client";

import { useState } from "react";
import { CheckCircle2, AlertTriangle, XCircle, ChevronDown, ChevronUp } from "lucide-react";

// Canonical IntakeResult shape — mirrors app/schemas/intake.py
type IntakeResult = {
  file_id?: number;
  file_name?: string;
  parse_status?: "ok" | "parsed_with_warnings" | "fallback";
  confidence?: number;
  file_kind?: "flat_table" | "preamble_csv" | "sectioned_csv" | "excel";
  detected_header_row?: number | null;
  preamble_rows?: number[];
  footer_rows?: number[];
  delimiter?: string;
  encoding?: string;
  n_columns?: number;
  warnings?: string[];
  parsing_decisions?: string[];
  file_metadata?: Record<string, unknown>;
  preview_sample?: Record<string, unknown>[];
};

// Legacy ParseReport — kept only as fallback for old upload responses
type LegacyParseReport = {
  file_kind?: string;
  status?: string;
  confidence?: number;
  header_row?: number | null;
  footer_start_row?: number | null;
  preamble_rows_skipped?: number;
  warnings?: string[];
  parsing_decisions?: string[];
  metadata?: Record<string, string>;
};

type Props = {
  filename: string;
  intakeResult?: IntakeResult | null;
  parseReport?: LegacyParseReport | null;
};

const FILE_KIND_LABELS: Record<string, string> = {
  flat_table:    "Standard table",
  preamble_csv:  "CSV with title rows",
  sectioned_csv: "Multi-section CSV",
  excel:         "Excel workbook",
};

const DELIMITER_LABELS: Record<string, string> = {
  ",":  "Comma (,)",
  "\t": "Tab",
  ";":  "Semicolon (;)",
  "|":  "Pipe (|)",
  "":   "N/A (Excel)",
};

function delimiterLabel(d: string | undefined): string {
  if (d == null) return "Auto-detected";
  return DELIMITER_LABELS[d] ?? d;
}

function statusConfig(status: string) {
  if (status === "ok") {
    return {
      Icon: CheckCircle2,
      label: "Parsed successfully",
      banner: "border-emerald-500/20 bg-emerald-500/5",
      iconColor: "text-emerald-400",
      textColor: "text-emerald-300",
    };
  }
  if (status === "parsed_with_warnings") {
    return {
      Icon: AlertTriangle,
      label: "Parsed with adjustments",
      banner: "border-amber-500/20 bg-amber-500/5",
      iconColor: "text-amber-400",
      textColor: "text-amber-300",
    };
  }
  return {
    Icon: XCircle,
    label: "Fallback parser used — review carefully",
    banner: "border-red-500/20 bg-red-500/5",
    iconColor: "text-red-400",
    textColor: "text-red-300",
  };
}

export function IntakeReview({ filename, intakeResult, parseReport }: Props) {
  const [showDecisions, setShowDecisions] = useState(false);

  const ir = intakeResult;
  const pr = parseReport;

  // Canonical-first field resolution
  const file_kind      = ir?.file_kind        ?? pr?.file_kind        ?? "flat_table";
  const status         = ir?.parse_status     ?? pr?.status           ?? "ok";
  const confidence     = ir?.confidence       ?? pr?.confidence       ?? 1;
  const header_row     = ir?.detected_header_row ?? pr?.header_row    ?? null;
  const preamble_count = ir
    ? (ir.preamble_rows?.length ?? 0)
    : (pr?.preamble_rows_skipped ?? 0);
  const footer_count   = ir
    ? (ir.footer_rows?.length ?? 0)
    : (pr?.footer_start_row != null ? 1 : 0);
  const warnings       = ir?.warnings         ?? pr?.warnings         ?? [];
  const decisions      = ir?.parsing_decisions ?? pr?.parsing_decisions ?? [];
  const metadata       = ir?.file_metadata    ?? (pr?.metadata as Record<string, unknown> | undefined) ?? {};
  const delimiter      = ir?.delimiter;
  const encoding       = ir?.encoding;
  const n_columns      = ir?.n_columns;
  const preview_sample = ir?.preview_sample   ?? [];

  const confidencePct    = Math.round(confidence * 100);
  const { Icon, label, banner, iconColor, textColor } = statusConfig(status);
  const previewColumns   = preview_sample.length > 0 ? Object.keys(preview_sample[0]) : [];
  const hasPreview       = previewColumns.length > 0;
  const hasParseDetails  = delimiter != null || !!encoding || n_columns != null;
  const hasMetadata      = Object.keys(metadata).length > 0;

  return (
    <div className="space-y-4">

      {/* ── Status banner — trust signal first ──────────────────────────── */}
      <div className={`flex items-center justify-between rounded-xl border px-4 py-3 ${banner}`}>
        <div className="flex items-center gap-2.5">
          <Icon className={`h-4 w-4 flex-shrink-0 ${iconColor}`} />
          <p className={`text-sm font-semibold ${textColor}`}>{label}</p>
        </div>
        <span
          className={`rounded-full px-2.5 py-0.5 text-[10px] font-medium ${
            confidencePct >= 90
              ? "bg-emerald-500/15 text-emerald-400"
              : confidencePct >= 70
              ? "bg-amber-500/15 text-amber-400"
              : "bg-red-500/15 text-red-400"
          }`}
        >
          {confidencePct}% confidence
        </span>
      </div>

      {/* ── Warnings — prominent, not buried ────────────────────────────── */}
      {warnings.length > 0 && (
        <div className="rounded-xl border border-amber-500/25 bg-amber-500/10 px-4 py-3 space-y-2">
          <p className="text-[10px] font-semibold uppercase tracking-wider text-amber-400/70">
            {warnings.length === 1 ? "1 issue to review" : `${warnings.length} issues to review`}
          </p>
          {warnings.map((w, i) => (
            <div key={i} className="flex items-start gap-2">
              <AlertTriangle className="mt-0.5 h-3.5 w-3.5 flex-shrink-0 text-amber-400" />
              <p className="text-xs leading-relaxed text-amber-200/80">{w}</p>
            </div>
          ))}
        </div>
      )}

      {/* ── Detected structure ───────────────────────────────────────────── */}
      <div>
        <p className="mb-2 text-[10px] font-medium uppercase tracking-wider text-white/25">
          Detected structure
        </p>
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
          {[
            {
              label: "File type",
              value: FILE_KIND_LABELS[file_kind] ?? file_kind.replace(/_/g, " "),
              highlight: false,
            },
            {
              label: "Column headers at",
              value: header_row != null && header_row > 0
                ? `Row ${header_row + 1}`
                : "First row",
              highlight: header_row != null && header_row > 0,
            },
            {
              label: "Rows skipped before table",
              value: preamble_count > 0
                ? `${preamble_count} row${preamble_count !== 1 ? "s" : ""}`
                : "None",
              highlight: preamble_count > 0,
            },
            {
              label: "Footer rows removed",
              value: footer_count > 0
                ? `${footer_count} row${footer_count !== 1 ? "s" : ""}`
                : "None",
              highlight: footer_count > 0,
            },
          ].map((item) => (
            <div
              key={item.label}
              className={`rounded-lg border px-3 py-2.5 ${
                item.highlight
                  ? "border-amber-500/20 bg-amber-500/5"
                  : "border-white/[0.06] bg-white/[0.02]"
              }`}
            >
              <p className="text-[10px] text-white/30 leading-tight">{item.label}</p>
              <p
                className={`mt-1 text-xs font-medium ${
                  item.highlight ? "text-amber-300" : "text-white/70"
                }`}
              >
                {item.value}
              </p>
            </div>
          ))}
        </div>
      </div>

      {/* ── Parsing details ──────────────────────────────────────────────── */}
      {hasParseDetails && (
        <div>
          <p className="mb-2 text-[10px] font-medium uppercase tracking-wider text-white/25">
            Parsing details
          </p>
          <div className="flex flex-wrap gap-2">
            {n_columns != null && (
              <span className="rounded-md border border-white/[0.08] bg-white/[0.03] px-3 py-1.5 text-xs">
                <span className="text-white/35">Columns detected:&nbsp;</span>
                <span className="font-medium text-white/75">{n_columns}</span>
              </span>
            )}
            {delimiter != null && (
              <span className="rounded-md border border-white/[0.08] bg-white/[0.03] px-3 py-1.5 text-xs">
                <span className="text-white/35">Delimiter:&nbsp;</span>
                <span className="font-medium text-white/75">{delimiterLabel(delimiter)}</span>
              </span>
            )}
            {encoding && (
              <span className="rounded-md border border-white/[0.08] bg-white/[0.03] px-3 py-1.5 text-xs">
                <span className="text-white/35">Encoding:&nbsp;</span>
                <span className="font-medium text-white/75">{encoding}</span>
              </span>
            )}
          </div>
        </div>
      )}

      {/* ── Preamble metadata ────────────────────────────────────────────── */}
      {hasMetadata && (
        <div className="rounded-xl border border-indigo-500/15 bg-indigo-500/5 px-4 py-3">
          <p className="mb-2 text-[10px] font-semibold uppercase tracking-wider text-indigo-400/60">
            Extracted from title rows
          </p>
          <div className="flex flex-wrap gap-x-5 gap-y-1.5">
            {Object.entries(metadata).map(([k, v]) => (
              <span key={k} className="text-xs">
                <span className="text-white/30">{k}:&nbsp;</span>
                <span className="text-white/65">{String(v)}</span>
              </span>
            ))}
          </div>
        </div>
      )}

      {/* ── Data preview — sanity check ──────────────────────────────────── */}
      {hasPreview && (
        <div>
          <p className="mb-2 text-[10px] font-medium uppercase tracking-wider text-white/25">
            Data preview — first {preview_sample.length} rows
          </p>
          <div className="overflow-x-auto rounded-xl border border-white/[0.07]">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-white/[0.07] bg-white/[0.03]">
                  {previewColumns.map((col) => (
                    <th
                      key={col}
                      className="px-3 py-2 text-left font-medium text-white/45 whitespace-nowrap"
                    >
                      {col}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {preview_sample.map((row, ri) => (
                  <tr
                    key={ri}
                    className="border-b border-white/[0.04] hover:bg-white/[0.02] transition-colors"
                  >
                    {previewColumns.map((col) => {
                      const cell = row[col];
                      return (
                        <td
                          key={col}
                          className="px-3 py-2 text-white/65 whitespace-nowrap max-w-[160px] truncate"
                          title={cell == null ? "" : String(cell)}
                        >
                          {cell == null ? (
                            <span className="text-white/20 italic">empty</span>
                          ) : (
                            String(cell)
                          )}
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="mt-1.5 text-[10px] text-white/20">
            These rows are as the parser understood them — column names should match your file.
          </p>
        </div>
      )}

      {/* ── Parser decisions — collapsible ───────────────────────────────── */}
      {decisions.length > 0 && (
        <div>
          <button
            onClick={() => setShowDecisions((v) => !v)}
            className="flex items-center gap-1.5 text-[11px] text-white/30 hover:text-white/50 transition-colors"
          >
            {showDecisions ? (
              <ChevronUp className="h-3 w-3" />
            ) : (
              <ChevronDown className="h-3 w-3" />
            )}
            {showDecisions ? "Hide" : "Show"} assumptions made by the parser ({decisions.length})
          </button>
          {showDecisions && (
            <div className="mt-2 space-y-1 pl-1">
              {decisions.map((d, i) => (
                <p key={i} className="text-[11px] text-white/35 leading-relaxed">
                  · {d}
                </p>
              ))}
            </div>
          )}
        </div>
      )}

      {/* ── Footer nudge ─────────────────────────────────────────────────── */}
      <p className="text-[11px] text-white/25">
        From <span className="text-white/40">{filename}</span> — columns look right? Continue to{" "}
        <span className="text-white/40">Health</span> to review data quality.
      </p>
    </div>
  );
}
