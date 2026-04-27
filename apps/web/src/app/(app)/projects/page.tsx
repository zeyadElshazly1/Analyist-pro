"use client";

import { useRef } from "react";
import Link from "next/link";
import { AppShell } from "@/components/layout/app-shell";
import { ProjectsList, ProjectsListHandle } from "@/components/dashboard/projects-list";
import { CreateProjectForm } from "@/components/dashboard/create-project-form";
import { Beaker, FolderPlus } from "lucide-react";

export default function ProjectsPage() {
  const listRef = useRef<ProjectsListHandle>(null);

  return (
    <AppShell>
      <div className="min-h-full bg-[#080810]">
        <div className="mx-auto max-w-3xl space-y-6 p-6 lg:p-10">

          {/* Header */}
          <div>
            <h1 className="text-2xl font-bold tracking-tight text-white">Client Workspaces</h1>
            <p className="mt-1 text-sm text-white/40">
              Create and manage workspaces for each client or reporting cycle.
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

          {/* Demo entry point */}
          <Link
            href="/demo"
            className="flex items-center justify-between rounded-2xl border border-amber-500/15 bg-amber-500/[0.04] p-5 transition-colors hover:bg-amber-500/[0.08] group"
          >
            <div className="flex items-center gap-3">
              <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-amber-600/15">
                <Beaker className="h-4 w-4 text-amber-400" strokeWidth={1.75} />
              </div>
              <div>
                <p className="text-sm font-medium text-white">Try the demo workspace</p>
                <p className="text-xs text-white/40">
                  Explore a pre-loaded analysis — no file upload needed
                </p>
              </div>
            </div>
            <span className="text-xs text-amber-400/70 group-hover:text-amber-300 transition-colors">
              Open demo →
            </span>
          </Link>
        </div>
      </div>
    </AppShell>
  );
}
