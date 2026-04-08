import { UserProvider } from "@/lib/user-context";
import type { ReactNode } from "react";

/**
 * Layout for all authenticated (app) routes.
 * Fetches the current user once here so every child page and component
 * can consume useUser() without independent getMe() calls.
 */
export default function AppLayout({ children }: { children: ReactNode }) {
  return <UserProvider>{children}</UserProvider>;
}
