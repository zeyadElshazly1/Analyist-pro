import Link from "next/link";
import { Navbar } from "@/components/layout/navbar";
import { Button } from "@/components/ui/button";
import { CheckCircle, BarChart2 } from "lucide-react";

const plans = [
  {
    name: "Free",
    price: "$0",
    period: "forever",
    description: "Perfect for trying out AnalystPro",
    cta: "Start for free",
    ctaHref: "/signup",
    highlighted: false,
    features: [
      "3 projects",
      "Basic analysis pipeline",
      "Health score & profiling",
      "Up to 10K rows per file",
      "Community support",
    ],
  },
  {
    name: "Pro",
    price: "$19",
    period: "/ month",
    description: "For solo analysts and founders",
    cta: "Get started",
    ctaHref: "/signup",
    highlighted: true,
    features: [
      "Unlimited projects",
      "Full AI insight engine",
      "Advanced charts & time series",
      "Outlier, correlation & duplicate detection",
      "Multi-file comparison",
      "Up to 1M rows per file",
      "Email support",
    ],
  },
  {
    name: "Team",
    price: "$49",
    period: "/ month",
    description: "For growing teams",
    cta: "Get started",
    ctaHref: "/signup",
    highlighted: false,
    features: [
      "Everything in Pro",
      "5 team seats",
      "Shared workspace",
      "Scheduled reports",
      "Priority support",
      "Custom branding on exports",
      "API access",
    ],
  },
];

export default function PricingPage() {
  return (
    <main className="min-h-screen bg-[#080810] text-white">
      <Navbar />

      {/* Header */}
      <section className="relative py-20 text-center">
        <div className="pointer-events-none absolute inset-0 -z-10 overflow-hidden">
          <div className="absolute left-1/2 top-0 h-96 w-[700px] -translate-x-1/2 rounded-full bg-indigo-600/8 blur-[100px]" />
        </div>

        <p className="mb-3 text-sm font-semibold uppercase tracking-widest text-indigo-400">Pricing</p>
        <h1 className="mx-auto max-w-2xl text-5xl font-bold tracking-tight">
          Simple, transparent pricing
        </h1>
        <p className="mx-auto mt-4 max-w-lg text-white/60">
          Start free, upgrade when you need more power. Cancel anytime.
        </p>
      </section>

      {/* Plans */}
      <section className="mx-auto max-w-6xl px-6 pb-24">
        <div className="grid gap-6 md:grid-cols-3">
          {plans.map((plan) => (
            <PlanCard key={plan.name} plan={plan} />
          ))}
        </div>

        {/* FAQ teaser */}
        <div className="mt-16 rounded-2xl border border-white/[0.07] bg-white/[0.02] p-8 text-center">
          <h3 className="text-lg font-semibold text-white">Have questions?</h3>
          <p className="mt-2 text-sm text-white/50">
            All plans include a 14-day Pro trial. No credit card required to start.
          </p>
          <div className="mt-6 flex flex-wrap items-center justify-center gap-8 text-sm text-white/50">
            {[
              "Can I switch plans?",
              "What counts as a project?",
              "Is my data secure?",
              "Do you support Excel?",
            ].map((q) => (
              <span key={q} className="cursor-pointer hover:text-indigo-400 transition-colors">{q}</span>
            ))}
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-white/[0.06] py-10">
        <div className="mx-auto max-w-7xl px-6 flex flex-col items-center justify-between gap-6 md:flex-row">
          <Link href="/" className="flex items-center gap-2">
            <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-gradient-to-br from-indigo-500 to-violet-600">
              <BarChart2 className="h-3.5 w-3.5 text-white" strokeWidth={2.5} />
            </div>
            <span className="text-sm font-bold text-white">
              Analyst<span className="text-indigo-400">Pro</span>
            </span>
          </Link>
          <nav className="flex items-center gap-6 text-sm text-white/40">
            <Link href="/" className="hover:text-white transition-colors">Home</Link>
            <Link href="/login" className="hover:text-white transition-colors">Log in</Link>
            <Link href="/signup" className="hover:text-white transition-colors">Sign up</Link>
          </nav>
          <p className="text-sm text-white/25">© 2025 AnalystPro. All rights reserved.</p>
        </div>
      </footer>
    </main>
  );
}

function PlanCard({ plan }: { plan: typeof plans[number] }) {
  return (
    <div className={`relative flex flex-col rounded-2xl border p-8 transition-all ${
      plan.highlighted
        ? "border-indigo-500/50 bg-gradient-to-b from-indigo-600/10 to-transparent shadow-2xl shadow-indigo-500/10"
        : "border-white/[0.07] bg-white/[0.02] hover:border-white/10 hover:bg-white/[0.04]"
    }`}>
      {plan.highlighted && (
        <div className="absolute -top-3.5 left-1/2 -translate-x-1/2">
          <span className="rounded-full bg-indigo-600 px-4 py-1 text-xs font-semibold text-white shadow-lg shadow-indigo-500/30">
            Most popular
          </span>
        </div>
      )}

      <div className="mb-6">
        <p className="text-sm font-semibold text-white/60">{plan.name}</p>
        <div className="mt-2 flex items-baseline gap-1">
          <span className="text-5xl font-bold text-white">{plan.price}</span>
          <span className="text-sm text-white/40">{plan.period}</span>
        </div>
        <p className="mt-2 text-sm text-white/50">{plan.description}</p>
      </div>

      <Button asChild className={`mb-8 w-full rounded-xl py-2.5 text-sm font-semibold transition-all ${
        plan.highlighted
          ? "bg-indigo-600 text-white shadow-lg shadow-indigo-500/25 hover:bg-indigo-500"
          : "bg-white/[0.07] text-white hover:bg-white/10"
      }`}>
        <Link href={plan.ctaHref}>{plan.cta}</Link>
      </Button>

      <ul className="flex-1 space-y-3">
        {plan.features.map((f) => (
          <li key={f} className="flex items-start gap-3 text-sm text-white/70">
            <CheckCircle className={`mt-0.5 h-4 w-4 flex-shrink-0 ${plan.highlighted ? "text-indigo-400" : "text-white/30"}`} />
            {f}
          </li>
        ))}
      </ul>
    </div>
  );
}
