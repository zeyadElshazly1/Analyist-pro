"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { AppShell } from "@/components/layout/app-shell";
import { UploadDataset } from "@/components/project/upload-dataset";
import { RunAnalysis } from "@/components/project/run-analysis";
import { getProjects } from "@/lib/api";
import { ArrowLeft, Database, Zap } from "lucide-react";

export default function ProjectPage() {
  const params = useParams();
  const rawId = params?.id;
  const projectId = Array.isArray(rawId) ? Number(rawId[0]) : Number(rawId);

  const [projectName, setProjectName] = useState<string | null>(null);

  useEffect(() => {
    if (!projectId || isNaN(projectId)) return;
    getProjects()
      .then((list: any[]) => {
        const p = list.find((p) => p.id === projectId);
        if (p) setProjectName(p.name);
      })
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
        </div>
      </div>
    </AppShell>
  );
}
