"use client";

import { useEffect, useState } from "react";
import { AppShell } from "@/components/layout/app-shell";
import { getProjectStats, createCheckoutSession } from "@/lib/api";
import { useUser } from "@/lib/user-context";
import { PLAN_NAMES, PLAN_LABELS, type PlanName } from "@/lib/plans";
import { CheckCircle, Sparkles, Zap, Users, ArrowRight, Loader2 } from "lucide-react";

type Stats = { total_projects: number; total_analyses: number };

const PLANS = [
  {
    id: PLAN_NAMES.FREE,
    name: PLAN_LABELS[PLAN_NAMES.FREE],
    price: "$0",
    period: "forever",
    highlighted: false,
    projectLimit: 3,
    features: [
      "3 projects",
      "Basic analysis pipeline",
      "Health score & profiling",
      "Up to 10K rows per file",
      "Community support",
    ],
    cta: "Current plan",
  },
  {
    id: PLAN_NAMES.CONSULTANT,
    name: PLAN_LABELS[PLAN_NAMES.CONSULTANT],
    price: "$39",
    period: "/ month",
    highlighted: true,
    projectLimit: Infinity,
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
    cta: "Upgrade to Consultant",
  },
  {
    id: PLAN_NAMES.STUDIO,
    name: PLAN_LABELS[PLAN_NAMES.STUDIO],
    price: "$49",
    period: "/ month",
    highlighted: false,
    projectLimit: Infinity,
    features: [
      "Everything in Consultant",
      "5 team seats",
      "Shared workspaces",
      "Scheduled reports",
      "Custom branding on exports",
      "API access",
      "Dedicated support",
    ],
    cta: "Contact sales",
  },
];

const PLAN_ICONS: Record<PlanName, React.ElementType> = {
  [PLAN_NAMES.FREE]:       Sparkles,
  [PLAN_NAMES.CONSULTANT]: Zap,
  [PLAN_NAMES.STUDIO]:     Users,
};

export default function BillingPage() {
  const [stats, setStats] = useState<Stats | null>(null);
  const [loadingPlan, setLoadingPlan] = useState<string | null>(null);
  const [checkoutError, setCheckoutError] = useState<string | null>(null);
  const [redirectUrl, setRedirectUrl] = useState<string | null>(null);
  const { user } = useUser();

  useEffect(() => {
    getProjectStats().then(setStats).catch(() => {});
  }, []);

  useEffect(() => {
    if (redirectUrl) {
      window.location.href = redirectUrl;
    }
  }, [redirectUrl]);

  async function handleUpgrade(planId: PlanName) {
    if (planId === PLAN_NAMES.FREE) return;
    setCheckoutError(null);
    setLoadingPlan(planId);
    try {
      const { checkout_url } = await createCheckoutSession(planId);
      setRedirectUrl(checkout_url);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Could not start checkout. Please try again.";
      setCheckoutError(msg);
      setLoadingPlan(null);
    }
  }

  const currentPlan = (user?.plan ?? PLAN_NAMES.FREE) as PlanName;

  const activePlan = PLANS.find((p) => p.id === currentPlan) ?? PLANS[0];
  const projectLimit = activePlan.projectLimit;
  const projectUsagePct =
    stats && projectLimit !== Infinity
      ? Math.min(100, (stats.total_projects / projectLimit) * 100)
      : stats
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
                <h2 className="mt-1 text-2xl font-bold text-white">{PLAN_LABELS[currentPlan]}</h2>
                <p className="mt-1 text-sm text-white/50">
                  {currentPlan === PLAN_NAMES.FREE ? "$0 / month · No expiry" : "Billed monthly"}
                </p>
              </div>
              {currentPlan === PLAN_NAMES.FREE && (
                <a
                  href="#plans"
                  className="flex items-center gap-2 rounded-xl bg-indigo-600 px-5 py-2.5 text-sm font-semibold text-white shadow-lg shadow-indigo-500/20 hover:bg-indigo-500 transition-all"
                >
                  <Zap className="h-4 w-4" />
                  Upgrade plan
                </a>
              )}
            </div>

            {/* Usage bars */}
            <div className="mt-6 space-y-4">
              <div>
                <div className="mb-1.5 flex justify-between text-xs">
                  <span className="text-white/50">Projects used</span>
                  <span className="text-white/70">
                    {stats?.total_projects ?? 0}
                    {projectLimit !== Infinity ? ` / ${projectLimit}` : " (unlimited)"}
                  </span>
                </div>
                <div className="h-2 w-full overflow-hidden rounded-full bg-white/[0.06]">
                  <div
                    className={`h-full rounded-full transition-all duration-700 ${
                      projectUsagePct >= 90
                        ? "bg-red-500"
                        : projectUsagePct >= 66
                          ? "bg-amber-500"
                          : "bg-indigo-500"
                    }`}
                    style={{ width: projectLimit === Infinity ? "0%" : `${projectUsagePct}%` }}
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
                <p className="mt-1 text-[11px] text-white/25">Unlimited on all plans</p>
              </div>
            </div>
          </div>

          {/* Plan cards */}
          <div id="plans">
            <h2 className="mb-4 text-base font-semibold text-white">Available plans</h2>
            <div className="grid gap-4 md:grid-cols-3">
              {PLANS.map((plan) => {
                const Icon = PLAN_ICONS[plan.id as PlanName];
                const isCurrent = plan.id === currentPlan;
                return (
                  <div
                    key={plan.id}
                    className={`relative flex flex-col rounded-2xl border p-6 transition-all ${
                      plan.highlighted
                        ? "border-indigo-500/50 bg-gradient-to-b from-indigo-600/10 to-transparent"
                        : isCurrent
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
                      <div
                        className={`flex h-8 w-8 items-center justify-center rounded-lg ${
                          plan.highlighted ? "bg-indigo-600/20" : "bg-white/[0.06]"
                        }`}
                      >
                        <Icon
                          className={`h-4 w-4 ${plan.highlighted ? "text-indigo-400" : "text-white/50"}`}
                        />
                      </div>
                      <div>
                        <p className="text-sm font-semibold text-white">{plan.name}</p>
                        {isCurrent && (
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
                          <CheckCircle
                            className={`mt-0.5 h-3.5 w-3.5 flex-shrink-0 ${
                              plan.highlighted ? "text-indigo-400" : "text-white/25"
                            }`}
                          />
                          {f}
                        </li>
                      ))}
                    </ul>

                    {isCurrent ? (
                      <div className="w-full rounded-xl bg-white/[0.05] py-2 text-center text-sm text-white/30">
                        Current plan
                      </div>
                    ) : plan.id === PLAN_NAMES.STUDIO ? (
                      <a
                        href="mailto:sales@analystpro.com"
                        className="block w-full rounded-xl bg-white/[0.07] py-2 text-center text-sm font-semibold text-white hover:bg-white/10 transition-all"
                      >
                        {plan.cta}
                      </a>
                    ) : (
                      <button
                        onClick={() => handleUpgrade(plan.id)}
                        disabled={loadingPlan !== null}
                        className={`flex w-full items-center justify-center gap-2 rounded-xl py-2 text-sm font-semibold transition-all disabled:opacity-60 disabled:cursor-not-allowed ${
                          plan.highlighted
                            ? "bg-indigo-600 text-white hover:bg-indigo-500 shadow-lg shadow-indigo-500/20"
                            : "bg-white/[0.07] text-white hover:bg-white/10"
                        }`}
                      >
                        {loadingPlan === plan.id ? (
                          <Loader2 className="h-4 w-4 animate-spin" />
                        ) : null}
                        {plan.cta}
                      </button>
                    )}
                  </div>
                );
              })}
            </div>
          </div>

          {checkoutError && (
            <div className="rounded-xl border border-red-500/20 bg-red-500/5 px-4 py-3 text-sm text-red-400">
              {checkoutError}
            </div>
          )}

          {/* Billing history placeholder */}
          <div className="rounded-2xl border border-white/[0.06] bg-white/[0.02] p-6">
            <div className="flex items-center justify-between">
              <h2 className="text-sm font-semibold text-white">Billing history</h2>
              <ArrowRight className="h-4 w-4 text-white/20" />
            </div>
            <p className="mt-3 text-sm text-white/35 italic">
              {currentPlan === PLAN_NAMES.FREE
                ? "No invoices yet — you're on the Free plan."
                : "Invoice history will appear here."}
            </p>
          </div>
        </div>
      </div>
    </AppShell>
  );
}
