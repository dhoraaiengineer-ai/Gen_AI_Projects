"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import Image from "next/image";
import {
  Mail,
  Lock,
  Eye,
  EyeOff,
  FlaskConical,
  ArrowLeft,
  Bot,
  Network,
  Layers,
  ShieldCheck,
  CheckCircle2,
  Database,
  Sparkles,
  Cpu,
  FileCheck,
  Award,
  Activity,
  ShieldAlert,
  Zap,
  GitBranch,
} from "lucide-react";

/* ─── Demo-mode authentication (deliberate, documented — 20-Jul-2026) ───
 * This page intentionally does NOT call Supabase auth. It's a fixed-string
 * comparison against DEMO_EMAIL/DEMO_PASS below, setting a plain
 * `autorag-demo-session` cookie on match, which `middleware.ts` explicitly
 * honors as a demo-team bypass. Typing a real, Supabase-registered
 * email/password here will NOT authenticate — only these two exact values
 * work.
 *
 * A fully real, tested `LoginForm.tsx` component exists
 * (`components/auth/LoginForm.tsx`, calls `supabase.auth.signInWithPassword`)
 * and is NOT used here — Signup and Forgot Password both wire to real
 * Supabase (`SignupForm`, `ForgotPasswordForm`), making this page the one
 * intentional exception.
 *
 * 25-Jul-2026: redesigned to match the public landing page's light theme
 * (bg-light-mesh, glass-panel-light) instead of the prior dark, animated
 * layout — the auth logic below is unchanged. A left info panel was
 * reintroduced (static, no animation, real facts only) after the
 * card-only version read as too sparse.
 */
const DEMO_EMAIL = "demo@autorag.dev";
const DEMO_PASS = "AutoRAG@2026";

// Real facts, matching lib/marketing-data.ts's STATS_DATA — no invented numbers.
const STATS = [
  { value: "9", label: "Autonomous Agents", icon: Bot },
  { value: "46", label: "REST Endpoints", icon: Network },
  { value: "4", label: "Retrieval Stages", icon: Layers },
  { value: "0.85", label: "Auto-Deploy Gate", icon: ShieldCheck },
];

const NINE_AGENTS = [
  { label: "Ingestion", icon: Database },
  { label: "Query Rewriter", icon: Sparkles },
  { label: "Builder", icon: Cpu },
  { label: "Context Compressor", icon: FileCheck },
  { label: "Evaluator", icon: Award },
  { label: "Observer", icon: Activity },
  { label: "Diagnoser", icon: ShieldAlert },
  { label: "Improver", icon: Zap },
  { label: "Deployer", icon: GitBranch },
];

const TRUST_INDICATORS = [
  "PII masked before every LLM call",
  "Faithfulness < 0.5 hard-blocks deployment",
  "INSERT-only audit trail",
];

/* ─── Checkbox — matches spec ("Checkbox: Remember me"), not a toggle ── */
function Checkbox({ checked, onChange, label }: { checked: boolean; onChange: () => void; label: string }) {
  return (
    <label className="flex cursor-pointer items-center gap-2 select-none">
      <button
        type="button"
        role="checkbox"
        aria-checked={checked}
        onClick={onChange}
        className={[
          "flex h-4 w-4 shrink-0 items-center justify-center rounded border transition-colors duration-150",
          checked ? "border-amber-500 bg-amber-500" : "border-slate-300 bg-white hover:border-slate-400",
        ].join(" ")}
      >
        {checked && (
          <svg className="h-2.5 w-2.5 text-white" viewBox="0 0 12 12" fill="none" aria-hidden="true">
            <path d="M2 6l2.5 2.5L10 3" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        )}
      </button>
      <span className="text-[12px] text-slate-600">{label}</span>
    </label>
  );
}

export default function LoginPage() {
  const router = useRouter();

  const [email, setEmail] = useState(DEMO_EMAIL);
  const [password, setPassword] = useState(DEMO_PASS);
  const [showPass, setShowPass] = useState(false);
  const [remember, setRemember] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function submit(useEmail: string, usePass: string) {
    setError(null);
    setLoading(true);
    await new Promise((r) => setTimeout(r, 500));
    if (useEmail === DEMO_EMAIL && usePass === DEMO_PASS) {
      document.cookie = "autorag-demo-session=1; path=/; max-age=86400";
      router.push("/dashboard");
      return;
    }
    setError("Invalid credentials. Demo credentials are pre-filled above.");
    setLoading(false);
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    await submit(email, password);
  }

  async function handleDemoLogin() {
    setEmail(DEMO_EMAIL);
    setPassword(DEMO_PASS);
    await submit(DEMO_EMAIL, DEMO_PASS);
  }

  return (
    <div className="relative flex min-h-screen w-full items-center justify-center bg-light-mesh px-4 py-10 lg:px-12">
      <div className="absolute inset-0 bg-grid-light opacity-60 pointer-events-none" />

      <Link
        href="/"
        className="absolute left-6 top-6 z-10 flex items-center gap-1.5 text-[13px] font-semibold text-slate-500 transition-colors hover:text-slate-800"
      >
        <ArrowLeft className="h-3.5 w-3.5" aria-hidden="true" />
        Back to AutoRAG Architect
      </Link>

      <div className="relative z-10 grid w-full max-w-5xl grid-cols-1 items-center gap-10 lg:grid-cols-[1.1fr_minmax(0,420px)] lg:gap-16">
        {/* ── LEFT — static info panel, real facts only, no animation ── */}
        <div className="hidden lg:block">
          <Image
            src="/AutoRAG_logo.png"
            alt="AutoRAG Architect"
            width={220}
            height={220}
            className="h-16 w-16 rounded-2xl object-cover object-[50%_28%] shadow-sm ring-1 ring-slate-200"
          />
          <span className="mt-3 block text-xl font-extrabold tracking-tight">
            <span className="text-orange-500">AutoRAG</span> <span className="text-slate-900">Architect</span>
          </span>

          <h1 className="mt-6 text-3xl xl:text-4xl font-extrabold leading-[1.15] text-slate-900">
            Your Pipelines, <br />
            <span className="text-gradient-brand">Watched Around the Clock</span>
          </h1>
          <p className="mt-3 max-w-md text-[14px] leading-relaxed text-slate-600">
            Sign in to view live Unified Scores, deployment history, and the Observer/Diagnoser/Improver
            loop working on your pipelines right now.
          </p>

          {/* Stats */}
          <div className="mt-8 grid grid-cols-4 gap-4">
            {STATS.map((s) => (
              <div key={s.label} className="rounded-xl border border-slate-200/80 bg-white/70 p-3">
                <s.icon className="h-4 w-4 text-amber-600" aria-hidden="true" />
                <p className="mt-1.5 text-xl font-bold text-slate-900">{s.value}</p>
                <p className="mt-0.5 text-[10px] leading-tight text-slate-500">{s.label}</p>
              </div>
            ))}
          </div>

          {/* 9 agents */}
          <div className="mt-6">
            <p className="mb-2 text-[10px] font-semibold uppercase tracking-[0.12em] text-slate-400">
              9 specialized agents
            </p>
            <div className="flex flex-wrap gap-1.5">
              {NINE_AGENTS.map((a) => (
                <span
                  key={a.label}
                  className="flex items-center gap-1.5 rounded-full border border-amber-200/70 bg-amber-50/80 px-2.5 py-1 text-[11px] font-medium text-amber-700"
                >
                  <a.icon className="h-3 w-3" aria-hidden="true" />
                  {a.label}
                </span>
              ))}
            </div>
          </div>

          {/* Trust indicators */}
          <div className="mt-6 space-y-1.5 border-t border-slate-200/80 pt-4">
            {TRUST_INDICATORS.map((t) => (
              <div key={t} className="flex items-center gap-2 text-[12px] font-medium text-slate-600">
                <CheckCircle2 className="h-3.5 w-3.5 shrink-0 text-emerald-600" aria-hidden="true" />
                <span>{t}</span>
              </div>
            ))}
          </div>
        </div>

        {/* ── RIGHT — login card ── */}
        <div className="glass-panel-light w-full overflow-hidden rounded-2xl border border-slate-200/90 shadow-xl">
          <div
            className="h-1 w-full"
            style={{ background: "linear-gradient(90deg,#F97316,#F59E0B)" }}
            aria-hidden="true"
          />
          <div className="p-8">
            {/* Mobile-only logo (left panel hidden below lg) */}
            <Link href="/" className="mb-6 flex items-center gap-2.5 lg:hidden">
              <Image
                src="/AutoRAG_logo.png"
                alt=""
                width={220}
                height={220}
                className="h-9 w-9 rounded-lg object-cover object-[50%_28%] shadow-sm ring-1 ring-slate-200"
              />
              <span className="text-lg font-extrabold tracking-tight">
                <span className="text-orange-500">AutoRAG</span> <span className="text-slate-900">Architect</span>
              </span>
            </Link>

            <h2 className="text-2xl font-bold text-slate-900">Welcome back</h2>
            <p className="mt-1 text-[13px] text-slate-500">Sign in to continue to your AutoRAG workspace.</p>

            <form onSubmit={(e) => void handleSubmit(e)} className="mt-6 space-y-4">
              {/* Email */}
              <div className="space-y-1">
                <label htmlFor="email" className="block text-[11px] font-semibold uppercase tracking-widest text-slate-500">
                  Email
                </label>
                <div className="relative">
                  <Mail className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" aria-hidden="true" />
                  <input
                    id="email"
                    type="email"
                    autoComplete="email"
                    required
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="you@company.com"
                    className="w-full rounded-lg border border-slate-200 bg-white py-2.5 pl-9 pr-3 text-sm text-slate-900 placeholder-slate-400 outline-none transition-all duration-200 focus:border-amber-500 focus:ring-2 focus:ring-amber-500/20"
                  />
                </div>
              </div>

              {/* Password */}
              <div className="space-y-1">
                <div className="flex items-center justify-between">
                  <label htmlFor="password" className="block text-[11px] font-semibold uppercase tracking-widest text-slate-500">
                    Password
                  </label>
                  <button type="button" className="text-[11px] text-amber-600 transition-colors hover:text-amber-700">
                    Forgot?
                  </button>
                </div>
                <div className="relative">
                  <Lock className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" aria-hidden="true" />
                  <input
                    id="password"
                    type={showPass ? "text" : "password"}
                    autoComplete="current-password"
                    required
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    className="w-full rounded-lg border border-slate-200 bg-white py-2.5 pl-9 pr-10 text-sm text-slate-900 placeholder-slate-400 outline-none transition-all duration-200 focus:border-amber-500 focus:ring-2 focus:ring-amber-500/20"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPass((v) => !v)}
                    aria-label={showPass ? "Hide password" : "Show password"}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 transition-colors hover:text-slate-600"
                  >
                    {showPass ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                  </button>
                </div>
              </div>

              <Checkbox checked={remember} onChange={() => setRemember((v) => !v)} label="Remember me" />

              {error && (
                <p className="rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-[12px] text-rose-700" role="alert">
                  {error}
                </p>
              )}

              <button
                type="submit"
                disabled={loading}
                className="w-full rounded-lg bg-gradient-to-r from-orange-500 to-amber-500 py-2.5 text-sm font-bold text-white shadow-md shadow-amber-500/20 transition-all duration-150 hover:from-orange-600 hover:to-amber-600 hover:shadow-lg hover:shadow-amber-500/30 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {loading ? (
                  <span className="flex items-center justify-center gap-2">
                    <svg className="h-4 w-4 animate-spin" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                    </svg>
                    Signing in&hellip;
                  </span>
                ) : (
                  "Sign In"
                )}
              </button>
            </form>

            <div className="my-5 flex items-center gap-3">
              <div className="h-px flex-1 bg-slate-200" />
              <span className="text-[11px] text-slate-400">OR</span>
              <div className="h-px flex-1 bg-slate-200" />
            </div>

            <button
              type="button"
              disabled={loading}
              onClick={() => void handleDemoLogin()}
              className="flex w-full items-center justify-center gap-2 rounded-lg border border-slate-200 bg-white py-2.5 text-[13px] font-medium text-slate-700 transition-colors duration-150 hover:bg-slate-50 disabled:opacity-60"
            >
              <FlaskConical className="h-4 w-4 text-slate-500" aria-hidden="true" />
              Launch Demo Workspace
            </button>

            <p className="mt-5 text-center text-[13px] text-slate-500">
              Don&apos;t have an account?{" "}
              <a href="#" className="font-medium text-amber-600 transition-colors hover:text-amber-700">
                Request Access
              </a>
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
