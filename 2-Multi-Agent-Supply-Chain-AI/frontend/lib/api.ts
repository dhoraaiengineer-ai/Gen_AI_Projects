/**
 * API client. Components depend on the `SupplyApi` interface only; the data source is chosen by
 * NEXT_PUBLIC_DATA_SOURCE ("mock" for demo mode, "api" for the FastAPI backend via the /api proxy).
 */
import type {
  ActivityEvent,
  AgentInfo,
  AnalyticsData,
  ApprovalRequest,
  ChatRequest,
  CopilotEvent,
  CurrentUser,
  DemandForecast,
  DocumentItem,
  DocumentSearchResult,
  DocumentStats,
  ForecastHorizon,
  InventoryItem,
  InventoryQuery,
  InventorySummary,
  LogisticsSummary,
  Notification,
  Overview,
  Page,
  Shipment,
  ShipmentStatus,
  Supplier,
  SupplierRecommendation,
  SupplierSort,
  SystemStatus,
} from "@/types";
import { DATA_SOURCE, REQUEST_TIMEOUT_MS } from "./constants";

export interface SupplyApi {
  getCurrentUser(): Promise<CurrentUser>;
  getSystemStatus(): Promise<SystemStatus>;
  getOverview(): Promise<Overview>;
  getInventorySummary(): Promise<InventorySummary>;
  getInventory(query: InventoryQuery): Promise<Page<InventoryItem>>;
  getInventoryItem(sku: string): Promise<InventoryItem>;
  getDemandForecast(sku: string, horizon: ForecastHorizon): Promise<DemandForecast>;
  getForecastableSkus(): Promise<{ sku: string; name: string }[]>;
  getSuppliers(params: { sort?: SupplierSort; sku?: string }): Promise<Supplier[]>;
  getSupplierRecommendation(sku: string): Promise<SupplierRecommendation>;
  getShipments(params: { status?: ShipmentStatus | "all"; search?: string }): Promise<Shipment[]>;
  getLogisticsSummary(): Promise<LogisticsSummary>;
  getAgents(): Promise<AgentInfo[]>;
  getDocuments(): Promise<DocumentItem[]>;
  getDocumentStats(): Promise<DocumentStats>;
  uploadDocuments(files: File[]): Promise<{ name: string; status: "added" | "updated" | "unchanged" | "failed"; error?: string }[]>;
  deleteDocument(id: string): Promise<void>;
  reindexDocument(id: string): Promise<void>;
  searchDocuments(query: string): Promise<DocumentSearchResult>;
  getActivity(): Promise<ActivityEvent[]>;
  getNotifications(): Promise<Notification[]>;
  markNotificationsRead(ids: string[] | "all"): Promise<void>;
  getAnalytics(): Promise<AnalyticsData>;
  getPendingApprovals(): Promise<ApprovalRequest[]>;
  decideApproval(id: string, decision: "approved" | "rejected", comment?: string): Promise<ApprovalRequest>;
  streamCopilot(request: ChatRequest, signal?: AbortSignal): AsyncGenerator<CopilotEvent>;
}

/** Error surfaced to the UI. Never contains stack traces — only a safe message and the request ID. */
export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly code: string,
    readonly requestId?: string,
  ) {
    super(message);
    this.name = "ApiError";
  }

  get retryable(): boolean {
    return this.status === 0 || this.status === 429 || this.status >= 500;
  }
}

// ---------------------------------------------------------------- HTTP implementation

type TokenProvider = () => Promise<string | null>;
let tokenProvider: TokenProvider = async () => null;

export function setTokenProvider(provider: TokenProvider): void {
  tokenProvider = provider;
}

async function authHeaders(): Promise<Record<string, string>> {
  const token = await tokenProvider();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function toApiError(res: Response): Promise<ApiError> {
  const requestId = res.headers.get("x-request-id") ?? undefined;
  try {
    const body = (await res.json()) as { error?: { code?: string; message?: string; request_id?: string } };
    return new ApiError(
      body.error?.message ?? res.statusText,
      res.status,
      body.error?.code ?? "http_error",
      body.error?.request_id ?? requestId,
    );
  } catch {
    return new ApiError(res.statusText || "Request failed", res.status, "http_error", requestId);
  }
}

async function request<T>(path: string, init: RequestInit = {}, timeoutMs = REQUEST_TIMEOUT_MS): Promise<T> {
  const timeout = AbortSignal.timeout(timeoutMs);
  const signal = init.signal ? AbortSignal.any([init.signal, timeout]) : timeout;
  let res: Response;
  try {
    res = await fetch(`/api${path}`, {
      ...init,
      signal,
      headers: { Accept: "application/json", ...(init.body && !(init.body instanceof FormData) ? { "Content-Type": "application/json" } : {}), ...(await authHeaders()), ...init.headers },
    });
  } catch (err) {
    if (err instanceof DOMException && err.name === "TimeoutError") {
      throw new ApiError("The request timed out. Please try again.", 0, "timeout");
    }
    throw new ApiError("We couldn't reach the server. Check your connection and try again.", 0, "network");
  }
  if (!res.ok) throw await toApiError(res);
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

function qs(params: Record<string, string | number | undefined>): string {
  const entries = Object.entries(params).filter(([, v]) => v !== undefined && v !== "" && v !== "all");
  return entries.length ? `?${new URLSearchParams(entries.map(([k, v]) => [k, String(v)]))}` : "";
}

/** Parses a text/event-stream body into CopilotEvents. */
async function* readSse(body: ReadableStream<Uint8Array>): AsyncGenerator<CopilotEvent> {
  const reader = body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true }).replace(/\r\n/g, "\n");
    let boundary: number;
    while ((boundary = buffer.indexOf("\n\n")) >= 0) {
      const raw = buffer.slice(0, boundary);
      buffer = buffer.slice(boundary + 2);
      const data = raw
        .split("\n")
        .filter((line) => line.startsWith("data:"))
        .map((line) => line.slice(5).trimStart())
        .join("\n");
      if (data) yield JSON.parse(data) as CopilotEvent;
    }
  }
}

export const httpApi: SupplyApi = {
  getCurrentUser: () => request("/me"),
  getSystemStatus: () => request("/system/status"),
  getOverview: () => request("/dashboard/overview"),
  getInventorySummary: () => request("/inventory/summary"),
  getInventory: (q) =>
    request(`/inventory${qs({ search: q.search, risk: q.risk, category: q.category, sort: q.sort, order: q.order, page: q.page, page_size: q.pageSize })}`),
  getInventoryItem: (sku) => request(`/inventory/${encodeURIComponent(sku)}`),
  getDemandForecast: (sku, horizon) => request(`/demand/${encodeURIComponent(sku)}${qs({ horizon })}`),
  getForecastableSkus: () => request("/demand/skus"),
  getSuppliers: (p) => request(`/suppliers${qs({ sort: p.sort, sku: p.sku })}`),
  getSupplierRecommendation: (sku) => request(`/suppliers/recommendation${qs({ sku })}`),
  getShipments: (p) => request(`/shipments${qs({ status: p.status, search: p.search })}`),
  getLogisticsSummary: () => request("/logistics/summary"),
  getAgents: () => request("/agents"),
  getDocuments: () => request("/documents"),
  getDocumentStats: () => request("/documents/stats"),
  uploadDocuments: (files) => {
    const form = new FormData();
    files.forEach((f) => form.append("files", f));
    return request("/documents", { method: "POST", body: form }, 120_000);
  },
  deleteDocument: (id) => request(`/documents/${id}`, { method: "DELETE" }),
  reindexDocument: (id) => request(`/documents/${id}/reindex`, { method: "POST" }),
  searchDocuments: (query) => request("/rag/query", { method: "POST", body: JSON.stringify({ question: query }) }, 60_000),
  getActivity: () => request("/activity"),
  getNotifications: () => request("/notifications"),
  markNotificationsRead: (ids) => request("/notifications/read", { method: "POST", body: JSON.stringify({ ids }) }),
  getAnalytics: () => request("/analytics"),
  getPendingApprovals: () => request("/approvals?status=pending"),
  decideApproval: (id, decision, comment) =>
    request(`/approvals/${id}/decision`, { method: "POST", body: JSON.stringify({ decision, comment }) }, 60_000),
  async *streamCopilot(req, signal) {
    const res = await fetch("/api/chat/stream", {
      method: "POST",
      signal,
      headers: { "Content-Type": "application/json", Accept: "text/event-stream", ...(await authHeaders()) },
      body: JSON.stringify({ message: req.message, session_id: req.sessionId }),
    });
    if (!res.ok || !res.body) throw await toApiError(res);
    yield* readSse(res.body);
  },
};

// ---------------------------------------------------------------- source selection

let mockPromise: Promise<SupplyApi> | null = null;

/** Lazily loads the mock implementation so it is never bundled into API-mode pages' critical path. */
async function mockApi(): Promise<SupplyApi> {
  mockPromise ??= import("./mock").then((m) => m.mockApi);
  return mockPromise;
}

export async function getApi(): Promise<SupplyApi> {
  return DATA_SOURCE === "mock" ? mockApi() : httpApi;
}
