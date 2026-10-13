// Same-origin proxy to the FastAPI backend: /api/proxy/api/v1/... → API_INTERNAL_URL/api/v1/...
// Streams request and response bodies (SSE passes through unbuffered), forwards only the headers
// the API needs, and allows only /api/v1 paths. The browser never needs the API's address or CORS.
import type { NextRequest } from "next/server";

export const dynamic = "force-dynamic";

const API = process.env.API_INTERNAL_URL ?? `http://127.0.0.1:${process.env.API_PORT ?? "8020"}`;
const REQUEST_HEADERS = ["authorization", "content-type", "accept", "x-request-id", "traceparent"];
const RESPONSE_HEADERS = [
  "content-type",
  "cache-control",
  "x-request-id",
  "retry-after",
  "x-ratelimit-limit",
  "x-ratelimit-remaining",
  "x-ratelimit-reset",
];

function error(status: number, code: string, message: string) {
  return Response.json({ error: { code, message } }, { status });
}

async function forward(request: NextRequest, ctx: { params: Promise<{ path: string[] }> }) {
  const { path } = await ctx.params;
  if (path[0] !== "api" || path[1] !== "v1" || path.some((p) => p === ".." || p.includes("\\"))) {
    return error(404, "not_found", "Not found");
  }
  const target = new URL(`/${path.map(encodeURIComponent).join("/")}${request.nextUrl.search}`, API);
  const headers = new Headers();
  for (const name of REQUEST_HEADERS) {
    const value = request.headers.get(name);
    if (value) headers.set(name, value);
  }
  const hasBody = !["GET", "HEAD"].includes(request.method);
  let upstream: Response;
  try {
    upstream = await fetch(target, {
      method: request.method,
      headers,
      body: hasBody ? request.body : undefined,
      cache: "no-store",
      signal: request.signal,
      // Required by Node's fetch to stream a request body.
      ...(hasBody ? { duplex: "half" } : {}),
    } as RequestInit);
  } catch {
    return error(502, "api_unreachable", "The FinAgent API is unreachable.");
  }
  const out = new Headers();
  for (const name of RESPONSE_HEADERS) {
    const value = upstream.headers.get(name);
    if (value) out.set(name, value);
  }
  if (out.get("content-type")?.includes("text/event-stream")) {
    out.set("cache-control", "no-cache, no-transform");
    out.set("x-accel-buffering", "no");
  }
  return new Response(upstream.body, { status: upstream.status, headers: out });
}

export { forward as GET, forward as POST, forward as DELETE };
