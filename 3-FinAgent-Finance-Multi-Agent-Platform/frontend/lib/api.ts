// Model: typed API client for the FinAgent backend (bearer token from Supabase).
// Requests go through the same-origin proxy by default (lib/config.ts); mock mode uses fixtures.
import { API_BASE, API_MODE } from "@/lib/config";
import { mockApi } from "@/lib/mock";
import type {
  AgentCard,
  Approval,
  AuditTrace,
  ChatResponse,
  ComplianceView,
  Conversation,
  DocumentItem,
  FraudAlert,
  MarketSummary,
  Me,
  ModelCard,
  NewsItem,
  Overview,
  PortfolioListItem,
  PortfolioView,
  RagAnswer,
  RiskView,
  StreamEvent,
  SystemStatus,
  UploadResult,
} from "@/types";

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly requestId?: string,
    readonly retryAfter?: number,
  ) {
    super(message);
  }
}

async function failure(response: Response): Promise<ApiError> {
  const body = await response.json().catch(() => null);
  const retry = Number(response.headers.get("retry-after")) || undefined;
  return new ApiError(body?.error?.message ?? response.statusText, response.status, body?.error?.requestId, retry);
}

async function request<T>(path: string, token: string, init?: RequestInit): Promise<T> {
  if (API_MODE === "mock") return mockApi.request<T>(path, init);
  const isForm = init?.body instanceof FormData;
  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, {
      ...init,
      headers: {
        ...(isForm ? {} : { "Content-Type": "application/json" }),
        Authorization: `Bearer ${token}`,
        ...init?.headers,
      },
    });
  } catch {
    throw new ApiError("The FinAgent API is unreachable. Is it running on port 8020?", 0);
  }
  if (!response.ok) throw await failure(response);
  return (await response.json()) as T;
}

const post = <T>(path: string, token: string, body: unknown) =>
  request<T>(path, token, { method: "POST", body: JSON.stringify(body) });

export interface AnalyzeBody {
  portfolioId?: string;
  ticker?: string;
  transactionId?: string;
  customerId?: string;
  question?: string;
  conversationId?: string | null;
}

export const api = {
  me: (token: string) => request<Me>("/api/v1/me", token),
  portfolios: (token: string) => request<PortfolioListItem[]>("/api/v1/portfolios", token),
  portfolio: (token: string, id: string) => request<PortfolioView>(`/api/v1/portfolio/${id}`, token),
  risk: (token: string, id: string) => request<RiskView>(`/api/v1/risk/${id}`, token),

  overview: (token: string) => request<Overview>("/api/v1/dashboard/overview", token),
  compliance: (token: string) => request<ComplianceView>("/api/v1/dashboard/compliance", token),
  markets: (token: string) => request<MarketSummary>("/api/v1/dashboard/markets", token),
  news: (token: string) => request<{ provider: string; items: NewsItem[] }>("/api/v1/dashboard/news", token),
  fraud: (token: string) => request<{ alerts: FraudAlert[]; flagged: number; note: string }>("/api/v1/dashboard/fraud", token),
  agents: (token: string) => request<{ agents: AgentCard[] }>("/api/v1/dashboard/agents", token),
  models: (token: string) => request<ModelCard[]>("/api/v1/dashboard/ml/models", token),
  system: (token: string) => request<SystemStatus>("/api/v1/dashboard/system/status", token),
  activity: (token: string) => request<Overview["recentActivity"]>("/api/v1/dashboard/activity", token),
  audit: (token: string, requestId: string) => request<AuditTrace>(`/api/v1/audit/${encodeURIComponent(requestId)}`, token),
  conversations: (token: string) => request<Conversation[]>("/api/v1/conversations", token),

  approvals: (token: string, status?: string) =>
    request<Approval[]>(`/api/v1/approvals${status ? `?status=${status}` : ""}`, token),
  decide: (token: string, id: string, approve: boolean, note: string) =>
    post<Approval>(`/api/v1/approvals/${id}/decision`, token, { approve, note: note || null }),

  analyze: (token: string, kind: string, body: AnalyzeBody) => {
    const path = ["research", "predict"].includes(kind) ? `/api/v1/${kind}` : `/api/v1/analyze/${kind}`;
    return post<ChatResponse>(path, token, body);
  },

  documents: (token: string) => request<DocumentItem[]>("/api/v1/documents", token),
  ragQuery: (token: string, question: string) => post<RagAnswer>("/api/v1/rag/query", token, { question }),
  upload: (token: string, form: FormData) =>
    request<UploadResult>("/api/v1/documents", token, { method: "POST", body: form }),
  deleteDocument: (token: string, id: string) =>
    request<{ deleted: boolean }>(`/api/v1/documents/${id}`, token, { method: "DELETE" }),

  /** POST /api/v1/chat/stream and deliver each Server-Sent Event to ``onEvent``. */
  async streamChat(
    token: string,
    question: string,
    conversationId: string | null,
    onEvent: (event: StreamEvent) => void,
    signal?: AbortSignal,
  ): Promise<void> {
    if (API_MODE === "mock") return mockApi.stream(question, onEvent, signal);
    let response: Response;
    try {
      response = await fetch(`${API_BASE}/api/v1/chat/stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({ question, conversationId }),
        signal,
      });
    } catch (e) {
      if ((e as Error).name === "AbortError") return;
      throw new ApiError("The FinAgent API is unreachable. Is it running on port 8020?", 0);
    }
    if (!response.ok || !response.body) throw await failure(response);
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    for (;;) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      let boundary = buffer.indexOf("\n\n");
      while (boundary !== -1) {
        const frame = buffer.slice(0, boundary);
        buffer = buffer.slice(boundary + 2);
        const data = frame.split("\n").find((line) => line.startsWith("data: "));
        if (data) onEvent(JSON.parse(data.slice(6)) as StreamEvent);
        boundary = buffer.indexOf("\n\n");
      }
    }
  },
};
