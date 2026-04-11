"use client";

import { useState } from "react";
import { AppShell } from "@/components/layout/app-shell";
import { useUser } from "@/lib/user-context";
import { User, Bell, Shield, Download, Loader2, Check, AlertTriangle } from "lucide-react";
import { toast } from "@/components/ui/toast";
import { deleteMyAccount, exportMyData, ApiError } from "@/lib/api";

function Section({
  title,
  description,
  icon: Icon,
  children,
}: {
  title: string;
  description: string;
  icon: React.ElementType;
  children: React.ReactNode;
}) {
  return (
    <div className="rounded-2xl border border-white/[0.06] bg-white/[0.02] p-6">
      <div className="mb-5 flex items-start gap-3">
        <div className="mt-0.5 flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-lg bg-white/[0.05]">
          <Icon className="h-4 w-4 text-white/50" strokeWidth={1.75} />
        </div>
        <div>
          <h2 className="text-sm font-semibold text-white">{title}</h2>
          <p className="mt-0.5 text-xs text-white/40">{description}</p>
        </div>
      </div>
      {children}
    </div>
  );
}

function Toggle({
  label,
  description,
  defaultOn = false,
}: {
  label: string;
  description: string;
  defaultOn?: boolean;
}) {
  const [on, setOn] = useState(defaultOn);
  return (
    <div className="flex items-start justify-between gap-4 py-3 border-b border-white/[0.05] last:border-0">
      <div>
        <p className="text-sm text-white/80">{label}</p>
        <p className="text-xs text-white/35">{description}</p>
      </div>
      <button
        onClick={() => setOn((o) => !o)}
        className={`relative mt-0.5 h-5 w-9 flex-shrink-0 rounded-full transition-colors ${
          on ? "bg-indigo-600" : "bg-white/15"
        }`}
        aria-checked={on}
        role="switch"
      >
        <span
          className={`absolute top-0.5 h-4 w-4 rounded-full bg-white shadow transition-transform ${
            on ? "translate-x-4" : "translate-x-0.5"
          }`}
        />
      </button>
    </div>
  );
}

export default function SettingsPage() {
  const { user, loading: loadingUser } = useUser();
  const [deleteConfirm, setDeleteConfirm] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [exporting, setExporting] = useState(false);

  const initial = user?.email?.[0]?.toUpperCase() ?? "U";
  const planLabel =
    user?.plan
      ? user.plan.charAt(0).toUpperCase() + user.plan.slice(1) + " plan"
      : "Free plan";

  const memberSince = user?.created_at
    ? new Date(user.created_at).toLocaleDateString(undefined, { year: "numeric", month: "long" })
    : null;

  async function handleExport() {
    setExporting(true);
    try {
      await exportMyData();
      toast.success("Your data export has been downloaded.");
    } catch (err) {
      const msg = err instanceof ApiError ? err.userMessage : "Export failed. Please try again.";
      toast.error(msg);
    } finally {
      setExporting(false);
    }
  }

  async function handleDelete() {
    if (!deleteConfirm) {
      setDeleteConfirm(true);
      return;
    }
    setDeleting(true);
    try {
      await deleteMyAccount();
      toast.success("Your account has been deleted.");
      // Redirect to marketing site after deletion
      window.location.href = "/";
    } catch (err) {
      const msg = err instanceof ApiError ? err.userMessage : "Deletion failed. Please try again.";
      toast.error(msg);
      setDeleting(false);
      setDeleteConfirm(false);
    }
  }

  return (
    <AppShell>
      <div className="min-h-full bg-[#080810]">
        <div className="mx-auto max-w-2xl space-y-6 p-6 lg:p-10">

          {/* Header */}
          <div>
            <h1 className="text-2xl font-bold tracking-tight text-white">Settings</h1>
            <p className="mt-1 text-sm text-white/40">Manage your account and preferences.</p>
          </div>

          {/* Profile */}
          <Section title="Profile" description="Your account identity on AnalystPro." icon={User}>
            {loadingUser ? (
              <div className="flex items-center gap-2 py-4 text-white/40">
                <Loader2 className="h-4 w-4 animate-spin" />
                <span className="text-sm">Loading profile…</span>
              </div>
            ) : (
              <div className="space-y-4">
                <div className="flex items-center gap-4">
                  <div className="flex h-14 w-14 flex-shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-indigo-500 to-violet-600 text-lg font-bold text-white shadow-lg shadow-indigo-500/20">
                    {initial}
                  </div>
                  <div>
                    <p className="text-sm font-semibold text-white">{user?.email ?? "—"}</p>
                    <p className="text-xs text-white/40">{planLabel}{memberSince ? ` · Member since ${memberSince}` : ""}</p>
                  </div>
                </div>

                <div className="space-y-3">
                  <div className="space-y-1.5">
                    <label className="block text-xs font-medium text-white/50">Email address</label>
                    <div className="w-full rounded-xl border border-white/[0.06] bg-white/[0.02] px-3 py-2 text-sm text-white/50 select-all">
                      {user?.email ?? "—"}
                    </div>
                    <p className="text-[11px] text-white/25">
                      Email changes are managed through your authentication provider.
                    </p>
                  </div>

                  <div className="space-y-1.5">
                    <label className="block text-xs font-medium text-white/50">Plan</label>
                    <div className="flex items-center gap-2">
                      <div className="rounded-xl border border-white/[0.06] bg-white/[0.02] px-3 py-2 text-sm text-white/50">
                        {planLabel}
                      </div>
                      {user?.plan === "free" && (
                        <a
                          href="/billing"
                          className="rounded-lg bg-indigo-600/20 border border-indigo-500/30 px-3 py-1.5 text-xs font-medium text-indigo-300 hover:bg-indigo-600/30 transition-colors"
                        >
                          Upgrade →
                        </a>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            )}
          </Section>

          {/* Notifications */}
          <Section
            title="Notifications"
            description="Control when and how you receive alerts."
            icon={Bell}
          >
            <div className="mb-3 inline-flex items-center gap-1.5 rounded-full border border-amber-500/30 bg-amber-500/10 px-2.5 py-1 text-[11px] font-medium text-amber-400">
              Coming soon — preferences are not yet persisted
            </div>
            <div>
              <Toggle
                label="Analysis complete"
                description="Get notified when a project analysis finishes."
                defaultOn
              />
              <Toggle
                label="Weekly digest"
                description="A summary of your project activity every Monday."
                defaultOn
              />
              <Toggle
                label="Product updates"
                description="New features, improvements, and changelogs."
              />
              <Toggle
                label="Marketing emails"
                description="Tips, case studies, and promotional offers."
              />
            </div>
          </Section>

          {/* Security */}
          <Section title="Security" description="Protect your account." icon={Shield}>
            <div className="space-y-3">
              <div className="flex items-center justify-between rounded-xl border border-white/[0.06] bg-white/[0.02] p-4">
                <div>
                  <p className="text-sm text-white/80">Password</p>
                  <p className="text-xs text-white/35">Managed by your authentication provider</p>
                </div>
                <span className="flex items-center gap-1.5 rounded-lg border border-emerald-500/30 bg-emerald-500/10 px-3 py-1.5 text-xs text-emerald-400">
                  <Check className="h-3 w-3" />
                  Secure
                </span>
              </div>
              <div className="flex items-center justify-between rounded-xl border border-white/[0.06] bg-white/[0.02] p-4">
                <div>
                  <p className="text-sm text-white/80">Two-factor authentication</p>
                  <p className="text-xs text-white/35">
                    Configure 2FA through your authentication provider
                  </p>
                </div>
              </div>
              {user && (
                <div className="rounded-xl border border-white/[0.06] bg-white/[0.02] p-4">
                  <p className="text-xs text-white/40 font-mono">
                    User ID: <span className="text-white/25">{user.id}</span>
                  </p>
                </div>
              )}
            </div>
          </Section>

          {/* Data & Privacy */}
          <Section
            title="Data & Privacy"
            description="GDPR rights — export or delete all data we hold about you."
            icon={Download}
          >
            <div className="space-y-3">
              <div className="flex items-start justify-between gap-4 rounded-xl border border-white/[0.06] bg-white/[0.02] p-4">
                <div>
                  <p className="text-sm text-white/80">Export your data</p>
                  <p className="text-xs text-white/35">
                    Download a JSON file of all your projects, analyses, and account information.
                  </p>
                </div>
                <button
                  onClick={handleExport}
                  disabled={exporting}
                  className="flex-shrink-0 flex items-center gap-1.5 rounded-lg border border-white/10 px-3 py-1.5 text-xs font-medium text-white/60 hover:text-white hover:border-white/20 transition-colors disabled:opacity-50"
                >
                  {exporting ? (
                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  ) : (
                    <Download className="h-3.5 w-3.5" />
                  )}
                  {exporting ? "Exporting…" : "Export"}
                </button>
              </div>
            </div>
          </Section>

          {/* Danger zone */}
          <div className="rounded-2xl border border-red-500/20 bg-red-500/5 p-6">
            <h2 className="mb-1 text-sm font-semibold text-red-400">Danger zone</h2>
            <p className="mb-4 text-xs text-white/40">
              Irreversible actions — proceed with caution.
            </p>

            {deleteConfirm ? (
              <div className="space-y-3">
                <div className="flex items-start gap-2 rounded-lg border border-red-500/30 bg-red-500/10 p-3">
                  <AlertTriangle className="h-4 w-4 text-red-400 flex-shrink-0 mt-0.5" />
                  <p className="text-xs text-red-300">
                    This will permanently delete your account, all projects, uploaded files, and analysis
                    results. This action <strong>cannot be undone</strong>.
                  </p>
                </div>
                <div className="flex items-center gap-2">
                  <button
                    onClick={handleDelete}
                    disabled={deleting}
                    className="flex items-center gap-1.5 rounded-lg bg-red-600 px-4 py-2 text-xs font-medium text-white hover:bg-red-500 transition-colors disabled:opacity-50"
                  >
                    {deleting && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
                    {deleting ? "Deleting…" : "Yes, delete my account"}
                  </button>
                  <button
                    onClick={() => setDeleteConfirm(false)}
                    disabled={deleting}
                    className="rounded-lg border border-white/10 px-4 py-2 text-xs font-medium text-white/50 hover:text-white transition-colors"
                  >
                    Cancel
                  </button>
                </div>
              </div>
            ) : (
              <button
                onClick={handleDelete}
                className="rounded-lg border border-red-500/30 px-4 py-2 text-xs font-medium text-red-400 hover:bg-red-500/10 transition-colors"
              >
                Delete account
              </button>
            )}
          </div>

        </div>
      </div>
    </AppShell>
  );
}
