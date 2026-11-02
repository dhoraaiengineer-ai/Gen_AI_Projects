import { useState, type FormEvent } from "react";
import { useLocation, useNavigate } from "react-router-dom";

import { ApiError } from "../api/envelope";
import { useAuth } from "../auth/AuthContext";

const HOME: Record<string, string> = {
  vehicle_owner: "/chat",
  service_advisor: "/advisor",
  technician: "/tech",
  warranty_admin: "/warranty",
  admin: "/admin",
};

export function Login() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const me = await login(email, password);
      const from = (location.state as { from?: string } | null)?.from;
      navigate(from ?? HOME[me.role] ?? "/", { replace: true });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Sign-in failed. Please try again.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section aria-labelledby="page-title" className="mx-auto max-w-sm p-6">
      <h1 id="page-title" className="text-2xl font-semibold">
        Sign in
      </h1>
      <p className="mt-1 text-sm text-slate-600 dark:text-slate-400">DEMO accounts only — synthetic data.</p>
      <form onSubmit={submit} className="mt-4 space-y-3">
        <label className="block text-sm font-medium">
          Email
          <input
            type="email"
            required
            autoComplete="username"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="mt-1 block min-h-tap w-full rounded border border-slate-300 px-3 dark:border-slate-600 dark:bg-slate-900"
          />
        </label>
        <label className="block text-sm font-medium">
          Password
          <input
            type="password"
            required
            autoComplete="current-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="mt-1 block min-h-tap w-full rounded border border-slate-300 px-3 dark:border-slate-600 dark:bg-slate-900"
          />
        </label>
        {error && (
          <p role="alert" className="text-sm text-red-700">
            {error}
          </p>
        )}
        <button
          type="submit"
          disabled={busy}
          className="min-h-tap w-full rounded bg-blue-700 px-4 font-medium text-white hover:bg-blue-800 disabled:opacity-60"
        >
          {busy ? "Signing in…" : "Sign in"}
        </button>
      </form>
    </section>
  );
}
