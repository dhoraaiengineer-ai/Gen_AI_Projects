import { createBrowserClient } from "@supabase/ssr";

/**
 * Returns a Supabase browser client for use in 'use client' components.
 * Called inside components — not a singleton — so cookies are always fresh.
 * Uses @supabase/ssr (replaces deprecated @supabase/auth-helpers-nextjs).
 */
export function createSupabaseClient() {
  return createBrowserClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
  );
}
