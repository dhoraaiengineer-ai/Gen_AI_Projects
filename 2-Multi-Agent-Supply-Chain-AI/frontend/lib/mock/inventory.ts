import type { InventoryItem, InventorySummary, RiskLevel } from "@/types";
import { PRODUCT_CATEGORIES } from "../constants";
import { ceilTo, Rng, round } from "./rng";

/**
 * Inventory maths mirrors app/services/inventory_math.py so mock and live numbers behave the same:
 *   SS  = z · σ_d · √LT            (z = 1.65 → 95% service level)
 *   ROP = d̄ · LT + SS
 *   qty = forecast30 + SS − available − onOrder   (rounded up to pack size) when available + onOrder < ROP
 */
const Z_95 = 1.65;
const REVIEW_DAYS = 30;

export const CATEGORIES = PRODUCT_CATEGORIES;

export const WAREHOUSES = ["Tokyo DC", "Osaka DC", "Singapore Hub", "Rotterdam DC", "Dallas DC"] as const;

const NAMES: Record<(typeof CATEGORIES)[number], { items: string[]; variants: string[]; cost: [number, number] }> = {
  "Power Systems": {
    items: ["Lithium-Ion Battery Pack", "DC Power Supply", "Inverter Module", "Charging Controller", "UPS Battery Cell"],
    variants: ["12V", "24V", "48V", "72V", "5kW", "10kW"],
    cost: [18, 240],
  },
  Electronics: {
    items: ["Microcontroller Board", "Thermal Sensor", "Proximity Sensor", "Relay Module", "Display Panel", "Wiring Harness"],
    variants: ["Rev A", "Rev B", "Gen 2", "Gen 3", "Industrial", "Compact"],
    cost: [3, 85],
  },
  "Mechanical Parts": {
    items: ["Ball Bearing", "Drive Belt", "Gear Assembly", "Hydraulic Valve", "Shaft Coupling", "Conveyor Roller"],
    variants: ["6204-2RS", "6305-ZZ", "HTD-8M", "Series 40", "Series 60", "Heavy Duty"],
    cost: [2, 120],
  },
  Packaging: {
    items: ["Corrugated Carton", "Stretch Film Roll", "Pallet Wrap", "Foam Insert", "Shipping Label Roll"],
    variants: ["Small", "Medium", "Large", "XL", "Recycled", "Heavy Duty"],
    cost: [0.4, 18],
  },
  "Raw Materials": {
    items: ["Aluminium Sheet", "Copper Wire Spool", "Steel Rod", "ABS Pellets", "Polycarbonate Sheet"],
    variants: ["1mm", "2mm", "3mm", "10kg", "25kg", "Grade A"],
    cost: [6, 160],
  },
  "Safety Equipment": {
    items: ["Safety Gloves", "Hard Hat", "Hi-Vis Vest", "Safety Goggles", "Ear Protection"],
    variants: ["Size M", "Size L", "Size XL", "Class 2", "Class 3", "Anti-Fog"],
    cost: [1.5, 32],
  },
  "Fluids & Lubricants": {
    items: ["Hydraulic Oil", "Coolant Concentrate", "Bearing Grease", "Cutting Fluid", "Gear Oil"],
    variants: ["5L", "20L", "200L", "ISO 46", "ISO 68", "Synthetic"],
    cost: [8, 210],
  },
  Fasteners: {
    items: ["Hex Bolt", "Lock Nut", "Machine Screw", "Washer Pack", "Rivet Pack"],
    variants: ["M6", "M8", "M10", "M12", "Stainless", "Zinc Plated"],
    cost: [0.05, 6],
  },
};

export const TOTAL_SKUS = 1248;

export function classifyRisk(available: number, onOrder: number, daily: number, leadTime: number, rop: number): RiskLevel {
  const cover = daily > 0 ? available / daily : Infinity;
  if (cover < leadTime && available + onOrder < rop) return "critical";
  if (available + onOrder < rop) return "high";
  if (available < rop) return "medium";
  return "low";
}

function recommendationFor(risk: RiskLevel, qty: number, cover: number): string {
  if (risk === "critical") return `Expedite reorder of ${qty.toLocaleString()} units — stockout in ${cover.toFixed(1)} days`;
  if (risk === "high") return `Reorder ${qty.toLocaleString()} units this week`;
  if (risk === "medium") return "Inbound stock covers demand — monitor";
  return "No action needed";
}

export function buildItem(params: {
  sku: string;
  name: string;
  category: string;
  warehouse: string;
  onHand: number;
  allocated: number;
  onOrder: number;
  dailyDemand: number;
  leadTimeDays: number;
  unitCost: number;
  agingDays: number;
  trend: number[];
  growth?: number;
  pack?: number;
}): InventoryItem {
  const { dailyDemand: d, leadTimeDays: lt } = params;
  const sigma = d * 0.25;
  const safetyStock = Math.round(Z_95 * sigma * Math.sqrt(lt));
  const reorderPoint = Math.round(d * lt + safetyStock);
  const available = Math.max(0, params.onHand - params.allocated);
  const forecast30d = Math.round(d * REVIEW_DAYS * (1 + (params.growth ?? 0)));
  const pack = params.pack ?? (d > 100 ? 500 : d > 20 ? 50 : 10);
  const needsOrder = available + params.onOrder < reorderPoint;
  const reorderQty = needsOrder
    ? Math.max(pack, ceilTo(forecast30d + safetyStock - available - params.onOrder, pack))
    : 0;
  const daysOfCover = d > 0 ? available / d : 999;
  const risk = classifyRisk(available, params.onOrder, d, lt, reorderPoint);
  const annualCogs = d * 365 * params.unitCost;
  const stockValue = params.onHand * params.unitCost;
  return {
    sku: params.sku,
    name: params.name,
    category: params.category,
    warehouse: params.warehouse,
    onHand: params.onHand,
    available,
    onOrder: params.onOrder,
    dailyDemand: round(d, 0.1),
    forecast30d,
    safetyStock,
    reorderPoint,
    reorderQty,
    daysOfCover: round(daysOfCover, 0.1),
    leadTimeDays: lt,
    risk,
    recommendation: recommendationFor(risk, reorderQty, daysOfCover),
    unitCost: round(params.unitCost, 0.01),
    turnover: stockValue > 0 ? round(annualCogs / stockValue, 0.1) : 0,
    agingDays: params.agingDays,
    trend: params.trend,
  };
}

/** Hand-authored SKUs that anchor the demo narrative. */
function featuredItems(): InventoryItem[] {
  return [
    buildItem({
      sku: "SKU-100",
      name: "Lithium-Ion Battery Pack 48V",
      category: "Power Systems",
      warehouse: "Tokyo DC",
      onHand: 4000,
      allocated: 2350,
      onOrder: 850,
      dailyDemand: 400,
      leadTimeDays: 9,
      unitCost: 10.6,
      agingDays: 12,
      growth: 0,
      pack: 500,
      trend: [6200, 5900, 5600, 5400, 5100, 4800, 4600, 4400, 4200, 4000],
    }),
    buildItem({
      sku: "SKU-104",
      name: "Thermal Sensor Gen 3",
      category: "Electronics",
      warehouse: "Singapore Hub",
      onHand: 1180,
      allocated: 420,
      onOrder: 0,
      dailyDemand: 145,
      leadTimeDays: 12,
      unitCost: 14.2,
      agingDays: 21,
      trend: [2600, 2450, 2300, 2100, 1950, 1800, 1650, 1500, 1320, 1180],
    }),
    buildItem({
      sku: "SKU-117",
      name: "Hydraulic Valve Series 60",
      category: "Mechanical Parts",
      warehouse: "Rotterdam DC",
      onHand: 640,
      allocated: 180,
      onOrder: 200,
      dailyDemand: 52,
      leadTimeDays: 18,
      unitCost: 64,
      agingDays: 35,
      trend: [1200, 1150, 1080, 1010, 950, 880, 820, 760, 700, 640],
    }),
    buildItem({
      sku: "SKU-123",
      name: "Copper Wire Spool 25kg",
      category: "Raw Materials",
      warehouse: "Osaka DC",
      onHand: 920,
      allocated: 140,
      onOrder: 0,
      dailyDemand: 61,
      leadTimeDays: 14,
      unitCost: 118,
      agingDays: 18,
      trend: [1500, 1440, 1380, 1320, 1250, 1190, 1120, 1060, 990, 920],
    }),
    buildItem({
      sku: "SKU-131",
      name: "Microcontroller Board Rev B",
      category: "Electronics",
      warehouse: "Dallas DC",
      onHand: 2300,
      allocated: 600,
      onOrder: 1500,
      dailyDemand: 160,
      leadTimeDays: 10,
      unitCost: 22.5,
      agingDays: 9,
      trend: [3400, 3250, 3100, 2980, 2850, 2700, 2600, 2500, 2400, 2300],
    }),
  ];
}

function generatedItems(count: number, startNumber: number): InventoryItem[] {
  const rng = new Rng(2026);
  const items: InventoryItem[] = [];
  for (let i = 0; i < count; i++) {
    const category = CATEGORIES[i % CATEGORIES.length];
    const spec = NAMES[category];
    const name = `${rng.pick(spec.items)} ${rng.pick(spec.variants)}`;
    const daily = Math.max(1, rng.logNormal(28, 0.9));
    const leadTime = rng.int(4, 28);
    // Risk mix: ~1% critical, ~2% high, ~3% medium, rest healthy. Critical cover stays above
    // SKU-100's 4.1 days so the demo narrative leads the risk list.
    const r = rng.float();
    const ssDays = Z_95 * 0.25 * Math.sqrt(leadTime);
    let coverDays: number;
    let onOrder = 0;
    if (r < 0.009) coverDays = rng.float(Math.max(4.6, leadTime * 0.55), leadTime * 0.92);
    else if (r < 0.03) coverDays = rng.float(leadTime * 1.0, leadTime + ssDays * 0.7);
    else if (r < 0.06) {
      coverDays = rng.float(leadTime * 1.0, leadTime + ssDays * 0.8);
      onOrder = Math.round(daily * rng.float(8, 20));
    } else {
      coverDays = rng.float(leadTime * 1.6, 120);
      onOrder = rng.chance(0.3) ? Math.round(daily * 20) : 0;
    }
    const available = Math.round(daily * coverDays);
    const allocated = Math.round(available * rng.float(0.05, 0.25));
    const base = available + allocated;
    const slope = rng.float(-0.04, 0.03);
    const trend = Array.from({ length: 10 }, (_, k) => Math.max(0, Math.round(base * (1 - slope * (9 - k)))));
    items.push(
      buildItem({
        sku: `SKU-${startNumber + i}`,
        name,
        category,
        warehouse: rng.pick(WAREHOUSES),
        onHand: base,
        allocated,
        onOrder,
        dailyDemand: daily,
        leadTimeDays: leadTime,
        unitCost: rng.float(spec.cost[0], spec.cost[1]),
        agingDays: Math.round(rng.logNormal(38, 0.7)),
        trend,
      }),
    );
  }
  return items;
}

let cache: InventoryItem[] | null = null;

export function allInventory(): InventoryItem[] {
  if (!cache) {
    const featured = featuredItems();
    const featuredSkus = new Set(featured.map((f) => f.sku));
    const generated = generatedItems(TOTAL_SKUS + featured.length, 100).filter((g) => !featuredSkus.has(g.sku));
    cache = [...featured, ...generated].slice(0, TOTAL_SKUS);
  }
  return cache;
}

export function inventoryItem(sku: string): InventoryItem | undefined {
  return allInventory().find((i) => i.sku.toLowerCase() === sku.toLowerCase());
}

const RISK_ORDER: Record<RiskLevel, number> = { critical: 0, high: 1, medium: 2, low: 3 };

export function riskRank(risk: RiskLevel): number {
  return RISK_ORDER[risk];
}

export function atRiskItems(): InventoryItem[] {
  return allInventory()
    .filter((i) => i.risk === "critical" || i.risk === "high")
    .sort((a, b) => riskRank(a.risk) - riskRank(b.risk) || a.daysOfCover - b.daysOfCover);
}

export function inventorySummary(): InventorySummary {
  const items = allInventory();
  const value = (i: InventoryItem) => i.onHand * i.unitCost;
  const totalValue = items.reduce((s, i) => s + value(i), 0);
  const riskCounts = (["critical", "high", "medium", "low"] as RiskLevel[]).map((risk) => ({
    risk,
    count: items.filter((i) => i.risk === risk).length,
  }));
  const categoryDistribution = CATEGORIES.map((category) => {
    const inCat = items.filter((i) => i.category === category);
    return { category, value: Math.round(inCat.reduce((s, i) => s + value(i), 0)), skus: inCat.length };
  }).sort((a, b) => b.value - a.value);
  const bucket = (lo: number, hi: number) =>
    Math.round(items.filter((i) => i.agingDays >= lo && i.agingDays < hi).reduce((s, i) => s + value(i), 0));
  const months = lastMonths(12);
  const inventoryTrend = months.map((label, k) => ({
    label,
    onHand: Math.round(totalValue * (1.08 - 0.012 * k + 0.025 * Math.sin(k / 1.7))),
    safetyStock: Math.round(totalValue * 0.42),
  }));
  return {
    totalSkus: items.length,
    totalValue: Math.round(totalValue),
    atRisk: riskCounts[0].count + riskCounts[1].count,
    critical: riskCounts[0].count,
    stockoutWithin7d: items.filter((i) => i.daysOfCover < 7).length,
    reorderRecommended: items.filter((i) => i.reorderQty > 0).length,
    avgTurnover: round(items.reduce((s, i) => s + i.turnover, 0) / items.length, 0.1),
    agedValue: bucket(90, Infinity),
    inventoryTrend,
    riskDistribution: riskCounts,
    categoryDistribution,
    aging: [
      { bucket: "0–30 days", value: bucket(0, 30) },
      { bucket: "31–60 days", value: bucket(30, 60) },
      { bucket: "61–90 days", value: bucket(60, 90) },
      { bucket: "90+ days", value: bucket(90, Infinity) },
    ],
  };
}

export function lastMonths(n: number, base = new Date()): string[] {
  const out: string[] = [];
  for (let k = n - 1; k >= 0; k--) {
    const d = new Date(base.getFullYear(), base.getMonth() - k, 1);
    out.push(d.toLocaleString("en-US", { month: "short" }));
  }
  return out;
}
