"use client";

import Link from "next/link";
import { AppShell } from "@/components/layout/app-shell";
import { RunAnalysis, type AnalysisResult } from "@/components/project/run-analysis";
import { DEMO_RESULT, DEMO_COMPARE_RESULT } from "@/lib/demo-result";
import { ArrowLeft, Beaker, ExternalLink } from "lucide-react";

// Cast the fixture to AnalysisResult — insights is structurally compatible.
const demoResult = DEMO_RESULT as unknown as AnalysisResult;

export default function DemoPage() {
  return (
    <AppShell>
      <div className="min-h-full bg-[#080810]">
        <div className="mx-auto max-w-4xl space-y-6 p-6 lg:p-10">

          {/* Breadcrumb */}
          <Link
            href="/projects"
            className="inline-flex items-center gap-1.5 text-xs text-white/35 hover:text-white/60 transition-colors"
          >
            <ArrowLeft className="h-3 w-3" />
            Workspaces
          </Link>

          {/* Demo banner */}
          <div className="rounded-xl border border-amber-500/20 bg-amber-500/5 px-4 py-3">
            <div className="flex items-start gap-3">
              <Beaker className="mt-0.5 h-4 w-4 flex-shrink-0 text-amber-400" strokeWidth={1.75} />
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-white">Sample workspace — no upload needed</p>
                <p className="mt-0.5 text-xs text-white/50">
                  This is a pre-loaded demo showing a completed analysis of a fictional monthly sales file.
                  All 6 workflow steps and the October → November comparison are ready to explore.
                  Charts and AI features require a real workspace.
                </p>
              </div>
              <Link
                href="/projects"
                className="flex flex-shrink-0 items-center gap-1 rounded-lg bg-white/[0.06] px-3 py-1.5 text-xs font-medium text-white/70 hover:bg-white/10 hover:text-white transition-colors"
              >
                Create your own
                <ExternalLink className="h-3 w-3" />
              </Link>
            </div>
          </div>

          {/* Header */}
          <div className="flex items-center gap-3">
            <div className="flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-xl bg-amber-600/15">
              <Beaker className="h-4 w-4 text-amber-400" strokeWidth={1.75} />
            </div>
            <div>
              <p className="text-[11px] text-white/30">Demo workspace</p>
              <h1 className="text-xl font-bold tracking-tight text-white">
                Acme Retail — November 2024 Sales
              </h1>
            </div>
          </div>

          {/* Analysis workflow — pre-populated with demo fixture */}
          <section className="rounded-2xl border border-white/[0.06] bg-white/[0.02] p-6">
            <div className="mb-5 flex items-center gap-2.5">
              <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-amber-600/10">
                <Beaker className="h-3.5 w-3.5 text-amber-400" strokeWidth={1.75} />
              </div>
              <div>
                <h2 className="text-sm font-semibold text-white">Analysis workflow</h2>
                <p className="text-xs text-white/40">
                  Intake → Cleaning → Health → Findings → Compare (Oct vs Nov) → Report
                </p>
              </div>
            </div>
            <RunAnalysis
              projectId={0}
              initialResult={demoResult}
              initialCompareResult={DEMO_COMPARE_RESULT}
            />
          </section>

        </div>
      </div>
    </AppShell>
  );
}
