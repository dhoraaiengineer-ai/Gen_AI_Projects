import { createServerClient } from "@supabase/ssr";
import { NextResponse, type NextRequest } from "next/server";

/**
 * Auth guard middleware (E-9).
 * Protects all app routes. Unauthenticated users hitting a protected path
 * are redirected to /login. Authenticated users hitting an auth path are
 * redirected to /dashboard.
 *
 * NOTE: Next.js route groups (auth) are URL-transparent.
 * app/(auth)/login/page.tsx → serves at /login (NOT /(auth)/login).
 */

type CookieToSet = {
  name: string;
  value: string;
  options?: Record<string, unknown>;
};

const PROTECTED_PATHS = [
  "/dashboard",
  "/configurator",
  "/retrieve",
  "/evaluation",
  "/deploy",
  "/audit",
  "/settings",
  "/observe",
  "/diagnose",
  "/improve",
  "/experiments",
  "/documents",
  "/knowledge",
  "/health",
  "/pipelines",
];

const AUTH_PATHS = ["/login", "/signup", "/forgot-password"];

export async function middleware(request: NextRequest) {
  let supabaseResponse = NextResponse.next({ request });

  const supabase = createServerClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    {
      cookies: {
        getAll() {
          return request.cookies.getAll();
        },
        setAll(cookiesToSet: CookieToSet[]) {
          cookiesToSet.forEach(({ name, value }: CookieToSet) => request.cookies.set(name, value));
          supabaseResponse = NextResponse.next({ request });
          cookiesToSet.forEach(({ name, value, options }: CookieToSet) =>
            supabaseResponse.cookies.set(name, value, options),
          );
        },
      },
    },
  );

  // getUser() is the only safe way to verify the session server-side.
  const {
    data: { user },
  } = await supabase.auth.getUser();

  // Demo team bypass — cookie set directly by app/(auth)/login/page.tsx's
  // own demo-mode auth flow (deliberate, documented there; not the real
  // components/auth/LoginForm.tsx, which is unused — see that page's
  // top-of-file comment and .claude/docs/roadmap/VERSION_5_ROADMAP.md for
  // the planned consolidation).
  const isDemoSession = request.cookies.get("autorag-demo-session")?.value === "1";
  const isAuthed = !!user || isDemoSession;

  const { pathname } = request.nextUrl;

  const isProtected = PROTECTED_PATHS.some((p) => pathname.startsWith(p));
  const isAuthPage = AUTH_PATHS.some((p) => pathname.startsWith(p));

  if (!isAuthed && isProtected) {
    const loginUrl = request.nextUrl.clone();
    loginUrl.pathname = "/login";
    return NextResponse.redirect(loginUrl);
  }

  if (isAuthed && isAuthPage) {
    const dashboardUrl = request.nextUrl.clone();
    dashboardUrl.pathname = "/dashboard";
    return NextResponse.redirect(dashboardUrl);
  }

  return supabaseResponse;
}

export const config = {
  matcher: [
    // Match everything except Next.js internals and static files.
    "/((?!_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp)$).*)",
  ],
};
