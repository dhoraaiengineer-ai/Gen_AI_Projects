import type { AgentId, ApprovalRequest, CopilotEvent, RecommendationReport, RiskLevel } from "@/types";
import { demandForecast } from "./demand";
import { atRiskItems, inventoryItem } from "./inventory";
import { delayedShipments } from "./logistics";
import { recommendSupplier, suppliersForSku } from "./suppliers";
import { searchDocuments } from "./documents";
import { daysFromNow } from "./rng";
import { registerApproval } from "./approvals";

export const APPROVAL_THRESHOLD_USD = 50_000;

type Intent =
  | "full_recommendation"
  | "stockout_risk"
  | "reorder_quantity"
  | "supplier_selection"
  | "inventory_explanation"
  | "demand_forecast"
  | "shipment_status"
  | "policy_question"
  | "out_of_scope";

const KNOWLEDGE_TERMS =
  /policy|polic|contract|agreement|clause|procurement|sop|rule|approval|threshold|incoterm|terms|guarantee|credit|penalt|payment|warrant|service level|premium|un3480|dangerous goods|escalat|declare|rate card|moq|minimum order/;
const SUPPLIER_NAMES = /kaito|meridian|nordvolt|pacific rim|atlas|sakura|lone star|rhine valley|harbor packaging|guardian|brightway|baltic/;
const SUPPLY_CHAIN_TERMS =
  /sku|stock|inventory|order|supplier|vendor|lead time|demand|forecast|shipment|shipping|freight|carrier|logistic|deliver|warehouse|customs|battery|batteries|price|cost/;

/** Keyword router — the same fallback the backend supervisor uses when the LLM classifier is unavailable. */
export function classifyIntent(message: string): Intent {
  const m = message.toLowerCase();
  if (/(complete|full|end-to-end|overall).*(recommend|plan)|recommendation for/.test(m)) return "full_recommendation";
  if (/(how much|how many|quantity).*(reorder|order)|reorder/.test(m)) return "reorder_quantity";
  if (/why/.test(m) && /(inventory|stock|low)/.test(m)) return "inventory_explanation";
  if (/supplier|vendor/.test(m) && !/policy|contract/.test(m)) return "supplier_selection";
  if (/shipment|delayed|delivery|carrier|logistic/.test(m)) return "shipment_status";
  if (/forecast|demand|next month/.test(m)) return "demand_forecast";
  if (/risk|stockout|stock-out|running out/.test(m)) return "stockout_risk";
  if (KNOWLEDGE_TERMS.test(m) || SUPPLIER_NAMES.test(m)) return "policy_question";
  // A clearly supply-chain question with no specific intent → search the knowledge base instead of refusing.
  if (SUPPLY_CHAIN_TERMS.test(m)) return "policy_question";
  return "out_of_scope";
}

const PLANS: Record<Intent, AgentId[][]> = {
  full_recommendation: [["demand", "rag"], ["inventory"], ["supplier", "logistics"]],
  stockout_risk: [["demand"], ["inventory"]],
  reorder_quantity: [["demand"], ["inventory"]],
  supplier_selection: [["inventory"], ["supplier", "rag"]],
  inventory_explanation: [["demand", "logistics"], ["inventory"]],
  demand_forecast: [["demand"]],
  shipment_status: [["logistics"]],
  policy_question: [["rag"]],
  out_of_scope: [],
};

const RUNNING: Record<AgentId, string> = {
  supervisor: "Understanding request…",
  demand: "Analyzing demand…",
  inventory: "Checking inventory…",
  supplier: "Comparing suppliers…",
  logistics: "Checking shipments…",
  rag: "Searching policies and contracts…",
  research: "Researching external sources…",
};

function extractSku(message: string): string {
  const match = message.match(/sku[-\s]?(\d{3,6})/i);
  return match ? `SKU-${match[1]}` : "SKU-100";
}

function completedMessage(agent: AgentId, sku: string): string {
  const item = inventoryItem(sku);
  switch (agent) {
    case "demand":
      return `Forecast ${item?.forecast30d.toLocaleString() ?? "—"} units / 30 days`;
    case "inventory":
      return item ? `${item.daysOfCover} days of cover · ${item.risk} risk` : "Inventory checked";
    case "supplier": {
      const rec = recommendSupplier(sku);
      return `${suppliersForSku(sku).length} compared · ${suppliersForSku(sku).find((s) => s.id === rec.supplierId)?.name}`;
    }
    case "logistics":
      return `${delayedShipments().length} delayed shipments reviewed`;
    case "rag":
      return "3 relevant passages retrieved";
    default:
      return "Done";
  }
}

const sleep = (ms: number, signal?: AbortSignal) =>
  new Promise<void>((resolve, reject) => {
    const t = setTimeout(resolve, ms);
    signal?.addEventListener("abort", () => {
      clearTimeout(t);
      reject(new DOMException("Aborted", "AbortError"));
    });
  });

function requestId(): string {
  return `REQ-${Math.random().toString(16).slice(2, 8).toUpperCase()}`;
}

function baseReport(partial: Partial<RecommendationReport> & Pick<RecommendationReport, "headline" | "summary">): RecommendationReport {
  return {
    riskLevel: "low",
    reasoning: [],
    evidence: [],
    impact: [],
    confidence: { level: "high", score: 0.88 },
    sources: [],
    agentsInvolved: ["supervisor"],
    guard: { status: "grounded", reasons: [] },
    latencyMs: 0,
    requestId: requestId(),
    ...partial,
  };
}

function buildReport(intent: Intent, sku: string, message: string): RecommendationReport {
  const item = inventoryItem(sku);
  const plan = PLANS[intent].flat();
  const agentsInvolved: AgentId[] = ["supervisor", ...plan];

  if (intent === "out_of_scope") {
    return baseReport({
      headline: "That's outside what I can help with",
      summary:
        "I'm the supply-chain copilot. I can answer questions about inventory, demand, suppliers, logistics and your company's procurement, inventory and shipping policies.",
      confidence: { level: "high", score: 0.99 },
      agentsInvolved: ["supervisor"],
    });
  }

  if (intent === "stockout_risk") {
    const risks = atRiskItems();
    const critical = risks.filter((r) => r.risk === "critical");
    return baseReport({
      headline: `${risks.length} products are at risk of stockout — ${critical.length} critical`,
      riskLevel: critical.length ? "critical" : "high",
      summary: `${critical.length} SKUs will run out before replenishment can arrive. ${risks[0].sku} is the most urgent with ${risks[0].daysOfCover} days of cover against a ${risks[0].leadTimeDays}-day lead time.`,
      reasoning: [
        "Risk compares days of cover with supplier lead time and reorder point",
        "Critical: cover is shorter than lead time and inbound stock does not close the gap",
        "High: available plus on-order stock is below the reorder point",
      ],
      evidence: [
        { label: "Critical SKUs", value: String(critical.length), source: "inventory" },
        { label: "High-risk SKUs", value: String(risks.length - critical.length), source: "inventory" },
        { label: "Most urgent", value: `${risks[0].sku} · ${risks[0].daysOfCover} days`, source: "inventory" },
      ],
      table: {
        title: "Highest-risk products",
        columns: ["SKU", "Product", "Days of cover", "Lead time", "Risk", "Suggested reorder"],
        rows: risks.slice(0, 8).map((r) => [r.sku, r.name, r.daysOfCover, `${r.leadTimeDays} d`, r.risk.toUpperCase(), r.reorderQty.toLocaleString()]),
      },
      impact: ["Prioritised reorder list ready for review", "Critical SKUs can be sent to the full recommendation workflow"],
      agentsInvolved,
    });
  }

  if (intent === "shipment_status") {
    const delayed = delayedShipments();
    const avg = delayed.reduce((s, d) => s + d.delayDays, 0) / delayed.length;
    return baseReport({
      headline: `${delayed.length} shipments are delayed — average ${avg.toFixed(1)} days`,
      riskLevel: "high",
      summary: `${delayed.length} inbound shipments have passed their promised date. The largest impact is ${delayed[0].id} carrying ${delayed[0].units.toLocaleString()} units of ${delayed[0].sku}, delayed ${delayed[0].delayDays} days by port congestion.`,
      reasoning: ["A shipment is delayed when its ETA is later than the promised date", "Impact is weighted by the stockout risk of the SKU on board"],
      evidence: [
        { label: "Delayed shipments", value: String(delayed.length), source: "logistics" },
        { label: "Average delay", value: `${avg.toFixed(1)} days`, source: "logistics" },
        { label: "Affecting at-risk SKUs", value: "3", source: "inventory" },
      ],
      table: {
        title: "Delayed shipments",
        columns: ["Shipment", "SKU", "Carrier", "Route", "Delay", "Latest event"],
        rows: delayed.map((d) => [d.id, d.sku, d.carrier, `${d.origin} → ${d.destination}`, `${d.delayDays} d`, d.lastEvent]),
      },
      impact: ["Expediting SHP-48210 by air recovers 3 days of supply for SKU-100"],
      agentsInvolved,
    });
  }

  if (intent === "policy_question") {
    const result = searchDocuments(message);
    return baseReport({
      headline: result.citations.length ? "Here's what your policies say" : "I couldn't find that in your documents",
      summary: result.answer,
      riskLevel: "low",
      reasoning: result.citations.length ? ["Answer is limited to retrieved passages; every statement is cited"] : [],
      sources: result.citations.map((c) => ({ n: c.n, title: c.source, location: c.location })),
      confidence: result.citations.length ? { level: "high", score: 0.9 } : { level: "low", score: 0.2 },
      guard: { status: result.guard.status === "refused" ? "grounded" : result.guard.status, reasons: result.guard.reasons },
      agentsInvolved,
    });
  }

  if (!item) {
    return baseReport({
      headline: `I couldn't find ${sku}`,
      summary: `${sku} doesn't exist in the product catalogue. Check the SKU, or ask about at-risk products to see valid SKUs.`,
      confidence: { level: "high", score: 0.97 },
      agentsInvolved,
    });
  }

  const forecast = demandForecast(sku, "30d");
  const supplierRec = recommendSupplier(sku);
  const supplier = suppliersForSku(sku).find((s) => s.id === supplierRec.supplierId)!;
  const poValue = Math.round(item.reorderQty * supplier.unitPrice);

  if (intent === "demand_forecast") {
    return baseReport({
      headline: `${sku} demand forecast: ${forecast.totalForecast.toLocaleString()} units over the next 30 days`,
      riskLevel: "low",
      summary: `Expected demand is ${forecast.dailyMean.toLocaleString()} units per day on average, trending ${forecast.trend.direction} ${Math.abs(forecast.trend.pctChange)}%. Backtest accuracy is ${(100 - forecast.accuracy.mape).toFixed(1)}%.`,
      reasoning: forecast.drivers,
      evidence: [
        { label: "30-day forecast", value: `${forecast.totalForecast.toLocaleString()} units`, source: "demand" },
        { label: "Method", value: forecast.method, source: "demand" },
        { label: "MAPE (backtest)", value: `${forecast.accuracy.mape}%`, source: "demand" },
      ],
      forecast: forecast.points.slice(-60),
      confidence: { level: forecast.confidence, score: 1 - forecast.accuracy.mape / 100 },
      agentsInvolved,
    });
  }

  const inventoryEvidence = [
    { label: "Available stock", value: `${item.available.toLocaleString()} units`, source: "inventory" as AgentId },
    { label: "30-day forecast", value: `${item.forecast30d.toLocaleString()} units`, source: "demand" as AgentId },
    { label: "Days of cover", value: `${item.daysOfCover} days`, source: "inventory" as AgentId },
    { label: "Safety stock / ROP", value: `${item.safetyStock.toLocaleString()} / ${item.reorderPoint.toLocaleString()}`, source: "inventory" as AgentId },
  ];

  if (intent === "inventory_explanation") {
    return baseReport({
      headline: `${sku} inventory is low because demand outpaced replenishment`,
      riskLevel: item.risk,
      summary: `Available stock of ${item.available.toLocaleString()} units covers ${item.daysOfCover} days, below the ${item.leadTimeDays}-day lead time. Three factors explain the gap.`,
      reasoning: [
        `Demand rose ${Math.abs(forecast.trend.pctChange)}% over the period, ahead of the reorder point being recalculated`,
        `${(item.onHand - item.available).toLocaleString()} units are allocated to open customer orders`,
        "The inbound 850-unit shipment SHP-48210 is delayed 3 days by port congestion",
      ],
      evidence: inventoryEvidence,
      impact: [`Reordering ${item.reorderQty.toLocaleString()} units restores cover above the reorder point`],
      agentsInvolved,
    });
  }

  if (intent === "supplier_selection") {
    return baseReport({
      headline: `Select ${supplier.name} for ${sku}`,
      riskLevel: item.risk,
      summary: supplierRec.summary,
      reasoning: supplierRec.reasons,
      evidence: suppliersForSku(sku).map((s) => ({
        label: s.name,
        value: `$${s.unitPrice.toFixed(2)} · ${s.leadTimeDays} d · ${(s.reliability * 100).toFixed(0)}%`,
        source: "supplier" as AgentId,
      })),
      supplier: { id: supplier.id, name: supplier.name, unitPrice: supplier.unitPrice, leadTimeDays: supplier.leadTimeDays, reliability: supplier.reliability },
      sources: [{ n: 1, title: "Nordvolt Energy — Master Supply Agreement.pdf", location: "p. 3, clause 6.1" }],
      confidence: { level: "high", score: supplierRec.confidence },
      agentsInvolved,
    });
  }

  // reorder_quantity and full_recommendation
  const approval: ApprovalRequest | undefined =
    poValue > APPROVAL_THRESHOLD_USD
      ? {
          id: `APR-${Math.random().toString(16).slice(2, 7).toUpperCase()}`,
          runId: `run_${Date.now().toString(36)}`,
          sku,
          supplier: supplier.name,
          quantity: item.reorderQty,
          unitPrice: supplier.unitPrice,
          value: poValue,
          reason: `PO value $${poValue.toLocaleString()} exceeds the $${APPROVAL_THRESHOLD_USD.toLocaleString()} approval threshold (Procurement Policy §4.2)`,
          expiresAt: daysFromNow(1).toISOString(),
          status: "pending",
        }
      : undefined;

  const risk: RiskLevel = item.risk;
  if (intent === "reorder_quantity") {
    return baseReport({
      headline: `Reorder ${item.reorderQty.toLocaleString()} units of ${sku}`,
      riskLevel: risk,
      summary: `Covering the 30-day forecast of ${item.forecast30d.toLocaleString()} units plus ${item.safetyStock.toLocaleString()} units of safety stock, net of ${item.available.toLocaleString()} available and ${item.onOrder.toLocaleString()} on order, requires ${item.reorderQty.toLocaleString()} units (rounded to the 500-unit pack size).`,
      reasoning: ["Quantity = 30-day forecast + safety stock − available − on order", "Safety stock targets a 95% service level"],
      evidence: inventoryEvidence,
      approval,
      agentsInvolved,
    });
  }

  return baseReport({
    headline: `Replenish ${sku} with ${item.reorderQty.toLocaleString()} units from ${supplier.name}`,
    riskLevel: risk,
    summary: `Current available inventory is ${item.available.toLocaleString()} units while forecast demand is ${item.forecast30d.toLocaleString()} units over the next 30 days. Stock runs out in ${item.daysOfCover} days — before the current supplier's ${item.leadTimeDays}-day lead time.`,
    reasoning: [
      `Demand is trending ${forecast.trend.direction} ${Math.abs(forecast.trend.pctChange)}% with a weekly seasonal pattern`,
      `${supplier.name} is the only qualified supplier that delivers within the ${item.daysOfCover}-day cover window`,
      "Inbound shipment SHP-48210 (850 units) is delayed 3 days and cannot close the gap alone",
      "Procurement Policy §5.1 permits expedited orders when cover is below lead time [1]",
    ],
    evidence: inventoryEvidence,
    supplier: { id: supplier.id, name: supplier.name, unitPrice: supplier.unitPrice, leadTimeDays: supplier.leadTimeDays, reliability: supplier.reliability },
    impact: [
      "Stockout risk reduced from critical to low",
      `${supplier.leadTimeDays}-day delivery — arrives before projected stockout`,
      `${(supplier.reliability * 100).toFixed(0)}% supplier reliability`,
      "An estimated $412K in lost sales avoided",
    ],
    confidence: { level: "high", score: 0.91 },
    sources: [
      { n: 1, title: "Global Procurement Policy v4.2.pdf", location: "p. 9, §5.1" },
      { n: 2, title: "Global Procurement Policy v4.2.pdf", location: "p. 7, §4.2" },
      { n: 3, title: "Nordvolt Energy — Master Supply Agreement.pdf", location: "p. 3, clause 6.1" },
    ],
    approval,
    agentsInvolved,
  });
}

/** Simulated SSE stream with realistic pacing. Mirrors POST /api/chat/stream event types. */
export async function* mockCopilotStream(message: string, signal?: AbortSignal): AsyncGenerator<CopilotEvent> {
  const started = performance.now();
  const intent = classifyIntent(message);
  const sku = extractSku(message);
  const stages = PLANS[intent];
  const runId = `run_${Date.now().toString(36)}`;
  const report = buildReport(intent, sku, message);

  yield { type: "run_started", runId, requestId: report.requestId };

  // 1. Input guardrails (injection, PII/PHI, policy scope)
  yield { type: "step", step: "guard", status: "running", message: "Checking input guardrails…" };
  await sleep(250, signal);
  yield { type: "step", step: "guard", status: "completed", message: "No injection or sensitive data detected", durationMs: 250 };

  // 2. Intent classifier (structured output)
  yield { type: "step", step: "classifier", status: "running", message: "Understanding request…" };
  await sleep(550, signal);
  yield { type: "step", step: "classifier", status: "completed", message: `Intent: ${intent.replace(/_/g, " ")}${intent !== "out_of_scope" ? ` · ${sku}` : ""}`, durationMs: 550 };

  // 3. Supervisor plans and routes
  yield { type: "plan", intent, agents: stages.flat(), stages };
  yield { type: "step", step: "supervisor", status: "running", message: "Planning workflow…" };
  await sleep(350, signal);
  yield {
    type: "step",
    step: "supervisor",
    status: "completed",
    message: stages.length ? `Routed to ${stages.flat().length} agents in ${stages.length} stage${stages.length > 1 ? "s" : ""}` : "Out of scope — no agents needed",
    durationMs: 350,
  };

  // 4. Specialist agents — stages run in sequence, agents within a stage in parallel
  for (const stage of stages) {
    for (const agent of stage) yield { type: "step", step: agent, status: "running", message: RUNNING[agent] };
    const order = [...stage].sort(() => 0.5 - Math.random());
    for (const agent of order) {
      const ms = 650 + Math.random() * 700;
      await sleep(ms, signal);
      yield { type: "step", step: agent, status: "completed", message: completedMessage(agent, sku), durationMs: Math.round(ms) };
    }
  }

  // 5. Human-in-the-loop when policy requires it
  if (report.approval) {
    registerApproval(report.approval);
    yield { type: "step", step: "approval", status: "running", message: "Awaiting approver decision" };
    yield { type: "approval_required", approval: report.approval };
  }

  // 6. Synthesizer streams the report summary
  yield { type: "step", step: "synthesizer", status: "running", message: "Preparing recommendation…" };
  await sleep(300, signal);
  const words = report.summary.split(/(\s+)/);
  for (let i = 0; i < words.length; i += 4) {
    yield { type: "token", text: words.slice(i, i + 4).join("") };
    await sleep(35, signal);
  }
  yield { type: "step", step: "synthesizer", status: "completed", message: "Report drafted from tool evidence" };

  // 7. Validator — output guardrails (numbers, citations, PII)
  yield { type: "step", step: "validator", status: "running", message: "Validating against evidence…" };
  await sleep(250, signal);
  yield { type: "step", step: "validator", status: "completed", message: "All figures and citations verified", durationMs: 250 };

  yield { type: "report", report: { ...report, latencyMs: Math.round(performance.now() - started) } };
}
