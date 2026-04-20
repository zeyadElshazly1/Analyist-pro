"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  FolderOpen,
  BarChart2,
  CreditCard,
  Settings,
  Sparkles,
  LogOut,
  Users,
} from "lucide-react";
import { logout } from "@/lib/api";
import { useUser } from "@/lib/user-context";

const BASE_LINKS = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/projects", label: "Workspaces", icon: FolderOpen },
  { href: "/reports", label: "Reports", icon: BarChart2 },
  { href: "/billing", label: "Billing", icon: CreditCard },
  { href: "/settings", label: "Settings", icon: Settings },
];

const TEAM_LINK = { href: "/team", label: "Team", icon: Users };

export function AppSidebar() {
  const pathname = usePathname();
  const { user } = useUser();

  const initial = user?.email?.[0]?.toUpperCase() ?? "U";
  const planLabel = user?.plan
    ? user.plan.charAt(0).toUpperCase() + user.plan.slice(1) + " plan"
    : "Free plan";

  return (
    <aside className="hidden w-60 flex-shrink-0 flex-col border-r border-white/[0.05] bg-[#09090f] lg:flex">

      {/* Logo */}
      <div className="flex h-14 items-center gap-2.5 border-b border-white/[0.05] px-5">
        <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-gradient-to-br from-indigo-500 to-violet-600 shadow-md shadow-indigo-500/30">
          <BarChart2 className="h-3.5 w-3.5 text-white" strokeWidth={2.5} />
        </div>
        <Link href="/dashboard" className="text-sm font-bold tracking-tight text-white">
          Analyst<span className="text-indigo-400">Pro</span>
        </Link>
      </div>

      {/* Nav */}
      <nav className="flex-1 space-y-0.5 px-3 py-4">
        {[...BASE_LINKS, ...(user?.plan === "team" ? [TEAM_LINK] : [])].map(({ href, label, icon: Icon }) => {
          const active =
            pathname === href ||
            (href !== "/dashboard" && pathname.startsWith(href));
          return (
            <Link
              key={href}
              href={href}
              className={`flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm transition-all ${
                active
                  ? "bg-indigo-600/15 text-indigo-400 font-medium"
                  : "text-white/45 hover:bg-white/[0.04] hover:text-white/80"
              }`}
            >
              <Icon className="h-4 w-4 flex-shrink-0" strokeWidth={1.75} />
              {label}
              {active && (
                <span className="ml-auto h-1.5 w-1.5 rounded-full bg-indigo-400" />
              )}
            </Link>
          );
        })}
      </nav>

      {/* Upgrade nudge */}
      {(!user || user.plan === "free") && (
        <div className="mx-3 mb-3 rounded-xl border border-indigo-500/20 bg-indigo-600/8 p-3">
          <div className="mb-1.5 flex items-center gap-2">
            <Sparkles className="h-3.5 w-3.5 text-indigo-400" />
            <p className="text-xs font-semibold text-indigo-300">Free plan</p>
          </div>
          <p className="mb-2.5 text-[11px] leading-relaxed text-white/40">
            Upgrade to Consultant for unlimited workspaces and AI reports.
          </p>
          <Link
            href="/billing"
            className="block rounded-lg bg-indigo-600 px-3 py-1.5 text-center text-[11px] font-semibold text-white transition-colors hover:bg-indigo-500"
          >
            Upgrade to Consultant
          </Link>
        </div>
      )}

      {/* User */}
      <div className="border-t border-white/[0.05] p-3">
        <div className="flex items-center gap-2.5 rounded-lg px-2 py-2">
          <div className="flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-indigo-500 to-violet-600 text-xs font-bold text-white">
            {initial}
          </div>
          <div className="min-w-0 flex-1">
            <p className="truncate text-xs font-medium text-white/80">
              {user?.email ?? "…"}
            </p>
            <p className="truncate text-[11px] text-white/35">{planLabel}</p>
          </div>
          <button
            onClick={logout}
            title="Log out"
            className="ml-1 flex-shrink-0 rounded p-1 text-white/30 transition-colors hover:text-white/70"
          >
            <LogOut className="h-3.5 w-3.5" />
          </button>
        </div>
      </div>
    </aside>
  );
}
