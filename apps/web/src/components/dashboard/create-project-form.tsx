"use client";

import { useState } from "react";
import { createProject } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { toast } from "@/components/ui/toast";

type CreateProjectFormProps = {
  onCreated?: () => void;
};

export function CreateProjectForm({ onCreated }: CreateProjectFormProps) {
  const [name, setName] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();

    if (!name.trim()) {
      toast.error("Project name is required.");
      return;
    }

    try {
      setLoading(true);
      await createProject(name.trim());
      setName("");
      toast.success(`Project "${name.trim()}" created.`);
      onCreated?.();
    } catch {
      toast.error("Failed to create project. Please try again.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-3">
      <div className="flex flex-col gap-3 sm:flex-row">
        <Input
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Enter project name"
          className="border-white/10 bg-black/30 text-white placeholder:text-white/30"
        />
        <Button type="submit" disabled={loading} className="rounded-xl">
          {loading ? "Creating…" : "Create project"}
        </Button>
      </div>
    </form>
  );
}