"use client";

import Link from "next/link";
import { useEffect, useImperativeHandle, useState, forwardRef } from "react";
import { getProjects } from "@/lib/api";
import { Button } from "@/components/ui/button";

type Project = {
  id: number;
  name: string;
  status: string;
};

export type ProjectsListHandle = {
  reload: () => Promise<void>;
};

export const ProjectsList = forwardRef<ProjectsListHandle>(function ProjectsList(_, ref) {
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  async function loadProjects() {
    try {
      setLoading(true);
      setError("");

      const data = await getProjects();
      setProjects(data);
    } catch {
      setError("Failed to load projects.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadProjects();
  }, []);

  useImperativeHandle(ref, () => ({
    reload: loadProjects,
  }));

  if (loading) {
    return <p className="text-sm text-white/50">Loading projects...</p>;
  }

  if (error) {
    return <p className="text-sm text-red-400">{error}</p>;
  }

  if (projects.length === 0) {
    return <p className="text-sm text-white/50">No projects yet.</p>;
  }

  return (
    <div className="space-y-4">
      {projects.map((project) => (
        <div
          key={project.id}
          className="flex items-center justify-between rounded-2xl border border-white/10 bg-black/20 p-4"
        >
          <div>
            <p className="font-medium text-white">{project.name}</p>
            <p className="text-sm text-white/50">Status: {project.status}</p>
          </div>

          <Button
            asChild
            variant="outline"
            className="border-white/10 text-white hover:bg-white/5"
          >
            <Link href={`/projects/${project.id}`}>Open</Link>
          </Button>
        </div>
      ))}
    </div>
  );
});