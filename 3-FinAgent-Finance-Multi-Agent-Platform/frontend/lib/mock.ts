// Mock mode (NEXT_PUBLIC_API_MODE=mock): fixtures shaped exactly like the API, built from the
// seeded demo data (Portfolio A's NVTK 31% hard breach, semiconductors 46.5%, VaR 2.52%), and a
// simulated agent stream. Used for UI demos without a backend and for the Playwright tests.
import type { Approval, Report, StreamEvent } from "@/types";

const PERMISSIONS: Record<string, string[]> = {
  admin: ["admin:manage", "agents:run", "audit:read", "customers:read", "dashboard:read", "documents:read_restricted", "documents:write", "fraud:analyze", "portfolio:propose", "risk:analyze"],
  compliance_officer: ["agents:run", "approvals:decide", "audit:read", "customers:read", "dashboard:read", "documents:read_restricted", "documents:write", "fraud:analyze", "risk:analyze"],
  risk_manager: ["agents:run", "dashboard:read", "documents:read_restricted", "portfolio:propose", "risk:analyze"],
  portfolio_manager: ["agents:run", "approvals:decide", "dashboard:read", "documents:read_restricted", "portfolio:propose", "risk:analyze"],
  fraud_analyst: ["agents:run", "customers:read", "dashboard:read", "fraud:analyze"],
  analyst: ["agents:run", "dashboard:read", "documents:write", "risk:analyze"],
  viewer: ["dashboard:read"],
};

export const MOCK_USERS = Object.keys(PERMISSIONS).map((role) => ({
  email: `${role.split("_")[0]}@northwind.example.com`.replace("portfolio@", "pm@"),
  role,
}));

let mockRole = "risk_manager";
export const setMockRole = (role: string) => {
  mockRole = role;
};

const now = () => new Date().toISOString();
const sleep = (ms: number, signal?: AbortSignal) =>
  new Promise<void>((resolve, reject) => {
    const t = setTimeout(resolve, ms);
    signal?.addEventListener("abort", () => {
      clearTimeout(t);
      reject(new DOMException("aborted", "AbortError"));
    });
  });

const HOLDINGS = [
  ["NVTK", "Novatek Semiconductor", "Semiconductors", 0.31, 0.402],
  ["ORBX", "Orbix Systems", "Technology", 0.072, 0.061],
  ["CYPH", "Cypher Security", "Technology", 0.072, 0.083],
  ["HLXS", "Helix Semis", "Semiconductors", 0.064, 0.071],
  ["QNTA", "Quanta Devices", "Semiconductors", 0.052, 0.049],
  ["LMNQ", "Lumenq Health", "Health Care", 0.048, 0.021],
] as const;

const PORTFOLIO = {
  portfolioId: "PF-A",
  name: "Portfolio A — Technology Growth",
  currency: "USD",
  priceDate: "2026-09-30",
  nav: 250_000_000,
  cash: 5_000_000,
  dailyPnl: 1_830_000,
  dailyReturn: 0.0074,
  return1y: 0.542,
  sectorWeights: { Semiconductors: 0.465, Technology: 0.443, "Health Care": 0.048, Cash: 0.02, Other: 0.024 },
  holdings: HOLDINGS.map(([ticker, name, sector, weight, rc]) => ({
    ticker, name, sector, assetClass: "equity", quantity: Math.round((weight * 250e6) / 300), price: 300,
    value: weight * 250e6, weight, unrealisedPnl: weight * 40e6, riskContribution: rc,
  })),
  breaches: 4,
};

const LIMITS = [
  { limitType: "single_name", subject: "NVTK", actual: 0.31, threshold: 0.25, breached: true, severity: "hard", headroom: -0.06, policyReference: "Investment Policy §4.2" },
  { limitType: "sector", subject: "Semiconductors", actual: 0.465, threshold: 0.4, breached: true, severity: "warning", headroom: -0.065, policyReference: "Investment Policy §4.3" },
  { limitType: "sector", subject: "Technology", actual: 0.443, threshold: 0.4, breached: true, severity: "warning", headroom: -0.043, policyReference: "Investment Policy §4.3" },
  { limitType: "var_95_1d", subject: "portfolio", actual: 0.0252, threshold: 0.025, breached: true, severity: "warning", headroom: -0.0002, policyReference: "Risk Framework §3.1" },
];

const RISK = {
  portfolioId: "PF-A", priceDate: "2026-09-30", volatility: 0.268, volatilityRecentQuarter: 0.328, volatilityPriorQuarter: 0.229,
  var95: 0.0252, var95Amount: 6_300_000, var99: 0.0391, cvar95: 0.0316, maxDrawdown: -0.183, beta: 1.34, sharpe: 1.62,
  sortino: 2.1, effectiveHoldings: 8.4, limitChecks: LIMITS, riskLevel: "HIGH",
};

const ORDERS = [
  { ticker: "NVTK", side: "SELL", quantity: 36147, price: 484.13, value: 17_499_935 },
  { ticker: "LMNQ", side: "BUY", quantity: 162934, price: 108.05, value: 17_604_494 },
];

const approvals: Approval[] = [
  {
    approvalId: "7c1d2f9e-0000-4000-8000-000000000001", threadId: "req_mock_rebalance", requestId: "req_mock_rebalance",
    portfolio: "PF-A", status: "pending", reasons: ["hard limit breach: NVTK at 31.0% vs 25%", "draft orders $35.1M exceed the $250.0k threshold"],
    proposal: { orders: ORDERS, question: "Propose a rebalance for Portfolio A" }, totalValue: 35_104_429,
    requestedBy: "pm-user", decidedBy: null, decidedAt: null, decisionNote: null, expiresAt: now(), createdAt: now(),
  },
];

function report(question: string): Report {
  return {
    requestId: `req_mock_${Date.now()}`,
    question,
    intent: "risk_increase_explanation",
    portfolio: "PF-A",
    tickers: [],
    headline: "Portfolio A — Technology Growth: risk HIGH (67/100); volatility 22.9% → 32.8%, driven mainly by market moves; 1 hard limit breach (NVTK 31.0%).",
    riskLevel: "HIGH",
    sections: {
      facts: [
        { agent: "portfolio", text: "Portfolio A — Technology Growth (PF-A) is worth $250.0M as of 2026-09-30, with 2.0% in cash." },
        { agent: "portfolio", text: "The largest holding is NVTK at 31.0% of the portfolio." },
        { agent: "risk", text: "1-day 95% historical VaR is 2.52% ($6.3M); expected shortfall 3.16%." },
        { agent: "risk", text: "Annualised volatility rose from 22.9% to 32.8% over the last 63 trading days: 9.2% from market moves and 0.7% from position changes." },
        { agent: "risk", text: "Limit breach (hard): NVTK single-name at 31.0% vs 25% limit (Investment Policy §4.2 Single-issuer concentration)." },
      ],
      mlPredictions: [{ agent: "risk", text: "Next-quarter risk score 48/100 (MEDIUM) from risk-lgbm@2; an estimate, not a guarantee." }],
      interpretation: "Portfolio A's risk rose mainly because semiconductor volatility jumped while NVTK grew to 31.0% of the portfolio, above the 25% hard limit.",
      interpretationSource: "llm",
      recommendations: ["Bring NVTK back below the 25% single-name limit; a draft rebalance can be prepared and needs portfolio-manager or compliance approval."],
      assumptions: [],
      uncertainty: [],
    },
    approval: { required: true, reasons: ["hard limit breach: NVTK at 31.0% vs 25%"] },
    agents: ["portfolio", "market", "risk", "compliance"].map((name) => ({ name, status: "ok", confidence: 0.9, durationMs: 1200, llmUsed: true, toolCalls: [] })),
    evidence: [{ source: "get_market_news", citation: "Global equities end September higher", url: "https://example.com/news/1", as_of: "2026-09-28" }],
    confidence: 0.9,
    routing: { method: "mock", confidence: 1 },
    guard: { input: "allow", output: "pass" },
    disclaimer: "Decision support only — not investment advice.",
    durationMs: 4200,
  };
}

const FIXTURES: Record<string, () => unknown> = {
  "/api/v1/me": () => ({ userId: "mock-user", email: MOCK_USERS.find((u) => u.role === mockRole)?.email ?? null, role: mockRole, tenantId: "northwind", permissions: PERMISSIONS[mockRole] ?? [] }),
  "/api/v1/portfolios": () => [
    { portfolioId: "PF-A", name: "Portfolio A — Technology Growth", strategy: "growth" },
    { portfolioId: "PF-B", name: "Portfolio B — Balanced Multi-Asset", strategy: "balanced" },
  ],
  "/api/v1/portfolio/PF-A": () => PORTFOLIO,
  "/api/v1/portfolio/PF-B": () => ({ ...PORTFOLIO, portfolioId: "PF-B", name: "Portfolio B — Balanced Multi-Asset", breaches: 0 }),
  "/api/v1/risk/PF-A": () => RISK,
  "/api/v1/risk/PF-B": () => ({ ...RISK, portfolioId: "PF-B", riskLevel: "LOW", limitChecks: [] }),
  "/api/v1/dashboard/overview": () => ({
    portfolios: [
      { portfolioId: "PF-A", name: PORTFOLIO.name, nav: 250e6, dailyReturn: 0.0074, return1y: 0.542, volatility: 0.268, var95: 0.0252, breaches: 4, priceDate: "2026-09-30" },
      { portfolioId: "PF-B", name: "Portfolio B — Balanced Multi-Asset", nav: 180e6, dailyReturn: 0.0021, return1y: 0.118, volatility: 0.094, var95: 0.0089, breaches: 0, priceDate: "2026-09-30" },
    ],
    totals: { nav: 430e6, breaches: 4, pendingApprovals: approvals.filter((a) => a.status === "pending").length },
    recentActivity: [{ at: now(), requestId: "req_mock_rebalance", action: "approval.request", decision: "flag", reason: "draft orders need approval", userRole: "portfolio_manager" }],
    disclaimer: "Decision support only — not investment advice.",
  }),
  "/api/v1/dashboard/compliance": () => ({ checks: LIMITS.map((c) => ({ ...c, portfolioId: "PF-A", name: PORTFOLIO.name })), breaches: LIMITS.map((c) => ({ ...c, portfolioId: "PF-A", name: PORTFOLIO.name })) }),
  "/api/v1/dashboard/markets": () => ({
    date: "2026-09-30", benchmark: { ticker: "FGEI", level: 6456.95, return1d: 0.0081, return1m: 0.044, volatility3m: 0.131 },
    sectors: [{ sector: "Semiconductors", return1m: 0.254, names: 29 }, { sector: "Energy", return1m: 0.1, names: 25 }, { sector: "Fixed Income", return1m: 0.009, names: 30 }],
  }),
  "/api/v1/dashboard/news": () => ({ provider: "synthetic", items: [{ title: "Global equities end September higher; technology leads volatility", url: "https://example.com/news/1", published: "2026-09-28", source: "Synthetic Wire", summary: "Semiconductor names swung sharply.", tickers: ["NVTK"], sentiment: 0.2 }] }),
  "/api/v1/dashboard/fraud": () => ({ alerts: [{ transactionId: "TX-004512", at: now(), amount: 9850, currency: "USD", category: "electronics", channel: "online", country: "RO", probability: 0.98, riskLevel: "CRITICAL", reasons: ["new device", "foreign country", "amount 12x median"], modelVersion: "fraud-lgbm@2", scoredAt: now() }], flagged: 1, note: "ML predictions on synthetic data; a fraud analyst must review before action." }),
  "/api/v1/dashboard/agents": () => ({ agents: ["portfolio", "market", "risk", "compliance", "fraud", "research", "prediction"].map((name) => ({ name, description: `${name} agent`, version: "0.1.0", tasks: [name], tools: [], stats: { runs: 12, avgDurationMs: 1400, avgConfidence: 0.88, failed: 0, lastRunAt: now() } })) }),
  "/api/v1/dashboard/ml/models": () => [
    { kind: "fraud", name: "fraud-lgbm", version: "2", algorithm: "LightGBM classifier + IsolationForest anomaly feature", trainedAt: "2026-10-08T13:27:55+00:00", features: 16, testMetrics: { test_precision: 1, test_recall: 0.9, test_pr_auc: 0.981 }, note: "Trained on synthetic data; metrics on a time-based test split." },
  ],
  "/api/v1/dashboard/system/status": () => ({ checks: { database: "ok", redis: "ok" }, kvStore: "redis", circuits: {}, answerChain: ["euri:gpt-4.1-mini"], agentChain: ["euri:gpt-4.1-mini"], demoMode: true, environment: "mock" }),
  "/api/v1/dashboard/activity": () => [{ at: now(), requestId: "req_mock_rebalance", action: "approval.request", decision: "flag", reason: "draft orders need approval", userRole: "portfolio_manager" }],
  "/api/v1/conversations": () => [],
  "/api/v1/documents": () => [
    { documentId: "d1", source: "Investment_Policy_Statement.docx", title: "Investment Policy Statement", docType: "policy", classification: "internal", status: "ready", chunks: 6, updatedAt: now() },
    { documentId: "d2", source: "Risk_Management_Framework.md", title: "Risk Management Framework", docType: "policy", classification: "internal", status: "ready", chunks: 4, updatedAt: now() },
  ],
};

export const mockApi = {
  async request<T>(path: string, init?: RequestInit): Promise<T> {
    await sleep(120);
    const method = init?.method ?? "GET";
    const bare = path.split("?")[0];
    if (bare.startsWith("/api/v1/approvals")) {
      const decision = bare.match(/approvals\/([^/]+)\/decision$/);
      if (decision && method === "POST") {
        const item = approvals.find((a) => a.approvalId === decision[1]);
        const { approve, note } = JSON.parse(String(init?.body ?? "{}"));
        if (!item) throw new Error("approval not found");
        Object.assign(item, { status: approve ? "approved" : "rejected", decidedBy: "mock-user", decidedAt: now(), decisionNote: note, createdDraftOrders: approve ? item.proposal.orders : [] });
        return item as T;
      }
      return approvals as T;
    }
    if (bare === "/api/v1/rag/query") {
      return { question: "", answer: "No single issuer may exceed 25% of portfolio NAV [1]. A position above 20% of NAV triggers a warning [1].", answerSource: "llm", citations: [{ n: 1, citation: 'Investment_Policy_Statement.docx, section "1. Concentration limits"', documentId: "d1", chunkId: "c1", relevanceScore: 4.95 }], validation: [], kbVersion: 12, cached: false } as T;
    }
    if (bare.startsWith("/api/v1/audit/")) {
      return { requestId: bare.split("/").pop(), audit: [], agentRuns: [{ agent: "risk", task: "explain_risk_change", status: "ok", startedAt: now(), durationMs: 1800, confidence: 0.9, toolCalls: 4, error: null }], a2aMessages: [], toolCalls: [{ tool: "calculate_var", server: "risk", agent: "risk", status: "ok", durationMs: 120, errorCode: null, at: now() }] } as T;
    }
    if (bare.startsWith("/api/v1/analyze/") || bare === "/api/v1/research" || bare === "/api/v1/predict") {
      const r = report(`mock ${bare}`);
      return { requestId: r.requestId, report: r, conversationId: null } as T;
    }
    const fixture = FIXTURES[bare];
    if (!fixture) throw new Error(`mock: no fixture for ${method} ${bare}`);
    return fixture() as T;
  },

  async stream(question: string, onEvent: (event: StreamEvent) => void, signal?: AbortSignal): Promise<void> {
    const ts = () => Date.now() / 1000;
    const r = report(question);
    onEvent({ event: "start", requestId: r.requestId, traceId: "mock" });
    await sleep(300, signal);
    onEvent({ event: "classification", intent: r.intent, method: "mock", portfolio: "PF-A", confidence: 1, ts: ts() });
    onEvent({ event: "plan", intent: r.intent, stages: [["portfolio", "market"], ["risk"], ["compliance"]], ts: ts() });
    for (const stage of [["portfolio", "market"], ["risk"], ["compliance"]]) {
      stage.forEach((agent) => onEvent({ event: "agent_start", agent, ts: ts() }));
      await sleep(400, signal);
      stage.forEach((agent) => onEvent({ event: "agent_end", agent, status: "ok", confidence: 0.9, tools: ["get_holdings"], durationMs: 400, ts: ts() }));
    }
    for (const word of (r.sections.interpretation ?? "").split(" ")) {
      onEvent({ event: "token", text: `${word} `, ts: ts() });
      await sleep(15, signal);
    }
    onEvent({ event: "report", report: r, ts: ts() });
    onEvent({ event: "done", durationMs: 2400 });
  },
};
