"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { Users, Loader2, CheckCircle2, AlertTriangle } from "lucide-react";
import { getTeamInviteInfo, acceptTeamInvite, ApiError } from "@/lib/api";
import { useUser } from "@/lib/user-context";

type InviteInfo = {
  token: string;
  status: string;
  owner_email: string;
};

export default function JoinTeamPage() {
  const { token } = useParams<{ token: string }>();
  const router = useRouter();
  const { user, loading: loadingUser } = useUser();

  const [invite, setInvite] = useState<InviteInfo | null>(null);
  const [loading, setLoading] = useState(true);
  const [accepting, setAccepting] = useState(false);
  const [done, setDone] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!token) return;
    getTeamInviteInfo(token)
      .then(setInvite)
      .catch((err) => {
        setError(
          err instanceof ApiError && err.isNotFound
            ? "This invite link is invalid or has already been used."
            : "Could not load invite information.",
        );
      })
      .finally(() => setLoading(false));
  }, [token]);

  async function handleAccept() {
    if (!token) return;
    setAccepting(true);
    setError(null);
    try {
      await acceptTeamInvite(token);
      setDone(true);
      setTimeout(() => router.push("/dashboard"), 2500);
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.userMessage
          : "Failed to accept invite. Please try again.",
      );
    } finally {
      setAccepting(false);
    }
  }

  if (loading || loadingUser) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[#080810]">
        <Loader2 className="h-5 w-5 animate-spin text-white/30" />
      </div>
    );
  }

  if (done) {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center gap-4 bg-[#080810] text-center p-6">
        <CheckCircle2 className="h-12 w-12 text-emerald-400" />
        <h2 className="text-xl font-semibold text-white">Welcome to the team!</h2>
        <p className="text-sm text-white/40">Redirecting you to the dashboard…</p>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-[#080810] p-6">
      <div className="w-full max-w-sm space-y-6">
        {/* Logo */}
        <div className="flex items-center justify-center gap-2">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-indigo-500 to-violet-600">
            <Users className="h-4 w-4 text-white" />
          </div>
          <span className="text-sm font-bold text-white">
            Analyst<span className="text-indigo-400">Pro</span>
          </span>
        </div>

        <div className="rounded-2xl border border-white/[0.06] bg-white/[0.02] p-6 space-y-5">
          {error ? (
            <div className="space-y-4">
              <div className="flex items-start gap-3 rounded-xl border border-red-500/20 bg-red-500/5 p-4">
                <AlertTriangle className="h-4 w-4 text-red-400 flex-shrink-0 mt-0.5" />
                <p className="text-sm text-red-300">{error}</p>
              </div>
              {invite?.status === "pending" && (
                <button
                  onClick={handleAccept}
                  disabled={accepting}
                  className="w-full flex items-center justify-center gap-2 rounded-xl bg-indigo-600 py-2.5 text-sm font-medium text-white hover:bg-indigo-500 transition-colors disabled:opacity-50"
                >
                  {accepting && <Loader2 className="h-4 w-4 animate-spin" />}
                  Try again
                </button>
              )}
            </div>
          ) : invite ? (
            <>
              <div className="text-center space-y-2">
                <div className="flex h-14 w-14 mx-auto items-center justify-center rounded-full bg-indigo-500/10">
                  <Users className="h-7 w-7 text-indigo-400" />
                </div>
                <h2 className="text-lg font-semibold text-white">You've been invited</h2>
                <p className="text-sm text-white/50">
                  <span className="text-white/80 font-medium">{invite.owner_email}</span> has invited you
                  to join their AnalystPro team.
                </p>
              </div>

              {invite.status === "active" ? (
                <div className="rounded-xl border border-emerald-500/20 bg-emerald-500/5 p-4 text-center">
                  <CheckCircle2 className="mx-auto h-5 w-5 text-emerald-400 mb-1.5" />
                  <p className="text-sm text-emerald-300">This invite has already been accepted.</p>
                </div>
              ) : !user ? (
                <div className="space-y-3 text-center">
                  <p className="text-xs text-white/40">You need to be logged in to accept this invite.</p>
                  <a
                    href={`/login?redirect=/team/join/${token}`}
                    className="block w-full rounded-xl bg-indigo-600 py-2.5 text-sm font-medium text-white hover:bg-indigo-500 transition-colors text-center"
                  >
                    Log in to accept
                  </a>
                  <a
                    href={`/signup?redirect=/team/join/${token}`}
                    className="block w-full rounded-xl border border-white/10 py-2.5 text-sm font-medium text-white/60 hover:text-white transition-colors text-center"
                  >
                    Create an account
                  </a>
                </div>
              ) : (
                <button
                  onClick={handleAccept}
                  disabled={accepting}
                  className="w-full flex items-center justify-center gap-2 rounded-xl bg-indigo-600 py-2.5 text-sm font-medium text-white hover:bg-indigo-500 transition-colors disabled:opacity-50"
                >
                  {accepting && <Loader2 className="h-4 w-4 animate-spin" />}
                  Join team as {user.email}
                </button>
              )}
            </>
          ) : (
            <div className="text-center space-y-2 py-4">
              <AlertTriangle className="mx-auto h-8 w-8 text-amber-400" />
              <p className="text-sm text-white/50">This invite link is invalid or has expired.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
