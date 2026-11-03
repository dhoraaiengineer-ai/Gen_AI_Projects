"use client";

import { Suspense, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { AppShell } from "@/components/layout/AppShell";
import UploadPanel from "@/components/documents/UploadPanel";
import { apiClient } from "@/services/api-client";
import { toast } from "@/hooks/use-toast";
import type { ChunkStrategy, DocumentStatus } from "@/types";
import { Check, ChevronRight, Link2, Database, Cpu, Sliders, Rocket, FileText, Globe, Loader2, CheckCircle2, XCircle, Clock } from "lucide-react";

/* ── shared styles — theme-aware (ADR-010) ─────────────── */
const card: React.CSSProperties = {
  // Synced to the shared "Cards" elevation tier (19-Jul-2026 two-personality
  // theme: this page runs in Builder Mode, see AppShell mode="builder").
  background: "hsl(var(--card))",
  border: "1px solid hsl(var(--border))",
  borderRadius: 20, padding: "28px 32px",
  boxShadow: "0 1px 3px rgba(0,0,0,0.3), 0 8px 24px -12px rgba(0,0,0,0.4)",
};
const label: React.CSSProperties = { fontSize: 12, fontWeight: 600, color: "var(--text-3)", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: 6, display: "block" };
const input: React.CSSProperties = { width: "100%", padding: "10px 14px", borderRadius: 8, border: "1px solid hsl(var(--border))", fontSize: 14, color: "var(--text-1)", background: "hsl(var(--muted))", outline: "none" };
const mono: React.CSSProperties = { fontFamily: "var(--font-jetbrains-mono, monospace)", fontVariantNumeric: "tabular-nums" };
const head: React.CSSProperties = { fontFamily: "var(--font-space-grotesk, sans-serif)", fontWeight: 600 };

const STEPS = [
  { id: 1, label: "Pipeline",          icon: Database },
  { id: 2, label: "Knowledge Sources", icon: FileText  },
  { id: 3, label: "Chunking",          icon: Sliders   },
  { id: 4, label: "Retrieval",         icon: Cpu       },
  { id: 5, label: "Generation",        icon: Rocket    },
  { id: 6, label: "Review & Launch",   icon: Check     },
];

const CHUNK_STRATEGIES = [
  { id: "semantic",     label: "Semantic Chunking",      desc: "Splits on semantic boundaries using sentence embeddings. Best for long-form docs." },
  { id: "hierarchical", label: "Hierarchical (Parent/Child)", desc: "Parent chunks for context, child chunks for precision. Best for structured PDFs." },
  { id: "late",         label: "Late Chunking",          desc: "Chunks after full-document embedding. Best for financial reports and legal docs." },
];

const RETRIEVAL_MODES = [
  { id: "hybrid",  label: "Hybrid (Dense + BM25)",  desc: "Combines pgvector cosine similarity with keyword BM25. Recommended for most cases." },
  { id: "dense",   label: "Dense Only",              desc: "Pure vector similarity via Gemini Embedding 2. Fastest, best for semantic queries." },
  { id: "hyde",    label: "HyDE + Reranking",        desc: "Hypothetical Document Embeddings + Cohere Rerank v3. Highest recall, higher cost." },
];

const LLM_OPTIONS = [
  { id: "gemini-flash-3.5", label: "Gemini Flash 3.5",  badge: "Primary",  cost: "$0.00015/1K tk" },
  { id: "kimi-k2.6",        label: "KiMi K2.6",         badge: "Fallback", cost: "$0.00012/1K tk" },
  { id: "gemini-3.5",       label: "Gemini 3.5",        badge: "Emergency",cost: "$0.00035/1K tk" },
];

const DEFAULT_FORM = {
  name: "", description: "", chunkStrategy: "semantic", topK: 5, chunkSize: 512, chunkOverlap: 64,
  retrievalMode: "hybrid", rerankEnabled: true, hydeEnabled: false, maxTokens: 4096,
  llm: "gemini-flash-3.5", temperature: 0.1, sources: [] as string[],
};

// 26-Jul-2026 (session 4) fix for the known refresh-persistence gap (see the
// reverted attempt's comment in goToStep2 below): a plain mid-wizard browser
// refresh previously lost step/form/pipelineId entirely (pure useState, no
// persistence). sessionStorage is a simpler, independent fix that sidesteps
// the useSearchParams()/Suspense hydration-timing bug the URL-param approach
// hit -- it's read synchronously in each field's lazy useState initializer,
// which only runs on the client after Suspense has already resolved (this
// component is always rendered inside <Suspense>, see the page export below).
const DRAFT_STORAGE_KEY = "autorag_configurator_draft_v1";

type SavedDraft = { step: number; form: typeof DEFAULT_FORM; pipelineId: string | null };

function loadSavedDraft(): SavedDraft | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.sessionStorage.getItem(DRAFT_STORAGE_KEY);
    return raw ? (JSON.parse(raw) as SavedDraft) : null;
  } catch {
    return null;
  }
}

function clearSavedDraft() {
  if (typeof window === "undefined") return;
  try {
    window.sessionStorage.removeItem(DRAFT_STORAGE_KEY);
  } catch {
    // best-effort only -- a failed clear just means a stale draft lingers
  }
}

function ConfiguratorWizard() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const resumePipelineId = searchParams.get("pipeline_id");

  // Explicit ?pipeline_id= navigation (e.g. a link from /documents) always
  // wins over a lingering sessionStorage draft -- it's a more specific signal
  // of user intent than "whatever was open in this tab before."
  const [step, setStep] = useState(() => {
    if (resumePipelineId) return 3;
    return loadSavedDraft()?.step ?? 1;
  });
  const [form, setForm] = useState(() => {
    if (resumePipelineId) return DEFAULT_FORM;
    return loadSavedDraft()?.form ?? DEFAULT_FORM;
  });
  const [launching, setLaunching] = useState(false);
  const [launchError, setLaunchError] = useState<string | null>(null);

  // Pipeline is created in 'draft' status right after step 1 (16-Jul-2026 fix)
  // so step 2's document upload has a real pipeline_id from the start --
  // previously it only existed at step 6, so uploading at step 2 sent users
  // to /documents with no pipeline to attach to (see PLAN.md Section 11).
  const [pipelineId, setPipelineId] = useState<string | null>(() => {
    if (resumePipelineId) return resumePipelineId;
    return loadSavedDraft()?.pipelineId ?? null;
  });
  const [creatingDraft, setCreatingDraft] = useState(false);
  const [draftError, setDraftError] = useState<string | null>(null);

  // Persist on every change so a mid-wizard refresh (no ?pipeline_id= link
  // involved) actually resumes instead of dropping back to a blank step 1.
  useEffect(() => {
    if (typeof window === "undefined") return;
    try {
      window.sessionStorage.setItem(
        DRAFT_STORAGE_KEY,
        JSON.stringify({ step, form, pipelineId } satisfies SavedDraft),
      );
    } catch {
      // best-effort only -- e.g. sessionStorage disabled/full; wizard still
      // works for the current tab session, it just won't survive a refresh
    }
  }, [step, form, pipelineId]);

  // Documents page links here as /configurator?pipeline_id=<id> once a draft
  // pipeline already has documents uploaded (16-Jul-2026) -- resume straight
  // into step 3 using the wizard's existing Back/Continue navigation, rather
  // than re-creating a pipeline or requiring a separate full "resume draft"
  // system (deferred to Version 5 -- docs/roadmap/VERSION_5_ROADMAP.md §2). Chunking/retrieval/
  // generation are already set to real defaults from creation; this just lets
  // the user see and adjust them before finishing.
  const [resuming, setResuming] = useState(Boolean(resumePipelineId));
  const [resumeError, setResumeError] = useState<string | null>(null);
  useEffect(() => {
    if (!resumePipelineId) return;
    let cancelled = false;
    apiClient
      .getPipeline(resumePipelineId)
      .then((detail) => {
        if (cancelled) return;
        setForm((f) => ({ ...f, name: detail.pipeline.name, chunkStrategy: detail.pipeline.chunk_strategy ?? f.chunkStrategy }));
      })
      .catch((err) => {
        if (!cancelled) setResumeError(err instanceof Error ? err.message : "Failed to load pipeline");
      })
      .finally(() => {
        if (!cancelled) setResuming(false);
      });
    return () => { cancelled = true; };
  }, [resumePipelineId]);

  // Step 2 gate (20-Jul-2026, per direct product review: "Configurator is a
  // pipeline creation wizard, not just a settings form... prevent users from
  // creating unusable pipelines"). GET /documents has no pipeline_id filter
  // param (confirmed via the backend route) -- fetched sorted by uploaded_at
  // desc (the route's own default) and filtered client-side, which is
  // correct here because a freshly-created draft's uploads are always the
  // most recent in the whole org, so they're always on page 1.
  const documentsQuery = useQuery({
    queryKey: ["configurator-documents", pipelineId],
    queryFn: () => apiClient.listDocuments({ page_size: 50, sort_by: "uploaded_at", sort_order: "desc" }),
    enabled: step === 2 && Boolean(pipelineId),
    refetchInterval: (query) => {
      const docs = query.state.data?.documents.filter((d) => d.project_id === pipelineId) ?? [];
      const stillProcessing = docs.some((d) => !["indexed", "failed", "archived"].includes(d.status));
      return stillProcessing || docs.length === 0 ? 4000 : false;
    },
  });
  const pipelineDocuments = (documentsQuery.data?.documents ?? []).filter((d) => d.project_id === pipelineId);
  const hasIndexedDocument = pipelineDocuments.some((d) => d.status === "indexed");

  const set = (k: string, v: unknown) => setForm((f) => ({ ...f, [k]: v }));

  async function goToStep2() {
    if (pipelineId) {
      setStep(2);
      return;
    }
    setCreatingDraft(true);
    setDraftError(null);
    try {
      const pipeline = await apiClient.createPipeline({
        name: form.name.trim() || `Pipeline ${new Date().toISOString().slice(0, 10)}`,
        chunk_strategy: form.chunkStrategy as ChunkStrategy,
        status: "draft",
      });
      setPipelineId(pipeline.id);
      // 26-Jul-2026 (session 3): an earlier attempted fix here (router.replace
      // to write pipeline_id into the URL) was reverted -- live-verified via
      // Playwright that the URL correctly retained ?pipeline_id=... after a
      // hard refresh, but the wizard still rendered a blank Step 1, meaning
      // useState(resumePipelineId ? 3 : 1) evaluated resumePipelineId as
      // falsy at first render despite the URL being correct (a
      // useSearchParams()/Suspense hydration-timing issue). RESOLVED
      // (26-Jul-2026, session 4) by sessionStorage persistence instead --
      // see loadSavedDraft()/DRAFT_STORAGE_KEY above, which sidesteps the
      // URL-timing bug entirely by not depending on useSearchParams() at all.
      setStep(2);
    } catch (err) {
      setDraftError(err instanceof Error ? err.message : "Failed to create pipeline");
    } finally {
      setCreatingDraft(false);
    }
  }

  async function launchPipeline() {
    if (!pipelineId) {
      setLaunchError("No pipeline was created -- go back to step 1 and try again.");
      return;
    }
    setLaunching(true);
    setLaunchError(null);
    try {
      // 25-Jul-2026 fix: previously finalizePipeline() only ever sent
      // {status:"pending"} -- every setting from steps 3-5 below was
      // collected in `form` and displayed in the review above, then
      // silently discarded. retrievalMode's UI id "hyde" maps to the
      // backend's "hybrid+hyde" (also folds in the separate hydeEnabled
      // toggle -- either one turning HyDE on is real user intent).
      // min_unified_score/PII are deliberately NOT included here -- see the
      // step 1 comment on why those two are not wizard-configurable.
      const backendRetrievalMode = form.retrievalMode === "dense" ? "dense" : "hybrid";
      const hydeEnabled = form.hydeEnabled || form.retrievalMode === "hyde";
      await apiClient.finalizePipeline(pipelineId, form.chunkStrategy as ChunkStrategy, {
        chunk_size: form.chunkSize,
        chunk_overlap: form.chunkOverlap,
        retrieval_mode: backendRetrievalMode,
        hyde_enabled: hydeEnabled,
        top_k: form.topK,
        reranker_enabled: form.rerankEnabled,
        llm_provider: form.llm,
        temperature: form.temperature,
        max_tokens: form.maxTokens,
      });
      toast({
        variant: "success",
        title: "Pipeline created",
        description: `"${form.name.trim() || "Untitled pipeline"}" is ready — upload documents to start ingestion.`,
      });
      clearSavedDraft();
      router.push(`/pipelines/${pipelineId}/history`);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to launch pipeline";
      setLaunchError(message);
      setLaunching(false);
      toast({ variant: "destructive", title: "Pipeline launch failed", description: message });
    }
  }

  if (resuming) {
    return (
      <AppShell title="Pipeline Studio" mode="builder">
        <div style={{ ...card, display: "flex", alignItems: "center", justifyContent: "center", gap: 10, color: "var(--text-3)" }}>
          <Loader2 style={{ width: 18, height: 18 }} className="motion-safe:animate-spin" />
          Loading your pipeline…
        </div>
      </AppShell>
    );
  }

  if (resumeError) {
    return (
      <AppShell title="Pipeline Studio" mode="builder">
        <div style={{ ...card, color: "#FB7185" }}>
          Couldn&apos;t load that pipeline: {resumeError}.{" "}
          <Link href="/configurator" style={{ color: "var(--brand-1)", fontWeight: 600 }}>Start a new one</Link> instead.
        </div>
      </AppShell>
    );
  }

  return (
    <AppShell
      title={resumePipelineId ? "Finish Pipeline Setup" : "Create a Pipeline"}
      description={
        resumePipelineId
          ? "Your documents are uploaded — review chunking and retrieval, then launch the 9-agent loop."
          : "Six quick steps: name it, point it at your documents, pick chunking and retrieval, then launch — the 9-agent loop takes it from there."
      }
      mode="builder"
    >
      {/* Step Progress */}
      <div style={card}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 16 }}>
          <span style={{ fontSize: 12.5, fontWeight: 600, color: "var(--text-3)" }}>
            Step {step} of {STEPS.length} <span style={{ color: "var(--text-2)" }}>·</span> Estimated time: 2 minutes
          </span>
          <span style={{ ...mono, fontSize: 12.5, fontWeight: 700, color: "var(--brand-1)" }}>
            {Math.round((step / STEPS.length) * 100)}% Complete
          </span>
        </div>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          {STEPS.map((s, i) => {
            const done = step > s.id;
            const active = step === s.id;
            const Icon = s.icon;
            return (
              <div key={s.id} style={{ display: "flex", alignItems: "center", flex: i < STEPS.length - 1 ? 1 : undefined }}>
                <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 6 }}>
                  <div style={{
                    width: 38, height: 38, borderRadius: "50%", display: "flex", alignItems: "center", justifyContent: "center",
                    background: done ? "#10B981" : active ? "linear-gradient(135deg,#F59E0B,#EA580C)" : "hsl(var(--muted))",
                    border: active ? "none" : done ? "none" : "1px solid hsl(var(--border))",
                    cursor: done ? "pointer" : "default",
                    boxShadow: active ? "0 4px 12px rgba(37,99,235,0.35)" : "none",
                  }}
                    onClick={() => done && setStep(s.id)}
                  >
                    {done
                      ? <Check style={{ width: 16, height: 16, color: "var(--text-1)" }} />
                      : <Icon style={{ width: 16, height: 16, color: active ? "var(--text-1)" : "var(--text-3)" }} />}
                  </div>
                  <span style={{ fontSize: 11, fontWeight: 600, color: active ? "var(--brand-1)" : done ? "#10B981" : "var(--text-3)", maxWidth: 76, textAlign: "center", lineHeight: 1.3 }}>{s.label}</span>
                </div>
                {i < STEPS.length - 1 && (
                  <div style={{ flex: 1, height: 2, margin: "0 8px 18px", background: done ? "#10B981" : "hsl(var(--border))" }} />
                )}
              </div>
            );
          })}
        </div>
      </div>

      {/* Step Content */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 300px", gap: 24, alignItems: "start" }}>
        <div style={card}>
          {/* STEP 1 — Pipeline Identity */}
          {step === 1 && (
            <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
              <div>
                <h2 style={{ ...head, fontSize: 22, color: "var(--text-1)", margin: "0 0 4px" }}>Pipeline Identity</h2>
                <p style={{ fontSize: 14, color: "var(--text-3)", margin: 0 }}>Name and describe the RAG pipeline you are building.</p>
              </div>
              <div>
                <label style={label}>Pipeline Name *</label>
                <input style={input} placeholder="e.g. NEET-UG-Support-v1" value={form.name} onChange={(e) => set("name", e.target.value)} />
                <p style={{ fontSize: 12, color: "var(--text-3)", margin: "6px 0 0" }}>
                  Example: <span style={{ color: "var(--text-3)" }}>Customer Support Knowledge Base</span>
                </p>
              </div>
              <div>
                <label style={label}>Description</label>
                <textarea style={{ ...input, height: 88, resize: "vertical" }} placeholder="What domain does this pipeline serve? What queries will it answer?" value={form.description} onChange={(e) => set("description", e.target.value)} />
                <p style={{ fontSize: 12, color: "var(--text-3)", margin: "6px 0 0" }}>
                  Briefly describe what documents this pipeline will answer questions from.
                </p>
              </div>
              <div>
                {/* Not a select: PII masking is mandatory, platform-wide,
                    non-configurable (CLAUDE.md Forbidden Pattern #3) -- this
                    is a status confirmation, never an input. Unified Score
                    Gate removed 25-Jul-2026: it rendered as a configurable
                    select but nothing ever read the value -- and wiring it
                    for real would mean building a bypass of the >= 0.85
                    deployment gate, which Forbidden Pattern #2 prohibits
                    outright. */}
                <label style={label}>PII Masking</label>
                <div style={{ ...input, display: "flex", alignItems: "center", color: "var(--text-2)" }}>
                  Enabled (Required)
                </div>
              </div>
            </div>
          )}

          {/* STEP 2 — Document Sources */}
          {step === 2 && (
            <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
              <div>
                <h2 style={{ ...head, fontSize: 22, color: "var(--text-1)", margin: "0 0 4px" }}>Document Sources</h2>
                <p style={{ fontSize: 14, color: "var(--text-3)", margin: "0 0 4px" }}>
                  Add sources the Ingestion Agent will parse, PII-mask, chunk, and embed.
                </p>
                {/* 26-Jul-2026: each pipeline embeds into its own isolated vector
                    partition (Immutable Versioned Indexes) -- a document uploaded
                    to one pipeline is not searchable from another, so this can't
                    be a "pick from existing" step. State that plainly instead of
                    building a picker that would silently return zero results for
                    documents from other pipelines. */}
                <p style={{ fontSize: 12, color: "var(--text-3)", margin: 0 }}>
                  Documents uploaded here belong to <strong>this pipeline only</strong>. To browse or manage
                  documents across all pipelines, see the{" "}
                  <Link href="/documents" style={{ color: "var(--accent, #F97316)", textDecoration: "underline" }}>
                    Documents
                  </Link>{" "}
                  page.
                </p>
              </div>

              {/* Tiny always-visible reminder of which pipeline is being
                  configured, and what's already been decided about it -- per
                  direct product review: "reminds users which pipeline they're
                  configuring." Real form state only -- "Default" for anything
                  not yet chosen at this step. */}
              <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: "6px 14px", padding: "10px 16px", borderRadius: 10, background: "rgba(15,23,42,0.03)", border: "1px solid hsl(var(--border))" }}>
                {[
                  { k: "Pipeline", v: form.name.trim() || "Untitled" },
                  { k: "PII", v: "Enabled" },
                  { k: "Chunking", v: CHUNK_STRATEGIES.find((s) => s.id === form.chunkStrategy)?.label ?? "Default" },
                ].map(({ k, v }, i, arr) => (
                  <span key={k} style={{ display: "flex", alignItems: "center", gap: 14 }}>
                    <span style={{ fontSize: 12.5 }}>
                      <span style={{ color: "var(--text-3)" }}>{k}</span>{" "}
                      <span style={{ color: "var(--text-1)", fontWeight: 600 }}>{v}</span>
                    </span>
                    {i < arr.length - 1 && <span style={{ color: "hsl(var(--border))" }}>•</span>}
                  </span>
                ))}
              </div>

              {!hasIndexedDocument && (
                <div role="status" style={{ display: "flex", gap: 10, padding: "12px 16px", borderRadius: 10, background: "rgba(37,99,235,0.08)", border: "1px solid rgba(37,99,235,0.25)" }}>
                  <span style={{ fontSize: 15, color: "var(--brand-1)", flexShrink: 0, lineHeight: "20px" }}>ⓘ</span>
                  <p style={{ fontSize: 13, color: "var(--brand-1)", margin: 0 }}>
                    Every pipeline requires at least one document. Upload a PDF, DOCX, or TXT file to continue.
                  </p>
                </div>
              )}

              {/* 20-Jul-2026: embedded the real upload widget directly (was a
                  <Link> out to /documents, which broke the wizard's flow --
                  see chat). Same component, same POST /documents endpoint,
                  same Ingestion agent -- presentation-only change. */}
              <UploadPanel
                projectId={pipelineId ?? ""}
                pipelinesLoading={!pipelineId}
                onUploadComplete={() => void documentsQuery.refetch()}
              />

              {/* Live status per uploaded document -- polls every 4s until
                  every document reaches a terminal state (indexed/failed). */}
              {pipelineDocuments.length > 0 && (
                <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                  {pipelineDocuments.map((doc) => {
                    const STATUS_META: Record<DocumentStatus, { icon: typeof CheckCircle2; color: string; label: string }> = {
                      indexed: { icon: CheckCircle2, color: "#34D399", label: "Indexed" },
                      failed: { icon: XCircle, color: "#FB7185", label: "Failed" },
                      uploaded: { icon: Clock, color: "var(--text-3)", label: "Uploaded" },
                      validating: { icon: Loader2, color: "var(--brand-1)", label: "Validating" },
                      chunking: { icon: Loader2, color: "var(--brand-1)", label: "Chunking" },
                      embedding: { icon: Loader2, color: "var(--brand-1)", label: "Embedding" },
                      archived: { icon: Clock, color: "var(--text-3)", label: "Archived" },
                    };
                    const meta = STATUS_META[doc.status];
                    const spinning = !["indexed", "failed", "uploaded", "archived"].includes(doc.status);
                    return (
                      <div
                        key={doc.id}
                        style={{
                          display: "flex", alignItems: "center", gap: 10, padding: "10px 14px",
                          borderRadius: 10, border: "1px solid hsl(var(--border))", background: "rgba(15,23,42,0.03)",
                        }}
                      >
                        <meta.icon
                          style={{ width: 16, height: 16, color: meta.color, flexShrink: 0 }}
                          className={spinning ? "motion-safe:animate-spin" : undefined}
                        />
                        <span style={{ fontSize: 13, color: "var(--text-1)", flex: 1 }}>{doc.file_name}</span>
                        <span style={{ fontSize: 12, fontWeight: 600, color: meta.color }}>{meta.label}</span>
                      </div>
                    );
                  })}
                </div>
              )}

              {/* Only file upload is real (POST /documents, live-verified all
                  session). URL/Confluence/Supabase-table ingestion have no
                  backend route -- confirmed via repo-wide search -- so they
                  stay under a "Coming Soon" sub-header, ready to slot into
                  this same step once those connectors exist. */}
              <div>
                <p style={{ fontSize: 11, fontWeight: 700, color: "var(--text-3)", textTransform: "uppercase", letterSpacing: "0.05em", margin: "4px 0 10px" }}>
                  Coming Soon
                </p>
                <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                  {[
                    { icon: Globe,  label: "Web URL / Sitemap",  desc: "Crawl a URL or sitemap. JS-rendered pages supported.", color: "var(--brand-2)" },
                    { icon: Database, label: "Confluence Space", desc: "Sync an Atlassian Confluence space (OAuth 2.0 required).", color: "#06B6D4" },
                    { icon: Link2,  label: "Supabase Table",     desc: "Import rows from an existing Supabase PostgreSQL table.", color: "#10B981" },
                  ].map(({ icon: Icon, label: lbl, desc, color }) => (
                    <div
                      key={lbl}
                      style={{
                        display: "flex", gap: 14, padding: "14px 18px", borderRadius: 12,
                        border: "1.5px dashed rgba(15,23,42,0.15)", background: "hsl(var(--muted))",
                        alignItems: "flex-start", opacity: 0.55,
                      }}
                    >
                      <div style={{ width: 36, height: 36, borderRadius: 8, background: `${color}18`, display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>
                        <Icon style={{ width: 18, height: 18, color }} />
                      </div>
                      <div style={{ flex: 1 }}>
                        <div style={{ fontSize: 14, fontWeight: 600, color: "var(--text-1)" }}>{lbl}</div>
                        <div style={{ fontSize: 12.5, color: "var(--text-3)", marginTop: 3 }}>{desc}</div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* STEP 3 — Chunking Strategy */}
          {step === 3 && (
            <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
              <div>
                <h2 style={{ ...head, fontSize: 22, color: "var(--text-1)", margin: "0 0 4px" }}>Chunking Strategy</h2>
                <p style={{ fontSize: 14, color: "var(--text-3)", margin: 0 }}>How the Ingestion Agent splits your documents before embedding.</p>
              </div>
              {CHUNK_STRATEGIES.map((s) => (
                <div key={s.id}
                  onClick={() => set("chunkStrategy", s.id)}
                  style={{ padding: "16px 20px", borderRadius: 12, border: `2px solid ${form.chunkStrategy === s.id ? "var(--brand-1)" : "hsl(var(--border))"}`, background: form.chunkStrategy === s.id ? "rgba(37,99,235,0.10)" : "hsl(var(--muted))", cursor: "pointer" }}
                >
                  <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 4 }}>
                    <div style={{ width: 16, height: 16, borderRadius: "50%", border: "2px solid", borderColor: form.chunkStrategy === s.id ? "var(--brand-1)" : "rgba(15,23,42,0.2)", background: form.chunkStrategy === s.id ? "var(--brand-1)" : "transparent" }} />
                    <span style={{ fontSize: 14, fontWeight: 600, color: "var(--text-1)" }}>{s.label}</span>
                  </div>
                  <p style={{ fontSize: 13, color: "var(--text-3)", margin: "0 0 0 26px" }}>{s.desc}</p>
                </div>
              ))}
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 16 }}>
                <div>
                  <label style={label}>Chunk Size (tokens)</label>
                  <input style={{ ...input, ...mono }} type="number" value={form.chunkSize} onChange={(e) => set("chunkSize", +e.target.value)} />
                </div>
                <div>
                  <label style={label}>Overlap (tokens)</label>
                  <input style={{ ...input, ...mono }} type="number" value={form.chunkOverlap} onChange={(e) => set("chunkOverlap", +e.target.value)} />
                </div>
                <div>
                  <label style={label}>Min Chunk (tokens)</label>
                  <input style={{ ...input, ...mono }} type="number" defaultValue={128} />
                </div>
              </div>
            </div>
          )}

          {/* STEP 4 — Retrieval Config */}
          {step === 4 && (
            <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
              <div>
                <h2 style={{ ...head, fontSize: 22, color: "var(--text-1)", margin: "0 0 4px" }}>Retrieval Configuration</h2>
                <p style={{ fontSize: 14, color: "var(--text-3)", margin: 0 }}>4-stage retrieval stack: Dense → Hybrid → Reranker → HyDE.</p>
              </div>
              {RETRIEVAL_MODES.map((m) => (
                <div key={m.id}
                  onClick={() => set("retrievalMode", m.id)}
                  style={{ padding: "16px 20px", borderRadius: 12, border: `2px solid ${form.retrievalMode === m.id ? "var(--brand-2)" : "hsl(var(--border))"}`, background: form.retrievalMode === m.id ? "rgba(124,58,237,0.12)" : "hsl(var(--muted))", cursor: "pointer" }}
                >
                  <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 4 }}>
                    <div style={{ width: 16, height: 16, borderRadius: "50%", border: "2px solid", borderColor: form.retrievalMode === m.id ? "var(--brand-2)" : "rgba(15,23,42,0.2)", background: form.retrievalMode === m.id ? "var(--brand-2)" : "transparent" }} />
                    <span style={{ fontSize: 14, fontWeight: 600, color: "var(--text-1)" }}>{m.label}</span>
                  </div>
                  <p style={{ fontSize: 13, color: "var(--text-3)", margin: "0 0 0 26px" }}>{m.desc}</p>
                </div>
              ))}
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
                <div>
                  <label style={label}>Top-K Retrieval</label>
                  <input style={{ ...input, ...mono }} type="number" value={form.topK} min={1} max={20} onChange={(e) => set("topK", +e.target.value)} />
                </div>
                <div>
                  <label style={label}>Cohere Rerank Top-N</label>
                  <input style={{ ...input, ...mono }} type="number" defaultValue={3} min={1} max={10} />
                </div>
              </div>
              <div style={{ display: "flex", gap: 12 }}>
                {[{ k: "rerankEnabled", v: form.rerankEnabled, label: "Cohere Rerank v3" }, { k: "hydeEnabled", v: form.hydeEnabled, label: "HyDE Expansion" }].map(({ k, v, label: lbl }) => (
                  <button key={k} onClick={() => set(k, !v)} style={{ display: "flex", alignItems: "center", gap: 8, padding: "8px 16px", borderRadius: 8, border: "1.5px solid", borderColor: v ? "var(--brand-1)" : "hsl(var(--border))", background: v ? "rgba(37,99,235,0.12)" : "hsl(var(--muted))", fontSize: 13, fontWeight: 600, color: v ? "var(--brand-1)" : "var(--text-3)", cursor: "pointer" }}>
                    <div style={{ width: 14, height: 14, borderRadius: 3, background: v ? "var(--brand-1)" : "transparent", border: "2px solid", borderColor: v ? "var(--brand-1)" : "rgba(15,23,42,0.2)", display: "flex", alignItems: "center", justifyContent: "center" }}>
                      {v && <Check style={{ width: 9, height: 9, color: "var(--text-1)" }} />}
                    </div>
                    {lbl}
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* STEP 5 — Generation Config */}
          {step === 5 && (
            <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
              <div>
                <h2 style={{ ...head, fontSize: 22, color: "var(--text-1)", margin: "0 0 4px" }}>Generation Configuration</h2>
                <p style={{ fontSize: 14, color: "var(--text-3)", margin: 0 }}>LLM selection and generation parameters for the 9-agent loop.</p>
              </div>
              {LLM_OPTIONS.map((l) => (
                <div key={l.id}
                  onClick={() => set("llm", l.id)}
                  style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "14px 18px", borderRadius: 12, border: `2px solid ${form.llm === l.id ? "var(--brand-1)" : "hsl(var(--border))"}`, background: form.llm === l.id ? "rgba(37,99,235,0.12)" : "hsl(var(--muted))", cursor: "pointer" }}
                >
                  <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                    <div style={{ width: 16, height: 16, borderRadius: "50%", border: "2px solid", borderColor: form.llm === l.id ? "var(--brand-1)" : "rgba(15,23,42,0.2)", background: form.llm === l.id ? "var(--brand-1)" : "transparent" }} />
                    <span style={{ fontSize: 14, fontWeight: 600, color: "var(--text-1)" }}>{l.label}</span>
                    <span style={{ fontSize: 11, fontWeight: 700, padding: "2px 8px", borderRadius: 999, background: "rgba(37,99,235,0.10)", color: "var(--brand-1)" }}>{l.badge}</span>
                  </div>
                  <span style={{ ...mono, fontSize: 12, color: "var(--text-3)" }}>{l.cost}</span>
                </div>
              ))}
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
                <div>
                  <label style={label}>Max Completion Tokens</label>
                  <input style={{ ...input, ...mono }} type="number" value={form.maxTokens} onChange={(e) => set("maxTokens", +e.target.value)} />
                </div>
                <div>
                  <label style={label}>Temperature</label>
                  <input style={{ ...input, ...mono }} type="number" value={form.temperature} step={0.05} min={0} max={1} onChange={(e) => set("temperature", +e.target.value)} />
                </div>
              </div>
              <div>
                <label style={label}>Safety Constraints (added to all prompts)</label>
                <textarea readOnly style={{ ...input, height: 64, resize: "none", background: "rgba(16,185,129,0.07)", color: "#027A48", fontSize: 12, borderColor: "rgba(16,185,129,0.20)" }}
                  value={`Do not invent facts if the context is empty. Never reveal customer PII. If unsure, respond: "I don't have enough context to answer."`} />
              </div>
            </div>
          )}

          {/* STEP 6 — Review */}
          {step === 6 && (
            <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
              <div>
                <h2 style={{ ...head, fontSize: 22, color: "var(--text-1)", margin: "0 0 4px" }}>Review & Launch</h2>
                <p style={{ fontSize: 14, color: "var(--text-3)", margin: 0 }}>Review your configuration before the 9-agent loop begins.</p>
              </div>
              {[
                { label: "Pipeline Name",    value: form.name || "—"               },
                { label: "Chunk Strategy",   value: form.chunkStrategy             },
                { label: "Chunk Size",       value: `${form.chunkSize} tokens`     },
                { label: "Chunk Overlap",    value: `${form.chunkOverlap} tokens`  },
                { label: "Retrieval Mode",   value: form.retrievalMode             },
                { label: "Top-K",            value: String(form.topK)              },
                { label: "Cohere Rerank",    value: form.rerankEnabled ? "On" : "Off" },
                { label: "HyDE",             value: form.hydeEnabled ? "On" : "Off"   },
                { label: "LLM",              value: form.llm                       },
                { label: "Temperature",      value: String(form.temperature)       },
                { label: "Max Tokens",       value: String(form.maxTokens)         },
              ].map(({ label: lbl, value }) => (
                <div key={lbl} style={{ display: "flex", justifyContent: "space-between", padding: "10px 0", borderBottom: "1px solid hsl(var(--border))" }}>
                  <span style={{ fontSize: 13, color: "var(--text-3)" }}>{lbl}</span>
                  <span style={{ ...mono, fontSize: 13, fontWeight: 600, color: "var(--text-1)" }}>{value}</span>
                </div>
              ))}
              {launchError && (
                <div role="alert" style={{ padding: "10px 14px", borderRadius: 8, background: "rgba(239,68,68,0.1)", border: "1px solid rgba(239,68,68,0.3)", color: "#FB7185", fontSize: 13 }}>
                  {launchError}
                </div>
              )}
              <button
                onClick={() => void launchPipeline()}
                disabled={launching}
                style={{
                  marginTop: 8, padding: "13px", borderRadius: 10, border: "none",
                  cursor: launching ? "not-allowed" : "pointer",
                  opacity: launching ? 0.7 : 1,
                  background: "linear-gradient(135deg,#F59E0B,#EA580C)", color: "#ffffff", fontSize: 15, fontWeight: 700,
                  boxShadow: "0 8px 24px -8px rgba(37,99,235,0.6)",
                  display: "flex", alignItems: "center", justifyContent: "center", gap: 8,
                }}
              >
                {launching && <Loader2 style={{ width: 16, height: 16 }} className="motion-safe:animate-spin" />}
                {launching ? "Launching Pipeline…" : "Launch Pipeline — Start 9-Agent Loop"}
              </button>
            </div>
          )}

          {/* Navigation */}
          <div style={{ display: "flex", justifyContent: "space-between", marginTop: 28 }}>
            <button
              onClick={() => setStep((s) => Math.max(1, s - 1))}
              disabled={step === 1}
              style={{ padding: "10px 22px", borderRadius: 8, border: "1.5px solid rgba(15,23,42,0.15)", background: "hsl(var(--muted))", fontSize: 14, fontWeight: 600, color: step === 1 ? "var(--text-3)" : "var(--text-3)", cursor: step === 1 ? "not-allowed" : "pointer" }}
            >
              Back
            </button>
            {step < 6 && (() => {
              // 20-Jul-2026: Step 2 now also gates Continue -- at least one
              // document must reach "indexed" before the wizard proceeds
              // (per direct product review: creating a pipeline with zero
              // real sources just defers the same failure to evaluation).
              const continueBlocked =
                creatingDraft ||
                (step === 1 && !form.name.trim()) ||
                (step === 2 && !hasIndexedDocument);
              return (
              <button
                onClick={() => void (step === 1 ? goToStep2() : setStep((s) => Math.min(6, s + 1)))}
                disabled={continueBlocked}
                style={{
                  display: "flex", alignItems: "center", gap: 6, padding: "10px 22px", borderRadius: 8, border: "none",
                  background: "linear-gradient(135deg,#F59E0B,#EA580C)", color: "#ffffff", fontSize: 14, fontWeight: 700,
                  cursor: continueBlocked ? "not-allowed" : "pointer",
                  opacity: continueBlocked ? 0.55 : 1,
                  boxShadow: continueBlocked ? "none" : "0 6px 18px -6px rgba(37,99,235,0.55)",
                }}
              >
                {creatingDraft && <Loader2 style={{ width: 16, height: 16 }} className="motion-safe:animate-spin" />}
                {creatingDraft ? "Creating Pipeline…" : "Continue"}
                {!creatingDraft && <ChevronRight style={{ width: 16, height: 16 }} />}
              </button>
              );
            })()}
          </div>
          {step === 2 && !hasIndexedDocument && pipelineDocuments.length === 0 && (
            <p style={{ marginTop: 10, fontSize: 12, color: "var(--text-3)" }}>
              Continue unlocks once at least one document finishes indexing.
            </p>
          )}
          {step === 1 && draftError && (
            <div role="alert" style={{ marginTop: 12, padding: "10px 14px", borderRadius: 8, background: "rgba(239,68,68,0.1)", border: "1px solid rgba(239,68,68,0.3)", color: "#FB7185", fontSize: 13 }}>
              {draftError}
            </div>
          )}
        </div>

        {/* Right sidebar — 20-Jul-2026: replaced the always-visible 9-agent
            "Pipeline Preview" list (overloaded new users before they'd even
            named the pipeline, per direct product review) with a compact,
            progressively-filling "Configuration Summary" for steps 1-5. The
            full agent list only appears on Review, where seeing exactly what
            the launch triggers is actually useful. */}
        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          {step < 6 ? (
            <div style={card}>
              <div style={{ ...head, fontSize: 14, color: "var(--text-1)", marginBottom: 4 }}>Configuration Summary</div>
              <p style={{ fontSize: 11.5, color: "var(--text-3)", margin: "0 0 14px" }}>What AutoRAG will do automatically</p>

              <div style={{ ...head, fontSize: 11, fontWeight: 700, color: "var(--text-3)", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: 10 }}>Platform</div>
              {["9 Autonomous Agents", "PII Detection", "Hybrid Retrieval", "Unified Score Gate", "Human Approval"].map((item) => (
                <div key={item} style={{ display: "flex", alignItems: "center", gap: 8, padding: "5px 0" }}>
                  <Check style={{ width: 13, height: 13, color: "#10B981", flexShrink: 0 }} />
                  <span style={{ fontSize: 12.5, color: "var(--text-2)" }}>{item}</span>
                </div>
              ))}

              <div style={{ height: 1, background: "hsl(var(--border))", margin: "16px 0" }} />

              <div style={{ ...head, fontSize: 11, fontWeight: 700, color: "var(--text-3)", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: 10 }}>Current Configuration</div>
              {[
                { k: "Pipeline", v: form.name.trim() || "—" },
                { k: "Chunking",      v: step >= 3 ? (CHUNK_STRATEGIES.find((s) => s.id === form.chunkStrategy)?.label ?? "Default") : "Default" },
                { k: "Retrieval",     v: step >= 4 ? (RETRIEVAL_MODES.find((m) => m.id === form.retrievalMode)?.label ?? "Default") : "Default" },
                { k: "LLM",           v: step >= 5 ? (LLM_OPTIONS.find((l) => l.id === form.llm)?.label ?? "Default") : "Default" },
              ].map(({ k, v }) => (
                <div key={k} style={{ display: "flex", justifyContent: "space-between", padding: "7px 0", borderBottom: "1px solid hsl(var(--border))" }}>
                  <span style={{ fontSize: 12, color: "var(--text-3)" }}>{k}</span>
                  <span style={{ fontSize: 12, fontWeight: 600, color: "var(--text-1)", textAlign: "right" }}>{v}</span>
                </div>
              ))}
            </div>
          ) : (
            <>
              <div style={card}>
                <div style={{ ...head, fontSize: 14, color: "var(--text-1)", marginBottom: 14 }}>Platform Agents</div>
                {[
                  { label: "Ingestion Agent",    color: "#06B6D4",  desc: "Parse → PII mask → chunk" },
                  { label: "Builder Agent",      color: "var(--brand-1)",  desc: "Gemini Embedding 2 → pgvector" },
                  { label: "Query Rewriter",     color: "var(--brand-2)",  desc: "Improve ambiguous queries" },
                  { label: "Compressor Agent",   color: "#F59E0B",  desc: "Fit within token budget" },
                  { label: "Evaluator Agent",    color: "#10B981",  desc: "Unified Score + RAGAS" },
                  { label: "Observer Agent",     color: "#38BDF8",  desc: "Latency + cost + quality" },
                  { label: "Diagnoser Agent",    color: "#EF4444",  desc: "F-01…F-06 failure types" },
                  { label: "Improver Agent",     color: "#8B5CF6",  desc: "Generate variant configs" },
                  { label: "Deployer Agent",     color: "#10B981",  desc: "Blue/Green ECS Fargate" },
                ].map(({ label: lbl, color, desc }) => (
                  <div key={lbl} style={{ display: "flex", gap: 10, padding: "8px 0", borderBottom: "1px solid hsl(var(--border))", alignItems: "flex-start" }}>
                    <div style={{ width: 8, height: 8, borderRadius: "50%", background: color, marginTop: 4, flexShrink: 0 }} />
                    <div>
                      <div style={{ fontSize: 12.5, fontWeight: 600, color: "var(--text-1)" }}>{lbl}</div>
                      <div style={{ fontSize: 11, color: "var(--text-3)" }}>{desc}</div>
                    </div>
                  </div>
                ))}
              </div>
              <div style={card}>
                {/* Fixed platform constant, not pipeline-configurable (CLAUDE.md
                    Forbidden Pattern #2 -- the >= 0.85 gate is non-bypassable).
                    Hardcoded, not read from form state -- there is no field
                    that could ever change this value. */}
                <div style={{ ...head, fontSize: 14, color: "var(--text-1)", marginBottom: 10 }}>Unified Score Gate</div>
                <div style={{ ...mono, fontSize: 28, fontWeight: 700, color: "#10B981", marginBottom: 4 }}>≥ 0.85</div>
                <div style={{ fontSize: 12, color: "var(--text-3)" }}>Pipeline must pass to deploy automatically. Score = 0.25R + 0.35Q + 0.25F − 0.10L − 0.05C</div>
              </div>
            </>
          )}
        </div>
      </div>
    </AppShell>
  );
}

export default function ConfiguratorPage() {
  return (
    <Suspense fallback={null}>
      <ConfiguratorWizard />
    </Suspense>
  );
}
