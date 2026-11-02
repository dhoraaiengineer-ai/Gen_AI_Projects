import { z } from "zod";

import { ApiError, envelopeSchema } from "./envelope";

/** JWT kept in memory only (rules/20: never localStorage). A reload signs the user out — fine for the DEMO. */
let token: string | null = null;
export const setToken = (t: string | null) => {
  token = t;
};
export const getToken = () => token;

type Options = { method?: string; body?: unknown; idempotencyKey?: string; signal?: AbortSignal };

export async function api<T extends z.ZodTypeAny>(path: string, schema: T, opts: Options = {}): Promise<z.infer<T>> {
  const headers: Record<string, string> = { Accept: "application/json" };
  if (opts.body !== undefined) headers["Content-Type"] = "application/json";
  if (token) headers.Authorization = `Bearer ${token}`;
  if (opts.idempotencyKey) headers["Idempotency-Key"] = opts.idempotencyKey;
  const resp = await fetch(path, {
    method: opts.method ?? (opts.body !== undefined ? "POST" : "GET"),
    headers,
    body: opts.body !== undefined ? JSON.stringify(opts.body) : undefined,
    signal: opts.signal,
  });
  const env = envelopeSchema(schema).parse(await resp.json());
  if (env.status === "error" || env.data === null) {
    throw new ApiError(env.error?.code ?? "INTERNAL_ERROR", env.error?.message ?? "Request failed", env.request_id, resp.status);
  }
  return env.data;
}

export type SseEvent = { event: string; data: unknown };

/** Parse a text/event-stream body into events (handles events split across chunks). */
export async function* readSse(body: ReadableStream<Uint8Array>): AsyncGenerator<SseEvent> {
  const reader = body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let idx: number;
    while ((idx = buffer.indexOf("\n\n")) >= 0) {
      const block = buffer.slice(0, idx);
      buffer = buffer.slice(idx + 2);
      const event = /^event: (.*)$/m.exec(block)?.[1] ?? "message";
      const data = /^data: (.*)$/m.exec(block)?.[1];
      if (data !== undefined) yield { event, data: JSON.parse(data) };
    }
  }
}

/** POST a chat message and stream tokens; resolves with the validated final reply envelope data. */
export async function streamChat<T extends z.ZodTypeAny>(
  body: unknown,
  schema: T,
  onToken: (text: string) => void,
): Promise<z.infer<T>> {
  const resp = await fetch("/api/v1/chat/messages", {
    method: "POST",
    headers: {
      Accept: "text/event-stream",
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify(body),
  });
  if (!resp.ok || !resp.body) {
    const env = envelopeSchema(schema).safeParse(await resp.json().catch(() => null));
    const err = env.success ? env.data.error : null;
    throw new ApiError(err?.code ?? "INTERNAL_ERROR", err?.message ?? "Request failed", "", resp.status);
  }
  for await (const ev of readSse(resp.body)) {
    if (ev.event === "token") onToken(String((ev.data as { text?: string }).text ?? ""));
    if (ev.event === "final") {
      const env = envelopeSchema(schema).parse(ev.data);
      if (env.data === null) throw new ApiError(env.error?.code ?? "INTERNAL_ERROR", env.error?.message ?? "", env.request_id, 500);
      return env.data;
    }
  }
  throw new ApiError("INTERNAL_ERROR", "Stream ended without a final reply", "", 500);
}
