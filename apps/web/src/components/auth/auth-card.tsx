"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { login, register } from "@/lib/api";

type AuthCardProps = {
  title: string;
  subtitle: string;
  actionText: string;
  mode: "login" | "register";
};

export function AuthCard({ title, subtitle, actionText, mode }: AuthCardProps) {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      if (mode === "login") {
        await login(email, password);
      } else {
        await register(email, password);
      }
      router.push("/dashboard");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong");
    } finally {
      setLoading(false);
    }
  }

  return (
    <Card className="w-full max-w-md rounded-3xl border-white/10 bg-white/5 shadow-2xl shadow-black/30">
      <CardContent className="p-6">
        <h1 className="text-2xl font-semibold text-white">{title}</h1>
        <p className="mt-2 text-sm text-white/60">{subtitle}</p>

        <form onSubmit={handleSubmit} className="mt-6 space-y-4">
          <Input
            type="email"
            placeholder="Email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
            className="border-white/10 bg-black/30 text-white placeholder:text-white/30"
          />
          <Input
            type="password"
            placeholder="Password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            minLength={6}
            className="border-white/10 bg-black/30 text-white placeholder:text-white/30"
          />
          {error && (
            <p className="text-sm text-red-400">{error}</p>
          )}
          <Button type="submit" className="w-full rounded-xl" disabled={loading}>
            {loading ? "Please wait…" : actionText}
          </Button>
        </form>

        <div className="my-6 h-px bg-white/10" />

        <p className="text-center text-xs text-white/40">
          {mode === "login" ? (
            <>Don&apos;t have an account? <a href="/signup" className="text-indigo-400 hover:underline">Sign up</a></>
          ) : (
            <>Already have an account? <a href="/login" className="text-indigo-400 hover:underline">Log in</a></>
          )}
        </p>
      </CardContent>
    </Card>
  );
}
