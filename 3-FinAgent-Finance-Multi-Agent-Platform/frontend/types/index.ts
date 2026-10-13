// API types — mirror backend/src/schemas/views.py and the supervisor report (camelCase).

export interface Me {
  userId: string;
  email: string | null;
  role: string;
  tenantId: string;
  permissions: string[];
}

export interface PortfolioListItem {
  portfolioId: string;
  name: string;
  strategy: string;
}

export interface Holding {
  ticker: string;
  name: string;
  sector: string;
  assetClass: string;
  quantity: number;
  price: number;
  value: number;
  weight: number;
  unrealisedPnl: number;
  riskContribution: number;
}

export interface PortfolioView {
  portfolioId: string;
  name: string;
  currency: string;
  priceDate: string;
  nav: number;
  cash: number;
  dailyPnl: number;
  dailyReturn: number;
  return1y: number;
  sectorWeights: Record<string, number>;
  holdings: Holding[];
  breaches: number;
}

export interface LimitCheck {
  limitType: string;
  subject: string;
  actual: number;
  threshold: number;
  breached: boolean;
  severity: string;
  headroom: number;
  policyReference: string | null;
}

export interface RiskView {
  portfolioId: string;
  priceDate: string;
  volatility: number;
  volatilityRecentQuarter: number;
  volatilityPriorQuarter: number;
  var95: number;
  var95Amount: number | null;
  var99: number;
  cvar95: number;
  maxDrawdown: number;
  beta: number;
  sharpe: number;
  sortino: number;
  effectiveHoldings: number;
  limitChecks: LimitCheck[];
  riskLevel: string | null;
}

export interface ReportAgent {
  name: string;
  status: string;
  confidence: number;
  durationMs: number;
  llmUsed: boolean;
  toolCalls: string[];
}

export interface Evidence {
  source: string;
  citation: string;
  url: string | null;
  as_of: string | null;
}

export interface Report {
  requestId: string;
  question: string;
  intent: string;
  portfolio: string | null;
  tickers?: string[];
  headline: string;
  riskLevel: string | null;
  sections: {
    facts: { agent: string; text: string }[];
    mlPredictions: { agent: string; text: string }[];
    interpretation: string | null;
    interpretationSource: string;
    recommendations: string[];
    assumptions: string[];
    uncertainty: string[];
  };
  approval: {
    required: boolean;
    reasons: string[];
    approvalId?: string;
    status?: string;
    expiresAt?: string;
    draftOrders?: DraftOrder[];
  };
  agents: ReportAgent[];
  evidence: Evidence[];
  confidence: number;
  routing: { method?: string; confidence?: number };
  guard: { input: string; output: string };
  disclaimer: string;
  durationMs?: number;
}

export type StreamEvent =
  | { event: "start"; requestId: string; traceId: string }
  | { event: "conversation"; conversationId: string }
  | { event: "guard"; decision: string; reason: string | null; ts: number }
  | { event: "approval"; approval: Report["approval"]; ts: number }
  | { event: "step"; step: string; ts: number }
  | { event: "classification"; intent: string; method: string; portfolio: string | null; confidence: number; ts: number }
  | { event: "plan"; intent: string; stages: string[][]; ts: number }
  | { event: "agent_start"; agent: string; ts: number }
  | { event: "agent_end"; agent: string; status: string; confidence: number; tools: string[]; durationMs: number; ts: number }
  | { event: "token"; text: string; ts: number }
  | { event: "report"; report: Report; ts: number }
  | { event: "error"; message: string; code: string; requestId?: string }
  | { event: "done"; durationMs: number };

// ------------------------------------------------------------------ Stage 8/9 API views

export interface ChatResponse {
  requestId: string;
  report: Report;
  conversationId: string | null;
}

export interface DraftOrder {
  ticker: string;
  side: string;
  quantity: number;
  price: number;
  value: number;
}

export interface Approval {
  approvalId: string;
  threadId: string;
  requestId: string;
  portfolio: string | null;
  status: "pending" | "approved" | "rejected" | "expired";
  reasons: string[];
  proposal: { orders: DraftOrder[]; question?: string };
  totalValue: number;
  requestedBy: string | null;
  decidedBy: string | null;
  decidedAt: string | null;
  decisionNote: string | null;
  expiresAt: string;
  createdAt: string;
  createdDraftOrders?: DraftOrder[];
}

export interface OverviewPortfolio {
  portfolioId: string;
  name: string;
  nav: number;
  dailyReturn: number;
  return1y: number;
  volatility: number;
  var95: number;
  breaches: number;
  priceDate: string;
}

export interface ActivityItem {
  at: string;
  requestId: string | null;
  action: string;
  decision: string;
  reason: string | null;
  userRole: string | null;
}

export interface Overview {
  portfolios: OverviewPortfolio[];
  totals: { nav: number; breaches: number; pendingApprovals: number };
  recentActivity: ActivityItem[];
  disclaimer: string;
}

export interface ComplianceView {
  checks: (LimitCheck & { portfolioId: string; name: string })[];
  breaches: (LimitCheck & { portfolioId: string; name: string })[];
}

export interface MarketSummary {
  date: string;
  benchmark: { ticker: string; level: number; return1d: number; return1m: number; volatility3m: number };
  sectors: { sector: string; return1m: number; names: number }[];
}

export interface NewsItem {
  title: string;
  url: string;
  published: string | null;
  source: string;
  summary: string;
  tickers: string[];
  sentiment: number | null;
}

export interface FraudAlert {
  transactionId: string;
  at: string;
  amount: number;
  currency: string;
  category: string;
  channel: string;
  country: string;
  probability: number;
  riskLevel: string;
  reasons: string[];
  modelVersion: string;
  scoredAt: string;
}

export interface AgentCard {
  name: string;
  description: string;
  version: string;
  tasks: string[];
  tools: string[];
  stats: { runs: number; avgDurationMs: number; avgConfidence: number | null; failed: number; lastRunAt: string } | null;
}

export interface ModelCard {
  kind: string;
  name: string;
  version: string | null;
  algorithm: string | null;
  trainedAt: string | null;
  features: number;
  testMetrics: Record<string, number>;
  note: string;
}

export interface SystemStatus {
  checks: Record<string, string>;
  kvStore: string;
  circuits: Record<string, string>;
  answerChain: string[];
  agentChain: string[];
  demoMode: boolean;
  environment: string;
}

export interface DocumentItem {
  documentId: string;
  source: string;
  title: string;
  docType: string;
  classification: string;
  status: string;
  chunks: number;
  updatedAt: string;
}

export interface Citation {
  n: number;
  citation: string;
  documentId: string;
  chunkId: string;
  relevanceScore: number;
}

export interface RagAnswer {
  question: string;
  answer: string;
  answerSource: "llm" | "extractive" | "refusal";
  citations: Citation[];
  validation: string[];
  kbVersion: number;
  cached: boolean;
}

export interface UploadResult {
  source: string;
  status: string;
  documentId: string | null;
  chunks: number;
  error: string | null;
  warnings: string[];
}

export interface AuditTrace {
  requestId: string;
  audit: { at: string; action: string; decision: string; reason: string | null; userRole: string | null; resource: string | null }[];
  agentRuns: { agent: string; task: string; status: string; startedAt: string; durationMs: number; confidence: number | null; toolCalls: number; error: string | null }[];
  a2aMessages: { messageId: string; type: string; source: string; target: string; task: string; attempt: number; latencyMs: number | null; at: string }[];
  toolCalls: { tool: string; server: string; agent: string | null; status: string; durationMs: number; errorCode: string | null; at: string }[];
}

export interface Conversation {
  conversationId: string;
  title: string;
  createdAt: string;
  updatedAt: string;
}
