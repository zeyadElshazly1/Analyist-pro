"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { AppShell } from "@/components/layout/app-shell";
import { UploadDataset } from "@/components/project/upload-dataset";
import { RunAnalysis } from "@/components/project/run-analysis";
import { getProjects } from "@/lib/api";

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
        <div className="p-10">
          <h1 className="text-2xl font-semibold text-white">Invalid project</h1>
          <p className="mt-2 text-sm text-white/50">The project ID is missing or invalid.</p>
        </div>
      </AppShell>
    );
  }

  return (
    <AppShell>
      <div className="mx-auto max-w-4xl space-y-6 p-6 lg:p-10">
        <div>
          <p className="text-xs text-white/35 mb-1">Project #{projectId}</p>
          <h1 className="text-2xl font-semibold tracking-tight text-white">
            {projectName ?? "Loading…"}
          </h1>
        </div>

        <section className="rounded-2xl border border-white/[0.07] bg-white/[0.02] p-6">
          <h2 className="text-sm font-semibold text-white mb-1">Dataset</h2>
          <p className="text-xs text-white/40 mb-5">Upload a CSV or Excel file to begin.</p>
          <UploadDataset projectId={projectId} />
        </section>

        <section className="rounded-2xl border border-white/[0.07] bg-white/[0.02] p-6">
          <h2 className="text-sm font-semibold text-white mb-1">Analysis</h2>
          <p className="text-xs text-white/40 mb-5">
            Run the full pipeline — insights, charts, and data quality report.
          </p>
          <RunAnalysis projectId={projectId} />
        </section>
      </div>
    </AppShell>
  );
}
