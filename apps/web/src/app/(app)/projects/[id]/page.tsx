"use client";

import { useParams } from "next/navigation";
import { AppShell } from "@/components/layout/app-shell";
import { UploadDataset } from "@/components/project/upload-dataset";
import { RunAnalysis } from "@/components/project/run-analysis";

export default function ProjectPage() {
  const params = useParams();
  const rawId = params?.id;
  const projectId = Array.isArray(rawId) ? Number(rawId[0]) : Number(rawId);

  if (!projectId || Number.isNaN(projectId)) {
    return (
      <AppShell>
        <section className="space-y-6 p-6 lg:p-10">
          <h1 className="text-3xl font-semibold tracking-tight text-white">
            Invalid project
          </h1>
          <p className="text-white/60">
            The project ID is missing or invalid.
          </p>
        </section>
      </AppShell>
    );
  }

  return (
    <AppShell>
      <section className="space-y-6 p-6 lg:p-10">
        <div>
          <h1 className="text-3xl font-semibold tracking-tight text-white">
            Project {projectId}
          </h1>
          <p className="mt-2 text-white/60">
            Upload a dataset, then run the first real Analyst Pro analysis pipeline.
          </p>
        </div>

        <div className="rounded-3xl border border-white/10 bg-white/5 p-6">
          <h2 className="text-lg font-medium text-white">Upload dataset</h2>
          <div className="mt-4">
            <UploadDataset projectId={projectId} />
          </div>
        </div>

        <div className="rounded-3xl border border-white/10 bg-white/5 p-6">
          <h2 className="text-lg font-medium text-white">Analysis</h2>
          <div className="mt-4">
            <RunAnalysis projectId={projectId} />
          </div>
        </div>
      </section>
    </AppShell>
  );
}