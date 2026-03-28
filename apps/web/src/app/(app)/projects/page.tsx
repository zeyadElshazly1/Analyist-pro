"use client";

import { useRef } from "react";
import { AppShell } from "@/components/layout/app-shell";
import { ProjectsList, ProjectsListHandle } from "@/components/dashboard/projects-list";
import { CreateProjectForm } from "@/components/dashboard/create-project-form";

export default function ProjectsPage() {
  const listRef = useRef<ProjectsListHandle>(null);

  return (
    <AppShell>
      <div className="mx-auto max-w-3xl space-y-6 p-6 lg:p-10">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-white">Projects</h1>
          <p className="mt-1 text-sm text-white/40">
            Create and manage your analysis projects.
          </p>
        </div>

        <div className="rounded-2xl border border-white/[0.07] bg-white/[0.02] p-6">
          <h2 className="text-sm font-semibold text-white mb-4">New project</h2>
          <CreateProjectForm onCreated={() => listRef.current?.reload()} />
        </div>

        <div className="rounded-2xl border border-white/[0.07] bg-white/[0.02] p-6">
          <h2 className="text-sm font-semibold text-white mb-5">All projects</h2>
          <ProjectsList ref={listRef} />
        </div>
      </div>
    </AppShell>
  );
}
