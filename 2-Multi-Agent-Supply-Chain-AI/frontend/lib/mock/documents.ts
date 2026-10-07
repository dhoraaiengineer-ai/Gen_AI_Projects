import type { Citation, DocumentItem, DocumentSearchResult, DocumentStats } from "@/types";
import { DAY_MS, Rng } from "./rng";

type Seed = Omit<DocumentItem, "id" | "updatedAt" | "sizeKb" | "uploadedBy"> & { ageDays: number };

const SEEDS: Seed[] = [
  { name: "Global Procurement Policy v4.2.pdf", format: "pdf", type: "procurement_policy", classification: "internal", chunks: 86, status: "indexed", ocr: false, ageDays: 12 },
  { name: "Expedited Purchase Approval SOP.docx", format: "docx", type: "sop", classification: "internal", chunks: 24, status: "indexed", ocr: false, ageDays: 30 },
  { name: "Inventory Management Policy 2026.pdf", format: "pdf", type: "inventory_policy", classification: "internal", chunks: 64, status: "indexed", ocr: false, ageDays: 21 },
  { name: "Safety Stock & Service Level Standard.md", format: "md", type: "inventory_policy", classification: "internal", chunks: 18, status: "indexed", ocr: false, ageDays: 44 },
  { name: "Nordvolt Energy — Master Supply Agreement.pdf", format: "pdf", type: "supplier_contract", classification: "restricted", chunks: 42, status: "indexed", ocr: false, ageDays: 3 },
  { name: "Kaito Precision — Supply Agreement 2025.pdf", format: "pdf", type: "supplier_contract", classification: "restricted", chunks: 38, status: "indexed", ocr: false, ageDays: 58 },
  { name: "Meridian Power — Pricing Schedule.xlsx", format: "xlsx", type: "supplier_contract", classification: "restricted", chunks: 12, status: "indexed", ocr: false, ageDays: 15 },
  { name: "Pacific Rim Components — Signed Contract (scan).pdf", format: "pdf", type: "supplier_contract", classification: "restricted", chunks: 29, status: "indexed", ocr: true, ageDays: 70 },
  { name: "Atlas Industrial — Quality Agreement.docx", format: "docx", type: "supplier_contract", classification: "restricted", chunks: 21, status: "indexed", ocr: false, ageDays: 90 },
  { name: "International Shipping Policy.pptx", format: "pptx", type: "shipping_policy", classification: "internal", chunks: 31, status: "indexed", ocr: false, ageDays: 26 },
  { name: "Carrier Rate Card Q4.xlsx", format: "xlsx", type: "shipping_policy", classification: "internal", chunks: 9, status: "indexed", ocr: false, ageDays: 6 },
  { name: "Customs & Incoterms Guide.pdf", format: "pdf", type: "shipping_policy", classification: "public", chunks: 47, status: "indexed", ocr: false, ageDays: 120 },
  { name: "Dangerous Goods Handling — Lithium Batteries.pdf", format: "pdf", type: "sop", classification: "internal", chunks: 35, status: "indexed", ocr: false, ageDays: 33 },
  { name: "Warehouse Receiving SOP.docx", format: "docx", type: "sop", classification: "internal", chunks: 19, status: "indexed", ocr: false, ageDays: 64 },
  { name: "Supplier Onboarding Checklist.docx", format: "docx", type: "sop", classification: "internal", chunks: 14, status: "indexed", ocr: false, ageDays: 81 },
  { name: "Supplier Scorecard Methodology.pdf", format: "pdf", type: "procurement_policy", classification: "internal", chunks: 22, status: "indexed", ocr: false, ageDays: 39 },
  { name: "Single-Source Supplier Risk Policy.pdf", format: "pdf", type: "procurement_policy", classification: "internal", chunks: 17, status: "indexed", ocr: false, ageDays: 52 },
  { name: "Delegation of Authority Matrix.xlsx", format: "xlsx", type: "procurement_policy", classification: "restricted", chunks: 8, status: "indexed", ocr: false, ageDays: 18 },
  { name: "Cycle Count Procedure.md", format: "md", type: "inventory_policy", classification: "internal", chunks: 11, status: "indexed", ocr: false, ageDays: 95 },
  { name: "Obsolete & Slow-Moving Stock Policy.pdf", format: "pdf", type: "inventory_policy", classification: "internal", chunks: 16, status: "indexed", ocr: false, ageDays: 140 },
  { name: "Rhine Valley Chemicals — Contract Renewal Draft.docx", format: "docx", type: "supplier_contract", classification: "restricted", chunks: 0, status: "processing", ocr: false, ageDays: 0 },
  { name: "Q3 Supplier Audit Findings.pdf", format: "pdf", type: "procurement_policy", classification: "restricted", chunks: 0, status: "processing", ocr: false, ageDays: 0 },
  { name: "Freight Invoice Batch 0914 (scan).png", format: "png", type: "shipping_policy", classification: "internal", chunks: 0, status: "failed", ocr: true, ageDays: 1 },
  { name: "Sustainability Sourcing Code.pdf", format: "pdf", type: "procurement_policy", classification: "public", chunks: 27, status: "indexed", ocr: false, ageDays: 200 },
];

const UPLOADERS = ["Procurement Manager", "Inventory Planner", "Logistics Manager", "Demo User"];

let cache: DocumentItem[] | null = null;

export function allDocuments(): DocumentItem[] {
  if (!cache) {
    const rng = new Rng(5150);
    cache = SEEDS.map(({ ageDays, ...seed }, i) => ({
      ...seed,
      id: `DOC-${String(1000 + i)}`,
      updatedAt: new Date(Date.now() - ageDays * DAY_MS - rng.int(1, 600) * 60_000).toISOString(),
      uploadedBy: rng.pick(UPLOADERS),
      sizeKb: Math.round(seed.chunks * rng.float(9, 16) + rng.int(40, 300)),
      error:
        seed.status === "failed"
          ? "OCR confidence 41% is below the 60% threshold. Re-scan at 300 DPI or use the vision OCR engine."
          : undefined,
    }));
  }
  return cache;
}

export function addMockDocument(doc: DocumentItem): void {
  allDocuments().unshift(doc);
}

export function removeMockDocument(id: string): void {
  const list = allDocuments();
  const idx = list.findIndex((d) => d.id === id);
  if (idx >= 0) list.splice(idx, 1);
}

export function documentStats(): DocumentStats {
  const docs = allDocuments();
  return {
    total: docs.length,
    indexed: docs.filter((d) => d.status === "indexed").length,
    processing: docs.filter((d) => d.status === "processing").length,
    failed: docs.filter((d) => d.status === "failed").length,
    chunks: docs.reduce((s, d) => s + d.chunks, 0),
  };
}

interface Passage {
  documentId: string;
  location: string;
  text: string;
  keywords: string[];
}

const PASSAGES: Passage[] = [
  {
    documentId: "DOC-1000",
    location: "p. 7, §4.2",
    text: "Purchase orders above USD 50,000 require approval from a Procurement Manager or above before release to the supplier.",
    keywords: ["approval", "purchase", "order", "50,000", "threshold", "po", "procurement", "manager"],
  },
  {
    documentId: "DOC-1000",
    location: "p. 9, §5.1",
    text: "Expedited orders are permitted when projected days of cover fall below the supplier lead time. The expedite premium must not exceed 12% of the standard unit price.",
    keywords: ["expedite", "expedited", "premium", "cover", "lead", "time", "stockout", "urgent"],
  },
  {
    documentId: "DOC-1016",
    location: "p. 2, §2",
    text: "No critical SKU may rely on a single supplier for more than 70% of annual volume. A qualified secondary supplier must be maintained for all Power Systems components.",
    keywords: ["single", "source", "supplier", "secondary", "70%", "risk", "dual"],
  },
  {
    documentId: "DOC-1002",
    location: "p. 4, §3.1",
    text: "Safety stock is set to achieve a 95% cycle service level for A-class items and 90% for B-class items, using demand variability over the trailing 90 days.",
    keywords: ["safety", "stock", "service", "level", "95%", "a-class", "variability"],
  },
  {
    documentId: "DOC-1004",
    location: "p. 3, clause 6.1",
    text: "Supplier guarantees a maximum lead time of three (3) business days for standard battery pack SKUs, with a late-delivery credit of 2% of order value per day.",
    keywords: ["nordvolt", "lead", "time", "credit", "late", "delivery", "battery", "contract"],
  },
  {
    documentId: "DOC-1005",
    location: "clause 8.2",
    text: "Payment terms: Net 45 days from invoice date. The minimum order quantity for battery packs is 500 units.",
    keywords: ["kaito", "payment", "terms", "net", "invoice", "moq", "minimum"],
  },
  {
    documentId: "DOC-1009",
    location: "slide 6",
    text: "Lithium battery shipments by air must be declared as UN3480 dangerous goods and are limited to 30% state of charge.",
    keywords: ["lithium", "air", "dangerous", "goods", "un3480", "shipping", "battery"],
  },
  {
    documentId: "DOC-1010",
    location: "sheet Rates",
    text: "Shenzhen → Tokyo: ocean USD 0.18/kg (21 days), air USD 4.60/kg (3 days). Fuel surcharge 7% applies to air freight.",
    keywords: ["rate", "carrier", "air", "ocean", "shenzhen", "tokyo", "freight", "cost"],
  },
];

export function searchDocuments(query: string): DocumentSearchResult {
  const docs = allDocuments();
  const terms = query.toLowerCase().split(/[^a-z0-9%,.-]+/).filter((t) => t.length > 2);
  const scored = PASSAGES.map((p) => ({ p, hits: p.keywords.filter((k) => terms.some((t) => k.includes(t) || t.includes(k))).length }))
    .filter((x) => x.hits > 0)
    .sort((a, b) => b.hits - a.hits)
    .slice(0, 3);
  if (!scored.length) {
    return {
      answer: "I couldn't find this in the indexed documents. Try different wording, or upload the relevant policy.",
      citations: [],
      guard: { status: "refused", reasons: ["No passage matched the question"] },
      latencyMs: 640,
    };
  }
  const citations: Citation[] = scored.map(({ p, hits }, i) => ({
    n: i + 1,
    documentId: p.documentId,
    source: docs.find((d) => d.id === p.documentId)?.name ?? p.documentId,
    location: p.location,
    snippet: p.text,
    score: Math.min(0.97, 0.62 + hits * 0.08),
  }));
  const answer = scored.map(({ p }, i) => `${p.text} [${i + 1}]`).join(" ");
  return { answer, citations, guard: { status: "grounded", reasons: [] }, latencyMs: 1840 };
}
