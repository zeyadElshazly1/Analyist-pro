import { AppShell } from "@/components/layout/app-shell";
import { Card, CardContent } from "@/components/ui/card";

export default function BillingPage() {
  return (
    <AppShell>
      <section className="p-6 lg:p-10">
        <h1 className="text-3xl font-semibold tracking-tight">Billing</h1>
        <Card className="mt-8 rounded-3xl border-white/10 bg-white/5">
          <CardContent className="p-6">
            <p className="text-white/70">
              Subscription, plan details, and Stripe billing settings will live here.
            </p>
          </CardContent>
        </Card>
      </section>
    </AppShell>
  );
}