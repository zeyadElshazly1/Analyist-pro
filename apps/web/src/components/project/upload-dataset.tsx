"use client";

import { useCallback, useRef, useState } from "react";
import { uploadFile } from "@/lib/api";
import { Upload, FileText, CheckCircle2, AlertCircle } from "lucide-react";

type Props = {
  projectId: number;
  onUploaded?: () => void;
};

type Status = "idle" | "uploading" | "success" | "error";

export function UploadDataset({ projectId, onUploaded }: Props) {
  const [file, setFile] = useState<File | null>(null);
  const [status, setStatus] = useState<Status>("idle");
  const [message, setMessage] = useState("");
  const [dragging, setDragging] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  function selectFile(f: File) {
    setFile(f);
    setStatus("idle");
    setMessage("");
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
      await uploadFile(projectId, file);
      setStatus("success");
      setMessage(`${file.name} uploaded successfully.`);
      onUploaded?.();
    } catch (e) {
      setStatus("error");
      setMessage(e instanceof Error ? e.message : "Upload failed.");
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
              <p className="mt-1 text-xs text-white/30">CSV, XLSX, XLS · Max 50 MB</p>
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

      {status === "error" && (
        <p className="flex items-center gap-2 text-sm text-red-400">
          <AlertCircle className="h-4 w-4" />
          {message}
        </p>
      )}
    </div>
  );
}
