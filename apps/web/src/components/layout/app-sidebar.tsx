"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  FolderOpen,
  BarChart2,
  CreditCard,
  Settings,
} from "lucide-react";

const links = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/projects", label: "Projects", icon: FolderOpen },
  { href: "/reports", label: "Reports", icon: BarChart2 },
  { href: "/billing", label: "Billing", icon: CreditCard },
  { href: "/settings", label: "Settings", icon: Settings },
];

export function AppSidebar() {
  const pathname = usePathname();

  return (
    <aside className="hidden w-56 flex-shrink-0 flex-col border-r border-white/[0.06] bg-[#0d0d0f] lg:flex">
      <div className="flex h-14 items-center gap-2.5 px-5">
        <div className="flex h-6 w-6 items-center justify-center rounded-md bg-indigo-600">
          <span className="text-[10px] font-bold text-white">A</span>
        </div>
        <Link href="/dashboard" className="text-sm font-semibold text-white">
          Analyst Pro
        </Link>
      </div>

      <nav className="flex-1 space-y-0.5 px-2 py-3">
        {links.map(({ href, label, icon: Icon }) => {
          const active =
            pathname === href ||
            (href !== "/dashboard" && pathname.startsWith(href));
          return (
            <Link
              key={href}
              href={href}
              className={`flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition-colors ${
                active
                  ? "bg-indigo-600/15 text-indigo-400 font-medium"
                  : "text-white/50 hover:bg-white/5 hover:text-white"
              }`}
            >
              <Icon className="h-4 w-4 flex-shrink-0" strokeWidth={1.75} />
              {label}
            </Link>
          );
        })}
      </nav>

      <div className="border-t border-white/[0.06] p-3">
        <div className="flex items-center gap-2.5 rounded-lg px-2 py-2">
          <div className="flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-full bg-white/10 text-xs font-semibold text-white">
            U
          </div>
          <div className="min-w-0">
            <p className="truncate text-xs font-medium text-white/80">User</p>
            <p className="truncate text-[11px] text-white/35">Free plan</p>
          </div>
        </div>
      </div>
    </aside>
  );
}
