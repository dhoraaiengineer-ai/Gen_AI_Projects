import type { RiskLevel, Supplier, SupplierRecommendation, SupplierSort } from "@/types";
import { inventoryItem } from "./inventory";
import { daysFromNow, isoDate, Rng } from "./rng";

/** Weights mirror app/services/supplier_scoring.py (configurable on the backend). */
export const SCORE_WEIGHTS = { price: 0.35, leadTime: 0.3, reliability: 0.35 } as const;

type Seed = Omit<Supplier, "score" | "trend" | "risk"> & { riskOverride?: RiskLevel };

const SEEDS: Seed[] = [
  {
    id: "SUP-001", name: "Kaito Precision Industries", country: "Japan", region: "APAC",
    categories: ["Power Systems", "Electronics"], unitPrice: 10.0, leadTimeDays: 5, reliability: 0.94,
    defectRate: 0.006, fillRate: 0.97, moq: 500, contractExpiry: isoDate(daysFromNow(410)), skusSupplied: 214,
    spendYtd: 4_820_000, certifications: ["ISO 9001", "ISO 14001"],
  },
  {
    id: "SUP-002", name: "Meridian Power Systems", country: "South Korea", region: "APAC",
    categories: ["Power Systems"], unitPrice: 10.4, leadTimeDays: 7, reliability: 0.91,
    defectRate: 0.011, fillRate: 0.95, moq: 1000, contractExpiry: isoDate(daysFromNow(95)), skusSupplied: 88,
    spendYtd: 2_140_000, certifications: ["ISO 9001"],
  },
  {
    id: "SUP-003", name: "Nordvolt Energy", country: "Japan", region: "APAC",
    categories: ["Power Systems", "Raw Materials"], unitPrice: 11.0, leadTimeDays: 3, reliability: 0.98,
    defectRate: 0.003, fillRate: 0.99, moq: 500, contractExpiry: isoDate(daysFromNow(620)), skusSupplied: 126,
    spendYtd: 3_310_000, certifications: ["ISO 9001", "IATF 16949", "ISO 14001"],
  },
  {
    id: "SUP-004", name: "Pacific Rim Components", country: "Vietnam", region: "APAC",
    categories: ["Power Systems", "Electronics", "Fasteners"], unitPrice: 9.6, leadTimeDays: 14, reliability: 0.86,
    defectRate: 0.019, fillRate: 0.9, moq: 2000, contractExpiry: isoDate(daysFromNow(240)), skusSupplied: 302,
    spendYtd: 1_960_000, certifications: ["ISO 9001"], riskOverride: "high",
  },
  {
    id: "SUP-005", name: "Atlas Industrial Supply", country: "Germany", region: "EMEA",
    categories: ["Mechanical Parts", "Power Systems"], unitPrice: 10.8, leadTimeDays: 6, reliability: 0.95,
    defectRate: 0.005, fillRate: 0.96, moq: 250, contractExpiry: isoDate(daysFromNow(300)), skusSupplied: 175,
    spendYtd: 2_870_000, certifications: ["ISO 9001", "ISO 45001"],
  },
  {
    id: "SUP-006", name: "Sakura Electronics Trading", country: "Japan", region: "APAC",
    categories: ["Electronics"], unitPrice: 14.1, leadTimeDays: 4, reliability: 0.96,
    defectRate: 0.004, fillRate: 0.98, moq: 200, contractExpiry: isoDate(daysFromNow(510)), skusSupplied: 143,
    spendYtd: 2_450_000, certifications: ["ISO 9001", "RoHS"],
  },
  {
    id: "SUP-007", name: "Lone Star Fasteners", country: "United States", region: "AMER",
    categories: ["Fasteners", "Mechanical Parts"], unitPrice: 0.9, leadTimeDays: 8, reliability: 0.93,
    defectRate: 0.008, fillRate: 0.97, moq: 5000, contractExpiry: isoDate(daysFromNow(180)), skusSupplied: 96,
    spendYtd: 610_000, certifications: ["ISO 9001"],
  },
  {
    id: "SUP-008", name: "Rhine Valley Chemicals", country: "Netherlands", region: "EMEA",
    categories: ["Fluids & Lubricants", "Raw Materials"], unitPrice: 42.5, leadTimeDays: 10, reliability: 0.92,
    defectRate: 0.007, fillRate: 0.95, moq: 100, contractExpiry: isoDate(daysFromNow(45)), skusSupplied: 64,
    spendYtd: 1_230_000, certifications: ["ISO 9001", "REACH"], riskOverride: "medium",
  },
  {
    id: "SUP-009", name: "Harbor Packaging Co.", country: "Singapore", region: "APAC",
    categories: ["Packaging"], unitPrice: 2.3, leadTimeDays: 5, reliability: 0.97,
    defectRate: 0.004, fillRate: 0.98, moq: 1000, contractExpiry: isoDate(daysFromNow(370)), skusSupplied: 81,
    spendYtd: 540_000, certifications: ["FSC", "ISO 9001"],
  },
  {
    id: "SUP-010", name: "Guardian Safety Products", country: "Canada", region: "AMER",
    categories: ["Safety Equipment"], unitPrice: 6.8, leadTimeDays: 9, reliability: 0.9,
    defectRate: 0.009, fillRate: 0.94, moq: 300, contractExpiry: isoDate(daysFromNow(150)), skusSupplied: 72,
    spendYtd: 420_000, certifications: ["ISO 9001", "ANSI"],
  },
  {
    id: "SUP-011", name: "Shenzhen Brightway Tech", country: "China", region: "APAC",
    categories: ["Electronics", "Power Systems"], unitPrice: 9.2, leadTimeDays: 18, reliability: 0.83,
    defectRate: 0.024, fillRate: 0.88, moq: 3000, contractExpiry: isoDate(daysFromNow(210)), skusSupplied: 268,
    spendYtd: 1_580_000, certifications: ["ISO 9001"], riskOverride: "high",
  },
  {
    id: "SUP-012", name: "Baltic Metals Group", country: "Poland", region: "EMEA",
    categories: ["Raw Materials", "Mechanical Parts"], unitPrice: 112, leadTimeDays: 12, reliability: 0.94,
    defectRate: 0.006, fillRate: 0.96, moq: 50, contractExpiry: isoDate(daysFromNow(330)), skusSupplied: 59,
    spendYtd: 2_020_000, certifications: ["ISO 9001", "ISO 14001"],
  },
];

function normalise(value: number, min: number, max: number): number {
  return max === min ? 0 : (value - min) / (max - min);
}

/** Overall score (0-100) relative to a peer group: cheaper, faster and more reliable is better. */
export function scoreSuppliers<T extends Pick<Supplier, "unitPrice" | "leadTimeDays" | "reliability">>(peers: T[]): number[] {
  const prices = peers.map((p) => p.unitPrice);
  const leads = peers.map((p) => p.leadTimeDays);
  const rels = peers.map((p) => p.reliability);
  return peers.map((p) => {
    const s =
      SCORE_WEIGHTS.price * (1 - normalise(p.unitPrice, Math.min(...prices), Math.max(...prices))) +
      SCORE_WEIGHTS.leadTime * (1 - normalise(p.leadTimeDays, Math.min(...leads), Math.max(...leads))) +
      SCORE_WEIGHTS.reliability * normalise(p.reliability, Math.min(...rels), Math.max(...rels));
    return Math.round(s * 100);
  });
}

function riskFor(seed: Seed): RiskLevel {
  if (seed.riskOverride) return seed.riskOverride;
  if (seed.reliability >= 0.95 && seed.defectRate < 0.006) return "low";
  if (seed.reliability >= 0.9) return "low";
  return "medium";
}

let cache: Supplier[] | null = null;

export function allSuppliers(): Supplier[] {
  if (!cache) {
    const rng = new Rng(77);
    // Score within category peer groups so price comparisons are apples-to-apples.
    const scores = new Map<string, number>();
    const groups = new Map<string, Seed[]>();
    for (const s of SEEDS) {
      const key = s.categories[0];
      groups.set(key, [...(groups.get(key) ?? []), s]);
    }
    for (const group of groups.values()) {
      const peerScores = group.length > 1 ? scoreSuppliers(group) : [Math.round(group[0].reliability * 90)];
      group.forEach((s, i) => scores.set(s.id, Math.max(peerScores[i], 40)));
    }
    cache = SEEDS.map(({ riskOverride: _ignored, ...seed }) => ({
      ...seed,
      risk: riskFor({ ...seed, riskOverride: _ignored }),
      score: scores.get(seed.id) ?? 70,
      trend: Array.from({ length: 12 }, () => Math.round(seed.reliability * 100 + rng.normal(0, 1.6))),
    }));
  }
  return cache;
}

/** Suppliers able to supply a SKU, with SKU-specific price, scored as a peer group. */
export function suppliersForSku(sku: string): Supplier[] {
  const item = inventoryItem(sku);
  const all = allSuppliers();
  const candidates = item ? all.filter((s) => s.categories.includes(item.category)) : all;
  if (!item || item.sku !== "SKU-100") {
    const scores = scoreSuppliers(candidates);
    return candidates.map((s, i) => ({ ...s, score: scores[i] }));
  }
  // SKU-100 quotes (per unit), anchored for the demo narrative.
  const quotes: Record<string, number> = { "SUP-001": 10.0, "SUP-002": 10.4, "SUP-003": 11.0, "SUP-004": 9.6, "SUP-005": 10.8 };
  const list = all.filter((s) => s.id in quotes).map((s) => ({ ...s, unitPrice: quotes[s.id] }));
  const scores = scoreSuppliers(list);
  return list.map((s, i) => ({ ...s, score: scores[i] }));
}

const RISK_ORDER: Record<RiskLevel, number> = { low: 0, medium: 1, high: 2, critical: 3 };

export function sortSuppliers(list: Supplier[], sort: SupplierSort): Supplier[] {
  const copy = [...list];
  const by: Record<SupplierSort, (a: Supplier, b: Supplier) => number> = {
    price: (a, b) => a.unitPrice - b.unitPrice,
    leadTime: (a, b) => a.leadTimeDays - b.leadTimeDays,
    reliability: (a, b) => b.reliability - a.reliability,
    risk: (a, b) => RISK_ORDER[a.risk] - RISK_ORDER[b.risk],
    score: (a, b) => b.score - a.score,
  };
  return copy.sort(by[sort]);
}

/**
 * Recommendation logic mirrors the supplier agent: when the SKU is at stockout risk, suppliers whose
 * lead time exceeds the remaining days of cover are disqualified before scoring.
 */
export function recommendSupplier(sku: string): SupplierRecommendation {
  const item = inventoryItem(sku);
  const candidates = suppliersForSku(sku);
  const urgent = item && (item.risk === "critical" || item.risk === "high");
  const eligible = urgent ? candidates.filter((s) => s.leadTimeDays <= Math.max(item.daysOfCover, 1)) : candidates;
  const pool = eligible.length ? eligible : candidates;
  const best = [...pool].sort((a, b) => b.score - a.score || a.leadTimeDays - b.leadTimeDays)[0];
  const cheapest = [...candidates].sort((a, b) => a.unitPrice - b.unitPrice)[0];
  const reasons = [
    `${(best.reliability * 100).toFixed(0)}% on-time delivery over the last 12 months`,
    `${best.leadTimeDays}-day lead time${urgent && item ? ` — arrives before projected stockout in ${item.daysOfCover} days` : ""}`,
    `$${best.unitPrice.toFixed(2)} per unit${best.id !== cheapest.id ? ` (+$${(best.unitPrice - cheapest.unitPrice).toFixed(2)} vs. lowest quote)` : " — lowest quote"}`,
  ];
  if (urgent && eligible.length < candidates.length) {
    reasons.push(`${candidates.length - eligible.length} lower-cost suppliers excluded: lead time exceeds remaining cover`);
  }
  return {
    supplierId: best.id,
    sku,
    summary: urgent
      ? `${best.name} provides the best balance between delivery speed and reliability, and is the only option that can deliver before ${sku} runs out.`
      : `${best.name} offers the strongest overall balance of price, lead time and reliability for ${sku}.`,
    reasons,
    confidence: urgent ? 0.91 : 0.84,
  };
}
