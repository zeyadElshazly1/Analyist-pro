"use client";

import Link from "next/link";
import { useEffect, useImperativeHandle, useState, forwardRef } from "react";
import { getProjects } from "@/lib/api";
import { ArrowRight, FolderOpen } from "lucide-react";

type Project = { id: number; name: string; status: string };

export type ProjectsListHandle = { reload: () => Promise<void> };

const STATUS_COLOR: Record<string, string> = {
  ready:      "bg-emerald-500/15 text-emerald-400",
  created:    "bg-white/10 text-white/50",
  processing: "bg-amber-500/15 text-amber-400",
};

export const ProjectsList = forwardRef<ProjectsListHandle>(function ProjectsList(_, ref) {
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  async function loadProjects() {
    try {
      setLoading(true);
      setError("");
      setProjects(await getProjects());
    } catch {
      setError("Failed to load projects.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { loadProjects(); }, []);
  useImperativeHandle(ref, () => ({ reload: loadProjects }));

  if (loading) {
    return (
      <div className="space-y-2">
        {[...Array(3)].map((_, i) => (
          <div key={i} className="h-14 animate-pulse rounded-xl bg-white/5" />
        ))}
      </div>
    );
  }

  if (error) return <p className="text-sm text-red-400">{error}</p>;

  if (projects.length === 0) {
    return (
      <div className="flex flex-col items-center gap-2 py-8 text-center">
        <FolderOpen className="h-8 w-8 text-white/20" />
        <p className="text-sm text-white/40">No projects yet.</p>
      </div>
    );
  }

  return (
    <div className="divide-y divide-white/[0.06]">
      {projects.map((project) => (
        <Link
          key={project.id}
          href={`/projects/${project.id}`}
          className="group flex items-center justify-between py-3"
        >
          <div className="min-w-0">
            <p className="truncate text-sm font-medium text-white group-hover:text-indigo-300 transition-colors">
              {project.name}
            </p>
            <span className={`mt-0.5 inline-block rounded-full px-2 py-0.5 text-[11px] font-medium ${STATUS_COLOR[project.status] ?? "bg-white/10 text-white/50"}`}>
              {project.status}
            </span>
          </div>
          <ArrowRight className="h-4 w-4 flex-shrink-0 text-white/20 transition-colors group-hover:text-indigo-400" />
        </Link>
      ))}
    </div>
  );
});
