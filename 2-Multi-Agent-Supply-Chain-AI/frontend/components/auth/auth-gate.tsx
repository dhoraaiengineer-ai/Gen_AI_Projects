"use client";

import { useState } from "react";
import { Loader2, LockKeyhole, ShieldCheck } from "lucide-react";
import { useAuth } from "@/lib/auth";
import { APP_NAME } from "@/lib/constants";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/primitives";

function SignIn({ error: initialError }: { error?: string }) {
  const { signIn } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | undefined>(initialError);

  return (
    <div className="flex min-h-dvh items-center justify-center bg-sidebar px-4">
      <div className="w-full max-w-sm">
        <div className="mb-8 flex items-center justify-center gap-2.5">
          <span className="flex size-10 items-center justify-center rounded-xl bg-gradient-to-br from-[#3c6fe0] to-[#1f4fa3] text-lg text-white shadow-raised" aria-hidden>
            ◈
          </span>
          <span className="text-xl font-semibold tracking-tight text-white">{APP_NAME}</span>
        </div>
        <form
          className="rounded-xl border bg-card p-6 shadow-raised"
          onSubmit={async (e) => {
            e.preventDefault();
            setBusy(true);
            setError((await signIn(email.trim(), password)) ?? undefined);
            setBusy(false);
          }}
        >
          <h1 className="text-lg font-semibold tracking-tight">Sign in</h1>
          <p className="mt-1 text-[13px] text-muted-foreground">Your AI supply-chain command center.</p>
          <div className="mt-5 space-y-4">
            <div className="space-y-1.5">
              <Label htmlFor="email">Email</Label>
              <Input id="email" type="email" autoComplete="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="password">Password</Label>
              <Input id="password" type="password" autoComplete="current-password" required value={password} onChange={(e) => setPassword(e.target.value)} />
            </div>
            {error && (
              <p role="alert" className="rounded-md bg-critical/10 px-3 py-2 text-[13px] text-critical">
                {error}
              </p>
            )}
            <Button type="submit" className="w-full" disabled={busy}>
              {busy ? <Loader2 className="animate-spin" /> : <LockKeyhole />} Sign in
            </Button>
          </div>
          <p className="mt-5 flex items-start gap-2 border-t pt-4 text-[12px] text-muted-foreground">
            <ShieldCheck className="mt-0.5 size-3.5 shrink-0" aria-hidden />
            Access is role-based: viewer, analyst, approver or admin. Roles are assigned by an administrator.
          </p>
        </form>
      </div>
    </div>
  );
}

/** Renders the app only for signed-in users in API mode; demo mode passes straight through. */
export function AuthGate({ children }: { children: React.ReactNode }) {
  const { state } = useAuth();
  if (state.status === "demo" || state.status === "signed_in") return <>{children}</>;
  if (state.status === "loading") {
    return (
      <div className="flex min-h-dvh items-center justify-center bg-sidebar" role="status" aria-label="Loading">
        <Loader2 className="size-6 animate-spin text-sidebar-muted" />
      </div>
    );
  }
  return <SignIn error={state.status === "unavailable" ? state.error : state.error} />;
}
