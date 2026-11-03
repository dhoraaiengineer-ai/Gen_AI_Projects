"use client";

import { useState } from "react";
import Link from "next/link";
import { X, CheckCircle2, Key, ArrowRight } from "lucide-react";

/* ─── SIGN IN MODAL ───
 * The other modals previously here (Solutions/Docs/About/Contact) were
 * replaced by real page sections (SolutionsSection, DocsSection,
 * AboutSection, ContactSection) — see app/(marketing)/page.tsx. Sign In
 * stays a modal since there's no dedicated page section for it. */
interface SignInModalProps {
  isOpen: boolean;
  onClose: () => void;
  onOpenSandbox: () => void;
}

export function SignInModal({ isOpen, onClose, onOpenSandbox }: SignInModalProps) {
  const [signedIn, setSignedIn] = useState(false);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/70 backdrop-blur-sm animate-fade-in-marketing">
      <div className="bg-white w-full max-w-md rounded-3xl shadow-2xl border border-slate-200 overflow-hidden flex flex-col">
        <div className="p-6 border-b border-slate-200 flex items-center justify-between bg-slate-50">
          <div>
            <h3 className="text-xl font-extrabold text-slate-900">Sign In to AutoRAG</h3>
            <p className="text-xs text-slate-500 font-medium">Enterprise Single Sign-On &amp; Cloud Portal</p>
          </div>
          <button
            onClick={onClose}
            className="p-2 rounded-xl text-slate-400 hover:text-slate-700 hover:bg-slate-200/60 transition-colors cursor-pointer"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="p-6 space-y-4">
          {signedIn ? (
            <div className="py-6 text-center space-y-4">
              <div className="w-12 h-12 rounded-full bg-emerald-100 text-emerald-600 flex items-center justify-center mx-auto">
                <CheckCircle2 className="w-7 h-7" />
              </div>
              <h4 className="text-lg font-black text-slate-900">Authenticated Successfully</h4>
              <p className="text-xs text-slate-600 font-medium">Welcome back, Developer! Redirecting to Live Sandbox workspace...</p>
              <button
                onClick={() => {
                  onClose();
                  onOpenSandbox();
                }}
                className="px-6 py-2.5 rounded-xl bg-orange-500 text-white font-bold text-xs shadow-md hover:bg-orange-600 transition-colors cursor-pointer"
              >
                Launch Sandbox Workspace
              </button>
            </div>
          ) : (
            <>
              <button
                onClick={() => setSignedIn(true)}
                className="w-full py-2.5 px-4 rounded-xl border border-slate-300 hover:border-slate-400 bg-white text-slate-800 text-xs font-bold transition-all flex items-center justify-center gap-3 cursor-pointer shadow-xs"
              >
                <div className="w-4 h-4 rounded-full bg-slate-100 flex items-center justify-center font-bold text-[10px] text-blue-600">G</div>
                <span>Continue with Google Workspace</span>
              </button>

              <button
                onClick={() => setSignedIn(true)}
                className="w-full py-2.5 px-4 rounded-xl border border-slate-300 hover:border-slate-400 bg-slate-900 text-white text-xs font-bold transition-all flex items-center justify-center gap-3 cursor-pointer shadow-xs"
              >
                <Key className="w-4 h-4 text-amber-400" />
                <span>Single Sign-On (Okta / SAML 2.0)</span>
              </button>

              <div className="relative my-4">
                <div className="absolute inset-0 flex items-center"><div className="w-full border-t border-slate-200"></div></div>
                <div className="relative flex justify-center text-[10px] uppercase font-bold text-slate-400 bg-white px-2">Or email</div>
              </div>

              <div className="space-y-3">
                <input
                  type="email"
                  placeholder="developer@company.com"
                  className="w-full px-3.5 py-2 rounded-xl border border-slate-300 text-xs text-slate-900 focus:outline-none focus:border-indigo-600"
                />
                <button
                  onClick={() => setSignedIn(true)}
                  className="w-full py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white font-bold text-xs transition-colors cursor-pointer"
                >
                  Sign In
                </button>
              </div>

              <div className="pt-2 text-center">
                <Link
                  href="/login"
                  onClick={onClose}
                  className="inline-flex items-center gap-1 text-[11px] font-bold text-slate-500 hover:text-indigo-600 transition-colors"
                >
                  <span>Have a real AutoRAG account? Sign in at /login</span>
                  <ArrowRight className="w-3 h-3" />
                </Link>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
