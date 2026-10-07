/**
 * Server-side proxy to the FastAPI backend (used when NEXT_PUBLIC_DATA_SOURCE=api).
 *
 * - BACKEND_URL is read at runtime, so one image works in every environment.
 * - Response bodies are piped through unbuffered, so LangGraph's SSE token stream reaches the
 *   browser chunk-by-chunk (real-time streaming, not a buffered response).
 * - Only an allow-list of headers is forwarded in each direction.
 */
import type { NextRequest } from "next/server";

const BACKEND_URL = process.env.BACKEND_URL ?? "http://localhost:8000";
const FORWARD_REQUEST_HEADERS = ["authorization", "content-type", "accept", "x-request-id"];
const FORWARD_RESPONSE_HEADERS = ["content-type", "x-request-id", "retry-after", "x-ratelimit-limit", "x-ratelimit-remaining", "x-ratelimit-reset", "cache-control"];

async function proxy(req: NextRequest, ctx: { params: Promise<{ path: string[] }> }): Promise<Response> {
  const { path } = await ctx.params;
  const target = `${BACKEND_URL}/api/${path.map(encodeURIComponent).join("/")}${req.nextUrl.search}`;

  const headers = new Headers();
  for (const name of FORWARD_REQUEST_HEADERS) {
    const value = req.headers.get(name);
    if (value) headers.set(name, value);
  }

  let upstream: Response;
  try {
    upstream = await fetch(target, {
      method: req.method,
      headers,
      body: req.method === "GET" || req.method === "HEAD" ? undefined : req.body,
      // Required to stream a request body in Node's fetch.
      duplex: "half",
      cache: "no-store",
      signal: req.signal,
    } as RequestInit & { duplex: "half" });
  } catch {
    return Response.json(
      { error: { code: "backend_unavailable", message: "The service is temporarily unavailable. Please try again shortly." } },
      { status: 503 },
    );
  }

  const responseHeaders = new Headers();
  for (const name of FORWARD_RESPONSE_HEADERS) {
    const value = upstream.headers.get(name);
    if (value) responseHeaders.set(name, value);
  }
  if (upstream.headers.get("content-type")?.includes("text/event-stream")) {
    responseHeaders.set("cache-control", "no-cache, no-transform");
    responseHeaders.set("x-accel-buffering", "no");
  }
  return new Response(upstream.body, { status: upstream.status, headers: responseHeaders });
}

export { proxy as GET, proxy as POST, proxy as PUT, proxy as PATCH, proxy as DELETE };
