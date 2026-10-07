import type { ActivityEvent, Notification } from "@/types";
import { Rng } from "./rng";

type Template = Omit<ActivityEvent, "id" | "timestamp" | "runId">;

const TEMPLATES: Template[] = [
  { agent: "supervisor", kind: "workflow", message: "Supervisor started workflow: full recommendation for SKU-100", severity: "info", sku: "SKU-100" },
  { agent: "demand", kind: "analysis", message: "Demand Agent completed forecast for SKU-100 (12,000 units, 30 days)", severity: "success", sku: "SKU-100", durationMs: 2140 },
  { agent: "inventory", kind: "detection", message: "Inventory Agent detected stockout risk for SKU-100 — 4.1 days of cover", severity: "critical", sku: "SKU-100", durationMs: 1510 },
  { agent: "supplier", kind: "analysis", message: "Supplier Agent compared 5 suppliers for SKU-100", severity: "success", sku: "SKU-100", durationMs: 1980 },
  { agent: "logistics", kind: "detection", message: "Logistics Agent flagged SHP-48210 delayed 3 days (port congestion)", severity: "warning", durationMs: 1320 },
  { agent: "supervisor", kind: "approval", message: "PO draft for 10,000 units ($110,000) sent for approval", severity: "warning", sku: "SKU-100" },
  { agent: "rag", kind: "document", message: "Knowledge Agent retrieved procurement policy §4.2 (approval threshold)", severity: "info", durationMs: 2410 },
  { agent: "inventory", kind: "detection", message: "Inventory Agent flagged SKU-104 below reorder point", severity: "warning", sku: "SKU-104", durationMs: 1440 },
  { agent: "demand", kind: "analysis", message: "Demand Agent detected weekly seasonality across Electronics", severity: "insight", durationMs: 2620 },
  { agent: "supplier", kind: "detection", message: "Contract for Rhine Valley Chemicals expires in 45 days", severity: "warning" },
  { agent: "logistics", kind: "analysis", message: "Logistics Agent estimated delivery for 38 inbound shipments", severity: "success", durationMs: 1710 },
  { agent: "system", kind: "document", message: "Indexed Nordvolt Energy — Master Supply Agreement (42 chunks)", severity: "success" },
  { agent: "inventory", kind: "analysis", message: "Safety stock recalculated for 38 Power Systems SKUs", severity: "success", durationMs: 980 },
  { agent: "research", kind: "analysis", message: "Research Agent summarised Tokyo Bay port congestion (3 web sources)", severity: "insight", durationMs: 5880 },
  { agent: "user", kind: "approval", message: "Procurement Manager approved PO draft for SKU-131 (1,500 units)", severity: "success", sku: "SKU-131" },
  { agent: "supervisor", kind: "workflow", message: "Supervisor completed workflow: delayed shipment review", severity: "success", durationMs: 7420 },
  { agent: "inventory", kind: "detection", message: "Inventory Agent detected stockout risk for SKU-117 — 8.8 days of cover", severity: "critical", sku: "SKU-117" },
  { agent: "system", kind: "error", message: "OCR failed for Freight Invoice Batch 0914 — confidence below threshold", severity: "warning" },
];

const LIVE_INTERVAL_MS = 25_000;

/**
 * History plus a "live" event every 25 seconds so the feed visibly updates in demo mode.
 * Deterministic per time bucket, so repeated polls return identical events.
 */
export function activityFeed(limit = 60): ActivityEvent[] {
  const nowMs = Date.now();
  const currentBucket = Math.floor(nowMs / LIVE_INTERVAL_MS);
  const events: ActivityEvent[] = [];
  for (let k = 0; k < limit; k++) {
    const bucket = currentBucket - k * 3;
    const rng = new Rng(bucket);
    const template = TEMPLATES[((bucket % TEMPLATES.length) + TEMPLATES.length) % TEMPLATES.length];
    const ts = k === 0 ? bucket * LIVE_INTERVAL_MS : bucket * LIVE_INTERVAL_MS - rng.int(0, 20_000);
    events.push({
      ...template,
      id: `EVT-${bucket}`,
      timestamp: new Date(ts).toISOString(),
      runId: `run_${(bucket % 100000).toString(36)}`,
    });
  }
  return events;
}

const NOTIFICATIONS: (Omit<Notification, "createdAt" | "read"> & { minutesAgo: number })[] = [
  { id: "NTF-1", severity: "critical", title: "Stockout risk", message: "SKU-100 may stock out in 4 days. Reorder of 10,000 units is awaiting approval.", minutesAgo: 6, href: "/copilot?q=Give%20me%20a%20complete%20recommendation%20for%20SKU-100" },
  { id: "NTF-2", severity: "warning", title: "Delayed shipments", message: "12 shipments are delayed, average 3.2 days. 3 affect at-risk SKUs.", minutesAgo: 18, href: "/logistics" },
  { id: "NTF-3", severity: "insight", title: "AI insight", message: "Nordvolt Energy has 7% better delivery reliability than the current SKU-100 supplier.", minutesAgo: 42, href: "/suppliers" },
  { id: "NTF-4", severity: "critical", title: "Stockout risk", message: "SKU-117 Hydraulic Valve Series 60 has 8.8 days of cover against an 18-day lead time.", minutesAgo: 75, href: "/inventory" },
  { id: "NTF-5", severity: "warning", title: "Contract expiring", message: "Rhine Valley Chemicals supply contract expires in 45 days.", minutesAgo: 190, href: "/suppliers" },
  { id: "NTF-6", severity: "success", title: "PO approved", message: "Procurement Manager approved the PO draft for SKU-131 (1,500 units).", minutesAgo: 260 },
  { id: "NTF-7", severity: "info", title: "Document indexed", message: "Nordvolt Energy — Master Supply Agreement is now searchable (42 chunks).", minutesAgo: 320, href: "/documents" },
  { id: "NTF-8", severity: "warning", title: "OCR failed", message: "Freight Invoice Batch 0914 could not be read. Re-scan at 300 DPI.", minutesAgo: 1440, href: "/documents" },
];

const readIds = new Set<string>(["NTF-6", "NTF-7", "NTF-8"]);

export function notifications(): Notification[] {
  return NOTIFICATIONS.map(({ minutesAgo, ...n }) => ({
    ...n,
    createdAt: new Date(Date.now() - minutesAgo * 60_000).toISOString(),
    read: readIds.has(n.id),
  }));
}

export function markNotificationsRead(ids: string[] | "all"): void {
  const list = ids === "all" ? NOTIFICATIONS.map((n) => n.id) : ids;
  list.forEach((id) => readIds.add(id));
}
