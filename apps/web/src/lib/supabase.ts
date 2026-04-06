import { createClient, type SupabaseClient } from "@supabase/supabase-js";

// Lazy singleton — only initialised on first property access.
// This prevents a module-load crash when .env.local is missing or when
// Next.js serves a stale build before env vars are inlined.
let _client: SupabaseClient | null = null;

function getClient(): SupabaseClient {
  if (!_client) {
    const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
    const key = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
    if (!url || !key) {
      throw new Error(
        "Missing NEXT_PUBLIC_SUPABASE_URL or NEXT_PUBLIC_SUPABASE_ANON_KEY.\n" +
          "Make sure apps/web/.env.local exists, then restart the dev server with:\n" +
          "  rm -rf .next && npm run dev"
      );
    }
    _client = createClient(url, key);
  }
  return _client;
}

export const supabase = new Proxy({} as SupabaseClient, {
  get(_, prop: string | symbol) {
    return (getClient() as unknown as Record<string | symbol, unknown>)[prop];
  },
});
