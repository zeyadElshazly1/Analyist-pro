"use client";

import { useState } from "react";
import { createProject } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

type CreateProjectFormProps = {
  onCreated?: () => void;
};

export function CreateProjectForm({ onCreated }: CreateProjectFormProps) {
  const [name, setName] = useState("");
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

      await createProject(name.trim());

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

      {message ? <p className="text-sm text-white/60">{message}</p> : null}
    </form>
  );
}