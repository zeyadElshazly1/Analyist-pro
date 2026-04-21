"use client";

import { useEffect, useState } from "react";
import { AppShell } from "@/components/layout/app-shell";
import { useUser } from "@/lib/user-context";
import {
  Users,
  UserPlus,
  Copy,
  Check,
  Trash2,
  Loader2,
  Clock,
  AlertTriangle,
} from "lucide-react";
import { toast } from "@/components/ui/toast";
import {
  getTeamMembers,
  createTeamInvite,
  removeTeamMember,
  TeamData,
  TeamMember,
  ApiError,
} from "@/lib/api";
import { PLAN_NAMES, PLAN_LABELS } from "@/lib/plans";

function SeatBar({ used, limit }: { used: number; limit: number }) {
  const pct = Math.min(100, (used / limit) * 100);
  const full = used >= limit;
  return (
    <div className="space-y-1.5">
      <div className="flex justify-between text-xs">
        <span className="text-white/40">Seats used</span>
        <span className={full ? "text-amber-400 font-medium" : "text-white/60"}>
          {used} / {limit}
        </span>
      </div>
      <div className="h-1.5 w-full rounded-full bg-white/10">
        <div
          className={`h-full rounded-full transition-all ${full ? "bg-amber-500" : "bg-indigo-500"}`}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}

function MemberRow({
  member,
  onRemove,
}: {
  member: TeamMember;
  onRemove: (id: number) => void;
}) {
  const [removing, setRemoving] = useState(false);
  const [copied, setCopied] = useState(false);
  const inviteUrl =
    typeof window !== "undefined"
      ? `${window.location.origin}/team/join/${member.token}`
      : `/team/join/${member.token}`;

  async function handleRemove() {
    setRemoving(true);
    try {
      await removeTeamMember(member.id);
      onRemove(member.id);
    } catch {
      toast.error("Failed to remove member.");
    } finally {
      setRemoving(false);
    }
  }

  function handleCopyLink() {
    navigator.clipboard.writeText(inviteUrl).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 1800);
    });
  }

  const email = member.member_email ?? member.email ?? "—";
  const isActive = member.status === "active";

  return (
    <div className="flex items-center gap-3 py-3 border-b border-white/[0.05] last:border-0">
      <div className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-indigo-500/40 to-violet-600/40 text-xs font-bold text-white/70">
        {email[0]?.toUpperCase() ?? "?"}
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-sm text-white/80 truncate">{email}</p>
        <div className="flex items-center gap-1.5 mt-0.5">
          {isActive ? (
            <span className="inline-flex items-center gap-1 rounded-full bg-emerald-500/15 px-2 py-0.5 text-[11px] text-emerald-400">
              <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" />
              Active
            </span>
          ) : (
            <span className="inline-flex items-center gap-1 rounded-full bg-amber-500/15 px-2 py-0.5 text-[11px] text-amber-400">
              <Clock className="h-3 w-3" />
              Pending
            </span>
          )}
          {member.accepted_at && (
            <span className="text-[11px] text-white/25">
              Joined {new Date(member.accepted_at).toLocaleDateString()}
            </span>
          )}
        </div>
      </div>

      {!isActive && (
        <button
          onClick={handleCopyLink}
          className="flex items-center gap-1.5 rounded-lg border border-white/10 px-2.5 py-1.5 text-xs text-white/40 hover:text-white/70 transition-colors"
          title="Copy invite link"
        >
          {copied ? <Check className="h-3.5 w-3.5 text-emerald-400" /> : <Copy className="h-3.5 w-3.5" />}
          {copied ? "Copied" : "Copy link"}
        </button>
      )}

      <button
        onClick={handleRemove}
        disabled={removing}
        className="rounded-lg p-1.5 text-white/20 hover:text-red-400 hover:bg-red-500/10 transition-colors disabled:opacity-50"
        title={isActive ? "Remove member" : "Revoke invite"}
      >
        {removing ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Trash2 className="h-3.5 w-3.5" />}
      </button>
    </div>
  );
}

export default function TeamPage() {
  const { user, loading: loadingUser } = useUser();
  const [data, setData] = useState<TeamData | null>(null);
  const [loading, setLoading] = useState(true);
  const [inviting, setInviting] = useState(false);
  const [inviteEmail, setInviteEmail] = useState("");
  const [showInviteForm, setShowInviteForm] = useState(false);
  const [newInviteLink, setNewInviteLink] = useState<string | null>(null);
  const [copiedNew, setCopiedNew] = useState(false);

  useEffect(() => {
    if (!loadingUser && user?.plan === PLAN_NAMES.STUDIO) {
      getTeamMembers()
        .then(setData)
        .catch(() => {})
        .finally(() => setLoading(false));
    } else if (!loadingUser) {
      setLoading(false);
    }
  }, [user, loadingUser]);

  async function handleInvite() {
    setInviting(true);
    try {
      const result = await createTeamInvite(inviteEmail || undefined);
      const inviteUrl = `${window.location.origin}/team/join/${result.token}`;
      setNewInviteLink(inviteUrl);
      setInviteEmail("");
      setShowInviteForm(false);
      // Refresh member list
      const updated = await getTeamMembers();
      setData(updated);
    } catch (err) {
      const msg = err instanceof ApiError ? err.userMessage : "Failed to create invite.";
      toast.error(msg);
    } finally {
      setInviting(false);
    }
  }

  function handleRemoved(id: number) {
    setData((prev) =>
      prev
        ? { ...prev, members: prev.members.filter((m) => m.id !== id), seats_used: prev.seats_used - 1 }
        : prev,
    );
  }

  function copyNewLink() {
    if (!newInviteLink) return;
    navigator.clipboard.writeText(newInviteLink).then(() => {
      setCopiedNew(true);
      setTimeout(() => setCopiedNew(false), 1800);
    });
  }

  if (loadingUser || loading) {
    return (
      <AppShell>
        <div className="flex min-h-full items-center justify-center bg-[#080810]">
          <Loader2 className="h-5 w-5 animate-spin text-white/30" />
        </div>
      </AppShell>
    );
  }

  if (user?.plan !== PLAN_NAMES.STUDIO) {
    return (
      <AppShell>
        <div className="flex min-h-full flex-col items-center justify-center gap-4 bg-[#080810] p-6 text-center">
          <div className="flex h-12 w-12 items-center justify-center rounded-full bg-indigo-500/10">
            <Users className="h-6 w-6 text-indigo-400" />
          </div>
          <div>
            <h2 className="text-lg font-semibold text-white">{PLAN_LABELS[PLAN_NAMES.STUDIO]} plan required</h2>
            <p className="mt-1 text-sm text-white/40">
              Upgrade to the {PLAN_LABELS[PLAN_NAMES.STUDIO]} plan to invite collaborators and manage seats.
            </p>
          </div>
          <a
            href="/billing"
            className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-500 transition-colors"
          >
            View plans
          </a>
        </div>
      </AppShell>
    );
  }

  const activeMembers = data?.members.filter((m) => m.status === "active") ?? [];
  const pendingInvites = data?.members.filter((m) => m.status === "pending") ?? [];
  const seatsLeft = (data?.seat_limit ?? 5) - (data?.seats_used ?? 1);

  return (
    <AppShell>
      <div className="min-h-full bg-[#080810]">
        <div className="mx-auto max-w-2xl space-y-6 p-6 lg:p-10">

          {/* Header */}
          <div className="flex items-start justify-between gap-4">
            <div>
              <h1 className="text-2xl font-bold tracking-tight text-white">Team</h1>
              <p className="mt-1 text-sm text-white/40">Manage your team members and invite collaborators.</p>
            </div>
            {seatsLeft > 0 && (
              <button
                onClick={() => { setShowInviteForm((v) => !v); setNewInviteLink(null); }}
                className="flex items-center gap-2 rounded-lg bg-indigo-600 px-3 py-2 text-sm font-medium text-white hover:bg-indigo-500 transition-colors"
              >
                <UserPlus className="h-4 w-4" />
                Invite member
              </button>
            )}
          </div>

          {/* Seat usage */}
          {data && (
            <div className="rounded-2xl border border-white/[0.06] bg-white/[0.02] p-5">
              <SeatBar used={data.seats_used} limit={data.seat_limit} />
              {seatsLeft === 0 && (
                <p className="mt-2 flex items-center gap-1.5 text-xs text-amber-400">
                  <AlertTriangle className="h-3.5 w-3.5" />
                  All seats are occupied. Remove a member to invite someone new.
                </p>
              )}
            </div>
          )}

          {/* New invite form */}
          {showInviteForm && (
            <div className="rounded-2xl border border-indigo-500/20 bg-indigo-500/5 p-5 space-y-3">
              <h3 className="text-sm font-semibold text-indigo-300">Create invite link</h3>
              <div className="flex gap-2">
                <input
                  type="email"
                  placeholder="Email hint (optional)"
                  value={inviteEmail}
                  onChange={(e) => setInviteEmail(e.target.value)}
                  className="flex-1 rounded-lg border border-white/10 bg-white/[0.04] px-3 py-2 text-sm text-white placeholder-white/25 focus:outline-none focus:border-indigo-500/50"
                />
                <button
                  onClick={handleInvite}
                  disabled={inviting}
                  className="flex items-center gap-1.5 rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-500 transition-colors disabled:opacity-50"
                >
                  {inviting ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
                  Generate
                </button>
              </div>
              <p className="text-xs text-white/30">
                Anyone with the link can join your team. Share it with your intended collaborator.
              </p>
            </div>
          )}

          {/* New invite link */}
          {newInviteLink && (
            <div className="rounded-2xl border border-emerald-500/20 bg-emerald-500/5 p-5 space-y-3">
              <div className="flex items-center gap-2">
                <Check className="h-4 w-4 text-emerald-400" />
                <p className="text-sm font-semibold text-emerald-300">Invite link created</p>
              </div>
              <div className="flex items-center gap-2 rounded-lg border border-white/10 bg-white/[0.04] px-3 py-2">
                <code className="flex-1 truncate text-xs text-white/60">{newInviteLink}</code>
                <button
                  onClick={copyNewLink}
                  className="flex-shrink-0 rounded p-1 text-white/30 hover:text-white/70 transition-colors"
                >
                  {copiedNew ? <Check className="h-3.5 w-3.5 text-emerald-400" /> : <Copy className="h-3.5 w-3.5" />}
                </button>
              </div>
              <p className="text-xs text-white/30">This link can be used once. It will appear in the pending list below.</p>
            </div>
          )}

          {/* Owner row */}
          <div className="rounded-2xl border border-white/[0.06] bg-white/[0.02] p-5">
            <h3 className="mb-3 text-xs font-semibold uppercase tracking-wider text-white/30">Owner</h3>
            <div className="flex items-center gap-3">
              <div className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-indigo-500 to-violet-600 text-xs font-bold text-white">
                {user.email[0]?.toUpperCase()}
              </div>
              <div>
                <p className="text-sm text-white/80">{user.email}</p>
                <span className="text-[11px] text-indigo-400">Team owner</span>
              </div>
            </div>
          </div>

          {/* Active members */}
          {activeMembers.length > 0 && (
            <div className="rounded-2xl border border-white/[0.06] bg-white/[0.02] p-5">
              <h3 className="mb-1 text-xs font-semibold uppercase tracking-wider text-white/30">
                Members ({activeMembers.length})
              </h3>
              <div>
                {activeMembers.map((m) => (
                  <MemberRow key={m.id} member={m} onRemove={handleRemoved} />
                ))}
              </div>
            </div>
          )}

          {/* Pending invites */}
          {pendingInvites.length > 0 && (
            <div className="rounded-2xl border border-white/[0.06] bg-white/[0.02] p-5">
              <h3 className="mb-1 text-xs font-semibold uppercase tracking-wider text-white/30">
                Pending invites ({pendingInvites.length})
              </h3>
              <div>
                {pendingInvites.map((m) => (
                  <MemberRow key={m.id} member={m} onRemove={handleRemoved} />
                ))}
              </div>
            </div>
          )}

          {data?.members.length === 0 && (
            <div className="rounded-2xl border border-dashed border-white/[0.08] p-8 text-center">
              <Users className="mx-auto h-8 w-8 text-white/15" />
              <p className="mt-3 text-sm text-white/40">No members yet.</p>
              <p className="text-xs text-white/25">Click &quot;Invite member&quot; to generate a shareable link.</p>
            </div>
          )}

        </div>
      </div>
    </AppShell>
  );
}
