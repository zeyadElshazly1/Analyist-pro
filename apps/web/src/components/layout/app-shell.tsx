"use client";

import { useState, useEffect, ReactNode } from "react";
import { AppSidebar } from "@/components/layout/app-sidebar";

export function AppShell({ children }: { children: ReactNode }) {
  const [collapsed, setCollapsed] = useState(false);

  useEffect(() => {
    const stored = localStorage.getItem("sidebar-collapsed");
    if (stored === "true") setCollapsed(true);
  }, []);

  const toggle = () => {
    setCollapsed((prev) => {
      const next = !prev;
      localStorage.setItem("sidebar-collapsed", String(next));
      return next;
    });
  };

  return (
    <div className="flex min-h-screen bg-[#0a0a0b] text-white">
      <AppSidebar collapsed={collapsed} onToggle={toggle} />
      <main className="min-w-0 flex-1">{children}</main>
    </div>
  );
}
