"use client";

import { useState } from "react";
import Link from "next/link";

import { createSupabaseClient } from "@/lib/supabase";
import { AUTH_ERROR_MESSAGES, mapSupabaseAuthError } from "@/types/auth";
import type { AuthErrorCode, SignupFormData } from "@/types/auth";

const ROLE_LABELS: Record<SignupFormData["role"], string> = {
  engineer: "Retrieval Engineer",
  lead: "Pipeline Lead",
  viewer: "Viewer",
};

export function SignupForm() {
  const [form, setForm] = useState<SignupFormData>({
    fullName: "",
    email: "",
    password: "",
    organisation: "",
    role: "engineer",
  });
  const [loading, setLoading] = useState(false);
  const [errorCode, setErrorCode] = useState<AuthErrorCode | null>(null);
  const [success, setSuccess] = useState(false);

  function update<K extends keyof SignupFormData>(field: K, value: SignupFormData[K]) {
    setForm((prev) => ({ ...prev, [field]: value }));
  }

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();

    if (form.password.length < 8) {
      setErrorCode("unknown");
      return;
    }

    setLoading(true);
    setErrorCode(null);

    const supabase = createSupabaseClient();
    const { error } = await supabase.auth.signUp({
      email: form.email,
      password: form.password,
      options: {
        data: {
          full_name: form.fullName,
          organisation: form.organisation,
          role: form.role,
        },
      },
    });

    setLoading(false);

    if (error) {
      setErrorCode(mapSupabaseAuthError(error.message));
      return;
    }

    setSuccess(true);
  }

  if (success) {
    return (
      <div className="space-y-4 text-center">
        <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-status-success/10 text-status-success text-2xl">
          ✓
        </div>
        <h2 className="text-xl font-semibold text-slate-50">Check your email</h2>
        <p className="text-sm text-text-3">
          We&apos;ve sent a confirmation link to{" "}
          <span className="text-foreground">{form.email}</span>. Click it to activate your account.
        </p>
        <Link
          href="/login"
          className="block text-sm text-accent-light transition-colors hover:text-accent"
        >
          Back to sign in
        </Link>
      </div>
    );
  }

  const canSubmit =
    form.fullName.trim().length > 0 &&
    form.email.trim().length > 0 &&
    form.password.length >= 8 &&
    form.organisation.trim().length > 0 &&
    !loading;

  return (
    <form onSubmit={handleSubmit} noValidate className="space-y-5">
      <div>
        <h2 className="text-2xl font-semibold text-slate-50">Create account</h2>
        <p className="mt-1 text-sm text-text-3">Join your team on AutoRAG Architect.</p>
      </div>

      {errorCode && (
        <p
          role="alert"
          className="rounded-lg border border-status-error/30 bg-status-error/10 px-4 py-3 text-sm text-red-400"
        >
          {errorCode === "unknown"
            ? "Password must be at least 8 characters."
            : AUTH_ERROR_MESSAGES[errorCode]}
        </p>
      )}

      <div className="space-y-1">
        <label htmlFor="signup-name" className="block text-sm text-text-3">
          Full name
        </label>
        <input
          id="signup-name"
          type="text"
          autoComplete="name"
          required
          value={form.fullName}
          onChange={(e) => update("fullName", e.target.value)}
          placeholder="Jane Smith"
          className="w-full rounded-lg border border-line bg-bg-input px-4 py-2.5 text-sm text-slate-50 placeholder-slate-600 outline-none transition-colors focus:border-accent-border focus:ring-1 focus:ring-accent-border"
        />
      </div>

      <div className="space-y-1">
        <label htmlFor="signup-email" className="block text-sm text-text-3">
          Email
        </label>
        <input
          id="signup-email"
          type="email"
          autoComplete="email"
          required
          value={form.email}
          onChange={(e) => update("email", e.target.value)}
          placeholder="you@company.com"
          className="w-full rounded-lg border border-line bg-bg-input px-4 py-2.5 text-sm text-slate-50 placeholder-slate-600 outline-none transition-colors focus:border-accent-border focus:ring-1 focus:ring-accent-border"
        />
      </div>

      <div className="space-y-1">
        <label htmlFor="signup-password" className="block text-sm text-text-3">
          Password{" "}
          <span className="text-text-3">(min 8 characters)</span>
        </label>
        <input
          id="signup-password"
          type="password"
          autoComplete="new-password"
          required
          minLength={8}
          value={form.password}
          onChange={(e) => update("password", e.target.value)}
          placeholder="••••••••"
          className="w-full rounded-lg border border-line bg-bg-input px-4 py-2.5 text-sm text-slate-50 placeholder-slate-600 outline-none transition-colors focus:border-accent-border focus:ring-1 focus:ring-accent-border"
        />
      </div>

      <div className="space-y-1">
        <label htmlFor="signup-org" className="block text-sm text-text-3">
          Organisation
        </label>
        <input
          id="signup-org"
          type="text"
          required
          value={form.organisation}
          onChange={(e) => update("organisation", e.target.value)}
          placeholder="Acme Corp"
          className="w-full rounded-lg border border-line bg-bg-input px-4 py-2.5 text-sm text-slate-50 placeholder-slate-600 outline-none transition-colors focus:border-accent-border focus:ring-1 focus:ring-accent-border"
        />
      </div>

      <div className="space-y-1">
        <label htmlFor="signup-role" className="block text-sm text-text-3">
          Role
        </label>
        <select
          id="signup-role"
          value={form.role}
          onChange={(e) => update("role", e.target.value as SignupFormData["role"])}
          className="w-full rounded-lg border border-line bg-bg-input px-4 py-2.5 text-sm text-slate-50 outline-none transition-colors focus:border-accent-border focus:ring-1 focus:ring-accent-border"
        >
          {(Object.entries(ROLE_LABELS) as [SignupFormData["role"], string][]).map(
            ([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ),
          )}
        </select>
      </div>

      <button
        type="submit"
        disabled={!canSubmit}
        className="w-full rounded-lg bg-accent px-4 py-2.5 text-sm font-semibold text-foreground transition-colors hover:bg-accent-light disabled:cursor-not-allowed disabled:opacity-50"
      >
        {loading ? "Creating account…" : "Create account"}
      </button>

      <p className="text-center text-sm text-text-3">
        Already have an account?{" "}
        <Link href="/login" className="text-accent-light transition-colors hover:text-accent">
          Sign in
        </Link>
      </p>
    </form>
  );
}
