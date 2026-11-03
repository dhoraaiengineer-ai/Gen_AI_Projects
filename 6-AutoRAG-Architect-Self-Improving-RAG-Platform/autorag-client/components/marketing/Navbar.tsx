"use client";

import { useState, useEffect } from "react";
import Image from "next/image";
import {
  Sparkles,
  ArrowRight,
  Menu,
  X,
  User,
  ChevronDown,
  Search,
  FileText,
  Headphones,
  Building2,
  Stethoscope,
  Scale,
  Code2,
  Layers,
  ShieldCheck,
  Zap,
  CheckCircle2,
  Send,
  MessageSquare,
  Umbrella,
  Factory,
  Users,
} from "lucide-react";
import { SignInModal } from "./NavModals";

// Solutions dropdown labels are ported verbatim (explicit product decision, not
// derived from lib/marketing-data.ts) — Solutions is now a real page section
// (SolutionsSection, id="solutions") rather than a modal, so every item just
// scrolls there; the section's own tab state handles which industry shows.
// Kept in sync with SolutionsSection.tsx's 10 real industry entries.
const SOLUTIONS_ITEMS = [
  { label: "Enterprise Search", icon: <Search className="w-4 h-4 text-indigo-600" /> },
  { label: "Documentation QA", icon: <FileText className="w-4 h-4 text-blue-600" /> },
  { label: "Customer Support", icon: <Headphones className="w-4 h-4 text-emerald-600" /> },
  { label: "Financial Services", icon: <Building2 className="w-4 h-4 text-amber-600" /> },
  { label: "Healthcare & Clinical", icon: <Stethoscope className="w-4 h-4 text-rose-600" /> },
  { label: "Legal Tech", icon: <Scale className="w-4 h-4 text-purple-600" /> },
  { label: "Developer Copilot", icon: <Code2 className="w-4 h-4 text-cyan-600" /> },
  { label: "Insurance", icon: <Umbrella className="w-4 h-4 text-sky-600" /> },
  { label: "Manufacturing & Supply Chain", icon: <Factory className="w-4 h-4 text-orange-600" /> },
  { label: "HR & People Operations", icon: <Users className="w-4 h-4 text-pink-600" /> },
];

interface NavbarProps {
  onOpenSandbox: () => void;
  onOpenChat: () => void;
}

export function Navbar({ onOpenSandbox, onOpenChat }: NavbarProps) {
  const [scrolled, setScrolled] = useState(false);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [activeDropdown, setActiveDropdown] = useState<string | null>(null);
  const [activeSection, setActiveSection] = useState<string>("features");
  const [signInModalOpen, setSignInModalOpen] = useState(false);

  useEffect(() => {
    const handleScroll = () => {
      setScrolled(window.scrollY > 20);

      const sections = ["solutions", "architecture", "agents", "features", "analytics", "docs", "techstack", "security", "about", "pricing", "contact"];
      const scrollPosition = window.scrollY + 100;

      for (const section of sections) {
        const el = document.getElementById(section);
        if (el) {
          const top = el.offsetTop;
          const height = el.offsetHeight;
          if (scrollPosition >= top && scrollPosition < top + height) {
            setActiveSection(section);
            break;
          }
        }
      }
    };

    window.addEventListener("scroll", handleScroll);
    return () => window.removeEventListener("scroll", handleScroll);
  }, []);

  const scrollToSection = (id: string) => {
    setActiveDropdown(null);
    setMobileMenuOpen(false);
    const el = document.getElementById(id);
    if (el) el.scrollIntoView({ behavior: "smooth" });
  };

  return (
    <>
      <header
        className={`fixed top-0 left-0 right-0 z-40 transition-all duration-300 ${
          scrolled
            ? "bg-white/90 backdrop-blur-md border-b border-slate-200/90 shadow-sm py-2"
            : "bg-white/70 backdrop-blur-sm border-b border-slate-200/50 py-3"
        }`}
      >
        <div className="max-w-7xl mx-auto px-2 sm:px-3 lg:px-4">
          <div className="flex items-center justify-between">
            {/* Logo */}
            <a
              href="#"
              onClick={(e) => {
                e.preventDefault();
                window.scrollTo({ top: 0, behavior: "smooth" });
              }}
              className="flex items-center gap-2 group shrink-0"
            >
              <Image
                src="/AutoRAG_logo.png"
                alt=""
                width={220}
                height={220}
                className="w-12 h-12 rounded-xl object-cover object-[50%_28%] shadow-sm ring-1 ring-slate-200 group-hover:ring-orange-300 transition-all duration-300 group-hover:scale-105"
              />
              <div className="flex flex-col">
                <div className="flex items-center gap-1.5">
                  <span className="font-extrabold text-xl tracking-tight text-orange-500">AutoRAG</span>
                  <span className="font-extrabold text-xl tracking-tight text-slate-900">Architect</span>
                </div>
                <span className="text-[10px] font-bold text-slate-500 tracking-wider uppercase">
                  Autonomous RAG Platform
                </span>
              </div>
            </a>

            {/* Center Nav */}
            <nav className="hidden lg:flex items-center gap-2">
              {/* --- FEATURES DROPDOWN --- */}
              <div className="relative" onMouseEnter={() => setActiveDropdown("features")} onMouseLeave={() => setActiveDropdown(null)}>
                <button
                  onClick={() => scrollToSection("features")}
                  className={`px-3 py-2 text-sm font-bold transition-all duration-200 flex items-center gap-1 cursor-pointer relative group ${
                    ["features", "agents", "security"].includes(activeSection) ? "text-slate-900" : "text-slate-600 hover:text-slate-900"
                  }`}
                >
                  <span>Features</span>
                  <ChevronDown className={`w-4 h-4 text-slate-400 transition-transform duration-200 ${activeDropdown === "features" ? "rotate-180 text-orange-500" : ""}`} />
                  <span
                    className={`absolute bottom-0 left-3 right-3 h-1 bg-gradient-to-r from-orange-500 to-amber-500 transition-all duration-200 rounded-full ${
                      ["features", "agents", "security"].includes(activeSection) ? "opacity-100 scale-x-100" : "opacity-0 scale-x-0 group-hover:opacity-100 group-hover:scale-x-100"
                    }`}
                  />
                </button>

                {activeDropdown === "features" && (
                  <div className="absolute top-full left-0 w-64 pt-2 animate-fade-in-marketing">
                    <div className="bg-white rounded-2xl shadow-xl border border-slate-200/90 p-2 space-y-1">
                      <button
                        onClick={() => scrollToSection("agents")}
                        className="w-full text-left p-2.5 rounded-xl hover:bg-orange-50/80 transition-colors flex items-center gap-2.5 group cursor-pointer"
                      >
                        <div className="p-1.5 rounded-lg bg-orange-100 text-orange-600 group-hover:bg-orange-500 group-hover:text-white transition-colors">
                          <Zap className="w-3.5 h-3.5" />
                        </div>
                        <div>
                          <div className="text-xs font-extrabold text-slate-900 group-hover:text-orange-600 transition-colors">Autonomous Agents</div>
                          <div className="text-[10px] text-slate-500">9 specialized pipeline agents</div>
                        </div>
                      </button>

                      <button
                        onClick={() => scrollToSection("features")}
                        className="w-full text-left p-2.5 rounded-xl hover:bg-orange-50/80 transition-colors flex items-center gap-2.5 group cursor-pointer"
                      >
                        <div className="p-1.5 rounded-lg bg-indigo-100 text-indigo-600 group-hover:bg-indigo-600 group-hover:text-white transition-colors">
                          <Layers className="w-3.5 h-3.5" />
                        </div>
                        <div>
                          <div className="text-xs font-extrabold text-slate-900 group-hover:text-indigo-600 transition-colors">Hybrid Retrieval</div>
                          <div className="text-[10px] text-slate-500">BM25 + Multi-vector dense index</div>
                        </div>
                      </button>

                      <button
                        onClick={() => scrollToSection("evaluation")}
                        className="w-full text-left p-2.5 rounded-xl hover:bg-orange-50/80 transition-colors flex items-center gap-2.5 group cursor-pointer"
                      >
                        <div className="p-1.5 rounded-lg bg-emerald-100 text-emerald-600 group-hover:bg-emerald-600 group-hover:text-white transition-colors">
                          <CheckCircle2 className="w-3.5 h-3.5" />
                        </div>
                        <div>
                          <div className="text-xs font-extrabold text-slate-900 group-hover:text-emerald-600 transition-colors">Evaluation</div>
                          <div className="text-[10px] text-slate-500">Continuous CRAG hallucination scoring</div>
                        </div>
                      </button>

                      <button
                        onClick={() => scrollToSection("deployment")}
                        className="w-full text-left p-2.5 rounded-xl hover:bg-orange-50/80 transition-colors flex items-center gap-2.5 group cursor-pointer"
                      >
                        <div className="p-1.5 rounded-lg bg-purple-100 text-purple-600 group-hover:bg-purple-600 group-hover:text-white transition-colors">
                          <Send className="w-3.5 h-3.5" />
                        </div>
                        <div>
                          <div className="text-xs font-extrabold text-slate-900 group-hover:text-purple-600 transition-colors">Deployment</div>
                          <div className="text-[10px] text-slate-500">Private Cloud, On-Prem &amp; Managed</div>
                        </div>
                      </button>

                      <button
                        onClick={() => scrollToSection("security")}
                        className="w-full text-left p-2.5 rounded-xl hover:bg-orange-50/80 transition-colors flex items-center gap-2.5 group cursor-pointer"
                      >
                        <div className="p-1.5 rounded-lg bg-amber-100 text-amber-600 group-hover:bg-amber-600 group-hover:text-white transition-colors">
                          <ShieldCheck className="w-3.5 h-3.5" />
                        </div>
                        <div>
                          <div className="text-xs font-extrabold text-slate-900 group-hover:text-amber-600 transition-colors">Security &amp; Governance</div>
                          <div className="text-[10px] text-slate-500">SOC2 Type II, HIPAA &amp; RBAC</div>
                        </div>
                      </button>
                    </div>
                  </div>
                )}
              </div>

              {/* --- ARCHITECTURE DROPDOWN --- */}
              <div className="relative" onMouseEnter={() => setActiveDropdown("architecture")} onMouseLeave={() => setActiveDropdown(null)}>
                <button
                  onClick={() => scrollToSection("architecture")}
                  className={`px-3 py-2 text-sm font-bold transition-all duration-200 flex items-center gap-1 cursor-pointer relative group ${
                    ["architecture", "techstack"].includes(activeSection) ? "text-slate-900" : "text-slate-600 hover:text-slate-900"
                  }`}
                >
                  <span>Architecture</span>
                  <ChevronDown className={`w-4 h-4 text-slate-400 transition-transform duration-200 ${activeDropdown === "architecture" ? "rotate-180 text-orange-500" : ""}`} />
                  <span
                    className={`absolute bottom-0 left-3 right-3 h-1 bg-gradient-to-r from-orange-500 to-amber-500 transition-all duration-200 rounded-full ${
                      ["architecture", "techstack"].includes(activeSection) ? "opacity-100 scale-x-100" : "opacity-0 scale-x-0 group-hover:opacity-100 group-hover:scale-x-100"
                    }`}
                  />
                </button>

                {activeDropdown === "architecture" && (
                  <div className="absolute top-full left-0 w-64 pt-2 animate-fade-in-marketing">
                    <div className="bg-white rounded-2xl shadow-xl border border-slate-200/90 p-2 space-y-1">
                      <button
                        onClick={() => scrollToSection("architecture")}
                        className="w-full text-left p-2.5 rounded-xl hover:bg-orange-50/80 transition-colors flex items-center gap-2.5 group cursor-pointer"
                      >
                        <div className="p-1.5 rounded-lg bg-indigo-100 text-indigo-600 group-hover:bg-indigo-600 group-hover:text-white transition-colors">
                          <Layers className="w-3.5 h-3.5" />
                        </div>
                        <div>
                          <div className="text-xs font-extrabold text-slate-900 group-hover:text-indigo-600 transition-colors">Platform Architecture</div>
                          <div className="text-[10px] text-slate-500">End-to-end data flow map</div>
                        </div>
                      </button>

                      <button
                        onClick={() => scrollToSection("agents")}
                        className="w-full text-left p-2.5 rounded-xl hover:bg-orange-50/80 transition-colors flex items-center gap-2.5 group cursor-pointer"
                      >
                        <div className="p-1.5 rounded-lg bg-orange-100 text-orange-600 group-hover:bg-orange-500 group-hover:text-white transition-colors">
                          <Zap className="w-3.5 h-3.5" />
                        </div>
                        <div>
                          <div className="text-xs font-extrabold text-slate-900 group-hover:text-orange-600 transition-colors">9-Agent Orchestrator</div>
                          <div className="text-[10px] text-slate-500">Parallel agent DAG execution</div>
                        </div>
                      </button>

                      <button
                        onClick={() => scrollToSection("continuous-improvement")}
                        className="w-full text-left p-2.5 rounded-xl hover:bg-orange-50/80 transition-colors flex items-center gap-2.5 group cursor-pointer"
                      >
                        <div className="p-1.5 rounded-lg bg-emerald-100 text-emerald-600 group-hover:bg-emerald-600 group-hover:text-white transition-colors">
                          <CheckCircle2 className="w-3.5 h-3.5" />
                        </div>
                        <div>
                          <div className="text-xs font-extrabold text-slate-900 group-hover:text-emerald-600 transition-colors">Continuous Improvement</div>
                          <div className="text-[10px] text-slate-500">Auto-tuning feedback loops</div>
                        </div>
                      </button>

                      <button
                        onClick={() => scrollToSection("techstack")}
                        className="w-full text-left p-2.5 rounded-xl hover:bg-orange-50/80 transition-colors flex items-center gap-2.5 group cursor-pointer"
                      >
                        <div className="p-1.5 rounded-lg bg-blue-100 text-blue-600 group-hover:bg-blue-600 group-hover:text-white transition-colors">
                          <Code2 className="w-3.5 h-3.5" />
                        </div>
                        <div>
                          <div className="text-xs font-extrabold text-slate-900 group-hover:text-blue-600 transition-colors">Technology Stack</div>
                          <div className="text-[10px] text-slate-500">Vector stores &amp; cloud connectors</div>
                        </div>
                      </button>
                    </div>
                  </div>
                )}
              </div>

              {/* --- SOLUTIONS DROPDOWN --- */}
              <div className="relative" onMouseEnter={() => setActiveDropdown("solutions")} onMouseLeave={() => setActiveDropdown(null)}>
                <button
                  onClick={() => scrollToSection("solutions")}
                  className="px-3 py-2 text-sm font-bold text-slate-600 hover:text-slate-900 transition-all duration-200 flex items-center gap-1 cursor-pointer relative group"
                >
                  <span>Solutions</span>
                  <ChevronDown className={`w-4 h-4 text-slate-400 transition-transform duration-200 ${activeDropdown === "solutions" ? "rotate-180 text-orange-500" : ""}`} />
                  <span className="absolute bottom-0 left-3 right-3 h-1 bg-gradient-to-r from-orange-500 to-amber-500 transition-all duration-200 rounded-full opacity-0 scale-x-0 group-hover:opacity-100 group-hover:scale-x-100" />
                </button>

                {activeDropdown === "solutions" && (
                  <div className="absolute top-full left-0 w-72 pt-2 animate-fade-in-marketing">
                    <div className="bg-white rounded-2xl shadow-xl border border-slate-200/90 p-2 space-y-1">
                      <div className="px-3 py-1.5 text-[10px] font-black uppercase tracking-wider text-slate-400">Industry Use Cases</div>
                      {SOLUTIONS_ITEMS.map((item) => (
                        <button
                          key={item.label}
                          onClick={() => scrollToSection("solutions")}
                          className="w-full text-left p-2 rounded-xl hover:bg-orange-50/80 transition-colors flex items-center gap-2.5 text-xs font-extrabold text-slate-800 hover:text-orange-600 cursor-pointer"
                        >
                          {item.icon} {item.label}
                        </button>
                      ))}
                    </div>
                  </div>
                )}
              </div>

              {/* --- DOCUMENTATION LINK --- */}
              <button onClick={() => scrollToSection("docs")} className="px-3 py-2 text-sm font-bold text-slate-600 hover:text-slate-900 transition-all duration-200 flex items-center gap-1 cursor-pointer relative group">
                <span>Documentation</span>
                <span className="absolute bottom-0 left-3 right-3 h-1 bg-gradient-to-r from-orange-500 to-amber-500 transition-all duration-200 rounded-full opacity-0 scale-x-0 group-hover:opacity-100 group-hover:scale-x-100" />
              </button>

              {/* --- ABOUT LINK --- */}
              <button onClick={() => scrollToSection("about")} className="px-3 py-2 text-sm font-bold text-slate-600 hover:text-slate-900 transition-all duration-200 flex items-center gap-1 cursor-pointer relative group">
                <span>Company</span>
                <span className="absolute bottom-0 left-3 right-3 h-1 bg-gradient-to-r from-orange-500 to-amber-500 transition-all duration-200 rounded-full opacity-0 scale-x-0 group-hover:opacity-100 group-hover:scale-x-100" />
              </button>

              {/* --- CONTACT LINK --- */}
              <button onClick={() => scrollToSection("contact")} className="px-3 py-2 text-sm font-bold text-slate-600 hover:text-slate-900 transition-all duration-200 flex items-center gap-1 cursor-pointer relative group">
                <span>Contact</span>
                <span className="absolute bottom-0 left-3 right-3 h-1 bg-gradient-to-r from-orange-500 to-amber-500 transition-all duration-200 rounded-full opacity-0 scale-x-0 group-hover:opacity-100 group-hover:scale-x-100" />
              </button>
            </nav>

            {/* Right Side */}
            <div className="hidden sm:flex items-center gap-2">
              <button
                onClick={onOpenChat}
                className="flex shrink-0 items-center gap-1.5 whitespace-nowrap px-3.5 py-2 text-xs font-bold text-orange-700 bg-orange-50 hover:bg-orange-100 border border-orange-200 hover:border-orange-300 rounded-full transition-all duration-200 cursor-pointer"
              >
                <MessageSquare className="w-4 h-4" />
                <span>Try AI Assistant</span>
              </button>

              <button
                onClick={() => setSignInModalOpen(true)}
                className="flex shrink-0 items-center gap-1.5 whitespace-nowrap px-5 py-2 text-sm font-semibold text-slate-700 hover:text-slate-900 hover:underline underline-offset-4 transition-all duration-200 cursor-pointer"
              >
                <User className="w-4 h-4" />
                Sign In
              </button>

              <button
                onClick={onOpenSandbox}
                className="group flex shrink-0 items-center gap-2 whitespace-nowrap px-4 py-2 text-sm font-extrabold text-white rounded-full bg-gradient-to-r from-orange-500 via-amber-500 to-orange-600 hover:from-orange-600 hover:to-amber-600 shadow-md shadow-orange-500/20 hover:shadow-lg hover:shadow-orange-500/35 transition-all duration-200"
              >
                <Sparkles className="w-4 h-4 text-white" />
                <span>Request Demo</span>
                <ArrowRight className="w-4 h-4 transition-transform duration-200 group-hover:translate-x-1" />
              </button>
            </div>

            {/* Compact CTA kept visible below `sm` (the full button group hides
                there) so the primary conversion action is never fully hidden
                behind the hamburger. */}
            <button
              onClick={onOpenSandbox}
              className="sm:hidden flex shrink-0 items-center gap-1.5 whitespace-nowrap px-3 py-1.5 text-xs font-extrabold text-white rounded-full bg-gradient-to-r from-orange-500 via-amber-500 to-orange-600 shadow-md shadow-orange-500/20"
            >
              Request Demo
            </button>

            <button
              onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
              className="lg:hidden p-2 rounded-xl bg-slate-100 text-slate-700 hover:bg-slate-200 transition-colors"
              aria-label="Toggle menu"
            >
              {mobileMenuOpen ? <X className="w-6 h-6" /> : <Menu className="w-6 h-6" />}
            </button>
          </div>

          {/* Mobile Drawer */}
          {mobileMenuOpen && (
            <div className="lg:hidden mt-3 p-5 rounded-3xl bg-white border border-slate-200 shadow-2xl flex flex-col gap-3 animate-fade-in-marketing">
              <button
                onClick={() => { setMobileMenuOpen(false); onOpenChat(); }}
                className="px-3 py-2 text-left text-sm font-extrabold text-orange-600 bg-orange-50 hover:bg-orange-100 rounded-xl transition-colors flex items-center gap-2"
              >
                <MessageSquare className="w-4 h-4" />
                <span>Try AI Assistant</span>
              </button>
              <button onClick={() => scrollToSection("features")} className="px-3 py-2 text-left text-sm font-extrabold text-slate-800 hover:text-orange-600 hover:bg-orange-50 rounded-xl transition-colors flex items-center justify-between">
                <span>Features</span>
                <ChevronDown className="w-4 h-4 text-slate-400" />
              </button>
              <button onClick={() => scrollToSection("architecture")} className="px-3 py-2 text-left text-sm font-extrabold text-slate-800 hover:text-orange-600 hover:bg-orange-50 rounded-xl transition-colors flex items-center justify-between">
                <span>Architecture</span>
                <ChevronDown className="w-4 h-4 text-slate-400" />
              </button>
              <button onClick={() => scrollToSection("solutions")} className="px-3 py-2 text-left text-sm font-extrabold text-slate-800 hover:text-orange-600 hover:bg-orange-50 rounded-xl transition-colors flex items-center justify-between">
                <span>Solutions</span>
                <ChevronDown className="w-4 h-4 text-slate-400" />
              </button>
              <button onClick={() => scrollToSection("docs")} className="px-3 py-2 text-left text-sm font-extrabold text-slate-800 hover:text-orange-600 hover:bg-orange-50 rounded-xl transition-colors">
                Documentation
              </button>
              <button onClick={() => scrollToSection("about")} className="px-3 py-2 text-left text-sm font-extrabold text-slate-800 hover:text-orange-600 hover:bg-orange-50 rounded-xl transition-colors">
                Company
              </button>
              <button onClick={() => scrollToSection("contact")} className="px-3 py-2 text-left text-sm font-extrabold text-slate-800 hover:text-orange-600 hover:bg-orange-50 rounded-xl transition-colors">
                Contact
              </button>

              <div className="my-1 border-t border-slate-200" />

              <div className="flex flex-col gap-2 pt-1">
                <button
                  onClick={() => { setMobileMenuOpen(false); setSignInModalOpen(true); }}
                  className="w-full py-2.5 px-4 text-xs font-bold text-slate-800 border border-slate-300 rounded-xl hover:bg-slate-50 transition-colors"
                >
                  Sign In
                </button>
                <button
                  onClick={() => { setMobileMenuOpen(false); onOpenSandbox(); }}
                  className="w-full py-3 px-4 text-xs font-extrabold text-white bg-gradient-to-r from-orange-500 via-amber-500 to-orange-600 rounded-xl flex items-center justify-center gap-2 shadow-md shadow-orange-500/20"
                >
                  <Sparkles className="w-4 h-4 text-white" />
                  Request Demo
                </button>
              </div>
            </div>
          )}
        </div>
      </header>

      <SignInModal isOpen={signInModalOpen} onClose={() => setSignInModalOpen(false)} onOpenSandbox={onOpenSandbox} />
    </>
  );
}
