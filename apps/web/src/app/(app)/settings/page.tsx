"use client";

import { useState } from "react";
import { AppShell } from "@/components/layout/app-shell";
import { User, Key, Bell, Shield, Copy, Check, RefreshCw } from "lucide-react";

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

function Field({ label, value, editable = false }: { label: string; value: string; editable?: boolean }) {
  const [val, setVal] = useState(value);
  return (
    <div className="space-y-1.5">
      <label className="block text-xs font-medium text-white/50">{label}</label>
      {editable ? (
        <input
          value={val}
          onChange={(e) => setVal(e.target.value)}
          className="w-full rounded-xl border border-white/10 bg-black/30 px-3 py-2 text-sm text-white placeholder:text-white/25 focus:border-indigo-500/50 focus:outline-none focus:ring-1 focus:ring-indigo-500/30 transition-colors"
        />
      ) : (
        <div className="rounded-xl border border-white/[0.06] bg-white/[0.02] px-3 py-2 text-sm text-white/50">
          {value}
        </div>
      )}
    </div>
  );
}

function ApiKeyRow({ label, keyVal }: { label: string; keyVal: string }) {
  const [copied, setCopied] = useState(false);
  const [revealed, setRevealed] = useState(false);

  function handleCopy() {
    navigator.clipboard.writeText(keyVal).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  }

  return (
    <div className="rounded-xl border border-white/[0.06] bg-white/[0.02] p-4">
      <div className="mb-2 flex items-center justify-between">
        <span className="text-xs font-medium text-white/60">{label}</span>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setRevealed((r) => !r)}
            className="text-[11px] text-white/30 hover:text-white/60 transition-colors"
          >
            {revealed ? "Hide" : "Reveal"}
          </button>
          <button
            onClick={handleCopy}
            className="flex items-center gap-1 rounded-md px-2 py-1 text-[11px] text-white/40 hover:bg-white/[0.05] hover:text-white/70 transition-colors"
          >
            {copied ? <Check className="h-3 w-3 text-emerald-400" /> : <Copy className="h-3 w-3" />}
            {copied ? "Copied" : "Copy"}
          </button>
        </div>
      </div>
      <code className="text-xs text-white/40 font-mono">
        {revealed ? keyVal : keyVal.slice(0, 12) + "••••••••••••••••••••••••"}
      </code>
    </div>
  );
}

function Toggle({ label, description, defaultOn = false }: { label: string; description: string; defaultOn?: boolean }) {
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
  const [saved, setSaved] = useState(false);

  function handleSave() {
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  }

  return (
    <AppShell>
      <div className="min-h-full bg-[#080810]">
        <div className="mx-auto max-w-2xl space-y-6 p-6 lg:p-10">

          {/* Header */}
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-2xl font-bold tracking-tight text-white">Settings</h1>
              <p className="mt-1 text-sm text-white/40">Manage your account and preferences.</p>
            </div>
            <button
              onClick={handleSave}
              className={`flex items-center gap-2 rounded-xl px-4 py-2 text-sm font-semibold transition-all ${
                saved
                  ? "bg-emerald-600/20 text-emerald-400 border border-emerald-500/30"
                  : "bg-indigo-600 text-white hover:bg-indigo-500"
              }`}
            >
              {saved ? <Check className="h-4 w-4" /> : null}
              {saved ? "Saved!" : "Save changes"}
            </button>
          </div>

          {/* Profile */}
          <Section title="Profile" description="Your public identity on AnalystPro." icon={User}>
            <div className="space-y-4">
              <div className="flex items-center gap-4">
                <div className="flex h-14 w-14 flex-shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-indigo-500 to-violet-600 text-lg font-bold text-white shadow-lg shadow-indigo-500/20">
                  U
                </div>
                <button className="rounded-lg border border-white/10 px-3 py-1.5 text-xs text-white/50 hover:border-white/20 hover:text-white/70 transition-colors">
                  Change avatar
                </button>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <Field label="Display name" value="User" editable />
                <Field label="Email" value="user@example.com" editable />
              </div>
              <Field label="Plan" value="Free" />
            </div>
          </Section>

          {/* API Keys */}
          <Section title="API Keys" description="Use these keys to access the AnalystPro API programmatically." icon={Key}>
            <div className="space-y-3">
              <ApiKeyRow label="Production key" keyVal="ap_live_0000000000000000000000000000000000000000" />
              <ApiKeyRow label="Test key" keyVal="ap_test_0000000000000000000000000000000000000000" />
              <button className="flex items-center gap-2 rounded-lg border border-white/10 px-3 py-2 text-xs text-white/40 hover:border-white/20 hover:text-white/70 transition-colors">
                <RefreshCw className="h-3.5 w-3.5" />
                Regenerate keys
              </button>
              <p className="text-[11px] text-white/20">
                Keys rotate 90 days after generation. Treat them like passwords.
              </p>
            </div>
          </Section>

          {/* Notifications */}
          <Section title="Notifications" description="Control when and how you receive alerts." icon={Bell}>
            <div>
              <Toggle label="Analysis complete" description="Get notified when a project analysis finishes." defaultOn />
              <Toggle label="Weekly digest" description="A summary of your project activity every Monday." defaultOn />
              <Toggle label="Product updates" description="New features, improvements, and changelogs." />
              <Toggle label="Marketing emails" description="Tips, case studies, and promotional offers." />
            </div>
          </Section>

          {/* Security */}
          <Section title="Security" description="Protect your account." icon={Shield}>
            <div className="space-y-3">
              <div className="flex items-center justify-between rounded-xl border border-white/[0.06] bg-white/[0.02] p-4">
                <div>
                  <p className="text-sm text-white/80">Password</p>
                  <p className="text-xs text-white/35">Last changed never</p>
                </div>
                <button className="rounded-lg border border-white/10 px-3 py-1.5 text-xs text-white/50 hover:border-white/20 hover:text-white/70 transition-colors">
                  Change
                </button>
              </div>
              <div className="flex items-center justify-between rounded-xl border border-white/[0.06] bg-white/[0.02] p-4">
                <div>
                  <p className="text-sm text-white/80">Two-factor authentication</p>
                  <p className="text-xs text-amber-400/80">Not enabled</p>
                </div>
                <button className="rounded-lg border border-indigo-500/30 bg-indigo-600/10 px-3 py-1.5 text-xs font-medium text-indigo-300 hover:bg-indigo-600/20 transition-colors">
                  Enable 2FA
                </button>
              </div>
            </div>
          </Section>
        </div>
      </div>
    </AppShell>
  );
}
