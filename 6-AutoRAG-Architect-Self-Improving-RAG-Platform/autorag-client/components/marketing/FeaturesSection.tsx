"use client";

import { Layers, Cpu, ShieldCheck, Activity, GitCommit, Lock, Brain, Rocket, CheckCircle2, ArrowUpRight, Zap } from "lucide-react";

interface Feature {
  id: string;
  title: string;
  category: string;
  description: string;
  icon: string;
  metricLabel: string;
  metricValue: string;
  highlights: string[];
}

const FEATURES: Feature[] = [
  {
    id: "hybrid-retrieval",
    title: "Hybrid Retrieval",
    category: "HYBRID RETRIEVAL",
    description: "Fuses Sparse BM25 keyword matching with Dense Vector embeddings and cross-encoder reranking for pinpoint context extraction.",
    icon: "Layers",
    metricLabel: "Retrieval Stack",
    metricValue: "4-Stage Pipeline",
    highlights: ["Multi-Vector Indexing", "Reciprocal Rank Fusion (RRF)", "HyDE Expansion"],
  },
  {
    id: "multi-llm",
    title: "Multi-Model Orchestration",
    category: "MULTI-MODEL ORCHESTRATION",
    description: "Seamlessly route requests across commercial, open-source, private, and on-prem models based on cost, latency, or compliance.",
    icon: "Cpu",
    metricLabel: "Failover Chain",
    metricValue: "3-Provider Chain",
    highlights: ["Automatic Failover", "Token Cost Routing", "Private VPC Model Support"],
  },
  {
    id: "evaluation",
    title: "AI Quality Evaluation",
    category: "AI QUALITY EVALUATION",
    description: "Continuous automated benchmarking across Faithfulness, Context Recall, Answer Relevance, and Hallucination Risk.",
    icon: "ShieldCheck",
    metricLabel: "Evaluation Metrics",
    metricValue: "20+ Metrics",
    highlights: ["RAGAS-Based Scoring", "Adversarial Q&A Benchmark", "Faithfulness Hard-Block Gate"],
  },
  {
    id: "observability",
    title: "Observability & Monitoring",
    category: "OBSERVABILITY & MONITORING",
    description: "Full-stack tracing across vector DB lookups, reranking latencies, token consumption, and model response times.",
    icon: "Activity",
    metricLabel: "Telemetry Stack",
    metricValue: "Prometheus + Grafana",
    highlights: ["MLflow Experiment Sync", "Prometheus Metrics Export", "Cost-per-Query Tracking"],
  },
  {
    id: "pipeline-versioning",
    title: "Pipeline Governance",
    category: "PIPELINE GOVERNANCE",
    description: "Version every chunking strategy, vector index configuration, and prompt template with git-like version history and rollback.",
    icon: "GitCommit",
    metricLabel: "Version Control",
    metricValue: "Immutable Indexes",
    highlights: ["Compare Pipeline Versions", "Audit Trail Logging", "One-Click Rollback"],
  },
  {
    id: "enterprise-security",
    title: "Enterprise Security",
    category: "ENTERPRISE SECURITY",
    description: "SOC 2-aligned architecture with document-level Role-Based Access Control, automatic PII masking, and end-to-end encryption.",
    icon: "Lock",
    metricLabel: "Security Posture",
    metricValue: "SOC 2-Aligned",
    highlights: ["PII Masking at Ingest", "Document-Level RBAC", "Isolated VPC Deployment"],
  },
  {
    id: "autonomous-optimization",
    title: "Autonomous Optimization",
    category: "AUTONOMOUS OPTIMIZATION",
    description: "A closed self-improvement loop that observes production quality, diagnoses root causes, and generates better pipeline variants automatically.",
    icon: "Brain",
    metricLabel: "Optimization Loop",
    metricValue: "9-Agent Loop",
    highlights: ["Observer to Diagnoser to Improver", "6 Failure-Type Classification", "Continuous Pipeline Evolution"],
  },
  {
    id: "deployment",
    title: "Blue/Green Deployment",
    category: "DEPLOYMENT",
    description: "Zero-downtime blue/green promotion on AWS ECS Fargate with automatic rollback on error-rate or latency regressions.",
    icon: "Rocket",
    metricLabel: "Rollback Trigger",
    metricValue: "Auto-Rollback",
    highlights: ["Blue/Green Traffic Shifting", "10-Minute Canary Window", "8-Stage CI/CD Gate Chain"],
  },
];

const featureIconMap: Record<string, React.ReactNode> = {
  Layers: <Layers className="w-6 h-6 text-orange-500" />,
  Cpu: <Cpu className="w-6 h-6 text-amber-500" />,
  ShieldCheck: <ShieldCheck className="w-6 h-6 text-indigo-500" />,
  Activity: <Activity className="w-6 h-6 text-purple-500" />,
  GitCommit: <GitCommit className="w-6 h-6 text-emerald-500" />,
  Lock: <Lock className="w-6 h-6 text-rose-500" />,
  Brain: <Brain className="w-6 h-6 text-fuchsia-500" />,
  Rocket: <Rocket className="w-6 h-6 text-sky-500" />,
};

export function FeaturesSection() {
  return (
    <section id="features" className="py-24 bg-white relative">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="text-center max-w-3xl mx-auto space-y-4 mb-16">
          <div className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-orange-50 border border-orange-200 text-xs font-bold text-orange-700">
            <Zap className="w-3.5 h-3.5 text-orange-500" />
            <span>Production-Grade Architecture</span>
          </div>
          <h2 className="text-3xl sm:text-5xl font-extrabold text-slate-900 tracking-tight">
            Enterprise Capabilities for <br />
            <span className="text-gradient-primary">Reliable AI Systems</span>
          </h2>
          <p className="text-slate-600 font-medium text-base sm:text-lg">
            AutoRAG combines advanced retrieval, continuous evaluation, observability, governance, and
            enterprise security into a unified platform for building production-ready Retrieval-Augmented
            Generation systems.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
          {FEATURES.map((feat) => (
            <div
              key={feat.id}
              id={feat.id}
              className="group rounded-3xl p-7 flex flex-col justify-between border border-slate-200/90 hover:border-orange-500/70 transition-all duration-300 transform hover:-translate-y-1.5 hover:shadow-2xl bg-white shadow-md cursor-pointer scroll-mt-24"
            >
              <div>
                <div className="flex items-center justify-between mb-5">
                  <div className="w-12 h-12 rounded-2xl bg-slate-50 flex items-center justify-center border border-slate-200/80 shadow-xs group-hover:scale-110 group-hover:rotate-6 transition-transform duration-300">
                    {featureIconMap[feat.icon]}
                  </div>
                  <span className="text-[11px] font-extrabold px-2.5 py-1 rounded-full bg-slate-100 text-slate-700 uppercase tracking-wider">
                    {feat.category}
                  </span>
                </div>

                <h3 className="text-xl font-extrabold text-slate-900 mb-2 group-hover:text-orange-600 transition-colors">
                  {feat.title}
                </h3>

                <p className="text-xs text-slate-600 leading-relaxed font-medium mb-6">{feat.description}</p>

                <div className="space-y-2 mb-6">
                  {feat.highlights.map((hl) => (
                    <div key={hl} className="flex items-center gap-2 text-xs font-bold text-slate-700">
                      <CheckCircle2 className="w-3.5 h-3.5 text-orange-500 shrink-0" />
                      <span>{hl}</span>
                    </div>
                  ))}
                </div>
              </div>

              <div className="pt-4 border-t border-slate-100 flex items-center justify-between">
                <div>
                  <span className="text-[10px] text-slate-400 font-bold uppercase tracking-wider block">
                    {feat.metricLabel}
                  </span>
                  <span className="text-lg font-black text-orange-600 font-mono">{feat.metricValue}</span>
                </div>
                <div className="w-8 h-8 rounded-full bg-orange-50 text-orange-600 flex items-center justify-center group-hover:bg-orange-500 group-hover:text-white transition-colors">
                  <ArrowUpRight className="w-4 h-4" />
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
