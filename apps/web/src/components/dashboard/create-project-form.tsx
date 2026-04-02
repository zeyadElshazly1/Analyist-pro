"use client";

import { useState } from "react";
import { createProject, ProjectIntent } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

type CreateProjectFormProps = {
  onCreated?: () => void;
};

export function CreateProjectForm({ onCreated }: CreateProjectFormProps) {
  const [name, setName] = useState("");
  const [intent, setIntent] = useState<ProjectIntent>("general");
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState("");

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();

    if (!name.trim()) {
      setMessage("Project name is required.");
      return;
    }

    try {
      setLoading(true);
      setMessage("");

      await createProject(name.trim(), intent);

      setName("");
      setMessage("Project created successfully.");
      onCreated?.();
    } catch {
      setMessage("Failed to create project.");
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
          {loading ? "Creating..." : "Create new analysis"}
        </Button>
      </div>

      <div className="space-y-1">
        <label className="text-xs font-medium text-white/45">Primary workflow</label>
        <select
          value={intent}
          onChange={(e) => setIntent(e.target.value as ProjectIntent)}
          className="h-10 rounded-xl border border-white/10 bg-black/30 px-3 text-sm text-white outline-none"
        >
          <option value="general">General business analysis</option>
          <option value="marketing">Marketing performance</option>
          <option value="saas">SaaS growth & retention</option>
          <option value="sales">Sales pipeline</option>
          <option value="finance">Finance & reporting</option>
          <option value="operations">Operations & inventory</option>
        </select>
      </div>

      {message ? <p className="text-sm text-white/60">{message}</p> : null}
    </form>
  );
}
