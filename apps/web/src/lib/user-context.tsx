"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";
import * as Sentry from "@sentry/nextjs";
import { getMe } from "@/lib/api";

// ── Types ─────────────────────────────────────────────────────────────────────

export type NotificationPrefs = {
  analysis_complete: boolean;
  weekly_digest: boolean;
  product_updates: boolean;
  marketing_emails: boolean;
};

export type UserData = {
  id: string;
  email: string;
  plan: string;
  notification_prefs: NotificationPrefs;
  created_at: string;
};

type UserContextValue = {
  /** null while loading or when unauthenticated */
  user: UserData | null;
  /** true only during the initial fetch */
  loading: boolean;
  /** call to force a fresh getMe() — e.g. after plan upgrade */
  refetch: () => Promise<void>;
};

// ── Context ───────────────────────────────────────────────────────────────────

const UserContext = createContext<UserContextValue | null>(null);

// ── Provider ──────────────────────────────────────────────────────────────────

export function UserProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<UserData | null>(null);
  const [loading, setLoading] = useState(true);

  const fetchUser = useCallback(async () => {
    try {
      const data = await getMe();
      setUser(data);
      Sentry.setUser({ id: data.id, email: data.email });
    } catch {
      // Unauthenticated or network error — leave user as null
      setUser(null);
      Sentry.setUser(null);
    }
  }, []);

  // Single fetch on mount — all children share this one result
  useEffect(() => {
    fetchUser().finally(() => setLoading(false));
  }, [fetchUser]);

  const refetch = useCallback(async () => {
    await fetchUser();
  }, [fetchUser]);

  return (
    <UserContext.Provider value={{ user, loading, refetch }}>
      {children}
    </UserContext.Provider>
  );
}

// ── Consumer hook ─────────────────────────────────────────────────────────────

/**
 * Returns the current authenticated user, a loading flag, and a refetch fn.
 * Must be used inside <UserProvider> (i.e. within the (app) layout).
 */
export function useUser(): UserContextValue {
  const ctx = useContext(UserContext);
  if (!ctx) {
    throw new Error("useUser() must be used inside <UserProvider>");
  }
  return ctx;
}
