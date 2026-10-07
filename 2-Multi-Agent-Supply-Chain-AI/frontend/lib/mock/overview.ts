import type { AnalyticsData, Overview, Recommendation } from "@/types";
import { atRiskItems, inventorySummary, lastMonths } from "./inventory";
import { logisticsSummary } from "./logistics";
import { Rng } from "./rng";

const RECOMMENDATIONS: Omit<Recommendation, "createdAt">[] = [
  {
    id: "REC-1",
    title: "Replenish SKU-100 with 10,000 units from Nordvolt Energy",
    detail: "4.1 days of cover against a 9-day lead time. Nordvolt delivers in 3 days at 98% reliability.",
    sku: "SKU-100",
    risk: "critical",
    impact: "Avoids an estimated $412K in lost sales",
    agents: ["demand", "inventory", "supplier", "logistics", "rag"],
    confidence: 0.91,
  },
  {
    id: "REC-2",
    title: "Expedite SHP-48210 by air for the remaining 850 units",
    detail: "Ocean shipment delayed 3 days by port congestion; air freight closes the gap for $3,900.",
    sku: "SKU-100",
    risk: "high",
    impact: "Recovers 3 days of supply",
    agents: ["logistics", "rag"],
    confidence: 0.82,
  },
  {
    id: "REC-3",
    title: "Qualify a secondary supplier for Hydraulic Valve Series 60",
    detail: "SKU-117 is single-sourced, which breaches the 70% single-source policy limit.",
    sku: "SKU-117",
    risk: "medium",
    impact: "Reduces supply concentration risk",
    agents: ["supplier", "rag"],
    confidence: 0.77,
  },
];

export function overview(): Overview {
  const inv = inventorySummary();
  const log = logisticsSummary();
  const rng = new Rng(11);
  const spark = (start: number, drift: number) =>
    Array.from({ length: 12 }, (_, k) => Math.round(start * (1 + drift * k) + rng.normal(0, start * 0.01)));
  const months = lastMonths(8);
  return {
    kpis: [
      {
        id: "skus", label: "Total SKUs", value: inv.totalSkus, display: inv.totalSkus.toLocaleString(),
        delta: 4.8, deltaLabel: "vs last quarter", goodDirection: "neutral", context: "Across 5 distribution centres",
        trend: spark(1190, 0.004), icon: "boxes",
      },
      {
        id: "risk", label: "Inventory Risk", value: inv.atRisk, display: String(inv.atRisk),
        delta: -11.2, deltaLabel: "vs last week", goodDirection: "down", context: `${inv.critical} critical · ${inv.atRisk - inv.critical} high`,
        trend: spark(44, -0.015), icon: "alert",
      },
      {
        id: "delayed", label: "Delayed Shipments", value: log.delayed, display: String(log.delayed),
        delta: -8.4, deltaLabel: "vs last week", goodDirection: "down", context: `Avg delay ${log.avgDelayDays} days`,
        trend: spark(14, -0.012), icon: "truck",
      },
      {
        id: "health", label: "Supply Chain Health", value: 94.8, display: "94.8%",
        delta: 2.1, deltaLabel: "vs last month", goodDirection: "up", context: "Service level target 95%",
        trend: spark(91.5, 0.003), icon: "activity",
      },
    ],
    healthScore: 94.8,
    healthDimensions: [
      { label: "Inventory availability", score: 96.2 },
      { label: "Supplier reliability", score: 93.4 },
      { label: "On-time delivery", score: 92.7 },
      { label: "Forecast accuracy", score: 91.6 },
    ],
    topRisks: atRiskItems().slice(0, 5),
    recommendations: RECOMMENDATIONS.map((r, i) => ({ ...r, createdAt: new Date(Date.now() - (i * 37 + 6) * 60_000).toISOString() })),
    supplyDemand: months.map((label, k) => ({
      label,
      demand: Math.round(212_000 + k * 4_100 + 9_000 * Math.sin(k / 1.3)),
      supply: Math.round(219_000 + k * 3_200 + 6_000 * Math.cos(k / 1.6)),
    })),
  };
}

export function analytics(): AnalyticsData {
  const months = lastMonths(12);
  const rng = new Rng(808);
  return {
    period: "Last 12 months",
    headline: [
      { id: "savings", label: "Cost Savings", value: 2_840_000, display: "$2.84M", delta: 18.6, deltaLabel: "vs prior year", goodDirection: "up", context: "Procurement and expedite avoidance", trend: months.map((_, k) => 150 + k * 14), icon: "dollar" },
      { id: "stockouts", label: "Stockout Reduction", value: 37, display: "37%", delta: 9.2, deltaLabel: "vs prior year", goodDirection: "up", context: "Stockout events vs. pre-AI baseline", trend: months.map((_, k) => 12 + k * 2.2), icon: "target" },
      { id: "accuracy", label: "Forecast Accuracy", value: 91.6, display: "91.6%", delta: 3.4, deltaLabel: "vs prior year", goodDirection: "up", context: "1 − weighted MAPE, 30-day horizon", trend: months.map((_, k) => 86 + k * 0.48), icon: "gauge" },
      { id: "automation", label: "Automation Rate", value: 72, display: "72%", delta: 6.1, deltaLabel: "vs last quarter", goodDirection: "up", context: "Recommendations needing no escalation", trend: months.map((_, k) => 58 + k * 1.2), icon: "bot" },
    ],
    costSavings: months.map((label, k) => ({ label, value: Math.round(170_000 + k * 14_000 + rng.normal(0, 18_000)) })),
    forecastAccuracy: months.map((label, k) => ({ label, accuracy: Math.round((86 + k * 0.48 + rng.normal(0, 0.6)) * 10) / 10, target: 90 })),
    stockouts: months.map((label, k) => ({ label, baseline: Math.round(46 + rng.normal(0, 3)), withAi: Math.round(44 - k * 1.6 + rng.normal(0, 2)) })),
    supplierPerformance: [
      { supplier: "Nordvolt", onTime: 98, quality: 99.7 },
      { supplier: "Sakura", onTime: 96, quality: 99.6 },
      { supplier: "Atlas", onTime: 95, quality: 99.5 },
      { supplier: "Kaito", onTime: 94, quality: 99.4 },
      { supplier: "Baltic", onTime: 94, quality: 99.4 },
      { supplier: "Meridian", onTime: 91, quality: 98.9 },
      { supplier: "Pacific Rim", onTime: 86, quality: 98.1 },
    ],
    deliveryPerformance: months.map((label, k) => {
      const total = 1_480 + k * 22;
      const onTimePct = 0.89 + k * 0.0035 + rng.normal(0, 0.006);
      return { label, onTime: Math.round(total * onTimePct), late: Math.round(total * (1 - onTimePct)) };
    }),
    aiUsage: months.map((label, k) => {
      const recs = Math.round(820 + k * 95);
      const automated = Math.round(recs * (0.58 + k * 0.012));
      return { label, recommendations: recs, automated, escalated: recs - automated };
    }),
  };
}
