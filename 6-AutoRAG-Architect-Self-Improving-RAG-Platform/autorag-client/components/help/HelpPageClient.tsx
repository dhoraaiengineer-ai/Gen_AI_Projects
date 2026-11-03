"use client";

/**
 * Help & Documentation — redesigned 19-Jul-2026 to separate audiences that were
 * previously mixed on one page (product users vs. engineers/contributors).
 * Reviewer feedback: "This page currently looks like an internal engineering
 * wiki, not product help... two different audiences." Structure:
 *   Help Center       -> default tab, for platform users (onboarding, guides,
 *                         plain-language reference, troubleshooting, FAQ)
 *   Developer Portal   -> Swagger/health/GitHub/DB links + architecture pages
 *   Internal Governance -> CLAUDE.md/ADRs/GraphState/DB Schema/etc., explicitly
 *                         labelled as contributor-only, not for end users
 */

import { useState } from "react";
import {
  GitBranch, Upload, FlaskConical, Rocket as Deploy,
  LayoutDashboard, Wrench, FolderOpen, BookOpen, Search,
  Activity, Stethoscope, Wand2, Shield, ExternalLink, HelpCircle,
  FileText, Layers, Gauge, ListChecks, AlertTriangle, XCircle,
  Clock, Code2, GitPullRequest, Lock, BarChart3,
  MessageCircle, Github, Mail, Users,
} from "lucide-react";

const CARD: React.CSSProperties = {
  background: "hsl(var(--card))",
  border: "1px solid hsl(var(--border))",
  borderRadius: 12,
  padding: 20,
};

const SECTION_TITLE: React.CSSProperties = {
  fontSize: 14, fontWeight: 700, color: "#FBBF24",
  textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: 16,
};

type Tab = "help" | "developer" | "governance";

// ─────────────────────────────────────────────────────────────────────────────
// Help Center content
// ─────────────────────────────────────────────────────────────────────────────

const GETTING_STARTED = [
  { route: "/configurator", label: "Create Your First Pipeline", desc: "Use the 6-step Pipeline Configurator to set up sources, chunking, retrieval, and generation.", icon: GitBranch, color: "#EA580C" },
  { route: "/documents", label: "Upload Documents", desc: "Upload PDFs, DOCX, TXT, Markdown, HTML, or CSV files for a pipeline to ingest.", icon: Upload, color: "#0EA5E9" },
  { route: "/evaluate", label: "Run Your First Evaluation", desc: "Ask a question against your pipeline and see the Unified Score, Recall, Faithfulness, and Quality metrics.", icon: FlaskConical, color: "#10B981" },
  { route: "/deploy", label: "Deploy Your Pipeline", desc: "Deploy automatically once your score clears the gate, or approve manually through Human-in-the-Loop review.", icon: Deploy, color: "#F97316" },
];

/** Real, checkable steps -- each one names the exact page and the exact
 * signal that tells you the step actually worked, not just "go here." */
const QUICK_START_STEPS = [
  {
    step: "1. Create a pipeline",
    route: "/configurator",
    action: "Open the 6-step Configurator, name your pipeline, and pick a chunking strategy (Semantic is the safe default).",
    check: "The pipeline appears on /dashboard with status Draft.",
  },
  {
    step: "2. Upload documents",
    route: "/documents",
    action: "Drag in your files (PDF, DOCX, TXT, Markdown, HTML, or CSV — 50MB max per file).",
    check: "Each document's status moves to Indexed. If it shows Failed, open it to see the error and see Troubleshooting → Upload Problems below.",
  },
  {
    step: "3. Run an evaluation",
    route: "/evaluate",
    action: "Ask a real question about your documents' content.",
    check: "You'll see Unified Score, Recall, Faithfulness, and Quality. Watch the gate result — it will say Deploy Eligible, Human Approval Required, or Hard Block.",
  },
  {
    step: "4. Deploy or fix",
    route: "/deploy",
    action: "If the score cleared the gate, deploy directly here. If it needs approval or scored low, open /diagnose first to see the specific reason.",
    check: "Deployment status changes to Live, and the run shows up in /audit.",
  },
];

/**
 * Every real sidebar item (lib/nav.ts — the single source of truth for what's
 * actually in primary navigation), grouped into the same product-area
 * sections as the sidebar itself (Core -> Pipeline Studio -> Knowledge ->
 * Retrieval -> Evaluation -> Optimization -> Deployment -> Platform, per the
 * 24-Jul-2026 nav restructuring — "Navigation is a contract with the user"),
 * each with a real "what to do" and "what to check" — not just a one-line
 * blurb. Deliberately excludes pages still hidden from nav for showing
 * fabricated data with no real backend (see verification/releases/v4.0/DEFERRED_BACKEND_
 * WIRING.md) — Agent Hub, Agent State, Workflow, Chunk Explorer, Embedding
 * Explorer, AI Chat, Cost Analytics, Security, Infrastructure, Prompt Studio.
 * Guiding users to those would point them at an honest "not connected in
 * this build" placeholder.
 */
const PLATFORM_GUIDES: {
  section: string;
  items: { route: string; label: string; icon: React.ComponentType<{ style?: React.CSSProperties }>; color: string; doThis: string; check: string }[];
}[] = [
  {
    section: "Core",
    items: [
      { route: "/dashboard", label: "Dashboard", icon: LayoutDashboard, color: "#0EA5E9", doThis: "Land here first — see every pipeline's status, pending approvals, and platform health at a glance.", check: "Pipeline cards show real status badges: Draft, Running, Ready, Failed, or Archived." },
    ],
  },
  {
    section: "Pipeline Studio",
    items: [
      { route: "/configurator", label: "Pipeline Studio", icon: Wrench, color: "#EA580C", doThis: "Walk through the 6 steps — Identity, Sources, Chunking, Retrieval, Generation, Launch.", check: "After Launch, the new pipeline shows on Dashboard with status Draft, then Running as ingestion starts." },
      { route: "/pipelines", label: "Pipeline History", icon: GitBranch, color: "#EA580C", doThis: "Browse every past pipeline version and its outcome.", check: "Each version lists its Unified Score and deployment status." },
    ],
  },
  {
    section: "Knowledge",
    items: [
      { route: "/knowledge", label: "Knowledge Base", icon: BookOpen, color: "#EA580C", doThis: "Check the Health tab for a unified view of storage, index status, collection health, and failed documents — retry a failed document right from there.", check: "The Health tab's status badge reads Healthy, Warning, or Critical, matching the real indexed/failed document counts." },
      { route: "/documents", label: "Documents", icon: FolderOpen, color: "#0EA5E9", doThis: "Pick a pipeline, then upload or manage its source files.", check: "Each file's status moves to Indexed. A Failed row is clickable and shows the exact error." },
    ],
  },
  {
    section: "Retrieval",
    items: [
      { route: "/retrieve", label: "Retrieval Explorer", icon: Search, color: "#06B6D4", doThis: "Type a test query against a pipeline before running a full evaluation, to see which chunks come back.", check: "A ranked list of retrieved chunks appears with relevance scores." },
      { route: "/playground", label: "Query Playground", icon: FlaskConical, color: "#10B981", doThis: "Freeform space to try queries and prompt variations against a pipeline without starting a formal evaluation run.", check: "Responses stream back with the provider and latency shown." },
    ],
  },
  {
    section: "Evaluation",
    items: [
      { route: "/evaluation", label: "Evaluation Center", icon: Gauge, color: "#F59E0B", doThis: "The full workspace: Run Evaluation (quick, ad hoc single-question sanity-check), Batch Runs, Live Monitor, Results, Failed Questions (with human review), Compare Runs, and Settings for reusable evaluation configs.", check: "The Overview tab's recent-runs list and per-pipeline leaderboard populate with real batch run history, not placeholders." },
      { route: "/datasets", label: "Golden Datasets", icon: ListChecks, color: "#F59E0B", doThis: "Create a versioned set of golden questions (with reference answers, so Answer Correctness and Recall get fully measured, not just diagnostic), then run it as a batch against a pipeline. Use the Import/Export tab to bulk-load questions from CSV/JSON/JSONL or export a version as CSV/JSON/XLSX.", check: "A dataset version must be marked Published before it's selectable for a batch run — draft versions are rejected with a clear error." },
      { route: "/experiments", label: "Experiments", icon: FlaskConical, color: "#10B981", doThis: "Track evaluation runs and configurations across a pipeline's history in one place.", check: "Summary cards show real totals — active, completed, and best Unified Score." },
    ],
  },
  {
    section: "Optimization",
    items: [
      { route: "/observe", label: "Observer", icon: Activity, color: "#F59E0B", doThis: "Monitor production latency, cost, and quality trends over time, across runs — including the Evaluation Trends panel sourced from real batch-run history.", check: "Charts populate with real run history, not placeholder data." },
      { route: "/diagnose", label: "Diagnoser", icon: Stethoscope, color: "#EF4444", doThis: "Open this when a run scores low or hard-blocks, to see the specific root cause. The Failed Question Analysis panel drills into a batch run's worst-scoring questions.", check: "A specific failure type and remediation hint is shown — not a generic \"failed\" message." },
      { route: "/improve", label: "Improver", icon: Wand2, color: "#EC4899", doThis: "Compare hyperparameter/configuration variants for a pipeline side-by-side.", check: "A recommended variant is highlighted along with its projected score improvement." },
      { route: "/evolution", label: "Evolution History", icon: GitBranch, color: "#EC4899", doThis: "See the full version history of applied improvements and roll back to an earlier version if a change made things worse.", check: "Each version lists the real score it achieved, and rollback is a single click." },
    ],
  },
  {
    section: "Deployment",
    items: [
      { route: "/deploy", label: "Deployment Center", icon: Deploy, color: "#F97316", doThis: "Approve a run that needs Human-in-the-Loop sign-off, or release one that already cleared the gate.", check: "Status changes to Live, and a rollback option becomes available." },
      { route: "/audit", label: "Audit Logs", icon: Shield, color: "var(--text-3)", doThis: "Review the immutable history of platform events — deployments, approvals, PII detections.", check: "Every action has a timestamp and cannot be edited or deleted (insert-only by design)." },
    ],
  },
  {
    section: "System",
    items: [
      { route: "/health", label: "System Health", icon: Activity, color: "#34D399", doThis: "Check overall platform uptime, API latency, and active alerts.", check: "An overall status badge reads Healthy, Degraded, or Down." },
      { route: "/settings/profile", label: "Settings", icon: Wrench, color: "var(--text-3)", doThis: "Manage your profile, organization, and integration settings.", check: "Changes save immediately and persist on reload." },
    ],
  },
];

const CHUNKING_STRATEGIES = ["Semantic", "Hierarchical", "Late Chunking"];
const RETRIEVAL_PIPELINE = ["Query Rewriting", "Hybrid Search", "Reranking", "Context Compression"];
const FILE_TYPES = ["PDF", "DOCX", "TXT", "Markdown", "HTML", "CSV"];

const TROUBLESHOOTING = [
  {
    title: "Upload Problems", icon: Upload, color: "#0EA5E9",
    items: ["File upload failed", "Unsupported file format", "OCR issues on scanned pages"],
  },
  {
    title: "Evaluation Issues", icon: AlertTriangle, color: "#F59E0B",
    items: ["Low Unified Score", "Faithfulness check failed", "Evaluation timed out"],
  },
  {
    title: "Deployment Issues", icon: XCircle, color: "#EF4444",
    items: ["Waiting for approval", "Deployment blocked", "Rollback triggered"],
  },
  {
    title: "Pipeline Status Glossary", icon: ListChecks, color: "var(--text-3)",
    items: ["Draft", "Running", "Ready", "Failed", "Archived"],
  },
];

const FAQS = [
  {
    q: "What is the Unified Score?",
    a: "The Unified Score combines retrieval quality, answer quality, faithfulness, latency, and cost into a single number from 0 to 1. Scores of 0.85 or higher deploy automatically. Scores between 0.70 and 0.84 require a human to approve. Below 0.70, the pipeline needs improvement before it can deploy.",
  },
  {
    q: "Why is deployment blocked?",
    a: "Either the Unified Score is below 0.85 (needs human approval or improvement), or the answer's faithfulness score is below 0.5 — a hard safety rule that blocks deployment no matter how high the other scores are, since it means the answer wasn't well-grounded in your documents.",
  },
  {
    q: "How do I improve my score?",
    a: "Start with the Diagnoser page — it identifies the specific reason a run scored low and suggests a fix. Common improvements include trying a different chunking strategy, adjusting retrieval settings, or refining the prompt used for generation.",
  },
  {
    q: "Which LLM providers are supported?",
    a: "The platform supports multiple providers with automatic failover — if one is unavailable or rate-limited, the platform automatically retries on the next configured provider so your evaluation still completes.",
  },
  {
    q: "How does PII protection work?",
    a: "Every document is automatically scanned for personal information (emails, phone numbers, addresses, and more) and masked before it's stored or sent to any AI model — this happens automatically during upload, with no setup required.",
  },
  {
    q: "What's the difference between Evaluate, Evaluation Center, and Golden Datasets?",
    a: "Evaluate is a quick, ad hoc check of one question. Evaluation Center is the full workspace for running, monitoring, and reviewing evaluations at scale — including batch runs. Golden Datasets is where you build the reusable, versioned question set that a batch run executes: create questions with reference answers (so metrics like Answer Correctness and Recall are fully measured, not just diagnostic), get them reviewed and approved, publish a version, then run it as a batch from Evaluation Center.",
  },
  {
    q: "Why can't I start a batch run against my dataset version?",
    a: "Only a Published dataset version can be selected for a batch run — a version still in Draft or Under Review is rejected, so a benchmark can never run against a question set that's still being edited. Publish the version from the Datasets page first.",
  },
];

// ─────────────────────────────────────────────────────────────────────────────
// Developer Portal content
// ─────────────────────────────────────────────────────────────────────────────

const DEVELOPER_TOOLS = [
  { label: "API Documentation (Swagger)", desc: "REST API reference.", href: "http://localhost:8000/docs", icon: Code2, color: "#0EA5E9" },
  { label: "API Health", desc: "Platform health endpoint.", href: "http://localhost:8000/health", icon: Activity, color: "#34D399" },
  { label: "Database (Supabase)", desc: "Postgres + Vector + Storage dashboard.", href: "https://app.supabase.com", icon: Layers, color: "#3ECF8E" },
  { label: "GitHub Repository", desc: "Source code and issue tracking.", href: "https://github.com", icon: Github, color: "#EA580C" },
];

// 19-Jul-2026: /workflow, /agent-state, and /security were removed from here --
// all three are on the 11-page deferred-fabrication list (verification/releases/v4.0/
// DEFERRED_BACKEND_WIRING.md): hidden from primary nav because they render
// hardcoded/Math.random() data with no real backend, showing an honest
// "not connected in this build" placeholder if visited directly. Pointing
// engineers at them as "architecture" resources would be misleading them
// with fake data. /observe is real (it's in the actual sidebar) and stays.
const ARCHITECTURE_PAGES = [
  { route: "/observe", label: "Observer (real metrics)", desc: "The one live observability page — real production latency, cost, and quality trends, logs, and traces.", icon: BarChart3, color: "#F59E0B" },
];

// ─────────────────────────────────────────────────────────────────────────────
// Internal Governance content (contributors only)
// ─────────────────────────────────────────────────────────────────────────────

const GOVERNANCE_DOCS = [
  { label: "CLAUDE.md — Master Contract", path: ".claude/CLAUDE.md" },
  { label: "18 Coding Rules", path: ".claude/rules/coding-standards.md" },
  { label: "DB Schema v1.0 (Frozen)", path: ".claude/docs/DB_SCHEMA.md" },
  { label: "API Spec v1.0 (Frozen)", path: ".claude/docs/API_SPEC.md" },
  { label: "GraphState v1.0 (Frozen)", path: ".claude/docs/GRAPH_STATE.md" },
  { label: "Architectural Decision Records", path: "architecture/adr-index.md" },
  { label: "Frontend Design System", path: ".claude/docs/frontend_design.md" },
  { label: "Task Tracker", path: ".claude/TASK_TRACKER.md" },
];

// ─────────────────────────────────────────────────────────────────────────────
// Shared building blocks
// ─────────────────────────────────────────────────────────────────────────────

function LinkCard({ route, label, desc, icon: Icon, color }: {
  route: string; label: string; desc: string;
  icon: React.ComponentType<{ style?: React.CSSProperties }>; color: string;
}) {
  return (
    <a
      href={route}
      style={{
        display: "flex", gap: 12, padding: "12px 14px", borderRadius: 8,
        background: "hsl(var(--card))", border: "1px solid hsl(var(--border))",
        textDecoration: "none", transition: "background 140ms",
      }}
    >
      <div style={{
        width: 32, height: 32, borderRadius: 8, flexShrink: 0,
        display: "flex", alignItems: "center", justifyContent: "center",
        background: `${color}18`, border: `1px solid ${color}30`,
      }}>
        <Icon style={{ width: 15, height: 15, color }} />
      </div>
      <div>
        <div style={{ fontSize: 13, fontWeight: 600, color: "var(--text-1)", marginBottom: 3 }}>{label}</div>
        <div style={{ fontSize: 12, color: "var(--text-3)", lineHeight: 1.5 }}>{desc}</div>
      </div>
    </a>
  );
}

function ExternalLinkCard({ label, href, icon: Icon, color }: {
  label: string; href: string;
  icon: React.ComponentType<{ style?: React.CSSProperties }>; color: string;
}) {
  return (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      style={{
        display: "flex", alignItems: "center", gap: 10,
        padding: "10px 14px", borderRadius: 8, textDecoration: "none",
        background: `${color}10`, border: `1px solid ${color}30`,
        color: "var(--text-1)", fontSize: 13, fontWeight: 500,
      }}
    >
      <Icon style={{ width: 15, height: 15, color, flexShrink: 0 }} />
      {label}
      <ExternalLink style={{ width: 11, height: 11, color: "var(--text-3)", marginLeft: "auto" }} />
    </a>
  );
}

const TAB_META: Record<Tab, { label: string; icon: React.ComponentType<{ style?: React.CSSProperties }> }> = {
  help: { label: "Help Center", icon: HelpCircle },
  developer: { label: "Developer Portal", icon: Code2 },
  governance: { label: "Architecture & Governance", icon: FileText },
};

export function HelpPageClient() {
  const [tab, setTab] = useState<Tab>("help");

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>

      {/* Tabs */}
      <div style={{ display: "flex", gap: 8, borderBottom: "1px solid hsl(var(--border))" }}>
        {(Object.keys(TAB_META) as Tab[]).map((key) => {
          const { label, icon: Icon } = TAB_META[key];
          const active = tab === key;
          return (
            <button
              key={key}
              onClick={() => setTab(key)}
              style={{
                display: "flex", alignItems: "center", gap: 8,
                padding: "10px 16px", fontSize: 13, fontWeight: 600,
                background: "transparent", border: "none", cursor: "pointer",
                color: active ? "var(--text-1)" : "var(--text-3)",
                borderBottom: active ? "2px solid #F97316" : "2px solid transparent",
                marginBottom: -1,
              }}
            >
              <Icon style={{ width: 15, height: 15 }} />
              {label}
            </button>
          );
        })}
      </div>

      {tab === "help" && (
        <>
          {/* Getting Started */}
          <section style={CARD}>
            <h2 style={SECTION_TITLE}>🚀 Getting Started</h2>

            {/* Quick Start — the actual step-by-step, with what to check at each step */}
            <div style={{ display: "flex", flexDirection: "column", gap: 12, marginBottom: 20 }}>
              {QUICK_START_STEPS.map(({ step, route, action, check }) => (
                <a
                  key={step}
                  href={route}
                  style={{
                    display: "flex", gap: 14, padding: "14px 16px", borderRadius: 10,
                    background: "rgba(249,115,22,0.05)", border: "1px solid rgba(249,115,22,0.2)",
                    textDecoration: "none",
                  }}
                >
                  <div style={{
                    fontSize: 12, fontWeight: 700, color: "#F97316", flexShrink: 0,
                    width: 22, height: 22, borderRadius: "50%",
                    display: "flex", alignItems: "center", justifyContent: "center",
                    background: "rgba(249,115,22,0.12)", border: "1px solid rgba(249,115,22,0.3)",
                  }}>
                    {step.split(".")[0]}
                  </div>
                  <div>
                    <div style={{ fontSize: 13, fontWeight: 600, color: "var(--text-1)", marginBottom: 3 }}>
                      {step.replace(/^\d+\.\s*/, "")}
                      <span style={{ fontSize: 11, color: "var(--text-3)", marginLeft: 8, fontWeight: 400 }}>{route}</span>
                    </div>
                    <p style={{ fontSize: 12, color: "var(--text-2)", lineHeight: 1.5, margin: "0 0 4px" }}>{action}</p>
                    <p style={{ fontSize: 11, color: "var(--text-3)", lineHeight: 1.5, margin: 0 }}>
                      <span style={{ color: "#34D399", fontWeight: 600 }}>Check: </span>{check}
                    </p>
                  </div>
                </a>
              ))}
            </div>

            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))", gap: 10 }}>
              {GETTING_STARTED.map((item) => <LinkCard key={item.route} {...item} />)}
            </div>
          </section>

          {/* Platform Guides — every real sidebar item, grouped exactly like the sidebar itself */}
          <section style={CARD}>
            <h2 style={SECTION_TITLE}>📚 Platform Guides</h2>
            <p style={{ fontSize: 12, color: "var(--text-3)", marginBottom: 16 }}>
              Every item in the sidebar, grouped the same way — what to do on each page, and what tells you it worked.
            </p>
            <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
              {PLATFORM_GUIDES.map(({ section, items }) => (
                <div key={section}>
                  <div style={{ ...SECTION_TITLE, fontSize: 11, color: "var(--text-3)", marginBottom: 10 }}>{section}</div>
                  <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(300px, 1fr))", gap: 10 }}>
                    {items.map(({ route, label, icon: Icon, color, doThis, check }) => (
                      <a
                        key={route}
                        href={route}
                        style={{
                          display: "flex", gap: 12, padding: "12px 14px", borderRadius: 8,
                          background: "hsl(var(--card))", border: "1px solid hsl(var(--border))",
                          textDecoration: "none",
                        }}
                      >
                        <div style={{
                          width: 32, height: 32, borderRadius: 8, flexShrink: 0,
                          display: "flex", alignItems: "center", justifyContent: "center",
                          background: `${color}18`, border: `1px solid ${color}30`,
                        }}>
                          <Icon style={{ width: 15, height: 15, color }} />
                        </div>
                        <div>
                          <div style={{ fontSize: 13, fontWeight: 600, color: "var(--text-1)", marginBottom: 3 }}>
                            {label}
                            <span style={{ fontSize: 11, color: "var(--text-3)", marginLeft: 8, fontWeight: 400 }}>{route}</span>
                          </div>
                          <p style={{ fontSize: 12, color: "var(--text-2)", lineHeight: 1.5, margin: "0 0 4px" }}>{doThis}</p>
                          <p style={{ fontSize: 11, color: "var(--text-3)", lineHeight: 1.5, margin: 0 }}>
                            <span style={{ color: "#34D399", fontWeight: 600 }}>Check: </span>{check}
                          </p>
                        </div>
                      </a>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </section>

          {/* Platform Reference */}
          <section style={CARD}>
            <h2 style={SECTION_TITLE}>📖 Platform Reference</h2>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))", gap: 16 }}>
              <div>
                <div style={{ fontSize: 13, fontWeight: 600, color: "var(--text-1)", marginBottom: 8 }}>Unified Score</div>
                <p style={{ fontSize: 12, color: "var(--text-3)", lineHeight: 1.6, marginBottom: 8 }}>
                  Combines retrieval quality, answer quality, faithfulness, latency, and cost into one deployment decision.
                </p>
                <div style={{ display: "flex", flexDirection: "column", gap: 4, fontSize: 11 }}>
                  <div><span style={{ color: "#34D399", fontWeight: 700 }}>≥ 0.85</span> <span style={{ color: "var(--text-3)" }}>— Automatic Deployment</span></div>
                  <div><span style={{ color: "#FBBF24", fontWeight: 700 }}>0.70–0.84</span> <span style={{ color: "var(--text-3)" }}>— Human Approval</span></div>
                  <div><span style={{ color: "#F87171", fontWeight: 700 }}>&lt; 0.70</span> <span style={{ color: "var(--text-3)" }}>— Improvement Required</span></div>
                </div>
              </div>
              <div>
                <div style={{ fontSize: 13, fontWeight: 600, color: "var(--text-1)", marginBottom: 8 }}>Chunking Strategies</div>
                <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                  {CHUNKING_STRATEGIES.map((s) => (
                    <div key={s} style={{ fontSize: 12, color: "var(--text-3)" }}>• {s}</div>
                  ))}
                </div>
              </div>
              <div>
                <div style={{ fontSize: 13, fontWeight: 600, color: "var(--text-1)", marginBottom: 8 }}>Retrieval Pipeline</div>
                <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                  {RETRIEVAL_PIPELINE.map((s) => (
                    <div key={s} style={{ fontSize: 12, color: "var(--text-3)" }}>• {s}</div>
                  ))}
                </div>
              </div>
              <div>
                <div style={{ fontSize: 13, fontWeight: 600, color: "var(--text-1)", marginBottom: 8 }}>Supported File Types</div>
                <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
                  {FILE_TYPES.map((f) => (
                    <span key={f} style={{
                      fontSize: 11, color: "var(--text-2)", background: "rgba(15,23,42,0.06)",
                      border: "1px solid hsl(var(--border))", borderRadius: 6, padding: "3px 8px",
                    }}>{f}</span>
                  ))}
                </div>
              </div>
              <div>
                <div style={{ fontSize: 13, fontWeight: 600, color: "var(--text-1)", marginBottom: 8 }}>Deployment Workflow</div>
                <p style={{ fontSize: 12, color: "var(--text-3)", lineHeight: 1.6 }}>
                  Development → Evaluation → Human Approval → Production
                </p>
              </div>
            </div>
          </section>

          {/* Troubleshooting */}
          <section style={CARD}>
            <h2 style={SECTION_TITLE}>❓ Troubleshooting</h2>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: 16 }}>
              {TROUBLESHOOTING.map(({ title, icon: Icon, color, items }) => (
                <div key={title}>
                  <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
                    <Icon style={{ width: 14, height: 14, color }} />
                    <span style={{ fontSize: 13, fontWeight: 600, color: "var(--text-1)" }}>{title}</span>
                  </div>
                  <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                    {items.map((it) => (
                      <div key={it} style={{ fontSize: 12, color: "var(--text-3)" }}>• {it}</div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </section>

          {/* FAQ */}
          <section style={CARD}>
            <h2 style={SECTION_TITLE}>❔ Frequently Asked Questions</h2>
            <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
              {FAQS.map(({ q, a }) => (
                <div key={q} style={{ borderBottom: "1px solid hsl(var(--border))", paddingBottom: 16 }}>
                  <div style={{ display: "flex", gap: 10, marginBottom: 6 }}>
                    <HelpCircle style={{ width: 15, height: 15, color: "#0EA5E9", flexShrink: 0, marginTop: 1 }} />
                    <span style={{ fontSize: 14, fontWeight: 600, color: "var(--text-1)" }}>{q}</span>
                  </div>
                  <p style={{ fontSize: 13, color: "var(--text-3)", lineHeight: 1.6, marginLeft: 25 }}>{a}</p>
                </div>
              ))}
            </div>
          </section>
        </>
      )}

      {tab === "developer" && (
        <>
          <section style={CARD}>
            <h2 style={SECTION_TITLE}>🛠 Developer Tools</h2>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(220px, 1fr))", gap: 10 }}>
              {DEVELOPER_TOOLS.map((item) => <ExternalLinkCard key={item.href} {...item} />)}
            </div>
          </section>

          <section style={CARD}>
            <h2 style={SECTION_TITLE}>🏗 Architecture</h2>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))", gap: 10 }}>
              {ARCHITECTURE_PAGES.map((item) => <LinkCard key={item.route} {...item} />)}
            </div>
          </section>

          <section style={{ ...CARD, display: "flex", flexDirection: "column", gap: 12 }}>
            <h2 style={SECTION_TITLE}>📞 Support</h2>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: 10 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                <Users style={{ width: 15, height: 15, color: "#0EA5E9" }} />
                <span style={{ fontSize: 13, color: "var(--text-2)" }}>Engineering Team — internal Slack/Teams</span>
              </div>
              <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                <GitPullRequest style={{ width: 15, height: 15, color: "#EA580C" }} />
                <span style={{ fontSize: 13, color: "var(--text-2)" }}>Report an Issue — GitHub Issues</span>
              </div>
              <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                <Mail style={{ width: 15, height: 15, color: "#34D399" }} />
                <span style={{ fontSize: 13, color: "var(--text-2)" }}>Email — engineering support</span>
              </div>
              <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                <MessageCircle style={{ width: 15, height: 15, color: "#F59E0B" }} />
                <span style={{ fontSize: 13, color: "var(--text-2)" }}>Community — team workspace</span>
              </div>
            </div>
          </section>
        </>
      )}

      {tab === "governance" && (
        <section style={CARD}>
          <div style={{
            display: "flex", alignItems: "center", gap: 10, marginBottom: 16,
            padding: "10px 14px", borderRadius: 8,
            background: "rgba(239,68,68,0.08)", border: "1px solid rgba(239,68,68,0.25)",
          }}>
            <Lock style={{ width: 15, height: 15, color: "#F87171", flexShrink: 0 }} />
            <span style={{ fontSize: 12, color: "#FCA5A5" }}>
              Internal engineering documentation — for contributors and administrators, not end users.
            </span>
          </div>
          <h2 style={SECTION_TITLE}>Engineering Governance</h2>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(200px, 1fr))", gap: 8 }}>
            {GOVERNANCE_DOCS.map(({ label, path }) => (
              <div
                key={path}
                style={{
                  padding: "8px 12px", borderRadius: 6, fontSize: 12, color: "var(--text-3)",
                  background: "rgba(15,23,42,0.04)", border: "1px solid hsl(var(--border))",
                }}
              >
                <div style={{ fontWeight: 600, color: "var(--text-1)", marginBottom: 2 }}>{label}</div>
                <code style={{ fontSize: 10, color: "var(--text-3)" }}>{path}</code>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Timestamp footer */}
      <p style={{ fontSize: 11, color: "var(--text-3)", textAlign: "center" }}>
        <Clock style={{ width: 11, height: 11, display: "inline", marginRight: 4, verticalAlign: "-1px" }} />
        Last updated 24-Jul-2026
      </p>
    </div>
  );
}
