"use client";

import { useRef } from "react";
import Link from "next/link";
import { AppShell } from "@/components/layout/app-shell";
import { CreateProjectForm } from "@/components/dashboard/create-project-form";
import { ProjectsList, ProjectsListHandle } from "@/components/dashboard/projects-list";
import { Plus, ArrowRight, TrendingUp, FolderOpen, FileStack, Activity } from "lucide-react";

const stats = [
  { label: "Projects", value: "12", icon: FolderOpen, color: "text-indigo-400", bg: "bg-indigo-500/10" },
  { label: "Files analyzed", value: "38", icon: FileStack, color: "text-violet-400", bg: "bg-violet-500/10" },
  { label: "Reports", value: "19", icon: TrendingUp, color: "text-emerald-400", bg: "bg-emerald-500/10" },
  { label: "Usage this month", value: "72%", icon: Activity, color: "text-amber-400", bg: "bg-amber-500/10" },
];

export default function DashboardPage() {
  const projectsListRef = useRef<ProjectsListHandle>(null);

  return (
    <AppShell>
      <div className="min-h-full bg-[#080810]">
        <div className="mx-auto max-w-6xl space-y-8 p-6 lg:p-10">

          {/* Header */}
          <div className="flex items-start justify-between">
            <div>
              <h1 className="text-2xl font-bold tracking-tight text-white">
                Welcome back 👋
              </h1>
              <p className="mt-1 text-sm text-white/50">
                Manage your projects and review your latest analyses.
              </p>
            </div>
            <Link
              href="/projects"
              className="hidden items-center gap-2 rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white shadow-lg shadow-indigo-500/20 transition-all hover:bg-indigo-500 sm:flex"
            >
              <Plus className="h-4 w-4" />
              New project
            </Link>
          </div>

          {/* Stats */}
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            {stats.map((stat) => (
              <div
                key={stat.label}
                className="rounded-2xl border border-white/[0.06] bg-white/[0.02] p-5 transition-all hover:border-white/10 hover:bg-white/[0.04]"
              >
                <div className="flex items-center justify-between">
                  <p className="text-sm text-white/50">{stat.label}</p>
                  <div className={`flex h-8 w-8 items-center justify-center rounded-lg ${stat.bg}`}>
                    <stat.icon className={`h-4 w-4 ${stat.color}`} strokeWidth={1.75} />
                  </div>
                </div>
                <p className="mt-3 text-3xl font-bold text-white">{stat.value}</p>
              </div>
            ))}
          </div>

          {/* Main content */}
          <div className="grid gap-6 xl:grid-cols-3">

            {/* Recent projects */}
            <div className="xl:col-span-2 rounded-2xl border border-white/[0.06] bg-white/[0.02] p-6">
              <div className="mb-5 flex items-center justify-between">
                <h2 className="text-base font-semibold text-white">Recent projects</h2>
                <Link
                  href="/projects"
                  className="flex items-center gap-1.5 text-xs text-indigo-400 hover:text-indigo-300 transition-colors"
                >
                  View all <ArrowRight className="h-3 w-3" />
                </Link>
              </div>
              <ProjectsList ref={projectsListRef} />
            </div>

            {/* Right column */}
            <div className="space-y-6">

              {/* Quick create */}
              <div className="rounded-2xl border border-white/[0.06] bg-white/[0.02] p-6">
                <h2 className="mb-4 text-base font-semibold text-white">New project</h2>
                <CreateProjectForm
                  onCreated={() => projectsListRef.current?.reload()}
                />
              </div>

              {/* Getting started card */}
              <div className="rounded-2xl border border-indigo-500/20 bg-gradient-to-br from-indigo-600/8 to-violet-600/5 p-6">
                <div className="mb-3 flex h-9 w-9 items-center justify-center rounded-xl bg-indigo-600/20">
                  <TrendingUp className="h-4.5 w-4.5 text-indigo-400" strokeWidth={1.75} />
                </div>
                <h3 className="text-sm font-semibold text-white">Get the most from your data</h3>
                <p className="mt-2 text-xs leading-relaxed text-white/45">
                  Create a project, upload a CSV or Excel file, and run the full AI analysis pipeline — insights, charts, and quality scoring in seconds.
                </p>
                <Link
                  href="/projects"
                  className="mt-4 flex items-center gap-1.5 text-xs font-medium text-indigo-400 hover:text-indigo-300 transition-colors"
                >
                  Create your first project <ArrowRight className="h-3 w-3" />
                </Link>
              </div>
            </div>
          </div>
        </div>
      </div>
    </AppShell>
  );
}
