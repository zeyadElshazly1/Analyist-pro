import { ReactNode } from "react";
import { AppSidebar } from "@/components/layout/app-sidebar";

export function AppShell({ children }: { children: ReactNode }) {
  return (
    <div className="flex min-h-screen bg-[#0a0a0b] text-white">
      <AppSidebar />
      <main className="flex-1">{children}</main>
    </div>
  );
}