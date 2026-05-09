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
  PanelLeftClose,
  PanelLeftOpen,
} from "lucide-react";
import { logout } from "@/lib/api";
import { useUser } from "@/lib/user-context";
import { PLAN_NAMES, PLAN_LABELS, normalizePlan } from "@/lib/plans";

interface AppSidebarProps {
  collapsed: boolean;
  onToggle: () => void;
}

const BASE_LINKS = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/projects", label: "Workspaces", icon: FolderOpen },
  { href: "/reports", label: "Reports", icon: BarChart2 },
  { href: "/billing", label: "Billing", icon: CreditCard },
  { href: "/settings", label: "Settings", icon: Settings },
];

const TEAM_LINK = { href: "/team", label: "Team", icon: Users };

export function AppSidebar({ collapsed, onToggle }: AppSidebarProps) {
  const pathname = usePathname();
  const { user } = useUser();

  const initial = user?.email?.[0]?.toUpperCase() ?? "U";
  const canonicalPlan = normalizePlan(user?.plan);
  const planLabel = `${PLAN_LABELS[canonicalPlan]} plan`;
  const links = [
    ...BASE_LINKS,
    ...(canonicalPlan === PLAN_NAMES.STUDIO ? [TEAM_LINK] : []),
  ];

  return (
    <aside
      className={`hidden flex-shrink-0 flex-col border-r border-white/[0.05] bg-[#09090f] lg:flex transition-[width] duration-200 overflow-hidden ${
        collapsed ? "w-16" : "w-60"
      }`}
    >
      {/* Header: logo + toggle */}
      <div className="flex h-14 flex-shrink-0 items-center border-b border-white/[0.05] px-3">
        {!collapsed && (
          <div className="flex flex-1 items-center gap-2.5 overflow-hidden pl-2">
            <div className="flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-lg bg-gradient-to-br from-indigo-500 to-violet-600 shadow-md shadow-indigo-500/30">
              <BarChart2 className="h-3.5 w-3.5 text-white" strokeWidth={2.5} />
            </div>
            <Link
              href="/dashboard"
              className="truncate text-sm font-bold tracking-tight text-white"
            >
              Analyst<span className="text-indigo-400">Pro</span>
            </Link>
          </div>
        )}
        <button
          onClick={onToggle}
          title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
          className={`flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-md text-white/30 transition-colors hover:bg-white/[0.04] hover:text-white/70 ${
            collapsed ? "mx-auto" : "ml-auto"
          }`}
        >
          {collapsed ? (
            <PanelLeftOpen className="h-4 w-4" strokeWidth={1.75} />
          ) : (
            <PanelLeftClose className="h-4 w-4" strokeWidth={1.75} />
          )}
        </button>
      </div>

      {/* Nav */}
      <nav className={`flex-1 space-y-0.5 py-4 ${collapsed ? "px-2" : "px-3"}`}>
        {links.map(({ href, label, icon: Icon }) => {
          const active =
            pathname === href ||
            (href !== "/dashboard" && pathname.startsWith(href));
          return (
            <Link
              key={href}
              href={href}
              title={collapsed ? label : undefined}
              className={`flex items-center rounded-lg py-2.5 text-sm transition-all ${
                collapsed ? "justify-center px-2" : "gap-3 px-3"
              } ${
                active
                  ? "bg-indigo-600/15 text-indigo-400 font-medium"
                  : "text-white/45 hover:bg-white/[0.04] hover:text-white/80"
              }`}
            >
              <Icon className="h-4 w-4 flex-shrink-0" strokeWidth={1.75} />
              {!collapsed && (
                <>
                  {label}
                  {active && (
                    <span className="ml-auto h-1.5 w-1.5 rounded-full bg-indigo-400" />
                  )}
                </>
              )}
            </Link>
          );
        })}
      </nav>

      {/* Upgrade nudge — hidden when collapsed */}
      {!collapsed && (!user || canonicalPlan === PLAN_NAMES.FREE) && (
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

      {/* User footer */}
      <div className="border-t border-white/[0.05] p-3">
        {collapsed ? (
          <div className="flex flex-col items-center gap-2 py-1">
            <div
              title={user?.email ?? "Account"}
              className="flex h-7 w-7 cursor-default items-center justify-center rounded-full bg-gradient-to-br from-indigo-500 to-violet-600 text-xs font-bold text-white"
            >
              {initial}
            </div>
            <button
              onClick={logout}
              title="Log out"
              className="flex h-6 w-6 items-center justify-center rounded p-1 text-white/30 transition-colors hover:text-white/70"
            >
              <LogOut className="h-3.5 w-3.5" />
            </button>
          </div>
        ) : (
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
        )}
      </div>
    </aside>
  );
}
