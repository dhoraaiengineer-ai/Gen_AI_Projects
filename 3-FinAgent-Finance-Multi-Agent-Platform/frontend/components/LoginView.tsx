"use client";
// View: sign-in form (Supabase e-mail + password), or a role picker in mock mode.
import { useState } from "react";

import { API_MODE } from "@/lib/config";
import { label } from "@/lib/format";
import { MOCK_USERS } from "@/lib/mock";

const DEMO_USERS = [
  "risk@northwind.example.com",
  "pm@northwind.example.com",
  "compliance@northwind.example.com",
  "analyst@northwind.example.com",
  "fraud@northwind.example.com",
  "viewer@northwind.example.com",
  "admin@northwind.example.com",
  "pm@contoso.example.com",
];

interface Props {
  onSignIn: (email: string, password: string) => void;
  onMock: (role: string) => void;
  error: string | null;
}

export function LoginView({ onSignIn, onMock, error }: Props) {
  const [email, setEmail] = useState(DEMO_USERS[0]);
  const [password, setPassword] = useState("");
  return (
    <main className="flex min-h-screen items-center justify-center px-4">
      <div className="w-full max-w-sm space-y-4 rounded-2xl border border-white/10 bg-panel p-8 shadow-xl">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">FinAgent</h1>
          <p className="mt-1 text-sm text-muted">Finance Multi-Agent Intelligence Platform</p>
        </div>
        {API_MODE === "mock" ? (
          <div className="space-y-2">
            <p className="text-sm text-muted">Mock mode — pick a role (no backend needed):</p>
            {MOCK_USERS.map((u) => (
              <button key={u.role} onClick={() => onMock(u.role)}
                className="w-full rounded-lg border border-white/10 px-3 py-2 text-left text-sm hover:border-accent">
                {label(u.role)} <span className="text-muted">· {u.email}</span>
              </button>
            ))}
          </div>
        ) : (
          <form
            className="space-y-4"
            onSubmit={(e) => {
              e.preventDefault();
              onSignIn(email, password);
            }}
          >
            <label className="block text-sm">
              <span className="text-muted">Email</span>
              <input list="demo-users" value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="username"
                className="mt-1 w-full rounded-lg border border-white/10 bg-ink px-3 py-2 outline-none focus:border-accent" />
              <datalist id="demo-users">
                {DEMO_USERS.map((u) => <option key={u} value={u} />)}
              </datalist>
            </label>
            <label className="block text-sm">
              <span className="text-muted">Password</span>
              <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="current-password"
                className="mt-1 w-full rounded-lg border border-white/10 bg-ink px-3 py-2 outline-none focus:border-accent" />
            </label>
            {error && <p role="alert" className="text-sm text-bad">{error}</p>}
            <button type="submit" className="w-full rounded-lg bg-accent px-3 py-2 font-medium text-ink hover:opacity-90">
              Sign in
            </button>
            <p className="text-xs text-muted">Demo users share the password in <code>DEMO_USER_PASSWORD</code> (.env).</p>
          </form>
        )}
        <p className="text-xs text-muted">Decision support only — not investment advice.</p>
      </div>
    </main>
  );
}
