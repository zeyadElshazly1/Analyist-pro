import Link from "next/link";
import { Navbar } from "@/components/layout/navbar";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";

const plans = [
  {
    name: "Free",
    price: "$0",
    description: "For trying Analyst Pro",
    features: ["3 projects", "Basic analysis", "Limited exports"],
  },
  {
    name: "Pro",
    price: "$19/mo",
    description: "For solo founders and analysts",
    features: ["Unlimited projects", "AI insights", "Advanced charts", "Report export"],
  },
  {
    name: "Team",
    price: "$49/mo",
    description: "For small teams",
    features: ["Shared workspace", "Team seats", "Scheduled reports", "Priority support"],
  },
];

export default function PricingPage() {
  return (
    <main className="min-h-screen bg-[#0a0a0b] text-white">
      <Navbar />

      <section className="mx-auto max-w-7xl px-6 py-20 lg:px-8">
        <div className="mx-auto max-w-2xl text-center">
          <h1 className="text-4xl font-semibold tracking-tight sm:text-5xl">
            Simple pricing for modern analytics
          </h1>
          <p className="mt-4 text-white/70">
            Start free, upgrade when you need more projects, reports, and team features.
          </p>
        </div>

        <div className="mt-14 grid gap-6 md:grid-cols-3">
          {plans.map((plan) => (
            <Card
              key={plan.name}
              className="rounded-3xl border-white/10 bg-white/5 shadow-xl shadow-black/20"
            >
              <CardContent className="p-6">
                <p className="text-sm text-white/50">{plan.name}</p>
                <h2 className="mt-2 text-3xl font-semibold">{plan.price}</h2>
                <p className="mt-2 text-sm text-white/70">{plan.description}</p>

                <div className="mt-6 space-y-3">
                  {plan.features.map((feature) => (
                    <div key={feature} className="text-sm text-white/80">
                      • {feature}
                    </div>
                  ))}
                </div>

                <Button asChild className="mt-8 w-full rounded-xl">
                  <Link href="/signup">Choose {plan.name}</Link>
                </Button>
              </CardContent>
            </Card>
          ))}
        </div>
      </section>
    </main>
  );
}