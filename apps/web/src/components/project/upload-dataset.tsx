"use client";

import { useCallback, useRef, useState } from "react";
import { uploadFile, getDataPreview, ApiError } from "@/lib/api";
import { Upload, FileText, CheckCircle2, AlertCircle, TableIcon } from "lucide-react";
import { IntakeReview } from "./intake-review";

type Props = {
  projectId: number;
  onUploaded?: () => void;
};

type Status = "idle" | "uploading" | "success" | "error";

type Preview = {
  columns: string[];
  rows: unknown[][];
  total_rows: number;
  total_columns: number;
};

// eslint-disable-next-line @typescript-eslint/no-explicit-any
type ParseReport = Record<string, any>;

export function UploadDataset({ projectId, onUploaded }: Props) {
  const [file, setFile] = useState<File | null>(null);
  const [status, setStatus] = useState<Status>("idle");
  const [message, setMessage] = useState("");
  const [dragging, setDragging] = useState(false);
  const [preview, setPreview] = useState<Preview | null>(null);
  const [parseReport, setParseReport] = useState<ParseReport | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  function selectFile(f: File) {
    setFile(f);
    setStatus("idle");
    setMessage("");
    setPreview(null);
    setParseReport(null);
  }

  const onDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragging(false);
    const f = e.dataTransfer.files?.[0];
    if (f) selectFile(f);
  }, []);

  async function handleUpload() {
    if (!file) return;
    try {
      setStatus("uploading");
      const result = await uploadFile(projectId, file);
      setStatus("success");
      setMessage(`${file.name} uploaded successfully.`);
      if (result?.parse_report && Object.keys(result.parse_report).length > 0) {
        setParseReport(result.parse_report);
      }
      onUploaded?.();
      // fetch preview in background — non-blocking, failure is not critical
      getDataPreview(projectId, 5)
        .then(setPreview)
        .catch((err) => {
          console.warn("[UploadDataset] Preview failed (non-critical):", err instanceof ApiError ? err.userMessage : err);
        });
    } catch (e) {
      setStatus("error");
      setMessage(e instanceof ApiError ? e.userMessage : "Upload failed. Please try again.");
    }
  }

  return (
    <div className="space-y-4">
      <div
        role="button"
        tabIndex={0}
        className={`cursor-pointer rounded-2xl border-2 border-dashed p-10 text-center transition-colors ${
          dragging
            ? "border-indigo-500 bg-indigo-500/10"
            : file
              ? "border-white/20 bg-white/[0.03]"
              : "border-white/10 bg-white/[0.02] hover:border-white/20 hover:bg-white/[0.04]"
        }`}
        onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
        onClick={() => inputRef.current?.click()}
        onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") inputRef.current?.click(); }}
      >
        <input
          ref={inputRef}
          type="file"
          accept=".csv,.xlsx,.xls"
          className="hidden"
          onChange={(e) => { const f = e.target.files?.[0]; if (f) selectFile(f); }}
        />

        {file ? (
          <div className="flex flex-col items-center gap-2">
            <FileText className="h-9 w-9 text-indigo-400" />
            <p className="text-sm font-medium text-white">{file.name}</p>
            <p className="text-xs text-white/40">
              {(file.size / 1024).toFixed(1)} KB · Click to change file
            </p>
          </div>
        ) : (
          <div className="flex flex-col items-center gap-3">
            <div className="flex h-12 w-12 items-center justify-center rounded-full bg-white/5">
              <Upload className="h-5 w-5 text-white/40" />
            </div>
            <div>
              <p className="text-sm text-white/70">
                Drag & drop your file, or{" "}
                <span className="text-indigo-400 underline underline-offset-2">browse</span>
              </p>
              <p className="mt-1 text-xs text-white/30">CSV, XLSX, XLS · Max 100 MB</p>
            </div>
          </div>
        )}
      </div>

      {file && status !== "success" && (
        <button
          onClick={handleUpload}
          disabled={status === "uploading"}
          className="flex items-center gap-2 rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-indigo-500 disabled:opacity-60"
        >
          {status === "uploading" ? (
            <>
              <div className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-white/30 border-t-white" />
              Uploading…
            </>
          ) : (
            <>
              <Upload className="h-3.5 w-3.5" />
              Upload dataset
            </>
          )}
        </button>
      )}

      {status === "success" && (
        <p className="flex items-center gap-2 text-sm text-emerald-400">
          <CheckCircle2 className="h-4 w-4" />
          {message}
        </p>
      )}

      {status === "success" && parseReport && file && (
        <IntakeReview filename={file.name} parseReport={parseReport} />
      )}

      {status === "error" && (
        <p className="flex items-center gap-2 text-sm text-red-400">
          <AlertCircle className="h-4 w-4" />
          {message}
        </p>
      )}

      {/* ── Data preview ────────────────────────────────────────────────────── */}
      {preview && (
        <div className="rounded-xl border border-white/[0.07] bg-white/[0.02] overflow-hidden">
          <div className="flex items-center gap-2 border-b border-white/[0.07] px-4 py-3">
            <TableIcon className="h-3.5 w-3.5 text-white/40" />
            <span className="text-xs font-medium text-white/60">
              Preview — first {preview.rows.length} of{" "}
              <span className="text-white/80">{preview.total_rows.toLocaleString()}</span> rows
              &nbsp;·&nbsp;
              <span className="text-white/80">{preview.total_columns}</span> columns
            </span>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-white/[0.06]">
                  {preview.columns.map((col) => (
                    <th
                      key={col}
                      className="px-4 py-2 text-left font-medium text-white/50 whitespace-nowrap"
                    >
                      {col}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {preview.rows.map((row, ri) => (
                  <tr
                    key={ri}
                    className="border-b border-white/[0.04] hover:bg-white/[0.02] transition-colors"
                  >
                    {(row as unknown[]).map((cell, ci) => (
                      <td
                        key={ci}
                        className="px-4 py-2 text-white/70 whitespace-nowrap max-w-[180px] truncate"
                        title={cell == null ? "" : String(cell)}
                      >
                        {cell == null ? (
                          <span className="text-white/20 italic">null</span>
                        ) : (
                          String(cell)
                        )}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
