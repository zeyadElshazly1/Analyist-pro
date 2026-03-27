"use client";

import { useRef } from "react";
import { AppShell } from "@/components/layout/app-shell";
import { Card, CardContent } from "@/components/ui/card";
import { CreateProjectForm } from "@/components/dashboard/create-project-form";
import { ProjectsList, ProjectsListHandle } from "@/components/dashboard/projects-list";

const stats = [
  { label: "Projects", value: "12" },
  { label: "Files analyzed", value: "38" },
  { label: "Reports", value: "19" },
  { label: "Usage this month", value: "72%" },
];

export default function DashboardPage() {
  const projectsListRef = useRef<ProjectsListHandle>(null);

  return (
    <AppShell>
      <section className="p-6 lg:p-10">
        <div className="flex flex-col gap-4">
          <div>
            <h1 className="text-3xl font-semibold tracking-tight text-white">
              Welcome back
            </h1>
            <p className="mt-2 text-white/60">
              Manage projects, upload new datasets, and review your latest reports.
            </p>
          </div>

          <CreateProjectForm
            onCreated={() => {
              projectsListRef.current?.reload();
            }}
          />
        </div>

        <div className="mt-8 grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          {stats.map((stat) => (
            <Card key={stat.label} className="rounded-3xl border-white/10 bg-white/5">
              <CardContent className="p-6">
                <p className="text-sm text-white/50">{stat.label}</p>
                <p className="mt-3 text-3xl font-semibold text-white">{stat.value}</p>
              </CardContent>
            </Card>
          ))}
        </div>

        <div className="mt-8 grid gap-6 xl:grid-cols-3">
          <Card className="rounded-3xl border-white/10 bg-white/5 xl:col-span-2">
            <CardContent className="p-6">
              <h2 className="text-lg font-medium text-white">Recent projects</h2>
              <div className="mt-6">
                <ProjectsList ref={projectsListRef} />
              </div>
            </CardContent>
          </Card>

          <Card className="rounded-3xl border-white/10 bg-white/5">
            <CardContent className="p-6">
              <h2 className="text-lg font-medium text-white">Next milestone</h2>
              <div className="mt-4 rounded-2xl border border-white/10 bg-black/20 p-4">
                <p className="font-medium text-white">Upload datasets</p>
                <p className="mt-1 text-sm text-white/50">
                  Next we connect file upload and the first real analysis flow.
                </p>
              </div>
            </CardContent>
          </Card>
        </div>
      </section>
    </AppShell>
  );
}