"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { AppShell } from "@/components/layout/app-shell";
import { getProjectStats } from "@/lib/api";
import { CheckCircle, Sparkles, Zap, Users, ArrowRight } from "lucide-react";

type Stats = { total_projects: number; total_analyses: number };

const PLANS = [
  {
    name: "Free",
    price: "$0",
    period: "forever",
    current: true,
    highlighted: false,
    limits: { projects: 3, rowsPerFile: "10K" },
    features: [
      "3 projects",
      "Basic analysis pipeline",
      "Health score & profiling",
      "Up to 10K rows per file",
      "Community support",
    ],
    cta: "Current plan",
    ctaDisabled: true,
  },
  {
    name: "Pro",
    price: "$19",
    period: "/ month",
    current: false,
    highlighted: true,
    limits: { projects: Infinity, rowsPerFile: "1M" },
    features: [
      "Unlimited projects",
      "Full AI insight engine",
      "Advanced charts & time series",
      "Outlier, correlation & duplicate detection",
      "Multi-file comparison",
      "Up to 1M rows per file",
      "Shareable analysis links",
      "Priority email support",
    ],
    cta: "Upgrade to Pro",
    ctaDisabled: false,
  },
  {
    name: "Team",
    price: "$49",
    period: "/ month",
    current: false,
    highlighted: false,
    limits: { projects: Infinity, rowsPerFile: "Unlimited" },
    features: [
      "Everything in Pro",
      "5 team seats",
      "Shared workspaces",
      "Scheduled reports",
      "Custom branding on exports",
      "API access",
      "Dedicated support",
    ],
    cta: "Contact sales",
    ctaDisabled: false,
  },
];

const PLAN_ICONS = { Free: Sparkles, Pro: Zap, Team: Users } as const;

export default function BillingPage() {
  const [stats, setStats] = useState<Stats | null>(null);

  useEffect(() => {
    getProjectStats().then(setStats).catch(() => {});
  }, []);

  const projectUsagePct = stats
    ? Math.min(100, (stats.total_projects / 3) * 100)
    : 0;

  return (
    <AppShell>
      <div className="min-h-full bg-[#080810]">
        <div className="mx-auto max-w-5xl space-y-8 p-6 lg:p-10">

          {/* Header */}
          <div>
            <h1 className="text-2xl font-bold tracking-tight text-white">Billing</h1>
            <p className="mt-1 text-sm text-white/40">
              Manage your plan and view usage.
            </p>
          </div>

          {/* Current plan summary */}
          <div className="rounded-2xl border border-indigo-500/20 bg-gradient-to-br from-indigo-600/8 to-transparent p-6">
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div>
                <p className="text-xs font-semibold uppercase tracking-widest text-indigo-400">Current plan</p>
                <h2 className="mt-1 text-2xl font-bold text-white">Free</h2>
                <p className="mt-1 text-sm text-white/50">$0 / month · Renews never</p>
              </div>
              <Link
                href="#plans"
                className="flex items-center gap-2 rounded-xl bg-indigo-600 px-5 py-2.5 text-sm font-semibold text-white shadow-lg shadow-indigo-500/20 hover:bg-indigo-500 transition-all"
              >
                <Zap className="h-4 w-4" />
                Upgrade plan
              </Link>
            </div>

            {/* Usage bars */}
            <div className="mt-6 space-y-4">
              <div>
                <div className="mb-1.5 flex justify-between text-xs">
                  <span className="text-white/50">Projects used</span>
                  <span className="text-white/70">
                    {stats?.total_projects ?? 0} / 3
                  </span>
                </div>
                <div className="h-2 w-full overflow-hidden rounded-full bg-white/[0.06]">
                  <div
                    className={`h-full rounded-full transition-all duration-700 ${
                      projectUsagePct >= 90 ? "bg-red-500" : projectUsagePct >= 66 ? "bg-amber-500" : "bg-indigo-500"
                    }`}
                    style={{ width: `${projectUsagePct}%` }}
                  />
                </div>
              </div>
              <div>
                <div className="mb-1.5 flex justify-between text-xs">
                  <span className="text-white/50">Analyses run</span>
                  <span className="text-white/70">{stats?.total_analyses ?? 0}</span>
                </div>
                <div className="h-2 w-full overflow-hidden rounded-full bg-white/[0.06]">
                  <div className="h-full w-full rounded-full bg-white/10" />
                </div>
                <p className="mt-1 text-[11px] text-white/25">Unlimited on Free plan</p>
              </div>
            </div>
          </div>

          {/* Plan cards */}
          <div id="plans">
            <h2 className="mb-4 text-base font-semibold text-white">Available plans</h2>
            <div className="grid gap-4 md:grid-cols-3">
              {PLANS.map((plan) => {
                const Icon = PLAN_ICONS[plan.name as keyof typeof PLAN_ICONS];
                return (
                  <div
                    key={plan.name}
                    className={`relative flex flex-col rounded-2xl border p-6 transition-all ${
                      plan.highlighted
                        ? "border-indigo-500/50 bg-gradient-to-b from-indigo-600/10 to-transparent"
                        : plan.current
                          ? "border-white/20 bg-white/[0.03]"
                          : "border-white/[0.07] bg-white/[0.02] hover:border-white/10"
                    }`}
                  >
                    {plan.highlighted && (
                      <div className="absolute -top-3 left-1/2 -translate-x-1/2">
                        <span className="rounded-full bg-indigo-600 px-3 py-0.5 text-[11px] font-semibold text-white">
                          Most popular
                        </span>
                      </div>
                    )}

                    <div className="mb-4 flex items-center gap-2.5">
                      <div className={`flex h-8 w-8 items-center justify-center rounded-lg ${
                        plan.highlighted ? "bg-indigo-600/20" : "bg-white/[0.06]"
                      }`}>
                        <Icon className={`h-4 w-4 ${plan.highlighted ? "text-indigo-400" : "text-white/50"}`} />
                      </div>
                      <div>
                        <p className="text-sm font-semibold text-white">{plan.name}</p>
                        {plan.current && (
                          <span className="text-[10px] text-emerald-400 font-medium">Active</span>
                        )}
                      </div>
                    </div>

                    <div className="mb-5">
                      <span className="text-3xl font-bold text-white">{plan.price}</span>
                      <span className="ml-1 text-sm text-white/40">{plan.period}</span>
                    </div>

                    <ul className="mb-6 flex-1 space-y-2.5">
                      {plan.features.map((f) => (
                        <li key={f} className="flex items-start gap-2 text-xs text-white/60">
                          <CheckCircle className={`mt-0.5 h-3.5 w-3.5 flex-shrink-0 ${
                            plan.highlighted ? "text-indigo-400" : "text-white/25"
                          }`} />
                          {f}
                        </li>
                      ))}
                    </ul>

                    <button
                      disabled={plan.ctaDisabled}
                      className={`w-full rounded-xl py-2 text-sm font-semibold transition-all ${
                        plan.ctaDisabled
                          ? "bg-white/[0.05] text-white/30 cursor-default"
                          : plan.highlighted
                            ? "bg-indigo-600 text-white hover:bg-indigo-500 shadow-lg shadow-indigo-500/20"
                            : "bg-white/[0.07] text-white hover:bg-white/10"
                      }`}
                    >
                      {plan.cta}
                    </button>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Billing history placeholder */}
          <div className="rounded-2xl border border-white/[0.06] bg-white/[0.02] p-6">
            <div className="flex items-center justify-between">
              <h2 className="text-sm font-semibold text-white">Billing history</h2>
              <ArrowRight className="h-4 w-4 text-white/20" />
            </div>
            <p className="mt-3 text-sm text-white/35 italic">
              No invoices yet — you&apos;re on the Free plan.
            </p>
          </div>
        </div>
      </div>
    </AppShell>
  );
}
