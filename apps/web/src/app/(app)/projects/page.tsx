"use client";

import { useRef } from "react";
import { AppShell } from "@/components/layout/app-shell";
import { ProjectsList, ProjectsListHandle } from "@/components/dashboard/projects-list";
import { CreateProjectForm } from "@/components/dashboard/create-project-form";
import { FolderPlus } from "lucide-react";

export default function ProjectsPage() {
  const listRef = useRef<ProjectsListHandle>(null);

  return (
    <AppShell>
      <div className="min-h-full bg-[#080810]">
        <div className="mx-auto max-w-3xl space-y-6 p-6 lg:p-10">

          {/* Header */}
          <div>
            <h1 className="text-2xl font-bold tracking-tight text-white">Projects</h1>
            <p className="mt-1 text-sm text-white/40">
              Create and manage your data analysis projects.
            </p>
          </div>

          {/* Create */}
          <div className="rounded-2xl border border-white/[0.06] bg-white/[0.02] p-6">
            <div className="mb-4 flex items-center gap-2.5">
              <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-indigo-600/15">
                <FolderPlus className="h-4 w-4 text-indigo-400" strokeWidth={1.75} />
              </div>
              <h2 className="text-sm font-semibold text-white">New project</h2>
            </div>
            <CreateProjectForm onCreated={() => listRef.current?.reload()} />
          </div>

          {/* List */}
          <div className="rounded-2xl border border-white/[0.06] bg-white/[0.02] p-6">
            <h2 className="mb-5 text-sm font-semibold text-white">All projects</h2>
            <ProjectsList ref={listRef} showSearch />
          </div>
        </div>
      </div>
    </AppShell>
  );
}
