import Link from "next/link";
import { buttonVariants } from "@/components/ui/button-variants";
import { cn } from "@/lib/utils";
import { Navbar } from "@/components/layout/navbar";
import {
  BarChart2,
  Sparkles,
  Upload,
  Brain,
  FileText,
  TrendingUp,
  Shield,
  ArrowRight,
  CheckCircle,
} from "lucide-react";

export default function HomePage() {
  return (
    <main className="min-h-screen bg-[#080810] text-white overflow-x-hidden">
      <Navbar />

      {/* ── HERO ────────────────────────────────────────────────────────── */}
      <section className="relative mx-auto max-w-7xl px-6 pb-24 pt-20 text-center">
        {/* Glow blobs */}
        <div className="pointer-events-none absolute inset-0 -z-10 overflow-hidden">
          <div className="absolute left-1/2 top-0 h-[600px] w-[900px] -translate-x-1/2 rounded-full bg-indigo-600/10 blur-[120px]" />
          <div className="absolute left-1/4 top-40 h-72 w-72 rounded-full bg-violet-600/10 blur-[80px]" />
          <div className="absolute right-1/4 top-60 h-72 w-72 rounded-full bg-indigo-400/8 blur-[80px]" />
        </div>

        {/* Badge */}
        <div className="mb-6 inline-flex items-center gap-2 rounded-full border border-indigo-500/30 bg-indigo-500/10 px-4 py-1.5 text-sm font-medium text-indigo-300">
          <Sparkles className="h-3.5 w-3.5" />
          Built for consultants who live in spreadsheets
        </div>

        {/* Headline */}
        <h1 className="mx-auto max-w-4xl text-5xl font-bold leading-[1.12] tracking-tight sm:text-6xl lg:text-7xl">
          Turn messy client spreadsheets into{" "}
          <span className="bg-gradient-to-r from-indigo-400 via-violet-400 to-purple-400 bg-clip-text text-transparent">
            client-ready analysis
          </span>
        </h1>

        {/* Subheading */}
        <p className="mx-auto mt-6 max-w-2xl text-lg leading-relaxed text-white/60">
          Upload CSV or Excel files, auto-clean the data, spot issues and trends, compare
          versions, and export polished reports — without rebuilding everything in Excel.
        </p>

        {/* CTAs */}
        <div className="mt-10 flex flex-col items-center gap-4 sm:flex-row sm:justify-center">
          <Link
            href="/signup"
            className={cn(buttonVariants(), "rounded-xl bg-indigo-600 px-8 py-3 text-base font-semibold text-white shadow-xl shadow-indigo-500/30 hover:bg-indigo-500 transition-all hover:-translate-y-0.5")}
          >
            Start for free
          </Link>
          <Link
            href="/pricing"
            className={cn(buttonVariants({ variant: "ghost" }), "flex items-center gap-2 rounded-xl px-8 py-3 text-base font-medium text-white/70 hover:text-white hover:bg-white/5 transition-all")}
          >
            View pricing <ArrowRight className="h-4 w-4" />
          </Link>
        </div>

        <p className="mt-8 text-sm text-white/30">
          No credit card required · Free forever plan · Setup in 30 seconds
        </p>

        {/* Mock dashboard preview */}
        <div className="relative mx-auto mt-16 max-w-5xl">
          <div className="rounded-2xl border border-white/[0.08] bg-white/[0.02] p-1 shadow-2xl shadow-black/60 ring-1 ring-white/[0.05]">
            <div className="rounded-xl border border-white/[0.06] bg-[#0d0d18] p-6">
              {/* Fake browser bar */}
              <div className="mb-5 flex items-center gap-2">
                <div className="h-3 w-3 rounded-full bg-red-500/60" />
                <div className="h-3 w-3 rounded-full bg-amber-500/60" />
                <div className="h-3 w-3 rounded-full bg-emerald-500/60" />
                <div className="ml-4 flex h-5 max-w-xs flex-1 items-center rounded-md bg-white/5 px-3 text-[10px] text-white/20">
                  app.analystpro.io/projects/42
                </div>
              </div>
              {/* Fake stat cards */}
              <div className="mb-5 grid grid-cols-4 gap-3">
                {[
                  { label: "Rows", value: "48,291", color: "text-white" },
                  { label: "Columns", value: "24", color: "text-white" },
                  { label: "Health Score", value: "91 / A", color: "text-emerald-400" },
                  { label: "Insights", value: "12", color: "text-indigo-400" },
                ].map((s) => (
                  <div key={s.label} className="rounded-xl border border-white/[0.06] bg-white/[0.03] p-3">
                    <p className="text-xs text-white/40">{s.label}</p>
                    <p className={`mt-1 text-xl font-bold ${s.color}`}>{s.value}</p>
                  </div>
                ))}
              </div>
              {/* Fake chart */}
              <div className="rounded-xl border border-white/[0.06] bg-white/[0.02] p-4">
                <p className="mb-3 text-xs font-medium text-white/40">Revenue over time</p>
                <div className="flex h-24 items-end gap-1.5">
                  {[40, 65, 50, 80, 70, 90, 75, 95, 85, 100, 88, 72].map((h, i) => (
                    <div
                      key={i}
                      className="flex-1 rounded-t-sm"
                      style={{ height: `${h}%`, background: `rgba(99,102,241,${0.3 + (h / 100) * 0.5})` }}
                    />
                  ))}
                </div>
              </div>
            </div>
          </div>

          {/* Floating badges */}
          <div className="absolute -left-6 top-16 hidden rounded-xl border border-white/10 bg-[#0d0d18]/90 px-3 py-2 shadow-xl backdrop-blur-sm lg:block">
            <div className="flex items-center gap-2">
              <div className="flex h-7 w-7 items-center justify-center rounded-full bg-emerald-500/20">
                <CheckCircle className="h-3.5 w-3.5 text-emerald-400" />
              </div>
              <div>
                <p className="text-xs font-semibold text-white">Analysis complete</p>
                <p className="text-[10px] text-white/40">12 insights found</p>
              </div>
            </div>
          </div>

          <div className="absolute -right-6 bottom-20 hidden rounded-xl border border-white/10 bg-[#0d0d18]/90 px-3 py-2 shadow-xl backdrop-blur-sm lg:block">
            <div className="flex items-center gap-2">
              <div className="flex h-7 w-7 items-center justify-center rounded-full bg-indigo-500/20">
                <TrendingUp className="h-3.5 w-3.5 text-indigo-400" />
              </div>
              <div>
                <p className="text-xs font-semibold text-white">+34% correlation</p>
                <p className="text-[10px] text-white/40">Revenue × Ad Spend</p>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ── OUTCOME PROOFS ──────────────────────────────────────────────── */}
      <section className="border-y border-white/[0.06] bg-white/[0.01] py-10">
        <div className="mx-auto max-w-5xl px-6">
          <div className="grid grid-cols-1 gap-8 md:grid-cols-3">
            {[
              { icon: "⚡", value: "Upload messy client files", label: "Auto-detected structure, cleaned and ready in seconds" },
              { icon: "↔", value: "Compare month vs month", label: "See exactly what changed between two client exports in one click" },
              { icon: "📄", value: "Export a polished report", label: "PDF and Excel output ready to send — no reformatting required" },
            ].map((item) => (
              <div key={item.value} className="text-center">
                <p className="text-2xl mb-2">{item.icon}</p>
                <p className="text-lg font-semibold text-white">{item.value}</p>
                <p className="mt-1 text-sm text-white/40">{item.label}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── FEATURES ────────────────────────────────────────────────────── */}
      <section id="features" className="py-24">
        <div className="mx-auto max-w-7xl px-6">
          <div className="mb-14 text-center">
            <p className="mb-3 text-sm font-semibold uppercase tracking-widest text-indigo-400">Features</p>
            <h2 className="text-4xl font-bold tracking-tight">
              Everything you need to go from
              <br />
              <span className="text-white/50">raw data to real insights</span>
            </h2>
          </div>

          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {features.map((f) => (
              <FeatureCard key={f.title} {...f} />
            ))}
          </div>
        </div>
      </section>

      {/* ── HOW IT WORKS ────────────────────────────────────────────────── */}
      <section className="border-t border-white/[0.06] py-24">
        <div className="mx-auto max-w-5xl px-6">
          <div className="mb-14 text-center">
            <p className="mb-3 text-sm font-semibold uppercase tracking-widest text-indigo-400">How it works</p>
            <h2 className="text-4xl font-bold tracking-tight">From upload to insight in 3 steps</h2>
          </div>

          <div className="grid gap-10 md:grid-cols-3">
            {steps.map((step, i) => (
              <div key={step.title}>
                <div className="mb-4 flex h-10 w-10 items-center justify-center rounded-xl border border-indigo-500/30 bg-indigo-600/20 text-sm font-bold text-indigo-400">
                  {i + 1}
                </div>
                <h3 className="mb-2 text-lg font-semibold text-white">{step.title}</h3>
                <p className="text-sm leading-relaxed text-white/50">{step.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── COMPARE SECTION ─────────────────────────────────────────────── */}
      <section className="border-t border-white/[0.06] py-24">
        <div className="mx-auto max-w-5xl px-6">
          <div className="grid gap-10 md:grid-cols-2 md:items-center">
            <div>
              <p className="mb-3 text-sm font-semibold uppercase tracking-widest text-indigo-400">
                Month-over-month comparison
              </p>
              <h2 className="text-4xl font-bold tracking-tight">
                See exactly what changed between two client files
              </h2>
              <p className="mt-4 text-lg leading-relaxed text-white/50">
                Upload your March and April exports side by side. Get a diff of every
                metric — rows added, columns changed, values shifted — with one click.
                No more manually reconciling spreadsheets.
              </p>
              <ul className="mt-6 space-y-3">
                {[
                  "Row-level adds, removes, and changes highlighted",
                  "Column-by-column metric delta",
                  "Before/after health score comparison",
                  "AI summary: "What changed and why it matters"",
                ].map((item) => (
                  <li key={item} className="flex items-start gap-3 text-sm text-white/60">
                    <CheckCircle className="mt-0.5 h-4 w-4 flex-shrink-0 text-indigo-400" />
                    {item}
                  </li>
                ))}
              </ul>
              <Link
                href="/signup"
                className={cn(buttonVariants(), "mt-8 inline-flex rounded-xl bg-indigo-600 px-6 py-2.5 text-sm font-semibold text-white shadow-lg shadow-indigo-500/25 hover:bg-indigo-500 transition-all")}
              >
                Try file comparison free
              </Link>
            </div>

            {/* Visual mock */}
            <div className="rounded-2xl border border-white/[0.08] bg-white/[0.02] p-5">
              <p className="mb-3 text-[11px] font-medium text-white/30 uppercase tracking-wider">
                March vs April — Revenue by channel
              </p>
              <div className="space-y-2">
                {[
                  { label: "Organic Search", before: "$12,400", after: "$14,800", delta: "+19%", up: true },
                  { label: "Paid Social",    before: "$8,200",  after: "$6,900",  delta: "-16%", up: false },
                  { label: "Email",          before: "$5,600",  after: "$6,100",  delta: "+9%",  up: true },
                  { label: "Direct",         before: "$3,100",  after: "$3,300",  delta: "+6%",  up: true },
                ].map((row) => (
                  <div
                    key={row.label}
                    className="grid grid-cols-4 items-center gap-2 rounded-lg border border-white/[0.05] bg-white/[0.02] px-3 py-2"
                  >
                    <p className="text-xs text-white/60 col-span-1">{row.label}</p>
                    <p className="text-xs text-white/30 text-right">{row.before}</p>
                    <p className="text-xs text-white/70 text-right font-medium">{row.after}</p>
                    <p className={`text-xs font-semibold text-right ${row.up ? "text-emerald-400" : "text-rose-400"}`}>
                      {row.delta}
                    </p>
                  </div>
                ))}
              </div>
              <p className="mt-3 text-[10px] text-white/20">
                AI summary: Organic growth offset paid social decline. Net revenue up 8%.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* ── CTA BANNER ──────────────────────────────────────────────────── */}
      <section className="py-24">
        <div className="mx-auto max-w-4xl px-6">
          <div className="relative overflow-hidden rounded-3xl border border-indigo-500/20 bg-gradient-to-br from-indigo-600/10 via-violet-600/8 to-transparent p-12 text-center">
            <div className="pointer-events-none absolute inset-0 -z-10">
              <div className="absolute left-1/2 top-0 h-72 w-96 -translate-x-1/2 rounded-full bg-indigo-600/15 blur-[80px]" />
            </div>
            <h2 className="text-4xl font-bold tracking-tight">Get from messy file to client-ready brief today</h2>
            <p className="mx-auto mt-4 max-w-lg text-white/60">
              Upload a client CSV or Excel file and see the health score, top findings, and a report draft in under 2 minutes.
            </p>
            <div className="mt-8 flex flex-col items-center gap-4 sm:flex-row sm:justify-center">
              <Link
                href="/signup"
                className={cn(buttonVariants(), "rounded-xl bg-indigo-600 px-8 py-3 text-base font-semibold text-white shadow-xl shadow-indigo-500/30 hover:bg-indigo-500 transition-all")}
              >
                Create free account
              </Link>
              <Link
                href="/pricing"
                className={cn(buttonVariants({ variant: "ghost" }), "rounded-xl px-8 py-3 text-base font-medium text-white/60 hover:text-white hover:bg-white/5")}
              >
                See pricing
              </Link>
            </div>
            <p className="mt-6 text-sm text-white/30">Free plan includes 3 client workspaces. No credit card required.</p>
          </div>
        </div>
      </section>

      {/* ── FOOTER ──────────────────────────────────────────────────────── */}
      <footer className="border-t border-white/[0.06] py-12">
        <div className="mx-auto max-w-7xl px-6">
          <div className="flex flex-col items-center justify-between gap-6 md:flex-row">
            <Link href="/" className="flex items-center gap-2">
              <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-gradient-to-br from-indigo-500 to-violet-600">
                <BarChart2 className="h-3.5 w-3.5 text-white" strokeWidth={2.5} />
              </div>
              <span className="text-sm font-bold text-white">
                Analyst<span className="text-indigo-400">Pro</span>
              </span>
            </Link>

            <nav className="flex items-center gap-6 text-sm text-white/40">
              <Link href="/#features" className="hover:text-white transition-colors">Features</Link>
              <Link href="/pricing" className="hover:text-white transition-colors">Pricing</Link>
              <Link href="/login" className="hover:text-white transition-colors">Log in</Link>
              <Link href="/signup" className="hover:text-white transition-colors">Sign up</Link>
            </nav>

            <p className="text-sm text-white/25">© 2025 AnalystPro. All rights reserved.</p>
          </div>
        </div>
      </footer>
    </main>
  );
}

/* ── Data ─────────────────────────────────────────────────────────────────── */

const features = [
  {
    icon: Upload,
    color: "from-indigo-500 to-indigo-600",
    glow: "shadow-indigo-500/20",
    title: "Upload any format",
    desc: "CSV, Excel (.xlsx, .xls), and more. Drag and drop your file — no formatting needed.",
  },
  {
    icon: Brain,
    color: "from-violet-500 to-violet-600",
    glow: "shadow-violet-500/20",
    title: "AI-powered insights",
    desc: "Automatically detects correlations, anomalies, skewed distributions, and segment gaps.",
  },
  {
    icon: BarChart2,
    color: "from-blue-500 to-blue-600",
    glow: "shadow-blue-500/20",
    title: "Smart chart generation",
    desc: "Get suggested charts based on your data types — bar, line, scatter, pie, and more.",
  },
  {
    icon: TrendingUp,
    color: "from-emerald-500 to-emerald-600",
    glow: "shadow-emerald-500/20",
    title: "Time series analysis",
    desc: "Detect trends, seasonality, anomalies, and stationarity across date-based data.",
  },
  {
    icon: Shield,
    color: "from-amber-500 to-orange-500",
    glow: "shadow-amber-500/20",
    title: "Data quality scoring",
    desc: "Get a health score (A–F) with deductions for missing data, duplicates, and outliers.",
  },
  {
    icon: FileText,
    color: "from-rose-500 to-pink-600",
    glow: "shadow-rose-500/20",
    title: "Export-ready reports",
    desc: "Share insights, charts, and cleaning reports with your team or clients.",
  },
];

const steps = [
  {
    title: "Upload your dataset",
    desc: "Drag and drop any CSV or Excel file. We handle parsing, type detection, and cleaning automatically.",
  },
  {
    title: "Run the analysis",
    desc: "One click triggers the full AI pipeline — profiling, insights, chart suggestions, and data quality scoring.",
  },
  {
    title: "Explore and share",
    desc: "Dive into 11 analysis tabs: correlations, outliers, time series, duplicates, column comparisons, and more.",
  },
];

/* ── Components ───────────────────────────────────────────────────────────── */

function FeatureCard({
  icon: Icon,
  color,
  glow,
  title,
  desc,
}: {
  icon: React.ElementType;
  color: string;
  glow: string;
  title: string;
  desc: string;
}) {
  return (
    <div className="group rounded-2xl border border-white/[0.07] bg-white/[0.02] p-6 transition-all hover:border-white/10 hover:bg-white/[0.04]">
      <div className={`mb-4 inline-flex h-11 w-11 items-center justify-center rounded-xl bg-gradient-to-br ${color} shadow-lg ${glow}`}>
        <Icon className="h-5 w-5 text-white" strokeWidth={2} />
      </div>
      <h3 className="mb-2 text-base font-semibold text-white">{title}</h3>
      <p className="text-sm leading-relaxed text-white/50">{desc}</p>
    </div>
  );
}
