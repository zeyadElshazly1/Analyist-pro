"use client";

import Link from "next/link";
import { useEffect, useImperativeHandle, useState, forwardRef, useMemo } from "react";
import { getProjects, deleteProject } from "@/lib/api";
import { toast } from "@/components/ui/toast";
import { ArrowRight, FolderOpen, Trash2, Search, BarChart2 } from "lucide-react";

type Project = { id: number; name: string; status: string; created_at?: string };

export type ProjectsListHandle = { reload: () => Promise<void> };

const STATUS_STYLE: Record<string, string> = {
  ready:      "bg-emerald-500/15 text-emerald-400",
  created:    "bg-white/10 text-white/50",
  processing: "bg-amber-500/15 text-amber-400",
  error:      "bg-red-500/15 text-red-400",
};

const STATUS_LABEL: Record<string, string> = {
  ready:      "Ready",
  created:    "No data",
  processing: "Processing",
  error:      "Error",
};

interface Props {
  showSearch?: boolean;
  limit?: number;
}

export const ProjectsList = forwardRef<ProjectsListHandle, Props>(
  function ProjectsList({ showSearch = false, limit }, ref) {
    const [projects, setProjects] = useState<Project[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState("");
    const [deletingId, setDeletingId] = useState<number | null>(null);
    const [search, setSearch] = useState("");

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

    async function handleDelete(e: React.MouseEvent, id: number, name: string) {
      e.preventDefault();
      e.stopPropagation();
      if (!confirm(`Delete "${name}" and all its data? This cannot be undone.`)) return;
      setDeletingId(id);
      try {
        await deleteProject(id);
        setProjects((prev) => prev.filter((p) => p.id !== id));
        toast.success("Project deleted.");
      } catch {
        toast.error("Failed to delete project. Please try again.");
      } finally {
        setDeletingId(null);
      }
    }

    const filtered = useMemo(() => {
      const q = search.trim().toLowerCase();
      const list = q ? projects.filter((p) => p.name.toLowerCase().includes(q)) : projects;
      return limit ? list.slice(0, limit) : list;
    }, [projects, search, limit]);

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

    return (
      <div className="space-y-3">
        {/* Search bar (optional) */}
        {showSearch && projects.length > 0 && (
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-white/25" />
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search projects…"
              className="w-full rounded-lg border border-white/[0.08] bg-white/[0.03] py-2 pl-9 pr-3 text-sm text-white placeholder:text-white/25 focus:border-indigo-500/40 focus:outline-none focus:ring-1 focus:ring-indigo-500/20 transition-colors"
            />
          </div>
        )}

        {/* List */}
        {filtered.length === 0 ? (
          <div className="flex flex-col items-center gap-2 py-8 text-center">
            <FolderOpen className="h-8 w-8 text-white/20" />
            <p className="text-sm text-white/40">
              {search ? "No projects match your search." : "No projects yet."}
            </p>
            {!search && (
              <p className="text-xs text-white/25">
                Create a project to get started.
              </p>
            )}
          </div>
        ) : (
          <div className="divide-y divide-white/[0.05]">
            {filtered.map((project) => (
              <Link
                key={project.id}
                href={project.status === "ready" ? `/reports/${project.id}` : `/projects/${project.id}`}
                className="group flex items-center justify-between py-3 gap-3"
              >
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-medium text-white group-hover:text-indigo-300 transition-colors">
                    {project.name}
                  </p>
                  <div className="mt-0.5 flex items-center gap-2">
                    <span
                      className={`inline-block rounded-full px-2 py-0.5 text-[10px] font-medium ${STATUS_STYLE[project.status] ?? "bg-white/10 text-white/50"}`}
                    >
                      {STATUS_LABEL[project.status] ?? project.status}
                    </span>
                    {project.created_at && (
                      <span className="text-[10px] text-white/25">
                        {new Date(project.created_at).toLocaleDateString()}
                      </span>
                    )}
                  </div>
                </div>

                <div className="flex items-center gap-1.5 pl-2 flex-shrink-0">
                  {/* View report shortcut */}
                  {project.status === "ready" && (
                    <span className="hidden sm:flex items-center gap-1 rounded-md border border-indigo-500/20 bg-indigo-500/10 px-2 py-1 text-[10px] text-indigo-400 opacity-0 group-hover:opacity-100 transition-opacity">
                      <BarChart2 className="h-2.5 w-2.5" />
                      Report
                    </span>
                  )}
                  <button
                    onClick={(e) => handleDelete(e, project.id, project.name)}
                    disabled={deletingId === project.id}
                    className="rounded-md p-1.5 text-white/20 opacity-0 group-hover:opacity-100 hover:bg-red-500/10 hover:text-red-400 transition-all"
                    aria-label="Delete project"
                    title="Delete project"
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </button>
                  <ArrowRight className="h-4 w-4 flex-shrink-0 text-white/20 transition-colors group-hover:text-indigo-400" />
                </div>
              </Link>
            ))}
          </div>
        )}
      </div>
    );
  }
);
