"use client";

import { useState, useMemo } from "react";
import { BookOpen, Terminal, Code2, Layers, ShieldCheck, Copy, Check, Sparkles, ChevronRight, Network, Rocket, Search, ListChecks } from "lucide-react";

type DocsTab = "quickstart" | "client" | "rest" | "evaluation" | "architecture" | "deployment";

interface DocsTopic {
  id: DocsTab;
  label: string;
  icon: React.ReactNode;
  keywords: string;
}

const DOCS_TOPICS: DocsTopic[] = [
  { id: "quickstart", label: "Quickstart Guide", icon: <Terminal className="w-4 h-4" />, keywords: "quickstart install setup docker make uv npm" },
  { id: "client", label: "Client Integration", icon: <Code2 className="w-4 h-4" />, keywords: "client integration sdk fetch typescript rest" },
  { id: "rest", label: "REST API Reference", icon: <Layers className="w-4 h-4" />, keywords: "rest api reference endpoint retrieve envelope" },
  { id: "evaluation", label: "3-Layer Evaluation", icon: <ShieldCheck className="w-4 h-4" />, keywords: "evaluation unified score ragas adversarial faithfulness" },
  { id: "architecture", label: "Architecture", icon: <Network className="w-4 h-4" />, keywords: "architecture agents langgraph orchestration llm failover" },
  { id: "deployment", label: "Deployment", icon: <Rocket className="w-4 h-4" />, keywords: "deployment ecs fargate rollback ci cd terraform" },
];

export function DocsSection() {
  const [activeTab, setActiveTab] = useState<DocsTab>("quickstart");
  const [copiedCode, setCopiedCode] = useState<string | null>(null);
  const [search, setSearch] = useState("");

  const handleCopy = (text: string, label: string) => {
    navigator.clipboard.writeText(text);
    setCopiedCode(label);
    setTimeout(() => setCopiedCode(null), 2000);
  };

  const filteredTopics = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return DOCS_TOPICS;
    return DOCS_TOPICS.filter((t) => t.label.toLowerCase().includes(q) || t.keywords.includes(q));
  }, [search]);

  return (
    <section id="docs" className="py-24 bg-slate-900 relative border-t border-slate-800">
      <div className="absolute top-1/3 right-10 w-96 h-96 bg-blue-500/10 rounded-full blur-3xl pointer-events-none" />

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 relative z-10 space-y-12">
        <div className="text-center max-w-3xl mx-auto space-y-4">
          <div className="inline-flex items-center gap-2 px-3.5 py-1 rounded-full bg-blue-500/10 border border-blue-500/20 text-blue-400 text-xs font-mono font-bold uppercase tracking-wider">
            <BookOpen className="w-3.5 h-3.5" />
            <span>Developer Documentation</span>
          </div>
          <h2 className="text-3xl sm:text-5xl font-black text-white tracking-tight">
            Build Autonomous RAG in Minutes
          </h2>
          <p className="text-slate-400 text-base sm:text-lg font-medium">
            A production FastAPI backend behind 46 versioned REST endpoints — open, self-hosted, and deployable to your own AWS ECS Fargate cluster. No proprietary SDK lock-in.
          </p>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
          <div className="lg:col-span-3 space-y-2 bg-slate-950/80 p-3 rounded-2xl border border-slate-800">
            <div className="px-3 py-2 text-[10px] font-mono font-bold uppercase text-slate-500 tracking-wider">
              Documentation Topics
            </div>

            <div className="relative px-1 pb-1">
              <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-slate-500 pointer-events-none" />
              <input
                type="text"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Search docs..."
                className="w-full pl-9 pr-3 py-2 rounded-xl bg-slate-900 border border-slate-800 text-xs text-slate-200 placeholder:text-slate-500 font-medium focus:outline-none focus:ring-2 focus:ring-orange-500/40 focus:border-orange-500/60 transition-all"
              />
            </div>

            {filteredTopics.length === 0 && (
              <div className="px-3 py-4 text-[11px] text-slate-500 font-medium text-center">No topics match &quot;{search}&quot;.</div>
            )}

            {filteredTopics.map((topic) => (
              <button
                key={topic.id}
                onClick={() => setActiveTab(topic.id)}
                className={`w-full text-left p-3 rounded-xl transition-all duration-200 flex items-center justify-between text-xs font-bold cursor-pointer ${
                  activeTab === topic.id ? "bg-orange-500 text-white shadow-md shadow-orange-500/20" : "text-slate-400 hover:text-white hover:bg-slate-900"
                }`}
              >
                <div className="flex items-center gap-2.5">
                  {topic.icon}
                  <span>{topic.label}</span>
                </div>
                <ChevronRight className="w-4 h-4" />
              </button>
            ))}

            <div className="pt-4 border-t border-slate-800 space-y-2">
              <div className="px-3 text-[10px] font-mono font-bold uppercase text-slate-500">
                Local Setup
              </div>
              <div className="p-3 bg-slate-900 rounded-xl border border-slate-800 flex items-center justify-between text-xs font-mono text-emerald-400">
                <span>make setup</span>
                <button
                  onClick={() => handleCopy("make setup", "cli")}
                  className="p-1 text-slate-400 hover:text-white transition-colors cursor-pointer"
                >
                  {copiedCode === "cli" ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
                </button>
              </div>
            </div>
          </div>

          <div className="lg:col-span-9 bg-slate-950 rounded-3xl border border-slate-800 p-6 sm:p-8 shadow-2xl space-y-6">
            {activeTab === "quickstart" && (
              <div className="space-y-6 animate-fade-in-marketing">
                <div>
                  <h3 className="text-2xl font-black text-white flex items-center gap-2">
                    <Terminal className="w-6 h-6 text-orange-400" />
                    <span>Quickstart</span>
                  </h3>
                  <p className="text-xs text-slate-400 font-medium mt-1">
                    Clone the repo, install dependencies, and bring up the FastAPI backend plus the Next.js dashboard locally.
                  </p>
                </div>

                <div className="p-4 rounded-2xl bg-slate-900 border border-slate-800 space-y-2.5">
                  <div className="flex items-center gap-2 text-xs font-mono font-bold text-slate-300">
                    <ListChecks className="w-4 h-4 text-emerald-400" />
                    <span>Prerequisites</span>
                  </div>
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                    {["Python 3.11", "Node.js 20+", "Docker", "uv"].map((req) => (
                      <div key={req} className="text-[11px] font-bold text-slate-300 bg-slate-950/80 border border-slate-800 rounded-lg px-2.5 py-1.5 text-center">
                        {req}
                      </div>
                    ))}
                  </div>
                </div>

                <div className="space-y-4">
                  <div className="flex items-center justify-between text-xs font-mono font-bold text-slate-400">
                    <span>1. Install &amp; start the stack</span>
                    <button
                      onClick={() => handleCopy(`make setup\ndocker compose up -d\ncd autorag-server && uv run uvicorn app.main:app --reload`, "qs1")}
                      className="text-xs text-orange-400 hover:underline flex items-center gap-1 cursor-pointer font-mono"
                    >
                      {copiedCode === "qs1" ? "Copied!" : "Copy Code"}
                    </button>
                  </div>

                  <div className="bg-[#0f172a] rounded-2xl p-4 border border-slate-800 font-mono text-xs text-slate-300 overflow-x-auto">
                    <pre><code>{`# 1. Install all dependencies (uv sync + npm install)
make setup

# 2. Start Redis (Supabase Cloud is used directly for Postgres + Vector)
docker compose up -d

# 3. Start the FastAPI backend
cd autorag-server && uv run uvicorn app.main:app --reload

# 4. Start the Next.js dashboard (new terminal)
npm run dev --workspace=autorag-client`}</code></pre>
                  </div>
                </div>

                <div className="p-4 rounded-2xl bg-orange-500/10 border border-orange-500/20 text-xs text-orange-300 flex items-start gap-3">
                  <Sparkles className="w-5 h-5 text-orange-400 shrink-0 mt-0.5" />
                  <div>
                    <span className="font-bold">Where to look: </span>
                    Interactive Swagger docs for all 46 endpoints are served at <code className="font-mono">localhost:8000/docs</code> once the backend is running.
                  </div>
                </div>
              </div>
            )}

            {activeTab === "client" && (
              <div className="space-y-6 animate-fade-in-marketing">
                <div>
                  <h3 className="text-2xl font-black text-white flex items-center gap-2">
                    <Code2 className="w-6 h-6 text-blue-400" />
                    <span>Client Integration</span>
                  </h3>
                  <p className="text-xs text-slate-400 font-medium mt-1">
                    No proprietary SDK — call the REST API directly from any language. The bundled Next.js dashboard uses a thin typed fetch wrapper (<code className="font-mono">services/api-client.ts</code>) as its own reference client.
                  </p>
                </div>

                <div className="space-y-3">
                  <div className="bg-[#0f172a] rounded-2xl p-4 border border-slate-800 font-mono text-xs text-slate-300 overflow-x-auto">
                    <pre><code>{`// Retrieval-only inspection: rewrite -> hybrid search -> rerank
const res = await fetch("http://localhost:8000/api/v1/retrieve", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({
    pipeline_id: "<your-pipeline-id>",
    query: "What is our leave policy?",
    top_k: 5,
  }),
});

const { data } = await res.json();
console.log(data.retrieved_chunks);`}</code></pre>
                  </div>
                </div>
              </div>
            )}

            {activeTab === "rest" && (
              <div className="space-y-6 animate-fade-in-marketing">
                <div>
                  <h3 className="text-2xl font-black text-white flex items-center gap-2">
                    <Layers className="w-6 h-6 text-emerald-400" />
                    <span>REST API</span>
                  </h3>
                  <p className="text-xs text-slate-400 font-medium mt-1">
                    Versioned under <code className="font-mono">/api/v1/</code>, every response uses the same envelope: status, data, error, request_id.
                  </p>
                </div>

                <div className="bg-[#0f172a] rounded-2xl p-4 border border-slate-800 font-mono text-xs text-slate-300 overflow-x-auto">
                  <pre><code>{`POST /api/v1/retrieve
Host: localhost:8000
Content-Type: application/json

{
  "pipeline_id": "018fcf7c-0d73-7e8a-b4f5-5e4f8f3a1b2c",
  "query": "What is our leave policy?",
  "top_k": 5
}`}</code></pre>
                </div>
              </div>
            )}

            {activeTab === "evaluation" && (
              <div className="space-y-6 animate-fade-in-marketing">
                <div>
                  <h3 className="text-2xl font-black text-white flex items-center gap-2">
                    <ShieldCheck className="w-6 h-6 text-indigo-400" />
                    <span>3-Layer Evaluation Stack</span>
                  </h3>
                  <p className="text-xs text-slate-400 font-medium mt-1">
                    How AutoRAG gates deployment before an answer ever reaches production traffic.
                  </p>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  <div className="p-4 rounded-2xl bg-slate-900 border border-slate-800 space-y-2">
                    <div className="text-xs font-mono font-bold text-orange-400">1. Unified Score</div>
                    <p className="text-xs text-slate-300">
                      0.25×Recall + 0.35×Quality + 0.25×Faithfulness − 0.10×Latency − 0.05×Cost. ≥0.85 auto-deploys, 0.70–0.84 requires human approval, &lt;0.70 is a hard block.
                    </p>
                  </div>

                  <div className="p-4 rounded-2xl bg-slate-900 border border-slate-800 space-y-2">
                    <div className="text-xs font-mono font-bold text-sky-400">2. RAGAS</div>
                    <p className="text-xs text-slate-300">
                      Context Precision, Context Recall, and Answer Relevancy computed per run for component-level diagnostics.
                    </p>
                  </div>

                  <div className="p-4 rounded-2xl bg-slate-900 border border-slate-800 space-y-2">
                    <div className="text-xs font-mono font-bold text-emerald-400">3. Adversarial</div>
                    <p className="text-xs text-slate-300">
                      A 10-question unanswerable benchmark. Faithfulness below 0.5 hard-blocks deployment regardless of total score.
                    </p>
                  </div>
                </div>
              </div>
            )}

            {activeTab === "architecture" && (
              <div className="space-y-6 animate-fade-in-marketing">
                <div>
                  <h3 className="text-2xl font-black text-white flex items-center gap-2">
                    <Network className="w-6 h-6 text-orange-400" />
                    <span>9-Agent Architecture</span>
                  </h3>
                  <p className="text-xs text-slate-400 font-medium mt-1">
                    A deterministic LangGraph state machine — every node is a stateless async function reading and writing one shared GraphState.
                  </p>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                  {[
                    { n: "1", name: "Ingestion", desc: "Parse, PII-mask, chunk, embed" },
                    { n: "2", name: "Query Rewriter", desc: "Clarify vague queries" },
                    { n: "3", name: "Builder", desc: "Index into pgvector" },
                    { n: "4", name: "Compressor", desc: "Fit context to token budget" },
                    { n: "5", name: "Evaluator", desc: "Unified Score + RAGAS + Adversarial" },
                    { n: "6", name: "Observer", desc: "Watch latency, cost, quality" },
                    { n: "7", name: "Diagnoser", desc: "Classify root cause (F-01…F-06)" },
                    { n: "8", name: "Improver", desc: "Generate better variants" },
                    { n: "9", name: "Deployer", desc: "Blue/Green + auto-rollback" },
                  ].map((agent) => (
                    <div key={agent.n} className="p-3 rounded-xl bg-slate-900 border border-slate-800 flex items-start gap-2.5">
                      <span className="mt-0.5 shrink-0 w-5 h-5 rounded-full bg-orange-500/15 border border-orange-500/30 text-orange-400 text-[10px] font-black flex items-center justify-center">
                        {agent.n}
                      </span>
                      <div>
                        <div className="text-xs font-bold text-white">{agent.name}</div>
                        <div className="text-[11px] text-slate-400">{agent.desc}</div>
                      </div>
                    </div>
                  ))}
                </div>

                <div className="p-4 rounded-2xl bg-orange-500/10 border border-orange-500/20 text-xs text-orange-300 flex items-start gap-3">
                  <Sparkles className="w-5 h-5 text-orange-400 shrink-0 mt-0.5" />
                  <div>
                    <span className="font-bold">LLM failover: </span>
                    Gemini Flash 3.5 → KiMi K2.6 → Gemini 3.5, with Gemini Embedding 2 for embeddings and Cohere Rerank v3 (BGE-Reranker fallback) for cross-encoder reranking.
                  </div>
                </div>
              </div>
            )}

            {activeTab === "deployment" && (
              <div className="space-y-6 animate-fade-in-marketing">
                <div>
                  <h3 className="text-2xl font-black text-white flex items-center gap-2">
                    <Rocket className="w-6 h-6 text-emerald-400" />
                    <span>Deployment</span>
                  </h3>
                  <p className="text-xs text-slate-400 font-medium mt-1">
                    Self-hosted on your own AWS account — immutable SHA-tagged containers, no vendor lock-in.
                  </p>
                </div>

                <div className="bg-[#0f172a] rounded-2xl p-4 border border-slate-800 font-mono text-xs text-slate-300 overflow-x-auto">
                  <pre><code>{`Lint -> Unit Tests -> Integration -> Build + ECR ->
ECS Staging -> Smoke Test -> Manual Gate -> ECS Production`}</code></pre>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div className="p-4 rounded-2xl bg-slate-900 border border-slate-800 space-y-1">
                    <div className="text-xs font-mono font-bold text-emerald-400">Infrastructure</div>
                    <p className="text-xs text-slate-300">AWS ECS Fargate, ECR, ALB, WAF — provisioned via Terraform, never console/CLI ad-hoc.</p>
                  </div>
                  <div className="p-4 rounded-2xl bg-slate-900 border border-slate-800 space-y-1">
                    <div className="text-xs font-mono font-bold text-sky-400">Auto-rollback</div>
                    <p className="text-xs text-slate-300">Within a 10-minute canary window on error rate &gt;1%, p95 latency &gt;3s, or a Unified Score drop &gt;0.10.</p>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </section>
  );
}
