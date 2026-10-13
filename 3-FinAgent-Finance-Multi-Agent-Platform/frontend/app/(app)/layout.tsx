"use client";
// Sign-in gate + application frame for every page in this route group (client-side: the
// Supabase session lives in the browser; see the Next.js 16 pitfall in CLAUDE.md).
import type { ReactNode } from "react";

import { AppShell } from "@/components/AppShell";
import { LoginView } from "@/components/LoginView";
import { ErrorBox } from "@/components/ui";
import { useSession } from "@/presenters/session";

export default function AppLayout({ children }: { children: ReactNode }) {
  const session = useSession();
  if (session.loading) return <main className="p-8 text-muted">Loading…</main>;
  if (!session.token) return <LoginView onSignIn={session.signIn} onMock={session.signInMock} error={session.error} />;
  if (!session.me) {
    return (
      <main className="mx-auto max-w-lg space-y-4 p-8">
        {session.error ? <ErrorBox message={session.error} /> : <p className="text-muted">Loading your profile…</p>}
        <button onClick={session.signOut} className="rounded-lg border border-white/10 px-3 py-1 text-sm">Sign out</button>
      </main>
    );
  }
  return (
    <AppShell me={session.me} onSignOut={session.signOut}>
      {children}
    </AppShell>
  );
}
