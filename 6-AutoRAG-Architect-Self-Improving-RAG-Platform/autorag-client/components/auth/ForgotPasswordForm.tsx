"use client";

import { useState } from "react";
import Link from "next/link";

import { createSupabaseClient } from "@/lib/supabase";

export function ForgotPasswordForm() {
  const [email, setEmail] = useState("");
  const [loading, setLoading] = useState(false);
  const [sent, setSent] = useState(false);

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setLoading(true);

    const supabase = createSupabaseClient();

    // Always reset the password regardless of whether the email exists.
    // Security: never reveal whether an email is registered (no user enumeration).
    await supabase.auth.resetPasswordForEmail(email, {
      redirectTo: `${window.location.origin}/auth/callback`,
    });

    setLoading(false);
    setSent(true);
  }

  if (sent) {
    return (
      <div className="space-y-4 text-center">
        <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-accent/10 text-accent-light text-2xl">
          ✉
        </div>
        <h2 className="text-xl font-semibold text-slate-50">Check your email</h2>
        <p className="text-sm text-text-3">
          If <span className="text-foreground">{email}</span> is registered, a password reset link
          has been sent. Check your inbox.
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

  return (
    <form onSubmit={handleSubmit} noValidate className="space-y-5">
      <div>
        <h2 className="text-2xl font-semibold text-slate-50">Reset password</h2>
        <p className="mt-1 text-sm text-text-3">
          Enter your email and we&apos;ll send a reset link.
        </p>
      </div>

      <div className="space-y-1">
        <label htmlFor="forgot-email" className="block text-sm text-text-3">
          Email
        </label>
        <input
          id="forgot-email"
          type="email"
          autoComplete="email"
          required
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder="you@company.com"
          className="w-full rounded-lg border border-line bg-bg-input px-4 py-2.5 text-sm text-slate-50 placeholder-slate-600 outline-none transition-colors focus:border-accent-border focus:ring-1 focus:ring-accent-border"
        />
      </div>

      <button
        type="submit"
        disabled={loading || email.trim().length === 0}
        className="w-full rounded-lg bg-accent px-4 py-2.5 text-sm font-semibold text-foreground transition-colors hover:bg-accent-light disabled:cursor-not-allowed disabled:opacity-50"
      >
        {loading ? "Sending…" : "Send reset link"}
      </button>

      <p className="text-center text-sm text-text-3">
        Remember your password?{" "}
        <Link href="/login" className="text-accent-light transition-colors hover:text-accent">
          Sign in
        </Link>
      </p>
    </form>
  );
}
