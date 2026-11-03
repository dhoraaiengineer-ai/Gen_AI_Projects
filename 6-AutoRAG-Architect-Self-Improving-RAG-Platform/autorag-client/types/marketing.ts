// Public marketing landing page — content shapes only.
// Values live in lib/marketing-data.ts and are kept factually accurate
// against the real platform (see .claude/CLAUDE.md, README.md).

export type AgentStatus = "OPERATIONAL" | "RUNNING" | "OPTIMIZING" | "STANDBY";

export interface AgentInfo {
  id: string;
  name: string;
  iconName: string;
  category: "Ingestion & Query" | "Pipeline Core" | "Evaluation & Observability" | "Auto-Tuning & Deploy";
  shortDesc: string;
  status: AgentStatus;
  responsibilities: string[];
  modelEngine: string;
}

export interface WorkflowStage {
  id: string;
  stepNumber: number;
  name: string;
  subtitle: string;
  icon: string;
  description: string;
  inputTypes: string[];
  outputArtifacts: string[];
  keyMetrics: { label: string; value: string }[];
  activeAgents: string[];
}

export interface FeatureItem {
  id: string;
  title: string;
  category: string;
  description: string;
  icon: string;
  metricLabel: string;
  metricValue: string;
  highlights: string[];
  gradient: string;
}

export interface PlatformScreen {
  id: string;
  title: string;
  tagline: string;
  description: string;
  icon: string;
  category: string;
  mockStats: { label: string; value: string; trend?: string }[];
  highlights: string[];
}

export interface TechStackItem {
  name: string;
  category: "Frontend & UI" | "Agentic & Backend" | "Databases & Vector" | "Observability & Cloud";
  description: string;
  logoText: string;
  accentColor: string;
}

export interface SecurityFeature {
  title: string;
  description: string;
  badge: string;
  icon: string;
  details: string[];
}

export interface PricingPlan {
  id: string;
  name: string;
  tagline: string;
  priceLabel: string;
  popular?: boolean;
  ctaText: string;
  features: string[];
  targetAudience: string;
}

export interface DomainVertical {
  id: string;
  label: string;
  icon: string;
}

export interface SandboxExecutionStep {
  agentId: string;
  agentName: string;
  status: "pending" | "running" | "completed" | "failed";
  timeTakenMs: number;
  outputSummary: string;
}
