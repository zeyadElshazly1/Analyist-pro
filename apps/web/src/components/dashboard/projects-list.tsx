"use client";

import Link from "next/link";
import { useEffect, useImperativeHandle, useState, forwardRef } from "react";
import { getProjects, deleteProject } from "@/lib/api";
import { ArrowRight, FolderOpen, Trash2 } from "lucide-react";

type Project = { id: number; name: string; status: string; created_at?: string };

export type ProjectsListHandle = { reload: () => Promise<void> };

const STATUS_STYLE: Record<string, string> = {
  ready:      "bg-emerald-500/15 text-emerald-400",
  created:    "bg-white/10 text-white/50",
  processing: "bg-amber-500/15 text-amber-400",
  error:      "bg-red-500/15 text-red-400",
};

export const ProjectsList = forwardRef<ProjectsListHandle>(function ProjectsList(_, ref) {
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [deletingId, setDeletingId] = useState<number | null>(null);

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

  async function handleDelete(e: React.MouseEvent, id: number) {
    e.preventDefault();
    e.stopPropagation();
    if (!confirm("Delete this project and all its data?")) return;
    setDeletingId(id);
    try {
      await deleteProject(id);
      setProjects((prev) => prev.filter((p) => p.id !== id));
    } catch {
      alert("Failed to delete project.");
    } finally {
      setDeletingId(null);
    }
  }

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
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm font-medium text-white group-hover:text-indigo-300 transition-colors">
              {project.name}
            </p>
            <div className="mt-0.5 flex items-center gap-2">
              <span
                className={`inline-block rounded-full px-2 py-0.5 text-[11px] font-medium ${STATUS_STYLE[project.status] ?? "bg-white/10 text-white/50"}`}
              >
                {project.status}
              </span>
              {project.created_at && (
                <span className="text-[11px] text-white/25">
                  {new Date(project.created_at).toLocaleDateString()}
                </span>
              )}
            </div>
          </div>
          <div className="flex items-center gap-2 pl-4">
            <button
              onClick={(e) => handleDelete(e, project.id)}
              disabled={deletingId === project.id}
              className="rounded-md p-1.5 text-white/20 opacity-0 group-hover:opacity-100 hover:bg-red-500/10 hover:text-red-400 transition-all"
              title="Delete project"
            >
              <Trash2 className="h-3.5 w-3.5" />
            </button>
            <ArrowRight className="h-4 w-4 flex-shrink-0 text-white/20 transition-colors group-hover:text-indigo-400" />
          </div>
        </Link>
      ))}
    </div>
  );
});
