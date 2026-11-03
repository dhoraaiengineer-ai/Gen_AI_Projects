// Public marketing landing page content.
//
// Every fact below is checked against the real platform as of this session:
// - 9 agents, LLM chain, and responsibilities: .claude/CLAUDE.md §"9-Agent Loop"
// - 46 endpoints, tech stack: README.md
// - Unified Score formula + thresholds: .claude/CLAUDE.md §9 / rules/coding-standards.md
// - F-01..F-06 failure taxonomy: .claude/rules/workflow-contracts.md Rule 8
// - 10 domain verticals: verification/corpus/ (real, committed test corpora)
//
// No fabricated customer names, testimonials, or live pricing are included.

import type {
  AgentInfo,
  WorkflowStage,
  FeatureItem,
  PlatformScreen,
  TechStackItem,
  SecurityFeature,
  PricingPlan,
  DomainVertical,
} from "@/types/marketing";

export const AGENTS_DATA: AgentInfo[] = [
  {
    id: "ingestion",
    name: "Ingestion Agent",
    iconName: "Database",
    category: "Ingestion & Query",
    shortDesc:
      "Parses uploaded documents, masks PII, and chunks content using semantic, hierarchical, or late chunking.",
    status: "OPERATIONAL",
    responsibilities: [
      "PDF / DOCX / Markdown / TXT parsing (with OCR fallback for scanned PDFs)",
      "Custom PII detection & masking before any content reaches an LLM",
      "Semantic, hierarchical, and late chunking strategies",
      "Chunk upload to Supabase Storage + Supabase Vector",
    ],
    modelEngine: "Gemini Flash 3.5",
  },
  {
    id: "query-rewriter",
    name: "Query Rewriter Agent",
    iconName: "Sparkles",
    category: "Ingestion & Query",
    shortDesc: "Improves vague or ambiguous user queries before retrieval runs.",
    status: "OPERATIONAL",
    responsibilities: [
      "Query clarification and reformulation",
      "Improves retrieval precision before the hybrid search stage runs",
    ],
    modelEngine: "Gemini Flash 3.5",
  },
  {
    id: "builder",
    name: "Builder Agent",
    iconName: "Cpu",
    category: "Pipeline Core",
    shortDesc: "Embeds chunks and configures the 4-stage retrieval pipeline.",
    status: "OPERATIONAL",
    responsibilities: [
      "Gemini Embedding 2 batch embedding (768-dim)",
      "Hybrid retrieval: dense + BM25 fusion",
      "Cohere Rerank v3 cross-encoder reranking (BGE-Reranker fallback)",
      "Optional HyDE (Hypothetical Document Embeddings) expansion",
    ],
    modelEngine: "Gemini Embedding 2 + Cohere Rerank v3",
  },
  {
    id: "context-compressor",
    name: "Context Compressor Agent",
    iconName: "FileCheck",
    category: "Pipeline Core",
    shortDesc: "Reduces retrieved context to fit the LLM's token budget before generation.",
    status: "OPERATIONAL",
    responsibilities: [
      "Token-budget-aware context trimming",
      "Directly targets the Context Overflow (F-02) failure type",
    ],
    modelEngine: "Gemini Flash 3.5",
  },
  {
    id: "evaluator",
    name: "Evaluator Agent",
    iconName: "Award",
    category: "Evaluation & Observability",
    shortDesc:
      "Computes the Unified Score, RAGAS metrics, and runs the adversarial hallucination benchmark on every run.",
    status: "OPERATIONAL",
    responsibilities: [
      "Unified Score: 0.25×Recall + 0.35×Quality + 0.25×Faithfulness − 0.10×Latency − 0.05×Cost",
      "RAGAS diagnostics: Context Precision, Context Recall, Faithfulness, Answer Relevancy",
      "10-question adversarial Q&A hallucination gate",
      "Faithfulness < 0.5 is a hard, non-bypassable deployment block",
    ],
    modelEngine: "Gemini Flash 3.5",
  },
  {
    id: "observer",
    name: "Observer Agent",
    iconName: "Activity",
    category: "Evaluation & Observability",
    shortDesc: "Watches production latency, cost, and quality trends after deployment.",
    status: "OPERATIONAL",
    responsibilities: [
      "Prometheus + Grafana metrics export",
      "5-run rolling window quality-drift detection",
      "Flags degradation before it's visible to end users",
    ],
    modelEngine: "Prometheus / Grafana",
  },
  {
    id: "diagnoser",
    name: "Diagnoser Agent",
    iconName: "ShieldAlert",
    category: "Auto-Tuning & Deploy",
    shortDesc: "Classifies failures into one of 6 root-cause types and recommends a fix.",
    status: "OPERATIONAL",
    responsibilities: [
      "F-01 Retrieval Miss, F-02 Context Overflow, F-03 Hallucination",
      "F-04 Answer Incomplete, F-05 Latency Spike, F-06 Quality Drift",
      "Generates targeted remediation guidance per failure type",
    ],
    modelEngine: "Gemini Flash 3.5",
  },
  {
    id: "improver",
    name: "Improver Agent",
    iconName: "Zap",
    category: "Auto-Tuning & Deploy",
    shortDesc: "Generates candidate pipeline variants aimed at a higher Unified Score.",
    status: "OPERATIONAL",
    responsibilities: [
      "Generates hyperparameter / configuration variants",
      "Targets Unified Score ≥ 0.85",
      "Candidates can be applied directly via Apply Improvement, which rebuilds and re-evaluates",
    ],
    modelEngine: "Gemini Flash 3.5",
  },
  {
    id: "deployer",
    name: "Deployer Agent",
    iconName: "GitBranch",
    category: "Auto-Tuning & Deploy",
    shortDesc: "Runs Blue/Green deployment to AWS ECS Fargate with automatic rollback.",
    status: "OPERATIONAL",
    responsibilities: [
      "Blue/Green deployment with a 10-minute canary window",
      "Auto-rollback if error rate > 1%, p95 latency > 3s, or Unified Score drops > 0.10",
      "Score ≥ 0.85 deploys automatically; 0.70–0.84 requires human approval",
    ],
    modelEngine: "AWS ECS Fargate",
  },
];

export const WORKFLOW_STAGES: WorkflowStage[] = [
  {
    id: "ingestion",
    stepNumber: 1,
    name: "Ingestion",
    subtitle: "Parse, Mask, Chunk",
    icon: "Database",
    description:
      "Documents are parsed, PII is masked before any LLM call, and content is split using semantic, hierarchical, or late chunking.",
    inputTypes: ["PDF", "DOCX", "Markdown", "TXT"],
    outputArtifacts: ["Masked chunk set", "Chunk metadata (source_uri, page_number, chunk_strategy)"],
    keyMetrics: [{ label: "Chunking strategies", value: "3" }],
    activeAgents: ["Ingestion Agent"],
  },
  {
    id: "retrieval",
    stepNumber: 2,
    name: "Retrieval",
    subtitle: "Hybrid Search + Rerank",
    icon: "Search",
    description:
      "Query Rewriter reformulates the question, then a 4-stage retrieval pipeline (dense + BM25, cross-encoder rerank, optional HyDE) surfaces the most relevant chunks.",
    inputTypes: ["User query"],
    outputArtifacts: ["Top-K ranked chunks"],
    keyMetrics: [{ label: "Retrieval stages", value: "4" }],
    activeAgents: ["Query Rewriter Agent", "Builder Agent"],
  },
  {
    id: "generation",
    stepNumber: 3,
    name: "Generation",
    subtitle: "Compress + Generate",
    icon: "Sliders",
    description:
      "Context is compressed to fit the token budget, then the LLM generates a grounded answer with citations.",
    inputTypes: ["Retrieved chunks"],
    outputArtifacts: ["Generated answer with citations"],
    keyMetrics: [{ label: "Grounding constraint", value: "Never invents facts" }],
    activeAgents: ["Context Compressor Agent"],
  },
  {
    id: "evaluation",
    stepNumber: 4,
    name: "Evaluation",
    subtitle: "Unified Score + RAGAS + Adversarial",
    icon: "CheckCircle2",
    description:
      "A 3-layer evaluation stack scores every run: the Unified Score gate, RAGAS component diagnostics, and a 10-question adversarial hallucination benchmark.",
    inputTypes: ["Generated answer", "Retrieved context"],
    outputArtifacts: ["Unified Score (0–1)", "Deployment eligibility decision"],
    keyMetrics: [{ label: "Auto-deploy threshold", value: "≥ 0.85" }],
    activeAgents: ["Evaluator Agent"],
  },
  {
    id: "deployment",
    stepNumber: 5,
    name: "Deployment",
    subtitle: "Blue/Green + Canary",
    icon: "Send",
    description:
      "Eligible pipelines deploy via Blue/Green strategy to AWS ECS Fargate with a 10-minute canary window and automatic rollback.",
    inputTypes: ["Deployment-eligible pipeline version"],
    outputArtifacts: ["Live production endpoint"],
    keyMetrics: [{ label: "Canary window", value: "10 min" }],
    activeAgents: ["Deployer Agent"],
  },
  {
    id: "observation",
    stepNumber: 6,
    name: "Observation & Improvement",
    subtitle: "Monitor, Diagnose, Improve",
    icon: "Activity",
    description:
      "The Observer watches production quality continuously. When it drifts, the Diagnoser classifies the failure and the Improver proposes a better configuration — closing the loop.",
    inputTypes: ["Production telemetry"],
    outputArtifacts: ["Failure classification", "Candidate pipeline variant"],
    keyMetrics: [{ label: "Failure taxonomy", value: "6 types (F-01–F-06)" }],
    activeAgents: ["Observer Agent", "Diagnoser Agent", "Improver Agent"],
  },
];

export const FEATURES_DATA: FeatureItem[] = [
  {
    id: "hybrid-retrieval",
    title: "4-Stage Hybrid Retrieval",
    category: "RETRIEVAL",
    description:
      "Dense vector search fused with BM25 keyword matching, cross-encoder reranking, and optional HyDE query expansion.",
    icon: "Layers",
    metricLabel: "Retrieval stages",
    metricValue: "4",
    highlights: ["Dense + BM25 fusion", "Cohere Rerank v3 cross-encoder", "Optional HyDE expansion"],
    gradient: "from-blue-500 to-cyan-500",
  },
  {
    id: "llm-failover",
    title: "Automatic LLM Failover",
    category: "RELIABILITY",
    description:
      "A configurable provider chain — Gemini Flash 3.5 primary, KiMi K2.6 fallback, Gemini 3.5 last resort — keeps generation available through provider outages.",
    icon: "Cpu",
    metricLabel: "Failover chain",
    metricValue: "3 providers",
    highlights: ["Configurable via CHAT_PROVIDER_ORDER", "Automatic failover on provider error", "Cost + latency tracked per call"],
    gradient: "from-purple-500 to-indigo-500",
  },
  {
    id: "eval-engine",
    title: "3-Layer Evaluation Stack",
    category: "QUALITY GATE",
    description:
      "Every pipeline run is scored by a weighted Unified Score, RAGAS component diagnostics, and a 10-question adversarial hallucination benchmark.",
    icon: "ShieldCheck",
    metricLabel: "Deploy gate",
    metricValue: "≥ 0.85",
    highlights: ["Unified Score gate", "RAGAS diagnostics", "Adversarial Q&A hallucination test"],
    gradient: "from-emerald-500 to-teal-500",
  },
  {
    id: "observability",
    title: "Prometheus + Grafana Observability",
    category: "TELEMETRY",
    description:
      "Cost, latency, token usage, and quality trend dashboards, with automatic quality-drift detection across a rolling 5-run window.",
    icon: "Activity",
    metricLabel: "Dashboards",
    metricValue: "2 (Overview + AIOps)",
    highlights: ["Per-agent cost & latency metrics", "5-run quality-drift window", "MLflow experiment tracking"],
    gradient: "from-amber-500 to-orange-500",
  },
  {
    id: "pipeline-versioning",
    title: "Immutable Versioned Indexes",
    category: "GOVERNANCE",
    description:
      "Every applied pipeline version's vector chunks are isolated and queryable — a rebuild never overwrites or corrupts a prior version's data, and rollback is one call away.",
    icon: "GitCommit",
    metricLabel: "Version isolation",
    metricValue: "Per-version, immutable",
    highlights: ["Full version history", "Real, reversible rollback", "INSERT-only audit trail"],
    gradient: "from-pink-500 to-rose-500",
  },
  {
    id: "enterprise-security",
    title: "PII Masking & Audit Trail",
    category: "COMPLIANCE",
    description:
      "Custom PII detection masks sensitive data before it ever reaches an LLM, and every important action is recorded in an append-only, INSERT-only audit log.",
    icon: "Lock",
    metricLabel: "Audit log",
    metricValue: "14 event types, INSERT-only",
    highlights: ["PII masked before every LLM call", "Immutable audit_log table", "Multi-tenant organization scoping"],
    gradient: "from-violet-500 to-purple-600",
  },
];

export const PLATFORM_SCREENS: PlatformScreen[] = [
  {
    id: "configurator",
    title: "Pipeline Configurator",
    tagline: "6-step guided setup wizard",
    description: "Configure chunking strategy, retrieval, generation, and evaluation settings without hand-writing YAML.",
    icon: "Sliders",
    category: "Design & Build",
    mockStats: [{ label: "Wizard steps", value: "6" }],
    highlights: ["Upload → chunking strategy → deploy in one guided flow", "No manual pipeline config required"],
  },
  {
    id: "evaluation",
    title: "Evaluation Dashboard",
    tagline: "Unified Score, RAGAS & adversarial results",
    description: "See the full evaluation breakdown for every run — Unified Score, RAGAS sub-metrics, and adversarial pass rate.",
    icon: "Award",
    category: "Quality Control",
    mockStats: [{ label: "Deploy threshold", value: "≥ 0.85" }],
    highlights: ["Unified Score gauge", "RAGAS component breakdown", "Adversarial Q&A results"],
  },
  {
    id: "retrieval-explorer",
    title: "Retrieval Explorer",
    tagline: "Inspect retrieved chunks and scores",
    description: "Drill into exactly which chunks were retrieved for a query, their scores, and page-level citations.",
    icon: "Search",
    category: "Debugging",
    mockStats: [{ label: "Retrieval stages shown", value: "4" }],
    highlights: ["Per-stage retrieval breakdown", "Chunk-level citation view"],
  },
  {
    id: "observer-telemetry",
    title: "Observer Dashboard",
    tagline: "Live agent telemetry",
    description: "Track latency, cost, and quality trend across the 9-agent loop, with alerts on quality drift.",
    icon: "Activity",
    category: "Observability",
    mockStats: [{ label: "Quality-drift window", value: "5 runs" }],
    highlights: ["Per-agent latency & cost", "5-run quality-drift detection", "Alert center"],
  },
  {
    id: "auto-improver",
    title: "Diagnoser & Improver Workspace",
    tagline: "Self-tuning recommendation loop",
    description: "When quality drifts, the Diagnoser classifies the root cause and the Improver proposes a better configuration you can apply directly.",
    icon: "Zap",
    category: "Auto-Tuning",
    mockStats: [{ label: "Failure taxonomy", value: "6 types" }],
    highlights: ["6-type root-cause classification", "One-click Apply Improvement", "Real rebuild + re-evaluation"],
  },
  {
    id: "deployment-center",
    title: "Deployment Center",
    tagline: "Blue/Green with instant rollback",
    description: "Promote a pipeline version to production with a 10-minute canary window and automatic rollback on regression.",
    icon: "Rocket",
    category: "Deployment",
    mockStats: [{ label: "Canary window", value: "10 min" }],
    highlights: ["Blue/Green traffic shift", "Auto-rollback on error/latency/score regression", "Version history & manual rollback"],
  },
];

export const TECH_STACK: TechStackItem[] = [
  { name: "Next.js 15", category: "Frontend & UI", description: "App Router framework for the dashboard.", logoText: "NEXT", accentColor: "border-blue-300 text-blue-700 bg-blue-50" },
  { name: "React 18", category: "Frontend & UI", description: "UI library powering every dashboard screen.", logoText: "REACT", accentColor: "border-cyan-300 text-cyan-700 bg-cyan-50" },
  { name: "TypeScript", category: "Frontend & UI", description: "End-to-end strict typing across frontend and backend.", logoText: "TS", accentColor: "border-indigo-300 text-indigo-700 bg-indigo-50" },
  { name: "FastAPI", category: "Agentic & Backend", description: "Async Python backend running all 9 agents.", logoText: "FAST", accentColor: "border-emerald-300 text-emerald-700 bg-emerald-50" },
  { name: "LangGraph", category: "Agentic & Backend", description: "Deterministic state-machine orchestration for the agent loop.", logoText: "LG", accentColor: "border-purple-300 text-purple-700 bg-purple-50" },
  { name: "Supabase", category: "Databases & Vector", description: "PostgreSQL + Vector + Storage in one managed platform.", logoText: "SUPA", accentColor: "border-teal-300 text-teal-700 bg-teal-50" },
  { name: "pgvector", category: "Databases & Vector", description: "Vector similarity search inside Supabase PostgreSQL.", logoText: "PGV", accentColor: "border-blue-400 text-blue-800 bg-blue-100" },
  { name: "Redis", category: "Databases & Vector", description: "LangGraph checkpoint cache and response caching.", logoText: "REDIS", accentColor: "border-rose-300 text-rose-700 bg-rose-50" },
  { name: "MLflow", category: "Observability & Cloud", description: "Experiment tracking and hyperparameter history.", logoText: "ML", accentColor: "border-amber-300 text-amber-700 bg-amber-50" },
  { name: "Prometheus", category: "Observability & Cloud", description: "Metrics collection across all 9 agents.", logoText: "PROM", accentColor: "border-orange-300 text-orange-700 bg-orange-50" },
  { name: "Grafana", category: "Observability & Cloud", description: "Overview + AIOps dashboards.", logoText: "GRAF", accentColor: "border-yellow-300 text-yellow-800 bg-yellow-50" },
  { name: "AWS ECS Fargate", category: "Observability & Cloud", description: "Serverless container hosting with Blue/Green deploys.", logoText: "AWS", accentColor: "border-slate-300 text-slate-700 bg-slate-100" },
];

export const SECURITY_FEATURES: SecurityFeature[] = [
  {
    title: "Non-Bypassable Deployment Gate",
    description: "No pipeline reaches production without meeting the Unified Score and Faithfulness thresholds.",
    badge: "Quality Gate",
    icon: "ShieldCheck",
    details: ["Unified Score ≥ 0.85 for auto-deploy", "Faithfulness < 0.5 is a hard block, always", "0.70–0.84 requires human approval"],
  },
  {
    title: "Multi-Tenant Isolation",
    description: "Every database query and vector write is scoped by organization and pipeline version.",
    badge: "Multi-Tenant",
    icon: "Key",
    details: ["organization_id scoping enforced on every query", "Per-version vector isolation (Immutable Versioned Indexes)", "No cross-tenant data access"],
  },
  {
    title: "Automatic PII Masking",
    description: "Custom PII detection masks sensitive data before it ever reaches an LLM or vector store.",
    badge: "PII Protection",
    icon: "EyeOff",
    details: ["Masking runs before every LLM call", "PII never stored unmasked in logs or checkpoints", "Redaction evidence recorded in the audit log"],
  },
  {
    title: "Immutable Audit Trail",
    description: "Every important action is recorded in an append-only log that can never be modified or deleted.",
    badge: "Audit Log",
    icon: "FileText",
    details: ["INSERT-only, enforced at the database level", "14 approved event types", "Full trace ID propagation from API to log"],
  },
];

export const DOMAIN_VERTICALS: DomainVertical[] = [
  { id: "customer_support", label: "Customer Support", icon: "Headphones" },
  { id: "finance", label: "Finance", icon: "Building2" },
  { id: "healthcare", label: "Healthcare", icon: "Stethoscope" },
  { id: "hr", label: "HR", icon: "Users" },
  { id: "it_operations", label: "IT Operations", icon: "Terminal" },
  { id: "legal", label: "Legal", icon: "Scale" },
  { id: "product", label: "Product", icon: "Box" },
  { id: "research_education", label: "Research & Education", icon: "BookOpen" },
  { id: "sales_marketing", label: "Sales & Marketing", icon: "TrendingUp" },
  { id: "technical", label: "Technical", icon: "Code2" },
];

export const SAMPLE_QUERIES = [
  "How does multi-head attention work in the Transformer?",
  "Summarize the Q3 compliance policy on cross-border data transfers.",
  "What is the deployment gate threshold for the Unified Score?",
];

// No live commercial pricing exists yet. Tiers below describe the intended
// shape of the offering; CTAs point to a real conversation, not a checkout.
export const PRICING_PLANS: PricingPlan[] = [
  {
    id: "open-source",
    name: "Open Source",
    tagline: "Full 9-agent system, self-hosted",
    priceLabel: "Free",
    ctaText: "View on GitHub",
    targetAudience: "Researchers, indie founders",
    features: [
      "Full 9-agent LangGraph loop",
      "Apply Improvement / Optimizer",
      "Self-hosted (Docker Compose)",
      "Community support",
    ],
  },
  {
    id: "self-hosted",
    name: "Self-Hosted (Team / Enterprise)",
    tagline: "Same platform, dedicated support & SLA",
    priceLabel: "Indicative — subject to change",
    popular: true,
    ctaText: "Request Early Access",
    targetAudience: "Teams running AutoRAG on their own infrastructure",
    features: [
      "Everything in Open Source",
      "Managed updates & email support",
      "SSO + RBAC (Enterprise tier)",
      "SLA-backed support",
    ],
  },
  {
    id: "managed",
    name: "Managed Cloud",
    tagline: "Fully managed ECS deployment",
    priceLabel: "Talk to the team",
    ctaText: "Talk to the Team",
    targetAudience: "Teams that prefer a managed SaaS deployment",
    features: [
      "Fully managed ECS Fargate hosting",
      "Multi-tenant isolation",
      "Dedicated onboarding",
    ],
  },
];
