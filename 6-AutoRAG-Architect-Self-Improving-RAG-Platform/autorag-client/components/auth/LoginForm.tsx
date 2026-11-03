"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";

import { createSupabaseClient } from "@/lib/supabase";
import { AUTH_ERROR_MESSAGES, mapSupabaseAuthError } from "@/types/auth";
import type { AuthErrorCode } from "@/types/auth";

export function LoginForm() {
  const router = useRouter();
  const DEMO_EMAIL = "demo@autorag.dev";
  const DEMO_PASSWORD = "AutoRAG@2026";

  const [email, setEmail] = useState(DEMO_EMAIL);
  const [password, setPassword] = useState(DEMO_PASSWORD);
  const [rememberMe, setRememberMe] = useState(false);
  const [loading, setLoading] = useState(false);
  const [errorCode, setErrorCode] = useState<AuthErrorCode | null>(null);

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setLoading(true);
    setErrorCode(null);

    // Demo bypass — skips Supabase for team testing
    if (email.trim() === DEMO_EMAIL && password === DEMO_PASSWORD) {
      document.cookie = "autorag-demo-session=1; path=/; max-age=86400";
      router.push("/dashboard");
      return;
    }

    const supabase = createSupabaseClient();
    const { error } = await supabase.auth.signInWithPassword({ email, password });

    if (error) {
      setErrorCode(mapSupabaseAuthError(error.message));
      setLoading(false);
      return;
    }

    router.push("/dashboard");
    router.refresh();
  }

  const canSubmit = email.trim().length > 0 && password.length > 0 && !loading;

  return (
    <form onSubmit={handleSubmit} noValidate className="space-y-5">
      {/* Header */}
      <div className="space-y-1">
        <h2 className="text-xl font-semibold text-slate-50">Welcome back</h2>
        <p className="text-sm text-text-3">
          Sign in to access your RAG pipelines and evaluation runs.
        </p>
      </div>

      {/* Demo credentials hint — subtle, pre-filled notice */}
      <div className="flex items-start gap-3 rounded-lg border border-amber-500/20 bg-amber-500/5 px-3.5 py-3">
        <svg
          className="mt-0.5 h-4 w-4 shrink-0 text-amber-400"
          viewBox="0 0 20 20"
          fill="currentColor"
          aria-hidden="true"
        >
          <path
            fillRule="evenodd"
            d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a.75.75 0 000 1.5h.253a.25.25 0 01.244.304l-.459 2.066A1.75 1.75 0 0010.747 15H11a.75.75 0 000-1.5h-.253a.25.25 0 01-.244-.304l.459-2.066A1.75 1.75 0 009.253 9H9z"
            clipRule="evenodd"
          />
        </svg>
        <div className="text-xs text-text-3 leading-relaxed">
          <span className="font-semibold text-amber-300">Demo session active.</span> Credentials are
          pre-filled — click <span className="font-medium text-text-2">Sign in</span> to enter the
          platform. After login you will land on the Dashboard with access to all 9 agents, pipelines,
          and evaluation tools.
        </div>
      </div>

      {errorCode && (
        <p
          role="alert"
          className="rounded-lg border border-status-error/30 bg-status-error/10 px-4 py-3 text-sm text-red-400"
        >
          {AUTH_ERROR_MESSAGES[errorCode]}
        </p>
      )}

      {/* Email */}
      <div className="space-y-1.5">
        <label htmlFor="login-email" className="block text-xs font-medium text-text-3 uppercase tracking-wide">
          Email address
        </label>
        <input
          id="login-email"
          type="email"
          autoComplete="email"
          required
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder="you@company.com"
          className="w-full rounded-lg border border-line bg-bg-input px-4 py-2.5 text-sm text-slate-50 placeholder-slate-600 outline-none transition-colors focus:border-accent-border focus:ring-1 focus:ring-accent-border"
        />
      </div>

      {/* Password */}
      <div className="space-y-1.5">
        <div className="flex items-center justify-between">
          <label htmlFor="login-password" className="block text-xs font-medium text-text-3 uppercase tracking-wide">
            Password
          </label>
          <Link
            href="/forgot-password"
            className="text-xs text-accent-light transition-colors hover:text-accent"
          >
            Forgot password?
          </Link>
        </div>
        <input
          id="login-password"
          type="password"
          autoComplete="current-password"
          required
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          placeholder="••••••••"
          className="w-full rounded-lg border border-line bg-bg-input px-4 py-2.5 text-sm text-slate-50 placeholder-slate-600 outline-none transition-colors focus:border-accent-border focus:ring-1 focus:ring-accent-border"
        />
      </div>

      {/* Remember me */}
      <label className="flex cursor-pointer items-center gap-2 text-sm text-text-3">
        <input
          type="checkbox"
          checked={rememberMe}
          onChange={(e) => setRememberMe(e.target.checked)}
          className="h-4 w-4 rounded border-line bg-bg-input accent-accent"
        />
        Keep me signed in for 24 hours
      </label>

      {/* Submit */}
      <button
        type="submit"
        disabled={!canSubmit}
        className="w-full rounded-lg bg-accent px-4 py-2.5 text-sm font-semibold text-foreground transition-colors hover:bg-accent-light disabled:cursor-not-allowed disabled:opacity-50"
      >
        {loading ? "Signing in…" : "Sign in to AutoRAG"}
      </button>

      {/* What happens next — short outcome guidance */}
      <div className="rounded-lg bg-bg-card-hover px-3.5 py-3 text-xs text-text-3 space-y-1">
        <p className="font-medium text-text-3">After signing in you can:</p>
        <ul className="space-y-0.5 list-none">
          <li className="flex items-center gap-2"><span className="text-brand">&#x2022;</span> Upload documents and run the ingestion pipeline</li>
          <li className="flex items-center gap-2"><span className="text-brand">&#x2022;</span> Evaluate RAG quality with the Unified Score gate (target &ge;0.85)</li>
          <li className="flex items-center gap-2"><span className="text-brand">&#x2022;</span> Monitor agent runs, latency, and cost in real-time</li>
          <li className="flex items-center gap-2"><span className="text-brand">&#x2022;</span> Deploy pipelines with automatic rollback protection</li>
        </ul>
      </div>

      <p className="text-center text-sm text-text-3">
        Don&apos;t have an account?{" "}
        <Link href="/signup" className="text-accent-light transition-colors hover:text-accent">
          Request access
        </Link>
      </p>
    </form>
  );
}
