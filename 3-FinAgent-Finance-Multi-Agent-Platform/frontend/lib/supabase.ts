// Model: Supabase browser client (publishable key only — safe in the browser).
import { createClient, type SupabaseClient } from "@supabase/supabase-js";

let client: SupabaseClient | null = null;

export function supabase(): SupabaseClient {
  if (!client) {
    const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
    const key = process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY;
    if (!url || !key) {
      throw new Error("Supabase is not configured: set SUPABASE_URL and SUPABASE_PUBLISHABLE_KEY in the root .env");
    }
    client = createClient(url, key, { auth: { persistSession: true, autoRefreshToken: true } });
  }
  return client;
}
