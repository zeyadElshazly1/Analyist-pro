/* eslint-disable @typescript-eslint/no-explicit-any */
"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { AppShell } from "@/components/layout/app-shell";
import { UploadDataset } from "@/components/project/upload-dataset";
import { RunAnalysis } from "@/components/project/run-analysis";
import { getProject, getAnalysisHistory } from "@/lib/api";
import { ArrowLeft, Database, Zap, Clock, FileText } from "lucide-react";

type HistoryEntry = { id: number; project_id: number; created_at: string; file_hash: string | null };

function HistoryPanel({ projectId }: { projectId: number }) {
  const [history, setHistory] = useState<HistoryEntry[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getAnalysisHistory(projectId, 8)
      .then(setHistory)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [projectId]);

  if (loading) return null;
  if (history.length === 0) return null;

  return (
    <section className="rounded-2xl border border-white/[0.06] bg-white/[0.02] p-6">
      <div className="mb-4 flex items-center justify-between">
        <div className="flex items-center gap-2.5">
          <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-white/[0.05]">
            <Clock className="h-3.5 w-3.5 text-white/50" strokeWidth={1.75} />
          </div>
          <h2 className="text-sm font-semibold text-white">Analysis history</h2>
        </div>
        <Link
          href={`/reports/${projectId}`}
          className="flex items-center gap-1 text-xs text-indigo-400 hover:text-indigo-300 transition-colors"
        >
          <FileText className="h-3.5 w-3.5" />
          View full report
        </Link>
      </div>

      <div className="space-y-1">
        {history.map((entry, i) => (
          <div
            key={entry.id}
            className={`flex items-center justify-between rounded-lg px-3 py-2.5 ${
              i === 0 ? "bg-indigo-600/10 border border-indigo-500/20" : "hover:bg-white/[0.02]"
            } transition-colors`}
          >
            <div className="flex items-center gap-2.5">
              <div className={`h-2 w-2 rounded-full flex-shrink-0 ${i === 0 ? "bg-indigo-400" : "bg-white/20"}`} />
              <span className="text-xs text-white/60">
                {new Date(entry.created_at).toLocaleString()}
              </span>
              {i === 0 && (
                <span className="rounded-full bg-indigo-600/20 px-2 py-0.5 text-[10px] font-medium text-indigo-400">
                  Latest
                </span>
              )}
            </div>
            {entry.file_hash && (
              <span className="font-mono text-[10px] text-white/20" title="File hash">
                #{entry.file_hash.slice(0, 8)}
              </span>
            )}
          </div>
        ))}
      </div>
    </section>
  );
}

export default function ProjectPage() {
  const params = useParams();
  const rawId = params?.id;
  const projectId = Array.isArray(rawId) ? Number(rawId[0]) : Number(rawId);

  const [projectName, setProjectName] = useState<string | null>(null);

  useEffect(() => {
    if (!projectId || isNaN(projectId)) return;
    getProject(projectId)
      .then((p) => setProjectName(p.name))
      .catch(() => {});
  }, [projectId]);

  if (!projectId || isNaN(projectId)) {
    return (
      <AppShell>
        <div className="min-h-full bg-[#080810] p-10">
          <h1 className="text-2xl font-bold text-white">Invalid project</h1>
          <p className="mt-2 text-sm text-white/50">The project ID is missing or invalid.</p>
        </div>
      </AppShell>
    );
  }

  return (
    <AppShell>
      <div className="min-h-full bg-[#080810]">
        <div className="mx-auto max-w-4xl space-y-6 p-6 lg:p-10">

          {/* Breadcrumb + header */}
          <div>
            <Link
              href="/projects"
              className="mb-3 inline-flex items-center gap-1.5 text-xs text-white/35 hover:text-white/60 transition-colors"
            >
              <ArrowLeft className="h-3 w-3" />
              Projects
            </Link>
            <div className="flex items-center justify-between gap-3">
              <div className="flex items-center gap-3">
                <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-indigo-600/15">
                  <Database className="h-4.5 w-4.5 text-indigo-400" strokeWidth={1.75} />
                </div>
                <div>
                  <p className="text-[11px] text-white/30">Project #{projectId}</p>
                  <h1 className="text-xl font-bold tracking-tight text-white">
                    {projectName ?? "Loading…"}
                  </h1>
                </div>
              </div>
              <Link
                href={`/reports/${projectId}`}
                className="hidden items-center gap-1.5 rounded-lg border border-white/10 px-3 py-1.5 text-xs text-white/50 hover:border-white/20 hover:text-white/70 transition-colors sm:flex"
              >
                <FileText className="h-3.5 w-3.5" />
                View report
              </Link>
            </div>
          </div>

          {/* Dataset upload */}
          <section className="rounded-2xl border border-white/[0.06] bg-white/[0.02] p-6">
            <div className="mb-5 flex items-center gap-2.5">
              <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-white/[0.05]">
                <Database className="h-3.5 w-3.5 text-white/60" strokeWidth={1.75} />
              </div>
              <div>
                <h2 className="text-sm font-semibold text-white">Dataset</h2>
                <p className="text-xs text-white/40">Upload a CSV or Excel file to begin.</p>
              </div>
            </div>
            <UploadDataset projectId={projectId} />
          </section>

          {/* Analysis */}
          <section className="rounded-2xl border border-white/[0.06] bg-white/[0.02] p-6">
            <div className="mb-5 flex items-center gap-2.5">
              <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-indigo-600/15">
                <Zap className="h-3.5 w-3.5 text-indigo-400" strokeWidth={1.75} />
              </div>
              <div>
                <h2 className="text-sm font-semibold text-white">Analysis</h2>
                <p className="text-xs text-white/40">
                  Run the full pipeline — insights, charts, and data quality report.
                </p>
              </div>
            </div>
            <RunAnalysis projectId={projectId} />
          </section>

          {/* Analysis history */}
          <HistoryPanel projectId={projectId} />
        </div>
      </div>
    </AppShell>
  );
}
