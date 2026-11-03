"use client";

import Image from "next/image";
import { Github, CheckCircle2 } from "lucide-react";

const TRUST_INDICATORS = [
  "Enterprise Ready",
  "Production Deployments",
  "Hybrid Retrieval",
  "AI Evaluation",
  "Audit & Governance",
];

export function Footer() {
  return (
    <footer className="bg-slate-900 text-slate-300 pt-16 pb-12 border-t border-slate-800">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="grid grid-cols-1 md:grid-cols-6 gap-8 mb-10">
          {/* Brand Col */}
          <div className="md:col-span-2">
            <div className="flex items-center gap-2.5 mb-4">
              <Image
                src="/AutoRAG_logo.png"
                alt="AutoRAG Architect"
                width={220}
                height={220}
                className="w-10 h-10 rounded-xl object-cover object-[50%_28%] shadow-sm ring-1 ring-slate-700"
              />
              <div>
                <div className="font-extrabold text-xl text-white tracking-tight">
                  <span className="text-orange-500">AutoRAG</span> Architect
                </div>
                <div className="text-[10px] font-mono text-indigo-400 uppercase tracking-widest">
                  Autonomous RAG Platform
                </div>
              </div>
            </div>

            <p className="text-xs text-slate-400 leading-relaxed font-medium max-w-sm mb-6">
              Enterprise platform for building, evaluating, optimizing, and deploying Retrieval-Augmented
              Generation (RAG) systems with autonomous orchestration, continuous evaluation, and
              production-grade governance.
            </p>

            <div className="flex items-center gap-3">
              <a
                href="https://github.com"
                target="_blank"
                rel="noreferrer"
                className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 text-[11px] font-bold transition-colors"
              >
                <Github className="w-3.5 h-3.5" />
                <span>Open Source</span>
              </a>
            </div>
          </div>

          {/* Product */}
          <div>
            <h4 className="text-xs font-bold uppercase tracking-wider text-white mb-4">Product</h4>
            <ul className="space-y-2.5 text-xs text-slate-400 font-medium">
              <li><a href="#features" className="hover:text-white transition-colors">Features</a></li>
              <li><a href="#architecture" className="hover:text-white transition-colors">Architecture</a></li>
              <li><a href="#pricing" className="hover:text-white transition-colors">Pricing</a></li>
              <li><a href="#docs" className="hover:text-white transition-colors">Documentation</a></li>
              <li><a href="#pricing" className="hover:text-white transition-colors">Request Demo</a></li>
            </ul>
          </div>

          {/* Company */}
          <div>
            <h4 className="text-xs font-bold uppercase tracking-wider text-white mb-4">Company</h4>
            <ul className="space-y-2.5 text-xs text-slate-400 font-medium">
              <li><a href="#about" className="hover:text-white transition-colors">About</a></li>
              <li><a href="#" className="hover:text-white transition-colors">Careers</a></li>
              <li><a href="#contact" className="hover:text-white transition-colors">Contact</a></li>
            </ul>
          </div>

          {/* Resources */}
          <div>
            <h4 className="text-xs font-bold uppercase tracking-wider text-white mb-4">Resources</h4>
            <ul className="space-y-2.5 text-xs text-slate-400 font-medium">
              <li><a href="#docs" className="hover:text-white transition-colors">API Reference</a></li>
              <li><a href="#docs" className="hover:text-white transition-colors">Tutorials</a></li>
              <li><a href="#" className="hover:text-white transition-colors">Release Notes</a></li>
            </ul>
          </div>

          {/* Legal */}
          <div>
            <h4 className="text-xs font-bold uppercase tracking-wider text-white mb-4">Legal</h4>
            <ul className="space-y-2.5 text-xs text-slate-400 font-medium">
              <li><a href="#" className="hover:text-white transition-colors">Privacy</a></li>
              <li><a href="#" className="hover:text-white transition-colors">Terms</a></li>
              <li><a href="#security" className="hover:text-white transition-colors">Security</a></li>
              <li><a href="#security" className="hover:text-white transition-colors">Responsible AI</a></li>
            </ul>
          </div>
        </div>

        {/* Trust indicators */}
        <div className="flex flex-wrap items-center gap-x-5 gap-y-2 pb-10 mb-10 border-b border-slate-800">
          {TRUST_INDICATORS.map((t) => (
            <div key={t} className="flex items-center gap-1.5 text-[11px] font-semibold text-slate-400">
              <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500 shrink-0" />
              <span>{t}</span>
            </div>
          ))}
        </div>

        {/* Bottom Stack Row */}
        <div className="flex flex-col md:flex-row items-center justify-between gap-4 text-xs text-slate-500 font-mono pt-4">
          <div className="text-center md:text-left space-y-1">
            <div className="text-slate-400 font-sans font-semibold">
              Designed &amp; Engineered by{" "}
              <a
                href="https://saffronyx.in"
                target="_blank"
                rel="noreferrer"
                className="text-orange-500 hover:text-orange-400 transition-colors"
              >
                Saffronyx - AI Engineering Company
              </a>
            </div>
            <div className="text-slate-500">📍 Bengaluru, Karnataka, India</div>
            <div>© 2026 Saffronyx. All rights reserved. · Version 4.0</div>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <span className="text-slate-400">Powered By:</span>
            <span className="px-2 py-0.5 rounded bg-slate-800 text-slate-300">Next.js 15</span>
            <span className="px-2 py-0.5 rounded bg-slate-800 text-slate-300">FastAPI</span>
            <span className="px-2 py-0.5 rounded bg-slate-800 text-slate-300">LangGraph</span>
            <span className="px-2 py-0.5 rounded bg-slate-800 text-slate-300">Supabase</span>
            <span className="px-2 py-0.5 rounded bg-slate-800 text-slate-300">MLflow</span>
            <span className="px-2 py-0.5 rounded bg-slate-800 text-slate-300">AWS ECS</span>
          </div>
        </div>
      </div>
    </footer>
  );
}
