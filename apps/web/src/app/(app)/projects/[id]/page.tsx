"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { AppShell } from "@/components/layout/app-shell";
import { UploadDataset } from "@/components/project/upload-dataset";
import { RunAnalysis } from "@/components/project/run-analysis";
import { getProject, ProjectDetail } from "@/lib/api";
import { ArrowLeft, Database, Target, Zap } from "lucide-react";

const INTENT_LABELS: Record<string, string> = {
  general: "General business analysis",
  marketing: "Marketing performance",
  saas: "SaaS growth & retention",
  sales: "Sales pipeline",
  finance: "Finance & reporting",
  operations: "Operations & inventory",
};

export default function ProjectPage() {
  const params = useParams();
  const rawId = params?.id;
  const projectId = Array.isArray(rawId) ? Number(rawId[0]) : Number(rawId);

  const [project, setProject] = useState<ProjectDetail | null>(null);

  const loadProject = useCallback(() => {
    if (!projectId || isNaN(projectId)) return;
    getProject(projectId).then(setProject).catch(() => {});
  }, [projectId]);

  useEffect(() => {
    loadProject();
  }, [loadProject]);

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
        <div className="mx-auto max-w-5xl space-y-6 p-6 lg:p-10">
          <div>
            <Link
              href="/projects"
              className="mb-3 inline-flex items-center gap-1.5 text-xs text-white/35 transition-colors hover:text-white/60"
            >
              <ArrowLeft className="h-3 w-3" />
              Projects
            </Link>
            <div className="flex flex-col gap-4 rounded-3xl border border-white/[0.06] bg-white/[0.02] p-6 sm:flex-row sm:items-end sm:justify-between">
              <div className="flex items-start gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-indigo-600/15">
                  <Database className="h-5 w-5 text-indigo-400" strokeWidth={1.75} />
                </div>
                <div>
                  <p className="text-[11px] text-white/30">Project #{projectId}</p>
                  <h1 className="text-2xl font-bold tracking-tight text-white">
                    {project?.name ?? "Loading..."}
                  </h1>
                  <div className="mt-2 flex flex-wrap items-center gap-2">
                    <span className="rounded-full border border-white/10 bg-white/5 px-2.5 py-1 text-[11px] text-white/60">
                      Status: {project?.status ?? "loading"}
                    </span>
                    <span className="inline-flex items-center gap-1 rounded-full border border-indigo-500/20 bg-indigo-500/10 px-2.5 py-1 text-[11px] text-indigo-300">
                      <Target className="h-3 w-3" />
                      {INTENT_LABELS[project?.intent ?? "general"]}
                    </span>
                  </div>
                </div>
              </div>

              <div className="rounded-2xl border border-white/[0.06] bg-black/20 px-4 py-3 text-sm text-white/60">
                {project?.latest_dataset ? (
                  <>
                    Latest dataset: <span className="text-white">{project.latest_dataset.filename}</span>
                  </>
                ) : (
                  "Upload a dataset to unlock the executive summary workflow."
                )}
              </div>
            </div>
          </div>

          <section className="rounded-2xl border border-white/[0.06] bg-white/[0.02] p-6">
            <div className="mb-5 flex items-center gap-2.5">
              <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-white/[0.05]">
                <Database className="h-3.5 w-3.5 text-white/60" strokeWidth={1.75} />
              </div>
              <div>
                <h2 className="text-sm font-semibold text-white">Upload</h2>
                <p className="text-xs text-white/40">
                  Add a CSV or Excel file. We keep the latest dataset attached to this project.
                </p>
              </div>
            </div>
            <UploadDataset projectId={projectId} onUploaded={loadProject} />
          </section>

          <section className="rounded-2xl border border-white/[0.06] bg-white/[0.02] p-6">
            <div className="mb-5 flex items-center gap-2.5">
              <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-indigo-600/15">
                <Zap className="h-3.5 w-3.5 text-indigo-400" strokeWidth={1.75} />
              </div>
              <div>
                <h2 className="text-sm font-semibold text-white">Understand and act</h2>
                <p className="text-xs text-white/40">
                  Run the saved analysis pipeline, review the executive summary, then explore deeper tools.
                </p>
              </div>
            </div>
            <RunAnalysis projectId={projectId} project={project} onRefresh={loadProject} />
          </section>
        </div>
      </div>
    </AppShell>
  );
}
