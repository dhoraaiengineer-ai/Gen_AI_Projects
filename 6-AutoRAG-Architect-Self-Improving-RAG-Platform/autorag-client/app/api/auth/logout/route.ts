import { createServerClient } from "@supabase/ssr";
import { cookies } from "next/headers";
import { NextResponse } from "next/server";

type CookieToSet = { name: string; value: string; options?: Record<string, unknown> };

/**
 * POST /api/auth/logout
 * Clears both Supabase session and the demo bypass cookie, then
 * redirects to /login. Works for real users and demo sessions alike.
 */
export async function POST() {
  const cookieStore = await cookies();

  const supabase = createServerClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    {
      cookies: {
        getAll() {
          return cookieStore.getAll();
        },
        setAll(cookiesToSet: CookieToSet[]) {
          cookiesToSet.forEach(({ name, value, options }) =>
            cookieStore.set(name, value, options),
          );
        },
      },
    },
  );

  // Sign out the Supabase session (no-op if already logged out).
  await supabase.auth.signOut();

  // Clear the demo bypass cookie.
  const response = NextResponse.redirect(
    new URL("/login", process.env.NEXT_PUBLIC_APP_URL ?? "http://localhost:3000"),
  );
  response.cookies.set("autorag-demo-session", "", {
    path: "/",
    maxAge: 0,
    httpOnly: false,
    sameSite: "lax",
  });

  return response;
}
