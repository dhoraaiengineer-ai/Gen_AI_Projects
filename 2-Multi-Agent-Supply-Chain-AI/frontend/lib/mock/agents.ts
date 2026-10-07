import type { AgentId, AgentInfo } from "@/types";
import { Rng } from "./rng";

export interface AgentMeta {
  id: AgentId;
  name: string;
  short: string;
  purpose: string;
  tools: string[];
}

/** Static agent catalogue — mirrors the specs in agents/*.md. */
export const AGENTS: Record<AgentId, AgentMeta> = {
  supervisor: {
    id: "supervisor",
    name: "Supervisor Agent",
    short: "Supervisor",
    purpose: "Understands intent, plans the workflow, routes work to specialists and assembles the final recommendation.",
    tools: ["classify_intent", "plan_workflow", "request_approval", "synthesize_report"],
  },
  demand: {
    id: "demand",
    name: "Demand Forecast Agent",
    short: "Demand",
    purpose: "Analyses sales history, trend and seasonality to produce structured demand forecasts.",
    tools: ["get_sales_history", "get_demand_forecast", "get_product_history"],
  },
  inventory: {
    id: "inventory",
    name: "Inventory Agent",
    short: "Inventory",
    purpose: "Checks stock positions, computes safety stock and reorder points, and detects stockout risk. Read-only.",
    tools: ["get_inventory", "get_sales_history", "get_demand_forecast", "calculate_reorder_quantity"],
  },
  supplier: {
    id: "supplier",
    name: "Supplier Agent",
    short: "Supplier",
    purpose: "Compares supplier price, lead time and reliability, and recommends the best-fit supplier.",
    tools: ["get_suppliers", "get_supplier_price", "get_supplier_lead_time", "get_supplier_score"],
  },
  logistics: {
    id: "logistics",
    name: "Logistics Agent",
    short: "Logistics",
    purpose: "Tracks shipments, flags delays, compares carriers and estimates delivery dates.",
    tools: ["get_shipments", "get_carrier_rates", "get_delivery_status", "estimate_delivery"],
  },
  rag: {
    id: "rag",
    name: "Knowledge Agent (RAG)",
    short: "Knowledge",
    purpose: "Searches policies, contracts and SOPs with hybrid retrieval and answers with source citations.",
    tools: ["search_knowledge_base", "rerank_passages", "cite_sources"],
  },
  research: {
    id: "research",
    name: "Research Agent",
    short: "Research",
    purpose: "Combines the knowledge base with web search for market and supplier intelligence. Web results are cited by URL.",
    tools: ["search_knowledge_base", "search_web"],
  },
};

export const AGENT_ORDER: AgentId[] = ["supervisor", "demand", "inventory", "supplier", "logistics", "rag", "research"];

const STATS: Record<AgentId, { latency: number; success: number; tasks: number; today: number; model: string }> = {
  supervisor: { latency: 1180, success: 0.993, tasks: 18_420, today: 214, model: "gpt-4.1-mini" },
  demand: { latency: 2340, success: 0.987, tasks: 9_870, today: 121, model: "gpt-4.1-mini" },
  inventory: { latency: 1620, success: 0.991, tasks: 12_310, today: 156, model: "gpt-4.1-mini" },
  supplier: { latency: 2010, success: 0.984, tasks: 6_045, today: 73, model: "gpt-4.1-mini" },
  logistics: { latency: 1490, success: 0.989, tasks: 7_288, today: 88, model: "gpt-4.1-mini" },
  rag: { latency: 2780, success: 0.978, tasks: 8_932, today: 104, model: "gemini-embedding-001 · gpt-4.1-mini" },
  research: { latency: 5420, success: 0.962, tasks: 1_204, today: 11, model: "qwen3.8-27b · Tavily" },
};

const ACTIVITY: Record<AgentId, string[]> = {
  supervisor: [
    "Routed full recommendation for SKU-100 to 5 agents",
    "Requested approval for PO draft above $50,000",
    "Completed workflow: delayed shipment review",
    "Classified intent: supplier selection",
  ],
  demand: ["Forecast SKU-100: 12,000 units next 30 days", "Detected weekly seasonality on SKU-104", "Backtest MAPE 6.8% on Power Systems"],
  inventory: ["Stockout risk detected: SKU-100 (4.1 days cover)", "Reorder quantity calculated: SKU-117", "Safety stock recalculated for 38 SKUs"],
  supplier: ["Compared 5 suppliers for SKU-100", "Excluded 4 suppliers: lead time exceeds cover", "Contract expiry flagged: Rhine Valley Chemicals"],
  logistics: ["12 delayed shipments identified", "Estimated delivery for SHP-48210: +3 days", "Compared air vs. ocean for Shenzhen → Tokyo"],
  rag: ["Retrieved procurement policy §4.2 (expedited orders)", "Answered: single-source supplier policy", "Indexed Nordvolt supply agreement (42 chunks)"],
  research: ["Researched port congestion at Tokyo Bay", "Summarised lithium price outlook (3 web sources)"],
};

export function agentInfo(id: AgentId): AgentInfo {
  const meta = AGENTS[id];
  const stats = STATS[id];
  const rng = new Rng(id.length * 131 + id.charCodeAt(0));
  const minutesAgo = (k: number) => new Date(Date.now() - k * 60_000).toISOString();
  return {
    id,
    name: meta.name,
    purpose: meta.purpose,
    status: id === "research" ? "degraded" : "operational",
    model: stats.model,
    tools: meta.tools,
    avgLatencyMs: stats.latency,
    p95LatencyMs: Math.round(stats.latency * 2.1),
    successRate: stats.success,
    tasksCompleted: stats.tasks,
    tasksToday: stats.today,
    lastActive: minutesAgo(rng.int(0, 6)),
    latencyTrend: Array.from({ length: 24 }, () => Math.round(stats.latency * rng.float(0.8, 1.25))),
    recentActivity: ACTIVITY[id].map((message, k) => ({
      timestamp: minutesAgo(3 + k * rng.int(4, 19)),
      message,
      outcome: message.startsWith("Requested approval") ? "escalated" : "success",
    })),
  };
}

export function allAgents(): AgentInfo[] {
  return AGENT_ORDER.map(agentInfo);
}
