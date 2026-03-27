import Link from "next/link";
import { Navbar } from "@/components/layout/navbar";
import { AuthCard } from "@/components/auth/auth-card";

export default function SignupPage() {
  return (
    <main className="min-h-screen bg-black text-white">
      <Navbar />

      <section className="flex min-h-[calc(100vh-72px)] items-center justify-center px-6 py-16">
        <div className="w-full max-w-md">
          <AuthCard
            title="Create your account"
            subtitle="Start analyzing data, generating insights, and exporting reports."
            actionText="Sign up"
          />

          <p className="mt-6 text-center text-sm text-white/60">
            Already have an account?{" "}
            <Link href="/login" className="text-white hover:underline">
              Login
            </Link>
          </p>
        </div>
      </section>
    </main>
  );
}