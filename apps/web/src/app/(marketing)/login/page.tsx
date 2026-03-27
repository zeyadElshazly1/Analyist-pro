import Link from "next/link";
import { Navbar } from "@/components/layout/navbar";
import { AuthCard } from "@/components/auth/auth-card";

export default function LoginPage() {
  return (
    <main className="min-h-screen bg-black text-white">
      <Navbar />

      <section className="flex min-h-[calc(100vh-72px)] items-center justify-center px-6 py-16">
        <div className="w-full max-w-md">
          <AuthCard
            title="Welcome back"
            subtitle="Sign in to access your projects, reports, and saved analyses."
            actionText="Login"
          />

          <p className="mt-6 text-center text-sm text-white/60">
            Don&apos;t have an account?{" "}
            <Link href="/signup" className="text-white hover:underline">
              Sign up
            </Link>
          </p>
        </div>
      </section>
    </main>
  );
}