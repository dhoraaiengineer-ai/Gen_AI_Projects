import type { ApprovalRequest, DocumentItem, InventoryItem } from "@/types";
import type { SupplyApi } from "../api";
import { ApiError } from "../api";
import { activityFeed, markNotificationsRead, notifications } from "./activity";
import { allAgents } from "./agents";
import { mockCopilotStream } from "./copilot";
import { demandForecast } from "./demand";
import { addMockDocument, allDocuments, documentStats, removeMockDocument, searchDocuments } from "./documents";
import { allInventory, inventoryItem, inventorySummary, riskRank } from "./inventory";
import { allShipments, logisticsSummary } from "./logistics";
import { analytics, overview } from "./overview";
import { recommendSupplier, sortSuppliers, allSuppliers, suppliersForSku } from "./suppliers";
import { approvals } from "./approvals";

/** Simulated network latency so loading states are exercised in demo mode. */
function latency<T>(value: () => T, min = 180, max = 520): Promise<T> {
  const ms = min + Math.random() * (max - min);
  return new Promise((resolve, reject) =>
    setTimeout(() => {
      try {
        resolve(value());
      } catch (err) {
        reject(err);
      }
    }, ms),
  );
}

function compare(a: InventoryItem, b: InventoryItem, key: keyof InventoryItem): number {
  if (key === "risk") return riskRank(a.risk) - riskRank(b.risk);
  const av = a[key];
  const bv = b[key];
  return typeof av === "number" && typeof bv === "number" ? av - bv : String(av).localeCompare(String(bv));
}

export const mockApi: SupplyApi = {
  getCurrentUser: () =>
    latency(() => ({ id: "usr_demo", email: "demo@supplyai.example", name: "Demo User", role: "approver", initials: "DU" })),
  getSystemStatus: () =>
    latency(() => ({
      status: "operational",
      environment: "production",
      version: "1.0.0",
      services: [
        { name: "API", status: "operational", latencyMs: 42 },
        { name: "Agent runtime", status: "operational", latencyMs: 118 },
        { name: "Knowledge base", status: "operational", latencyMs: 86 },
        { name: "PostgreSQL", status: "operational", latencyMs: 9 },
        { name: "LLM providers", status: "operational", latencyMs: 640 },
        { name: "Web research", status: "degraded", latencyMs: 2310 },
      ],
    })),
  getOverview: () => latency(overview, 300, 700),
  getInventorySummary: () => latency(inventorySummary),
  getInventory: (q) =>
    latency(() => {
      const search = q.search?.trim().toLowerCase();
      let items = allInventory().filter(
        (i) =>
          (!search || i.sku.toLowerCase().includes(search) || i.name.toLowerCase().includes(search)) &&
          (!q.risk || q.risk === "all" || i.risk === q.risk) &&
          (!q.category || q.category === "all" || i.category === q.category),
      );
      const sort = q.sort ?? "risk";
      const dir = q.order === "desc" ? -1 : 1;
      items = [...items].sort((a, b) => dir * compare(a, b, sort) || a.daysOfCover - b.daysOfCover);
      const page = q.page ?? 1;
      const pageSize = q.pageSize ?? 25;
      return { items: items.slice((page - 1) * pageSize, page * pageSize), total: items.length, page, pageSize };
    }),
  getInventoryItem: (sku) =>
    latency(() => {
      const item = inventoryItem(sku);
      if (!item) throw new ApiError(`${sku} was not found in the catalogue.`, 404, "not_found");
      return item;
    }),
  getDemandForecast: (sku, horizon) =>
    latency(() => {
      if (!inventoryItem(sku)) throw new ApiError(`${sku} was not found in the catalogue.`, 404, "not_found");
      return demandForecast(sku, horizon);
    }, 350, 800),
  getForecastableSkus: () => latency(() => allInventory().slice(0, 40).map((i) => ({ sku: i.sku, name: i.name }))),
  getSuppliers: ({ sort = "score", sku }) => latency(() => sortSuppliers(sku ? suppliersForSku(sku) : allSuppliers(), sort)),
  getSupplierRecommendation: (sku) => latency(() => recommendSupplier(sku), 500, 900),
  getShipments: ({ status, search }) =>
    latency(() => {
      const s = search?.trim().toLowerCase();
      return allShipments().filter(
        (x) =>
          (!status || status === "all" || x.status === status) &&
          (!s || [x.id, x.sku, x.carrier, x.origin, x.destination, x.poNumber].some((f) => f.toLowerCase().includes(s))),
      );
    }),
  getLogisticsSummary: () => latency(logisticsSummary),
  getAgents: () => latency(allAgents),
  getDocuments: () => latency(() => [...allDocuments()]),
  getDocumentStats: () => latency(documentStats),
  uploadDocuments: (files) =>
    latency(() =>
      files.map((f) => {
        const ext = f.name.split(".").pop()?.toLowerCase() ?? "";
        const supported = ["pdf", "docx", "xlsx", "pptx", "csv", "md", "txt", "png"];
        if (!supported.includes(ext)) {
          return { name: f.name, status: "failed" as const, error: `.${ext} files aren't supported. Convert to PDF, DOCX, XLSX or PPTX.` };
        }
        const doc: DocumentItem = {
          id: `DOC-${Date.now().toString().slice(-5)}${Math.floor(Math.random() * 10)}`,
          name: f.name,
          format: ext as DocumentItem["format"],
          type: "sop",
          classification: "internal",
          updatedAt: new Date().toISOString(),
          uploadedBy: "Demo User",
          chunks: Math.max(1, Math.round(f.size / 1800)),
          sizeKb: Math.max(1, Math.round(f.size / 1024)),
          status: "indexed",
          ocr: ext === "png",
        };
        addMockDocument(doc);
        return { name: f.name, status: "added" as const };
      }),
    1200, 2000),
  deleteDocument: (id) => latency(() => removeMockDocument(id)),
  reindexDocument: (id) =>
    latency(() => {
      const doc = allDocuments().find((d) => d.id === id);
      if (doc) Object.assign(doc, { status: "indexed", updatedAt: new Date().toISOString(), error: undefined, chunks: doc.chunks || 14 });
    }, 900, 1500),
  searchDocuments: (query) => latency(() => searchDocuments(query), 900, 1600),
  getActivity: () => latency(() => activityFeed(), 120, 300),
  getNotifications: () => latency(notifications, 120, 300),
  markNotificationsRead: (ids) => latency(() => markNotificationsRead(ids), 80, 150),
  getAnalytics: () => latency(analytics, 300, 700),
  getPendingApprovals: () => latency(() => [...approvals.values()].filter((a) => a.status === "pending")),
  decideApproval: (id, decision) =>
    latency(() => {
      const existing = approvals.get(id);
      const updated = { ...(existing as ApprovalRequest), id, status: decision };
      approvals.set(id, updated);
      return updated;
    }, 400, 800),
  streamCopilot: (req, signal) => mockCopilotStream(req.message, signal),
};
