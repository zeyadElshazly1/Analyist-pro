import { Button } from "@/components/ui/button"
import { Navbar } from "@/components/layout/navbar";

export default function HomePage() {
  return (
    <main className="min-h-screen bg-black text-white">
        <Navbar />

      {/* HERO */}
      <section className="mx-auto max-w-6xl px-6 py-24">
        <div className="max-w-3xl space-y-6">

          <h1 className="text-5xl font-bold tracking-tight">
            Analyze your data like a pro.
          </h1>

          <p className="text-lg text-white/70">
            Upload spreadsheets, ask questions in plain English,
            and get instant charts, insights, and reports.
          </p>

          <div className="flex gap-4">
            <Button size="lg">
              Start free
            </Button>

            <Button size="lg" variant="outline">
              See demo
            </Button>
          </div>

        </div>
      </section>


      {/* FEATURES */}
      <section className="border-t border-white/10 py-20">
        <div className="mx-auto max-w-6xl px-6 grid grid-cols-1 md:grid-cols-3 gap-6">

          <Feature
            title="Upload any dataset"
            desc="CSV, Excel, JSON, SQL exports."
          />

          <Feature
            title="AI insights"
            desc="Ask questions in plain English."
          />

          <Feature
            title="Export reports"
            desc="Charts, tables, client-ready PDFs."
          />

        </div>
      </section>


      {/* CTA */}
      <section className="border-t border-white/10 py-24 text-center">

        <h2 className="text-3xl font-semibold">
          Start analyzing in minutes
        </h2>

        <p className="mt-3 text-white/60">
          No setup. No SQL required.
        </p>

        <div className="mt-6">
          <Button size="lg">
            Create account
          </Button>
        </div>

      </section>

    </main>
  )
}


function Feature({
  title,
  desc,
}: {
  title: string
  desc: string
}) {
  return (
    <div className="rounded-2xl border border-white/10 p-6 bg-white/5">

      <h3 className="font-semibold text-lg">
        {title}
      </h3>

      <p className="mt-2 text-white/60">
        {desc}
      </p>

    </div>
  )
}