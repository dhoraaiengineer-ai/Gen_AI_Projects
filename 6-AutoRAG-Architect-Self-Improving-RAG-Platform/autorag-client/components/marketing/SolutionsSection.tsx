"use client";

import { useState } from "react";
import {
  Search,
  FileText,
  Headphones,
  Building2,
  Stethoscope,
  Scale,
  Code2,
  CheckCircle2,
  ArrowRight,
  Sparkles,
  Shield,
  Umbrella,
  Factory,
  Users,
  Plug,
  Server,
  Quote,
} from "lucide-react";

type SolutionTag = "Knowledge-Intensive" | "Operational" | "Regulated";

interface Solution {
  id: string;
  name: string;
  icon: React.ReactNode;
  tag: SolutionTag;
  tagline: string;
  useCases: string[];
  architecture: string;
  connectors: string[];
  sampleQuery: string;
  deployment: string;
}

const TAG_STYLES: Record<SolutionTag, string> = {
  "Knowledge-Intensive": "bg-indigo-500/20 text-indigo-300 border-indigo-500/30",
  Operational: "bg-emerald-500/20 text-emerald-300 border-emerald-500/30",
  Regulated: "bg-amber-500/20 text-amber-300 border-amber-500/30",
};

const SOLUTIONS: Solution[] = [
  {
    id: "search",
    name: "Enterprise Search",
    icon: <Search className="w-5 h-5 text-indigo-500" />,
    tag: "Knowledge-Intensive",
    tagline: "Unified semantic search across Confluence, Google Drive, Slack, and Notion.",
    useCases: [
      "Cross-repository semantic search across docs, wikis, and drives",
      "Federated Q&A across previously siloed knowledge bases",
      "Permission-aware result filtering by role and department",
    ],
    architecture: "Hybrid BM25 + dense retrieval with cross-encoder reranking across every connected source.",
    connectors: ["Confluence", "Google Drive", "SharePoint", "Slack"],
    sampleQuery: "What's our current Q3 SOC2 audit remediation policy?",
    deployment: "Managed Cloud or Private VPC",
  },
  {
    id: "qa",
    name: "Documentation QA",
    icon: <FileText className="w-5 h-5 text-blue-500" />,
    tag: "Knowledge-Intensive",
    tagline: "Self-correcting QA for internal specs and developer documentation.",
    useCases: [
      "Internal engineering spec Q&A with exact source citations",
      "Developer onboarding assistant grounded in real docs",
      "API reference lookup synced to OpenAPI definitions",
    ],
    architecture: "Adversarial-tested retrieval with mandatory citations and a faithfulness hard-block gate.",
    connectors: ["GitHub", "GitLab", "OpenAPI / Swagger", "Notion"],
    sampleQuery: "How do we handle rate-limiting backoff in the v2 API?",
    deployment: "Self-Hosted or Managed Cloud",
  },
  {
    id: "support",
    name: "Customer Support",
    icon: <Headphones className="w-5 h-5 text-emerald-500" />,
    tag: "Operational",
    tagline: "Agent-assist retrieval with confidence-gated human escalation.",
    useCases: [
      "Tier-1/2 ticket resolution drafting from the knowledge base",
      "Live agent-assist lookup during a support conversation",
      "Automatic escalation to a human on low-confidence answers",
    ],
    architecture: "Multi-turn conversational retrieval with a confidence threshold gating human-in-the-loop escalation.",
    connectors: ["Zendesk", "Intercom", "Salesforce", "Jira"],
    sampleQuery: "Why was my refund declined on order #48213?",
    deployment: "Managed Cloud",
  },
  {
    id: "financial",
    name: "Financial Services",
    icon: <Building2 className="w-5 h-5 text-amber-500" />,
    tag: "Regulated",
    tagline: "Compliance-aware analysis across filings, risk reports, and deal documents.",
    useCases: [
      "SEC filing (10-K / 10-Q) analysis and summarization",
      "M&A due-diligence document review",
      "Internal risk-report synthesis for compliance teams",
    ],
    architecture: "Table-aware chunking that preserves financial statement structure, with a VPC air-gap deployment option.",
    connectors: ["S3 Document Vaults", "SharePoint", "Internal Data Rooms"],
    sampleQuery: "Summarize the liabilities section of the FY25 10-K.",
    deployment: "VPC Air-Gapped",
  },
  {
    id: "healthcare",
    name: "Healthcare & Clinical",
    icon: <Stethoscope className="w-5 h-5 text-rose-500" />,
    tag: "Regulated",
    tagline: "PHI-masked medical research and clinical knowledge retrieval.",
    useCases: [
      "Clinical literature research assistant",
      "De-identified patient record semantic search",
      "Clinical trial eligibility matching",
    ],
    architecture: "Automatic PII/PHI masking at ingest — before any content reaches an LLM.",
    connectors: ["PubMed", "Internal EHR Exports", "Clinical Trial Registries"],
    sampleQuery: "What are the exclusion criteria for protocol #409?",
    deployment: "HIPAA-Ready VPC",
  },
  {
    id: "legal",
    name: "Legal Tech",
    icon: <Scale className="w-5 h-5 text-purple-500" />,
    tag: "Regulated",
    tagline: "Contract clause comparison, risk flagging, and precedent discovery.",
    useCases: [
      "Contract clause comparison across a full document set",
      "Precedent and statutory reference discovery",
      "Risk flagging against a standard corporate playbook",
    ],
    architecture: "Multi-document comparison retrieval with jurisdiction-filtered citation grounding.",
    connectors: ["iManage", "NetDocuments", "SharePoint"],
    sampleQuery: "Flag any indemnification clauses that deviate from our standard MSA.",
    deployment: "Private VPC",
  },
  {
    id: "developer",
    name: "Developer Copilot",
    icon: <Code2 className="w-5 h-5 text-cyan-500" />,
    tag: "Operational",
    tagline: "Context-aware code retrieval and codebase-grounded Q&A.",
    useCases: [
      "In-IDE code context retrieval while you type",
      "Codebase-aware Q&A for faster onboarding",
      "Automated API client snippet generation",
    ],
    architecture: "AST-aware code chunking (Tree-sitter) that preserves function and class structure.",
    connectors: ["GitHub", "GitLab", "VS Code", "JetBrains"],
    sampleQuery: "Where is refresh-token rotation handled in this codebase?",
    deployment: "Self-Hosted",
  },
  {
    id: "insurance",
    name: "Insurance",
    icon: <Umbrella className="w-5 h-5 text-teal-500" />,
    tag: "Regulated",
    tagline: "Policy interpretation, claims triage, and underwriting guideline lookup.",
    useCases: [
      "Policy wording interpretation for adjusters",
      "Claims triage assistance at intake",
      "Underwriting guideline lookup against the current rate manual",
    ],
    architecture: "Clause-level citation grounding cross-referenced against state-specific regulatory riders.",
    connectors: ["Policy Admin Systems", "Claims Management Platforms"],
    sampleQuery: "Is water damage covered under policy POL-2026-88431 in California?",
    deployment: "Private VPC",
  },
  {
    id: "manufacturing",
    name: "Manufacturing & Supply Chain",
    icon: <Factory className="w-5 h-5 text-orange-500" />,
    tag: "Operational",
    tagline: "Equipment manuals and supplier specs, searchable on the shop floor.",
    useCases: [
      "Equipment manual troubleshooting at the machine",
      "Multi-supplier spec sheet comparison",
      "SOP lookup for shop-floor operators",
    ],
    architecture: "Diagram-aware chunking that preserves exploded-view part references.",
    connectors: ["PLM Systems", "Supplier Portals", "Internal Wikis"],
    sampleQuery: "What does error code E-402 mean on CNC-MILL-014?",
    deployment: "On-Prem or Edge-Capable",
  },
  {
    id: "hr",
    name: "HR & People Operations",
    icon: <Users className="w-5 h-5 text-fuchsia-500" />,
    tag: "Operational",
    tagline: "Policy, benefits, and onboarding Q&A grounded in the real handbook.",
    useCases: [
      "Employee handbook Q&A for common policy questions",
      "Benefits and leave-policy lookup by locale",
      "Self-serve onboarding assistant for new hires",
    ],
    architecture: "Locale-aware answers pinned to the currently effective handbook version, not stale copies.",
    connectors: ["Workday", "BambooHR", "Internal Wikis"],
    sampleQuery: "How many parental leave days do I get in the UK?",
    deployment: "Managed Cloud",
  },
];

export function SolutionsSection() {
  const [activeTab, setActiveTab] = useState("search");

  const currentSolution = SOLUTIONS.find((s) => s.id === activeTab) ?? SOLUTIONS[0];

  return (
    <section id="solutions" className="py-24 bg-slate-950 relative border-t border-slate-800">
      <div className="absolute top-1/4 left-0 w-96 h-96 bg-indigo-500/10 rounded-full blur-3xl pointer-events-none" />
      <div className="absolute bottom-1/4 right-0 w-96 h-96 bg-orange-500/10 rounded-full blur-3xl pointer-events-none" />

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 relative z-10 space-y-12">
        <div className="text-center max-w-3xl mx-auto space-y-4">
          <div className="inline-flex items-center gap-2 px-3.5 py-1 rounded-full bg-indigo-500/10 border border-indigo-500/20 text-indigo-400 text-xs font-mono font-bold uppercase tracking-wider">
            <Sparkles className="w-3.5 h-3.5" />
            <span>Enterprise Solutions</span>
          </div>
          <h2 className="text-3xl sm:text-5xl font-black text-white tracking-tight">
            Tailored RAG Solutions for Every Industry
          </h2>
          <p className="text-slate-400 text-base sm:text-lg font-medium">
            Explore 10 domain-specific pipeline architectures — each with its own connectors, retrieval emphasis, and recommended deployment model.
          </p>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
          <div className="lg:col-span-4 space-y-2">
            <div className="text-xs font-mono font-bold uppercase text-slate-500 px-3 pb-2">
              Select Use Case Architecture
            </div>
            {SOLUTIONS.map((sol) => {
              const isActive = activeTab === sol.id;
              return (
                <button
                  key={sol.id}
                  onClick={() => setActiveTab(sol.id)}
                  className={`w-full text-left p-4 rounded-2xl transition-all duration-200 flex items-center justify-between group cursor-pointer border ${
                    isActive
                      ? "bg-slate-900 border-orange-500/60 shadow-lg shadow-orange-500/10 text-white"
                      : "bg-slate-900/40 border-slate-800/80 text-slate-400 hover:text-slate-200 hover:bg-slate-900/70 hover:border-slate-700"
                  }`}
                >
                  <div className="flex items-center gap-3">
                    <div className={`p-2.5 rounded-xl transition-colors ${
                      isActive ? "bg-orange-500/20 text-orange-400 border border-orange-500/30" : "bg-slate-800/60 text-slate-400"
                    }`}>
                      {sol.icon}
                    </div>
                    <div>
                      <div className="text-sm font-extrabold tracking-tight text-white group-hover:text-orange-400 transition-colors">
                        {sol.name}
                      </div>
                      <span className={`inline-block mt-1 px-1.5 py-0.5 rounded text-[9px] font-mono font-bold uppercase tracking-wider border ${TAG_STYLES[sol.tag]}`}>
                        {sol.tag}
                      </span>
                    </div>
                  </div>
                  <ArrowRight className={`w-4 h-4 transition-transform duration-200 ${
                    isActive ? "text-orange-400 translate-x-1" : "text-slate-600 opacity-0 group-hover:opacity-100"
                  }`} />
                </button>
              );
            })}
          </div>

          <div className="lg:col-span-8 bg-slate-900/90 rounded-3xl border border-slate-800 p-6 sm:p-8 shadow-2xl relative overflow-hidden space-y-6">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-6 border-b border-slate-800">
              <div className="flex items-center gap-3">
                <div className="p-3 rounded-2xl bg-orange-500/10 border border-orange-500/20 text-orange-400">
                  {currentSolution.icon}
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <h3 className="text-2xl font-black text-white">{currentSolution.name}</h3>
                    <span className={`px-2.5 py-0.5 rounded-full text-[10px] font-mono font-bold border ${TAG_STYLES[currentSolution.tag]}`}>
                      {currentSolution.tag}
                    </span>
                  </div>
                  <p className="text-xs text-slate-400 font-medium mt-0.5">
                    {currentSolution.tagline}
                  </p>
                </div>
              </div>
            </div>

            {/* Typical Use Cases */}
            <div className="space-y-3">
              <h4 className="text-xs font-mono font-bold text-slate-400 uppercase tracking-wider">
                Typical Use Cases
              </h4>
              <div className="grid grid-cols-1 gap-2.5">
                {currentSolution.useCases.map((uc) => (
                  <div key={uc} className="flex items-start gap-2.5 p-3 rounded-xl bg-slate-950/60 border border-slate-800/80 text-xs font-medium text-slate-200">
                    <CheckCircle2 className="w-4 h-4 text-emerald-400 mt-0.5 shrink-0" />
                    <span>{uc}</span>
                  </div>
                ))}
              </div>
            </div>

            {/* Architecture + Connectors */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div className="p-4 rounded-xl bg-slate-950/60 border border-slate-800/80 space-y-2">
                <h4 className="text-xs font-mono font-bold text-slate-400 uppercase tracking-wider flex items-center gap-1.5">
                  <Code2 className="w-3.5 h-3.5 text-orange-400" /> Architecture
                </h4>
                <p className="text-xs text-slate-300 font-medium leading-relaxed">{currentSolution.architecture}</p>
              </div>
              <div className="p-4 rounded-xl bg-slate-950/60 border border-slate-800/80 space-y-2.5">
                <h4 className="text-xs font-mono font-bold text-slate-400 uppercase tracking-wider flex items-center gap-1.5">
                  <Plug className="w-3.5 h-3.5 text-orange-400" /> Connectors
                </h4>
                <div className="flex flex-wrap gap-1.5">
                  {currentSolution.connectors.map((c) => (
                    <span key={c} className="text-[11px] font-bold px-2.5 py-1 rounded-md bg-slate-800/80 border border-slate-700 text-slate-300">
                      {c}
                    </span>
                  ))}
                </div>
              </div>
            </div>

            {/* Sample Query */}
            <div className="space-y-2">
              <h4 className="text-xs font-mono font-bold text-slate-400 uppercase tracking-wider flex items-center gap-1.5">
                <Quote className="w-3.5 h-3.5 text-orange-400" /> Sample Query
              </h4>
              <div className="bg-[#0f172a] rounded-2xl p-4 border border-slate-800 shadow-inner">
                <p className="text-sm text-slate-200 font-medium italic">&quot;{currentSolution.sampleQuery}&quot;</p>
              </div>
            </div>

            <div className="pt-4 border-t border-slate-800/80 flex flex-col sm:flex-row items-center justify-between text-xs text-slate-400 gap-3">
              <div className="flex items-center gap-2">
                <Server className="w-4 h-4 text-indigo-400 shrink-0" />
                <span>Recommended Deployment: <strong className="text-slate-200">{currentSolution.deployment}</strong></span>
              </div>
              <a
                href="#contact"
                className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl bg-orange-500 hover:bg-orange-600 text-white font-bold text-xs transition-colors cursor-pointer shrink-0"
              >
                <span>Deploy {currentSolution.name}</span>
                <ArrowRight className="w-3.5 h-3.5" />
              </a>
            </div>
          </div>
        </div>

        <div className="flex items-center justify-center gap-2 text-[11px] font-medium text-slate-500">
          <Shield className="w-3.5 h-3.5 text-indigo-400 shrink-0" />
          <span>Every solution includes automated hallucination guardrails and OpenTelemetry-based observability.</span>
        </div>
      </div>
    </section>
  );
}
